"use client";

// Import without dynamic import first to check if that was the issue, 
// usually ForceGraph needs 'use client' which we have.
// Actually, react-force-graph-2d often fails SSR, so let's keep dynamic import but handle it properly.
import dynamic from 'next/dynamic';
import { v4 as uuidv4 } from 'uuid';
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import ChatInterface, { ChatIntent } from "@/components/ChatInterface";
import RightSidebar from "@/components/RightSidebar";
import SessionManager from "@/components/SessionManager";
import { AvatarState } from "@/components/AvatarSlime";
import ConceptCard from "@/components/ConceptCard";

// Dynamically import GraphVisualization to avoid SSR issues with Canvas
const GraphVisualization = dynamic(() => import("@/components/GraphVisualization"), {
  ssr: false,
  loading: () => <div className="w-full h-full flex items-center justify-center text-slate-500">Loading Graph Core...</div>
});

export default function Home() {
  const router = useRouter();
  const [sessionID, setSessionID] = useState("");

  // Initialize Session on Mount
  useEffect(() => {
    const stored = localStorage.getItem("loom_current_session");
    if (stored) {
      setSessionID(stored);
    } else {
      const newID = uuidv4();
      setSessionID(newID);
      localStorage.setItem("loom_current_session", newID);
    }
  }, []);

  const handleNewSession = () => {
    const newID = uuidv4();
    setSessionID(newID);
    localStorage.setItem("loom_current_session", newID);
    // Reset local state if needed (e.g., clear graph)
    window.location.reload(); // Simple reload to clear state for MVP
  };
  const [isCrystallized, setIsCrystallized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showConceptCard, setShowConceptCard] = useState(false);

  // Graph Data State
  const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] }>({
    nodes: [
      // Initial Seed Node
      { id: "Cognitive Loom", group: "concept", val: 20, status: "verified" }
    ],
    links: []
  });

  // Chat State
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);

  // Upload State
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [evidenceHistory, setEvidenceHistory] = useState<any[]>([]);

  // Avatar & Alert State
  const [avatarState, setAvatarState] = useState<AvatarState>('IDLE');
  const [alerts, setAlerts] = useState<any[]>([]);

  // Derived Metrics
  const metrics = {
    concepts: graphData.nodes.filter(n => n.group === 'concept').length,
    sources: evidenceHistory.length,
    confidence: Math.round(graphData.nodes.reduce((acc, n) => acc + (n.status === 'verified' ? 100 : n.status === 'conflict' ? 0 : 50), 0) / (graphData.nodes.length || 1)),
    gaps: graphData.nodes.filter(n => n.status === 'conflict').length
  };

  useEffect(() => {
    if (showUpload || uploadStatus?.type === 'success') {
      fetch("http://127.0.0.1:8000/api/v1/ingest/history")
        .then(res => res.json())
        .then(data => setEvidenceHistory(data))
        .catch(err => console.error(err));
    }
  }, [showUpload, uploadStatus]);

  // Handlers
  const handleSendMessage = async (msg: string, intent: ChatIntent) => {
    setIsLoading(true);
    setAvatarState('LISTENING');
    // Optimistic UI
    setMessages(prev => [...prev, { role: 'user', content: msg }]);

    try {
      // Transition to THINKING after a brief delay
      setTimeout(() => setAvatarState('THINKING'), 500);

      const res = await fetch("http://127.0.0.1:8000/api/v1/session/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg,
          session_id: sessionID,
          intent: intent
        })
      });

      const data = await res.json();

      // 1. Update Chat with concept citations
      const citations = data.context && Array.isArray(data.context)
        ? data.context
          .filter((c: any) => c.doc?.label || c.doc?.highlight || c.doc?.source_url)
          .slice(0, 5)
          .map((c: any) => {
            // Derive a meaningful label
            let label = c.doc?.label;  // Concepts have labels
            if (!label) {
              // Seeds: Try to extract from source URL hostname
              if (c.doc?.source_url) {
                try {
                  label = new URL(c.doc.source_url).hostname.replace('www.', '');
                } catch { label = null; }
              }
              // Fallback: First 25 chars of highlight
              if (!label && c.doc?.highlight) {
                label = c.doc.highlight.substring(0, 25).trim() + '...';
              }
              // Final fallback
              if (!label) label = 'Source';
            }
            return {
              id: c.doc?._id || c.doc?.label,
              label: label
            };
          })
        : [];

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        citations: citations
      }]);

      // 2. Update Graph (Avatar Analysis) & State
      if (data.context && Array.isArray(data.context)) {
        updateGraphFromContext(data.context);

        // Push Alert if Insight or Conflict found
        const conflict = data.context.find((c: any) => c.edge_type === 'CONTRADICTS');
        if (conflict) {
          setAvatarState('ALERT');
          setAlerts(prev => [{
            id: Date.now().toString(),
            type: 'conflict',
            title: 'Contradiction Detected',
            message: `New evidence conflicts with ${conflict.doc.label || 'existing knowledge'}`,
            timestamp: new Date()
          }, ...prev]);
        } else if (data.context.some((c: any) => c.score > 0.85)) {
          setAvatarState('INSIGHT');
        } else {
          setAvatarState('IDLE');
        }
      } else {
        setAvatarState('IDLE');
      }

    } catch (err) {
      console.error("Chat Failed", err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: Neural Link Severed." }]);
      setAvatarState('ALERT');
    } finally {
      setIsLoading(false);
      // Fallback to idle after 3s if no other state
      setTimeout(() => setAvatarState(prev => prev === 'ALERT' ? prev : 'IDLE'), 3000);
    }
  };

  const clearAlert = (id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
    if (avatarState === 'ALERT') setAvatarState('IDLE');
  };

  const handleCreateSession = async () => {
    const title = prompt("Function Call: Initialize Session Protocol\n\nEnter Session Parameter (Name):");
    if (!title) return;

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/session/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title, goal: "User Initiated" })
      });
      const data = await res.json();
      setSessionID(data.session_id);
      setMessages([]); // Clear chat for new session
      // Optionally clear graph or reload it
      setGraphData({ nodes: [{ id: title, group: "concept", val: 20, status: "verified" }], links: [] });
    } catch (e) {
      alert("Failed to initialize session: " + e);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;

    const file = e.target.files[0];
    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionID);

    try {
      // Re-using existing ingestion API
      const res = await fetch("http://127.0.0.1:8000/api/v1/ingest/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      setUploadStatus({
        type: "success",
        message: `Processed ${file.name} (${data.chunks_count} chunks).`,
      });
    } catch (error) {
      setUploadStatus({
        type: "error",
        message: "Upload failed. Check backend.",
      });
    } finally {
      setUploading(false);
    }
  };

  const handleEndSession = async () => {
    // The Physics Implosion!
    setIsCrystallized(true);

    // Notify Backend
    try {
      await fetch("http://127.0.0.1:8000/api/v1/session/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionID })
      });
      // Visual Feedback could be a toast here
    } catch (e) {
      console.error("Consolidation Failed", e);
    }
  };

  // Helper to transform RAG context into Graph Data
  // Brain Layer State
  const [brainLayer, setBrainLayer] = useState<'layer1' | 'layer2'>('layer1');
  const [isGraphLoading, setIsGraphLoading] = useState(false);

  // Initial Data Fetch: Global Brain & History
  useEffect(() => {
    // Reload Graph on Session Change
    fetchGlobalGraph('layer1');

    // Reset UI State for new session
    setMessages([]);
    setAlerts([]);
    setAvatarState('IDLE');

    // Fetch History for Stats
    fetch("http://127.0.0.1:8000/api/v1/ingest/history")
      .then(res => res.json())
      .then(data => setEvidenceHistory(data))
      .catch(err => console.error("Failed to load history:", err));
  }, [sessionID]); // Trigger on Session Switch

  const fetchGlobalGraph = async (layer: 'layer1' | 'layer2') => {
    setIsGraphLoading(true);
    // Layer 1 = Top 50, Layer 2 = Top 1000 (Full)
    const limit = layer === 'layer1' ? 50 : 1000;

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/session/global/graph?limit=${limit}&session_id=${sessionID}`);
      const data = await res.json();

      // Transform ArangoDB graph to React Flow format
      const nodes = data.nodes.map((n: any) => ({
        id: n._id, // Use ArangoID as unique ID
        label: n.label || n._id.split('/')[1],
        // Updated Group Mapping: Source | Session | Concept
        group: n.type === 'source' ? 'source' : (n.type === 'session_node' ? 'session' : 'concept'),
        val: n.type === 'session_node' ? 20 : (n.val || 5), // Boost Session Nodes
        status: n.status || 'neutral',
        citation: `Global Influence: ${n.val ?? 'N/A'}`,
        sourceText: n.definition || n.text || n.description || n.highlight || "Content not available in graph node."
      }));

      const links = data.links.map((e: any) => ({
        source: e._from,
        target: e._to,
        type: e.type
      }));

      setGraphData({ nodes, links });
      setBrainLayer(layer);
    } catch (e) {
      console.error("Failed to fetch global brain:", e);
    } finally {
      setIsGraphLoading(false);
    }
  };

  const toggleBrainLayer = () => {
    const nextLayer = brainLayer === 'layer1' ? 'layer2' : 'layer1';
    fetchGlobalGraph(nextLayer);
  };

  // Helper to transform RAG context into Graph Data
  const updateGraphFromContext = (contextItems: any[]) => {
    setGraphData(prev => {
      // IMPORTANT: Keep original node references to preserve x, y, fx, fy positions
      const nodeMap = new Map(prev.nodes.map(n => [n.id, n]));
      const newLinks = [...prev.links];

      contextItems.forEach((item: any) => {
        const doc = item.doc;
        if (!doc) return;

        // Use label, or ArangoDB _id, or fallback to a snippet of the text
        const id = doc.label || doc._id || (doc.highlight ? doc.highlight.substring(0, 20) + "..." : "Unknown Concept");
        // Citation Logic
        let citation = "System Memory";
        if (doc.source) {
          citation = `${doc.source.split('/').pop()} (Page ${doc.page || '?'})`;
        } else if (doc.source_url) {
          try { citation = new URL(doc.source_url).hostname; } catch (e) { citation = "Web Source"; }
        }

        const sourceText = doc.highlight || doc.text || doc.definition || JSON.stringify(doc, null, 2);

        if (nodeMap.has(id)) {
          // MERGE: Update existing node IN PLACE to preserve x, y, fx, fy positions
          const existing = nodeMap.get(id);
          // Mutate in place - don't spread to new object, this preserves force-graph positions
          existing.status = item.edge_type === 'CONTRADICTS' ? 'conflict' : existing.status;
          existing.sourceText = sourceText;
          existing.citation = citation;
          existing.val = (existing.val || 5) + 3; // Highlight effect: grow slightly
        } else {
          // CREATE: New Node
          nodeMap.set(id, {
            id: id,
            group: 'concept',
            val: 5,
            status: item.edge_type === 'CONTRADICTS' ? 'conflict' : 'neutral',
            sourceText: sourceText,
            sourceType: doc.type || "Unknown",
            citation: citation
          });
        }
      });

      return {
        nodes: Array.from(nodeMap.values()),
        links: newLinks
      };
    });
  };

  // Layout State
  const [leftPanelWidth, setLeftPanelWidth] = useState(33); // Percentage
  const [isDragging, setIsDragging] = useState(false);

  // Main Graph Data and Selection State
  const [selectedNode, setSelectedNode] = useState<any>(null); // For "Explainability" Panel
  const [showSource, setShowSource] = useState(false); // Toggle for Inspection

  // Right Panel View State
  const [activeRightView, setActiveRightView] = useState<'AVATAR' | 'GRAPH'>('AVATAR');

  // Resizing Logic
  const handleDrag = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const newWidth = (e.clientX / window.innerWidth) * 100;
    if (newWidth > 20 && newWidth < 80) setLeftPanelWidth(newWidth);
  };

  const stopDrag = () => setIsDragging(false);

  const handleNodeClick = async (node: any) => {
    console.log("Node Clicked:", node);
    // 1. Optimistic Set (Show what we have)
    setSelectedNode(node);
    setShowSource(false);

    // 2. Hydrate with Full Details from DB
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/graph/node?id=${encodeURIComponent(node.id)}`);
      if (res.ok) {
        const details = await res.json();
        console.log("Details fetched:", details);

        // Merge DB data into visualization node
        setSelectedNode((prev: any) => ({
          ...prev, // Keep x,y, val, color
          ...details.data, // Overwrite info with DB truth (label, definition, etc)
          neighbors: details.neighbors, // Add neighbor context
          fetchedAt: new Date()
        }));
      }
    } catch (e) {
      console.error("Failed to hydrate node:", e);
    }
  };

  return (
    <div
      className="h-[calc(100vh-2rem)] flex flex-col gap-4"
      onMouseMove={handleDrag}
      onMouseUp={stopDrag}
      onMouseLeave={stopDrag}
    >
      {/* Header */}
      <div className="flex justify-between items-center px-2 shrink-0">
        <div>
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-purple-500">
            Mission Control
          </h1>
          <div className="flex items-center gap-3">
            <p className="text-xs text-slate-500">
              Global Brain •
              Status: <span className={isCrystallized ? "text-purple-400" : "text-green-400"}>
                {isCrystallized ? "CRYSTALLIZED" : "ACTIVE (FLUID)"}
              </span>
            </p>
            {/* Session ID Badge (Restored for Extension Linking) */}
            <div
              className="px-2 py-1 rounded bg-white/5 border border-white/10 text-[10px] font-mono text-slate-400 cursor-pointer hover:bg-white/10 hover:text-white transition-colors"
              onClick={() => { navigator.clipboard.writeText(sessionID); alert("Session ID copied!"); }}
              title="Click to Copy for Chrome Extension"
            >
              ID: {sessionID}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          {/* Layer Toggle */}
          <button
            onClick={toggleBrainLayer}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-2 transition-colors ${brainLayer === 'layer2'
              ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
              : 'bg-white/5 text-slate-400 border-white/10 hover:bg-white/10'
              }`}
          >
            {isGraphLoading ? (
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            )}
            {brainLayer === 'layer1' ? "Show Full Brain" : "Show Top 50"}
          </button>

          <SessionManager
            currentSessionId={sessionID}
            onSessionChange={(id) => setSessionID(id)}
            onCreateSession={handleCreateSession}
          />
          <button
            onClick={handleCreateSession}
            className="px-3 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-xs font-medium text-indigo-300 border border-indigo-500/30 flex items-center gap-2 transition-colors"
            title="Create a fresh session ID"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Session
          </button>
          <button
            onClick={() => setShowUpload(true)}
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-medium text-white border border-white/10 flex items-center gap-2 transition-colors"
            disabled={isCrystallized}
          >
            <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Upload Evidence
          </button>
        </div>
      </div>

      {/* Main Resizable Split View */}
      <div className="flex-1 flex gap-0 min-h-0 relative overflow-hidden">

        {/* Left Panel: Chat */}
        <div style={{ width: `${leftPanelWidth}%` }} className="h-full min-h-0 pr-2 transition-none">
          <ChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            onEndSession={handleEndSession}
            isCrystallized={isCrystallized}
            onConceptClick={(conceptId, label) => {
              // Find the node in the graph and focus it
              const node = graphData.nodes.find(n => n.id === label || n.id === conceptId);
              if (node) {
                setSelectedNode(node);
              }
            }}
          />
        </div>

        {/* Drag Handle */}
        <div
          className="w-2 cursor-col-resize hover:bg-teal-500/50 active:bg-teal-500 transition-colors flex items-center justify-center opacity-50 hover:opacity-100 z-50 rounded"
          onMouseDown={() => setIsDragging(true)}
        >
          <div className="w-0.5 h-8 bg-white/20 rounded-full" />
        </div>

        {/* Right Panel: Tabbed View (Avatar vs Graph) */}
        <div style={{ width: `${100 - leftPanelWidth}%` }} className="h-full min-h-0 pl-2 relative group flex-1 flex flex-col gap-2">

          {/* View Toggle Tabs */}
          <div className="flex bg-slate-900/50 p-1 rounded-lg border border-white/5 shrink-0 self-start">
            <button
              onClick={() => setActiveRightView('AVATAR')}
              className={`px-3 py-1 rounded text-xs font-bold transition-all ${activeRightView === 'AVATAR' ? 'bg-teal-500/20 text-teal-300 shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
            >
              System State
            </button>
            <button
              onClick={() => setActiveRightView('GRAPH')}
              className={`px-3 py-1 rounded text-xs font-bold transition-all ${activeRightView === 'GRAPH' ? 'bg-purple-500/20 text-purple-300 shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Knowledge Graph
            </button>
          </div>

          {/* 1. Avatar Stats Panel (Full Height if Active) */}
          {activeRightView === 'AVATAR' && (
            <div className="flex-1 min-h-0 animate-in fade-in duration-300">
              <RightSidebar
                avatarState={avatarState}
                metrics={metrics}
                alerts={alerts}
                onClearAlert={clearAlert}
              />
            </div>
          )}

          {/* 2. Global Graph (Full Height if Active) */}
          {activeRightView === 'GRAPH' && (
            <div className="flex-1 min-h-0 bg-gradient-to-tr from-teal-900/10 to-purple-900/10 rounded-xl overflow-hidden border border-white/5 relative animate-in fade-in duration-300">
              <GraphVisualization
                data={graphData}
                isCrystallized={isCrystallized}
                onNodeClick={handleNodeClick}
              />

              {/* System Info Overlay */}
              <div className="absolute bottom-4 right-4 text-right pointer-events-none">
                <div className="text-xs text-white/30 font-mono">
                  Layer: {brainLayer === 'layer1' ? 'Top 50' : 'Full'}
                </div>
                <div className="text-[10px] text-white/20 font-mono mt-1">
                  Nodes: {graphData.nodes.length}
                </div>
              </div>
            </div>
          )}

          {/* Node Explanation Overlay */}
          {selectedNode && !isCrystallized && (
            <div className="absolute top-4 right-4 w-80 glass-card p-4 rounded-xl border border-white/10 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-right-10 flex flex-col max-h-[80vh] z-50">
              <div className="flex justify-between items-start mb-2 shrink-0">
                <h3 className="font-bold text-white text-lg leading-tight truncate pr-2">{selectedNode.label || selectedNode.id.split('/').pop()}</h3>
                <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white">×</button>
              </div>

              <div className="space-y-3 overflow-y-auto flex-1 custom-scrollbar">
                {/* Status Tags */}
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${selectedNode.status === 'conflict' ? 'bg-red-500/20 text-red-300' :
                    selectedNode.group === 'concept' ? 'bg-teal-500/20 text-teal-300' : 'bg-blue-500/20 text-blue-300'
                    }`}>
                    {selectedNode.status || 'Verified'}
                  </span>
                  <span className="text-xs text-slate-500">Val: {Math.round(selectedNode.val)}</span>
                </div>

                {/* Content Area */}
                {!showSource ? (
                  <>
                    <p className="text-xs text-slate-300">
                      {selectedNode.group === 'concept'
                        ? "This concept is part of the Global Knowledge Graph."
                        : "This is a raw data point from your seed inputs."}
                    </p>

                    {selectedNode.citation && (
                      <div className="mt-2 p-2 bg-blue-900/20 border border-blue-500/20 rounded">
                        <p className="text-[10px] text-blue-300 font-mono flex items-center gap-1">
                          <span className="opacity-50">REF:</span> {selectedNode.citation}
                        </p>
                      </div>
                    )}

                    <div className="pt-2 border-t border-white/5 shrink-0 mt-auto">
                      <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Actions</p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setShowSource(true)}
                          className="text-xs bg-white/5 hover:bg-white/10 px-2 py-1 rounded text-white transition-colors border border-white/10"
                        >
                          Inspect Source
                        </button>

                        {/* NEW: Learn This Concept Button */}
                        <button
                          onClick={() => setShowConceptCard(true)}
                          className="text-xs bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 px-3 py-1.5 rounded-lg text-white font-medium transition-all shadow-lg shadow-purple-500/20"
                        >
                          🎓 Learn This
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="bg-black/40 rounded p-3 border border-white/5 text-xs font-mono text-slate-300 break-words whitespace-pre-wrap">
                    <div className="flex justify-between items-center mb-2 pb-2 border-b border-white/5">
                      <span className="text-[10px] uppercase text-slate-500">Raw Source Content</span>
                      <button onClick={() => setShowSource(false)} className="text-[10px] text-teal-400 hover:text-teal-300">Back</button>
                    </div>
                    {selectedNode.citation && (
                      <p className="text-[10px] text-slate-400 mb-2">Source: {selectedNode.citation}</p>
                    )}
                    {selectedNode.sourceText || "No raw text available."}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Session Summary Overlay (Crystallized State) */}
          {isCrystallized && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-8 z-50">
              {/* ... existing summary UI ... */}
              <div className="bg-slate-900 border border-purple-500/30 p-8 rounded-2xl max-w-2xl w-full text-center shadow-2xl relative">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-purple-600 rounded-full p-4 shadow-lg shadow-purple-500/20">
                  <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                </div>

                <h2 className="text-3xl font-bold text-white mt-4 mb-2">Session Crystallized</h2>
                <p className="text-slate-400 mb-8">
                  Knowledge from "<strong>{sessionID}</strong>" has been consolidated into the Main Graph.
                </p>

                <div className="grid grid-cols-3 gap-4 mb-8">
                  <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-2xl font-bold text-teal-400">{graphData.nodes.length}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Concepts</div>
                  </div>
                  <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-2xl font-bold text-blue-400">{evidenceHistory.length}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Sources</div>
                  </div>
                  <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    {/* Mock conflict count */}
                    <div className="text-2xl font-bold text-red-400">0</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Conflicts</div>
                  </div>
                </div>

                <div className="flex gap-4 justify-center">
                  <button
                    onClick={() => router.push(`/session/${sessionID}/report`)}
                    className="px-6 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-black font-bold transition-colors"
                  >
                    View Final Report
                  </button>
                  <button
                    onClick={() => setIsCrystallized(false)}
                    className="px-6 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white font-medium transition-colors"
                  >
                    Resume Session
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* Upload Modal */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 w-full max-w-md relative">
            <button onClick={() => setShowUpload(false)} className="absolute top-4 right-4 text-slate-400 hover:text-white">×</button>

            <div className="text-center mb-6">
              <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white">Upload Evidence</h2>
              <p className="text-sm text-slate-400 mt-1">Add PDFs or Text to this session's context.</p>
            </div>

            {uploadStatus && (
              <div className={`mb-4 p-3 rounded text-xs ${uploadStatus.type === 'success' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                {uploadStatus.message}
              </div>
            )}

            <div className="relative border-2 border-dashed border-white/10 rounded-xl p-8 hover:border-purple-500/50 transition-colors group">
              <input
                type="file"
                onChange={handleFileUpload}
                disabled={uploading}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="text-center pointer-events-none">
                {uploading ? (
                  <p className="text-purple-400 animate-pulse">Processing Neural Chunks...</p>
                ) : (
                  <p className="text-slate-400 group-hover:text-white transition-colors">Click or Drag file here</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Phase 12: Concept Card Modal */}
      {showConceptCard && selectedNode && (
        <ConceptCard
          conceptId={selectedNode.id}
          label={selectedNode.label || selectedNode.id.split('/').pop() || 'Concept'}
          sessionId={sessionID}
          onClose={() => setShowConceptCard(false)}
        />
      )}
    </div>
  );
}
