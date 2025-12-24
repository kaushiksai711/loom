"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Activity, ZoomIn, ZoomOut, Maximize } from "lucide-react";
import { motion } from "framer-motion";

// Dynamically import ForceGraph to avoid SSR issues
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
    ssr: false,
    loading: () => <div className="text-slate-500">Initializing Neural Interface...</div>,
});

interface Node {
    id: string;
    name: string;
    val: number;
    group?: string;
}

interface Link {
    source: string;
    target: string;
    type?: string;
}

interface GraphData {
    nodes: Node[];
    links: Link[];
}

export default function GraphPage() {
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Fetch graph data from backend
        const fetchGraph = async () => {
            try {
                const res = await fetch("/api/v1/graph");
                if (res.ok) {
                    const graphData = await res.json();
                    setData(graphData);
                }
            } catch (error) {
                console.error("Failed to fetch graph data:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchGraph();
    }, []);

    return (
        <div className="relative h-[calc(100vh-6rem)] w-full overflow-hidden rounded-xl border border-white/10 bg-black/50">

            {/* Overlay: Controls */}
            <div className="absolute top-4 left-4 z-10 p-4 glass-card rounded-lg max-w-xs">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-secondary" />
                    Neural Architecture
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                    Visualizing {data.nodes.length} concepts and {data.links.length} connections.
                </p>
            </div>

            <div className="absolute bottom-4 right-4 z-10 flex flex-col gap-2">
                <button className="p-2 glass rounded-full hover:bg-white/10 text-white" title="Zoom In">
                    <ZoomIn className="w-5 h-5" />
                </button>
                <button className="p-2 glass rounded-full hover:bg-white/10 text-white" title="Zoom Out">
                    <ZoomOut className="w-5 h-5" />
                </button>
                <button className="p-2 glass rounded-full hover:bg-white/10 text-white" title="Fit to Screen">
                    <Maximize className="w-5 h-5" />
                </button>
            </div>

            {loading ? (
                <div className="flex h-full items-center justify-center">
                    <Activity className="w-10 h-10 text-slate-500 animate-spin" />
                </div>
            ) : (
                <ForceGraph2D
                    graphData={data}
                    nodeLabel="name"
                    nodeColor={(node: any) => node.group === 'concept' ? '#10b981' : '#6366f1'}
                    nodeRelSize={6}
                    linkColor={() => 'rgba(255,255,255,0.2)'}
                    backgroundColor="rgba(0,0,0,0)"
                    d3VelocityDecay={0.1}
                    cooldownTicks={100}
                    onNodeClick={(node) => {
                        // Handle node click (e.g. open details)
                        console.log("Clicked node:", node);
                    }}
                />
            )}
        </div>
    );
}
