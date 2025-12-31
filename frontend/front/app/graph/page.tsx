"use client";

import dynamic from 'next/dynamic';
import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

// Dynamically import GraphVisualization to avoid SSR issues with Canvas
const GraphVisualization = dynamic(() => import("@/components/GraphVisualization"), {
    ssr: false,
    loading: () => <div className="w-full h-full flex items-center justify-center text-slate-500">Loading Graph Core...</div>
});

export default function GraphPage() {
    // Graph Data State
    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] }>({
        nodes: [],
        links: []
    });

    const [brainLayer, setBrainLayer] = useState<'layer1' | 'layer2'>('layer1');
    const [isGraphLoading, setIsGraphLoading] = useState(false);
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [showSource, setShowSource] = useState(false);

    // Initial Data Fetch
    useEffect(() => {
        fetchGlobalGraph('layer1');
    }, []);

    const fetchGlobalGraph = async (layer: 'layer1' | 'layer2') => {
        setIsGraphLoading(true);
        // Layer 1 = Top 50, Layer 2 = Top 1000 (Full)
        const limit = layer === 'layer1' ? 50 : 1000;

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/session/global/graph?limit=${limit}`);
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

    const handleNodeClick = (node: any) => {
        console.log("Node Clicked:", node);
        setSelectedNode(node);
        setShowSource(false); // Reset view
    };

    return (
        <div className="h-[calc(100vh-2rem)] flex flex-col gap-4">
            {/* Header */}
            <div className="flex justify-between items-center px-4 shrink-0">
                <div>
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-purple-500">
                        Knowledge Graph
                    </h1>
                    <p className="text-xs text-slate-500">
                        Global Brain Visualization
                    </p>
                </div>

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
            </div>


            <div className="flex-1 min-h-0 bg-gradient-to-tr from-teal-900/10 to-purple-900/10 rounded-xl overflow-hidden border border-white/5 relative mx-4 mb-4">
                <GraphVisualization
                    data={graphData}
                    // For global graph page, we don't have crystallization state, so default False or create prop if needed 
                    // GraphVisualization might expect isCrystallized prop? Checking Page.tsx usage: 
                    // isCrystallized={isCrystallized}
                    // We can default it to false as this is the Global Explorer.
                    isCrystallized={false}
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

                {/* Node Explanation Overlay */}
                {selectedNode && (
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
            </div>
        </div>
    );
}
