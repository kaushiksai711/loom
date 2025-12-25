"use client";

// Import without dynamic import first to check if that was the issue, 
// usually ForceGraph needs 'use client' which we have.
// Actually, react-force-graph-2d often fails SSR, so let's keep dynamic import but handle it properly.
import dynamic from 'next/dynamic';
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import ChatInterface, { ChatIntent } from "@/components/ChatInterface";

// Dynamically import GraphVisualization to avoid SSR issues with Canvas
const GraphVisualization = dynamic(() => import("@/components/GraphVisualization"), {
  ssr: false,
  loading: () => <div className="w-full h-full flex items-center justify-center text-slate-500">Loading Graph Core...</div>
});

export default function Home() {
  const router = useRouter();
  const [sessionID, setSessionID] = useState("session_alpha_1"); // Hardcoded for MVP
  const [isCrystallized, setIsCrystallized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

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
    // Optimistic UI
    setMessages(prev => [...prev, { role: 'user', content: msg }]);

    try {
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

      // 1. Update Chat
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);

      // 2. Update Graph (The Avatar Reacts)
      if (data.context && Array.isArray(data.context)) {
        updateGraphFromContext(data.context);
      }

    } catch (err) {
      console.error("Chat Failed", err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: Neural Link Severed." }]);
    } finally {
      setIsLoading(false);
    }
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
  // Helper to transform RAG context into Graph Data
  const updateGraphFromContext = (contextItems: any[]) => {
    setGraphData(prev => {
      const nodeMap = new Map(prev.nodes.map(n => [n.id, { ...n }]));
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
          // MERGE: Update existing node
          const existing = nodeMap.get(id);
          nodeMap.set(id, {
            ...existing,
            status: item.edge_type === 'CONTRADICTS' ? 'conflict' : existing.status,
            sourceText: sourceText,
            citation: citation,
            val: (existing.val || 5) + 3 // Highlight effect: grow slightly
          });
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

  // Resizing Logic
  const handleDrag = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const newWidth = (e.clientX / window.innerWidth) * 100;
    if (newWidth > 20 && newWidth < 80) setLeftPanelWidth(newWidth);
  };

  const stopDrag = () => setIsDragging(false);

  // ... (handleSendMessage remains same) ...

  const handleNodeClick = (node: any) => {
    console.log("Node Clicked:", node);
    setSelectedNode(node);
    setShowSource(false); // Reset view
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
          <p className="text-xs text-slate-500">
            Session:
            <input
              type="text"
              value={sessionID}
              onChange={(e) => setSessionID(e.target.value)}
              className="bg-transparent border-b border-white/20 text-slate-300 focus:outline-none focus:border-teal-400 w-32 px-1 mx-1 text-center"
            />
            • Status: <span className={isCrystallized ? "text-purple-400" : "text-green-400"}>
              {isCrystallized ? "CRYSTALLIZED" : "ACTIVE (FLUID)"}
            </span>
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleCreateSession}
            className="px-3 py-1.5 rounded-lg bg-teal-500/10 hover:bg-teal-500/20 text-xs font-medium text-teal-300 border border-teal-500/20 flex items-center gap-2 transition-colors"
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
          />
        </div>

        {/* Drag Handle */}
        <div
          className="w-2 cursor-col-resize hover:bg-teal-500/50 active:bg-teal-500 transition-colors flex items-center justify-center opacity-50 hover:opacity-100 z-50 rounded"
          onMouseDown={() => setIsDragging(true)}
        >
          <div className="w-0.5 h-8 bg-white/20 rounded-full" />
        </div>

        {/* Right Panel: Graph */}
        <div style={{ width: `${100 - leftPanelWidth}%` }} className="h-full min-h-0 pl-2 relative group flex-1">
          <div className="absolute inset-0 bg-gradient-to-tr from-teal-900/10 to-purple-900/10 rounded-xl overflow-hidden border border-white/5">
            <GraphVisualization
              data={graphData}
              isCrystallized={isCrystallized}
              onNodeClick={handleNodeClick}
            />
          </div>

          {/* System Info Overlay */}
          <div className="absolute bottom-4 right-4 text-right pointer-events-none">
            <div className="text-xs text-white/30 font-mono">
              System Entropy: {isCrystallized ? "0.01" : "0.85"}
            </div>
          </div>

          {/* Node Explanation Overlay */}
          {selectedNode && !isCrystallized && (
            <div className="absolute top-4 right-4 w-80 glass-card p-4 rounded-xl border border-white/10 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-right-10 flex flex-col max-h-[80vh]">
              <div className="flex justify-between items-start mb-2 shrink-0">
                <h3 className="font-bold text-white text-lg leading-tight truncate pr-2">{selectedNode.id}</h3>
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
                        ? "This concept was synthesized from your uploaded evidence."
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
                        <button className="text-xs bg-red-500/10 hover:bg-red-500/20 px-2 py-1 rounded text-red-300 transition-colors border border-red-500/10">
                          Mark Contradiction
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
                    {selectedNode.sourceText}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Session Summary Overlay (Crystallized State) */}
          {isCrystallized && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-8 z-50">
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
    </div>
  );
}
