"use client";

import React, { useMemo, useEffect, useState } from 'react';
import ReactFlow, {
    Background,
    Controls,
    Handle,
    Position,
    Node,
    Edge,
    MarkerType,
    useReactFlow,
    ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { FileText, Lightbulb, Brain, Gem, Database, ChevronRight, ChevronLeft, Clock, Globe, PenTool } from 'lucide-react';

/* --------------------------------------------------------------------------------
   CONSTANTS & CONFIG
   Generic Ontology Colors (Content Agnostic)
--------------------------------------------------------------------------------- */
const CATEGORY_COLORS: Record<string, string> = {
    "Organization": "#7C3AED", // Purple
    "Person": "#EC4899", // Pink
    "Event": "#DC2626", // Red
    "Technology": "#059669", // Green
    "Location": "#F59E0B", // Amber
    "Concept": "#2563EB", // Blue
    "Object": "#14B8A6", // Teal
    "default": "#2563EB"
};

const getCategoryColor = (cat?: string) => {
    if (!cat) return CATEGORY_COLORS["default"];
    // fuzzy match for generic categories
    for (const key of Object.keys(CATEGORY_COLORS)) {
        if (cat.toLowerCase().includes(key.toLowerCase())) {
            return CATEGORY_COLORS[key];
        }
    }
    return CATEGORY_COLORS["default"];
};

/* --------------------------------------------------------------------------------
   CUSTOM NODE TYPES
--------------------------------------------------------------------------------- */

const SourceContainerNode = ({ data }: { data: any }) => (
    <div className="px-4 py-3 shadow-md rounded-lg bg-orange-900/40 border-2 border-orange-600/50 w-64 backdrop-blur-sm">
        <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-orange-500/20 text-orange-400">
                <Database className="w-5 h-5" />
            </div>
            <div>
                <div className="text-xs text-orange-300 font-bold uppercase tracking-wider">Source Container</div>
                <div className="text-sm text-slate-100 font-medium truncate" title={data.label}>{data.label}</div>
                <div className="text-xs text-slate-400 mt-1">{data.count} Reference{data.count !== 1 ? 's' : ''}</div>
            </div>
        </div>
        <Handle type="target" position={Position.Left} className="w-3 h-3 bg-orange-500" />
    </div>
);

const VerifiedConceptNode = ({ data }: { data: any }) => {
    const color = getCategoryColor(data.category);
    return (
        <div
            className="px-4 py-3 shadow-xl rounded-xl border-2 w-72 backdrop-blur-md relative group transition-all hover:scale-105"
            style={{
                backgroundColor: `${color}20`, // 20% opacity hex
                borderColor: color
            }}
        >
            <div className="flex items-start gap-3">
                <div className="p-2 rounded-full mt-1" style={{ backgroundColor: `${color}30`, color: color }}>
                    <Gem className="w-5 h-5" />
                </div>
                <div>
                    <div className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: color }}>
                        {data.category || "Verified Concept"}
                    </div>
                    <div className="text-base text-white font-bold leading-tight mb-1">{data.label}</div>

                    {/* Source Badge */}
                    {data.sourceCount > 0 && (
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900/50 border border-slate-700 text-[10px] text-slate-300 mt-1">
                            <FileText className="w-3 h-3" />
                            <span>{data.sourceCount} Ref{data.sourceCount > 1 ? 's' : ''}</span>
                        </div>
                    )}

                    {data.summary && (
                        <div className="mt-2 text-xs text-slate-300 line-clamp-2 group-hover:line-clamp-none transition-all">
                            {data.summary}
                        </div>
                    )}
                </div>
            </div>
            <Handle type="target" position={Position.Left} className="w-3 h-3" style={{ background: color }} />
            <Handle type="source" position={Position.Right} className="w-3 h-3" style={{ background: color }} />
        </div>
    );
};

const SeedNode = ({ data }: { data: any }) => (
    <div className="px-4 py-3 shadow-md rounded-full bg-slate-900 border border-slate-700 w-60">
        <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-full bg-purple-500/20 text-purple-400">
                <Lightbulb className="w-4 h-4" />
            </div>
            <div>
                <div className="text-xs text-slate-500 font-bold uppercase">Raw Idea</div>
                <div className="text-sm text-slate-300 truncate">{data.label}</div>
            </div>
        </div>
        <Handle type="target" position={Position.Left} className="w-2 h-2 bg-slate-600" />
    </div>
);

const SessionRootNode = ({ data }: { data: any }) => (
    <div className="px-6 py-4 shadow-2xl rounded-2xl bg-gradient-to-br from-white to-slate-200 text-black border-4 border-white w-80">
        <div className="flex flex-col items-center text-center">
            <Brain className="w-8 h-8 text-black mb-2" />
            <div className="text-xs font-bold uppercase tracking-widest text-slate-600">Current Session</div>
            <div className="text-xl font-extrabold">{data.label}</div>
        </div>
        <Handle type="source" position={Position.Right} className="w-4 h-4 bg-white border-2 border-black" />
    </div>
);

const nodeTypes = {
    evidence: SourceContainerNode,
    concept: VerifiedConceptNode,
    seed: SeedNode,
    session: SessionRootNode,
};

/* --------------------------------------------------------------------------------
   LAYOUT ENGINE (DAGRE)
--------------------------------------------------------------------------------- */
const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    // Direction: LR = Left to Right (Root -> Concepts -> Evidence/Sources)
    dagreGraph.setGraph({ rankdir: 'LR', ranksep: 200, nodesep: 60 });

    nodes.forEach((node) => {
        // Set dimensions based on node types roughly
        const width = node.type === 'session' ? 320 : node.type === 'concept' ? 300 : 260;
        const height = node.type === 'session' ? 120 : (node.data.summary ? 150 : 100);
        dagreGraph.setNode(node.id, { width, height });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - (node.width || 0) / 2,
                y: nodeWithPosition.y - (node.height || 0) / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

/* --------------------------------------------------------------------------------
   MAIN COMPONENT
--------------------------------------------------------------------------------- */

interface StructuredMindmapProps {
    sessionTitle: string;
    graphData: {
        nodes: any[];
        links: any[];
    };
    onNodeClick?: (node: any) => void;
}

const MindmapContent = ({ sessionTitle, graphData, onNodeClick }: StructuredMindmapProps) => {
    const { fitView } = useReactFlow();
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // 1. Transform Backend Data -> React Flow Elements
    const { nodes: initialNodes, edges: initialEdges, timelineSeeds } = useMemo(() => {
        const rfNodes: Node[] = [];
        const rfEdges: Edge[] = [];
        const timelineSeeds: any[] = [];

        // --- A. GROUPS & MAPS ---
        const rawNodes = graphData.nodes;
        const evidenceNodes = rawNodes.filter(n => n.group === 'evidence' || n.id.includes('.pdf') || n.id.includes('http'));
        // Separate 'thought' nodes for the sidebar
        const thoughtNodes = rawNodes.filter(n => n.group === 'thought');
        const conceptNodes = rawNodes.filter(n => !evidenceNodes.includes(n) && !thoughtNodes.includes(n));

        // Group Evidence by Source
        const sourceMap = new Map<string, { id: string, label: string, count: number, originalIds: string[] }>();
        const chunkToSourceId = new Map<string, string>();
        const chunkToContent = new Map<string, string>();

        evidenceNodes.forEach(n => {
            const sourceLabel = n.title?.split('(')[0].trim() || n.label || "Unknown Source";
            const sourceId = `source-${sourceLabel.replace(/[^a-zA-Z0-9]/g, '-')}`;

            if (!sourceMap.has(sourceId)) {
                sourceMap.set(sourceId, { id: sourceId, label: sourceLabel, count: 0, originalIds: [] });
            }
            const entry = sourceMap.get(sourceId)!;
            entry.count++;
            entry.originalIds.push(n.id);
            chunkToSourceId.set(n.id, sourceId);
            chunkToContent.set(n.id, n.content || n.title || "");
        });

        // Store thoughts AND evidence for sidebar (Temporal Flow)
        // We want to show what the user added/uploaded.
        // Store thoughts AND specific web clips for sidebar (Temporal Flow)
        // User considers Web Clips as "Seeds", but likely wants to hide bulk PDF chunks.
        const combinedTimeline = [
            ...thoughtNodes,
            ...evidenceNodes.filter(n => {
                const titleLower = (n.title || "").toLowerCase();
                const idLower = (n.id || "").toLowerCase();
                // Include if Title OR ID looks like a URL. Exclude explicit PDF files unless they are URLs.
                return (titleLower.includes('http') || titleLower.includes('www') || idLower.includes('http'));
            })
        ];

        // Remove strictly PDF file chunks from the sidebar flow to reduce noise, 
        // keeping only "User Seeds" (Thoughts) and "Web Resources" (Links).
        const uniqueTimeline = Array.from(new Set(combinedTimeline.map(n => n.id)))
            .map(id => combinedTimeline.find(n => n.id === id)!);

        uniqueTimeline.forEach(n => timelineSeeds.push(n));

        // --- B. CREATE NODES ---

        // 1. Root Node
        rfNodes.push({
            id: 'root-session',
            type: 'session',
            data: { label: sessionTitle || "Untitled Session" },
            position: { x: 0, y: 0 }
        });

        // 2. Source Container Nodes
        sourceMap.forEach((val) => {
            rfNodes.push({
                id: val.id,
                type: 'evidence',
                data: { label: val.label, count: val.count },
                position: { x: 0, y: 0 }
            });
        });

        // 3. Concept Nodes
        // Calculate source counts AND accumulate references
        const conceptReferences = new Map<string, any[]>();

        graphData.links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            let conceptId = null;
            let evidenceId = null;

            if (conceptNodes.find(c => c.id === sourceId) && chunkToSourceId.has(targetId)) {
                conceptId = sourceId; evidenceId = targetId;
            } else if (chunkToSourceId.has(sourceId) && conceptNodes.find(c => c.id === targetId)) {
                evidenceId = sourceId; conceptId = targetId;
            }

            if (conceptId && evidenceId) {
                if (!conceptReferences.has(conceptId)) conceptReferences.set(conceptId, []);
                // Add reference details
                const sourceContainerId = chunkToSourceId.get(evidenceId)!;
                const sourceLabel = sourceMap.get(sourceContainerId)?.label;

                conceptReferences.get(conceptId)!.push({
                    source: sourceLabel,
                    text: chunkToContent.get(evidenceId)
                });
            }
        });

        conceptNodes.forEach(n => {
            const isConfirmed = n.group === 'concept' || (n.val && n.val > 10);
            const refs = conceptReferences.get(n.id) || [];

            rfNodes.push({
                id: n.id,
                type: isConfirmed ? 'concept' : 'seed',
                data: {
                    label: n.label,
                    summary: n.content || n.desc,
                    category: n.category,
                    sourceCount: refs.length,
                    references: refs // Pass full references to the node data
                },
                position: { x: 0, y: 0 }
            });

            // Link Root -> Concept
            rfEdges.push({
                id: `e-root-${n.id}`,
                source: 'root-session',
                target: n.id,
                type: 'smoothstep',
                animated: false,
                style: { stroke: '#CBD5E1', strokeWidth: 1 }
            });
        });

        // --- C. CREATE EDGES ---

        // 1. Concept -> Concept
        graphData.links.forEach((link, i) => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            const isSourceConcept = conceptNodes.find(c => c.id === sourceId);
            const isTargetConcept = conceptNodes.find(c => c.id === targetId);

            if (isSourceConcept && isTargetConcept) {
                rfEdges.push({
                    id: `e-c-${i}`,
                    source: sourceId,
                    target: targetId,
                    label: link.type || '',
                    type: 'smoothstep',
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#60A5FA' },
                    style: { stroke: '#60A5FA', strokeWidth: 2, strokeDasharray: '5,5' }
                });
            }
        });

        // 2. Concept -> Source Layout Edges
        const linkedSources = new Set<string>();
        graphData.links.forEach((link) => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            let conceptId = null;
            let chunkId = null;

            if (conceptNodes.find(c => c.id === sourceId) && chunkToSourceId.has(targetId)) {
                conceptId = sourceId; chunkId = targetId;
            } else if (chunkToSourceId.has(sourceId) && conceptNodes.find(c => c.id === targetId)) {
                chunkId = sourceId; conceptId = targetId;
            }

            if (conceptId && chunkId) {
                const sourceContainerId = chunkToSourceId.get(chunkId)!;
                const linkKey = `${conceptId}-${sourceContainerId}`;
                if (!linkedSources.has(linkKey)) {
                    linkedSources.add(linkKey);
                    rfEdges.push({
                        id: `e-layout-${linkKey}`,
                        source: conceptId,
                        target: sourceContainerId,
                        type: 'straight',
                        animated: false,
                        style: { opacity: 0 }
                    });
                }
            }
        });

        return { nodes: getLayoutedElements(rfNodes, rfEdges).nodes, edges: rfEdges, timelineSeeds: timelineSeeds };

    }, [graphData, sessionTitle]);

    const handleNodeClick = (_: React.MouseEvent, node: Node) => {
        if (onNodeClick && (node.type === 'concept' || node.type === 'seed')) {
            onNodeClick(node.data);
        }
    };

    useEffect(() => {
        window.requestAnimationFrame(() => fitView({ padding: 0.2 }));
    }, [initialNodes, fitView]);

    return (
        <div className="relative w-full h-full flex">
            {/* Mindmap Area */}
            <div className="flex-1 h-full relative">
                <ReactFlow
                    nodes={initialNodes}
                    edges={initialEdges}
                    nodeTypes={nodeTypes}
                    onNodeClick={handleNodeClick}
                    fitView
                    attributionPosition="bottom-right"
                >
                    <Background color="#1e293b" gap={20} />
                    <Controls className="bg-slate-800 text-white border-slate-700" />
                </ReactFlow>

                {/* Timeline Toggle */}
                <button
                    onClick={() => setSidebarOpen(!sidebarOpen)}
                    className="absolute top-4 right-4 z-10 bg-slate-800 p-2 rounded-md border border-slate-600 hover:bg-slate-700 text-slate-300 transition-colors"
                >
                    {sidebarOpen ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
                </button>
            </div>

            {/* Right Sidebar: Timeline / User Seeds */}
            <div className={`
                bg-slate-900 border-l border-slate-700 transition-all duration-300 overflow-hidden flex flex-col
                ${sidebarOpen ? 'w-80 opacity-100' : 'w-0 opacity-0'}
            `}>
                <div className="p-4 border-b border-slate-700 bg-slate-800/50">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <Clock className="w-4 h-4" /> Timeline Flow
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                    {timelineSeeds && timelineSeeds.length > 0 ? (
                        timelineSeeds.map((seed, idx) => (
                            <div key={seed.id || idx} className="relative pl-4 border-l-2 border-slate-700 pb-4 last:pb-0 last:border-l-0">
                                <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-2 ${seed.group === 'evidence' ? 'bg-orange-900 border-orange-500' : 'bg-slate-800 border-purple-500/50'
                                    }`}></div>
                                <div className={`
                                    p-3 rounded-lg border transition-colors
                                    ${seed.group === 'evidence'
                                        ? 'bg-orange-900/20 border-orange-700/50 hover:bg-orange-900/40'
                                        : 'bg-slate-800/50 border-slate-700/50 hover:bg-slate-800'
                                    }
                                `}>
                                    <div className={`text-xs font-mono mb-1 flex items-center gap-2 ${seed.group === 'evidence' ? 'text-orange-400' : 'text-purple-400'
                                        }`}>
                                        {seed.group === 'evidence' ? (
                                            (seed.id.includes('http') || seed.id.includes('www')) ? <Globe className="w-3 h-3" /> : <FileText className="w-3 h-3" />
                                        ) : <PenTool className="w-3 h-3" />}

                                        {seed.group === 'evidence' ? (
                                            (seed.id.includes('http') || seed.id.includes('www')) ? 'Web Clip' : 'Document'
                                        ) : 'User Note'}
                                    </div>
                                    <div className="text-sm text-slate-200 line-clamp-3" title={seed.content || seed.label}>
                                        {seed.content || seed.label}
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <div className="text-xs text-slate-500 italic text-center mt-10">
                            No user seeds recorded in this session.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default function StructuredMindmap(props: StructuredMindmapProps) {
    return (
        <div className="w-full h-[600px] bg-slate-950 rounded-xl border border-white/10 overflow-hidden">
            <ReactFlowProvider>
                <MindmapContent {...props} />
            </ReactFlowProvider>
        </div>
    );
}
