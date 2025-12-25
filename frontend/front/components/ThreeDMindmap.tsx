"use client";

import dynamic from 'next/dynamic';
import { useRef, useCallback, useState, useMemo, useEffect } from 'react';
import SpriteText from 'three-spritetext';
import { X, Filter, Info } from 'lucide-react';

const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
    ssr: false,
    loading: () => <div className="text-active animate-pulse">Loading Graph...</div>
});

const ThreeDMindmap = ({ graphData, onNodeClick }: { graphData: any, onNodeClick?: (node: any) => void }) => {
    const fgRef = useRef<any>();
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [filters, setFilters] = useState({
        evidence: true,
        thought: true,
        concept: true
    });
    const [showControls, setShowControls] = useState(false);

    // Initial camera position
    useEffect(() => {
        if (fgRef.current) {
            fgRef.current.d3Force('charge').strength(-120);
        }
    }, [fgRef.current]);

    const handleNodeClick = useCallback((node: any) => {
        // Aim at node
        const distance = 40;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

        if (fgRef.current) {
            fgRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                node,
                3000
            );
        }

        setSelectedNode(node);
        if (onNodeClick) onNodeClick(node);
    }, [onNodeClick]);

    // Filter Logic
    const filteredGraphData = useMemo(() => {
        if (!graphData) return { nodes: [], links: [] };

        const activeGroups = new Set();
        if (filters.evidence) activeGroups.add('evidence');
        if (filters.thought) activeGroups.add('thought');
        if (filters.concept) activeGroups.add('concept');

        const nodes = graphData.nodes.filter((n: any) => {
            // Default to 'concept' if group missing
            const group = n.group || 'concept';
            return activeGroups.has(group);
        });

        const nodeIds = new Set(nodes.map((n: any) => n.id));
        const links = graphData.links.filter((l: any) =>
            nodeIds.has(typeof l.source === 'object' ? l.source.id : l.source) &&
            nodeIds.has(typeof l.target === 'object' ? l.target.id : l.target)
        );

        return { nodes, links };
    }, [graphData, filters]);

    return (
        <div className="relative w-full h-[600px] border border-white/10 rounded-xl overflow-hidden bg-black/50 group">
            <ForceGraph3D
                ref={fgRef}
                graphData={filteredGraphData}
                nodeLabel="label"
                nodeColor={(node: any) => node.color || '#3b82f6'}
                nodeVal={(node: any) =>
                    node.group === 'concept' ? 15 :
                        node.group === 'thought' ? 10 : 8
                }
                nodeResolution={16}

                // Edges
                linkColor={() => 'rgba(100,200,255,0.4)'}
                linkOpacity={0.6}
                linkWidth={1.5}
                linkThreeObjectExtend={true}
                linkThreeObject={(link: any) => {
                    const sprite = new SpriteText(link.label || '');
                    sprite.color = 'rgba(255,255,255,0.6)';
                    sprite.textHeight = 1.5;
                    return sprite;
                }}
                linkPositionUpdate={(sprite: any, { start, end }: any) => {
                    const middlePos = Object.assign({}, start, {
                        x: start.x + (end.x - start.x) / 2,
                        y: start.y + (end.y - start.y) / 2,
                        z: start.z + (end.z - start.z) / 2
                    });
                    Object.assign(sprite.position, middlePos);
                }}

                onNodeClick={handleNodeClick}
                backgroundColor="rgba(0,0,0,0)"
            />

            {/* Controls Toggle */}
            <button
                onClick={() => setShowControls(!showControls)}
                className="absolute top-4 left-4 p-2 bg-black/60 rounded-lg hover:bg-white/10 text-slate-300 transition-colors"
                title="Graph Options"
            >
                <Filter className="w-5 h-5" />
            </button>

            {/* Filter Panel */}
            {showControls && (
                <div className="absolute top-16 left-4 bg-black/80 backdrop-blur-md border border-white/10 p-4 rounded-xl shadow-xl w-48">
                    <h3 className="text-xs font-semibold text-slate-400 uppercase mb-3">Filter Nodes</h3>
                    <div className="space-y-2">
                        <label className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer">
                            <input type="checkbox" checked={filters.concept} onChange={e => setFilters({ ...filters, concept: e.target.checked })} className="rounded bg-white/10 border-white/20 text-blue-500" />
                            <span className="w-2 h-2 rounded-full bg-blue-500" /> Concepts
                        </label>
                        <label className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer">
                            <input type="checkbox" checked={filters.thought} onChange={e => setFilters({ ...filters, thought: e.target.checked })} className="rounded bg-white/10 border-white/20 text-purple-500" />
                            <span className="w-2 h-2 rounded-full bg-purple-500" /> Thoughts
                        </label>
                        <label className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer">
                            <input type="checkbox" checked={filters.evidence} onChange={e => setFilters({ ...filters, evidence: e.target.checked })} className="rounded bg-white/10 border-white/20 text-orange-500" />
                            <span className="w-2 h-2 rounded-full bg-orange-500" /> Evidence
                        </label>
                    </div>
                </div>
            )}

            {/* Selected Node Details Overlay */}
            {selectedNode && (
                <div className="absolute bottom-4 right-4 max-w-sm bg-black/90 backdrop-blur-lg border border-active/30 p-5 rounded-xl shadow-2xl animate-slide-in">
                    <button onClick={() => setSelectedNode(null)} className="absolute top-2 right-2 p-1 hover:text-white text-slate-500">
                        <X className="w-4 h-4" />
                    </button>

                    <div className="flex items-center gap-2 mb-3">
                        <span className={`w-3 h-3 rounded-full ${selectedNode.group === 'evidence' ? 'bg-orange-500' :
                                selectedNode.group === 'thought' ? 'bg-purple-500' : 'bg-blue-500'
                            }`} />
                        <h3 className="text-lg font-bold text-white leading-tight">{selectedNode.label}</h3>
                    </div>

                    <p className="text-sm text-slate-300 leading-relaxed max-h-40 overflow-y-auto mb-2 custom-scrollbar">
                        {selectedNode.title || selectedNode.id}
                    </p>

                    {selectedNode.group === 'concept' && (
                        <div className="text-xs text-active border-t border-white/10 pt-2 mt-2">
                            System Extracted Concept
                        </div>
                    )}
                </div>
            )}

            {!selectedNode && (
                <div className="absolute bottom-4 right-4 text-xs text-slate-500 bg-black/40 px-3 py-1 rounded-full pointer-events-none">
                    Click a node to view details
                </div>
            )}
        </div>
    );
};

export default ThreeDMindmap;
