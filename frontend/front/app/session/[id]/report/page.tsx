"use client";

import { useEffect, useState, use } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Calendar, Clock, Edit2, Check, X, FileText, Brain, Share2, Layers } from "lucide-react";
import ThreeDMindmap from "@/components/ThreeDMindmap";
import CrystallizationWizard from "@/components/CrystallizationWizard";

interface TimelineEvent {
    type: "evidence" | "thought" | "analysis";
    id: string;
    content: string;
    full_content?: string;
    timestamp: string;
    source?: string;
    confidence?: string;
}

interface GraphNode {
    id: string;
    label: string;
    color: string;
    val: number;
}

interface GraphLink {
    source: string;
    target: string;
    label: string;
}

interface SessionSummary {
    session_id: string;
    title: string;
    goal: string;
    created_at: string;
    timeline: TimelineEvent[];
    graph_data: {
        nodes: GraphNode[];
        links: GraphLink[];
    };
    concept_count: number;
    evidence_count: number;
}

export default function SessionReport({ params }: { params: Promise<{ id: string }> }) {
    // Unwrap params in Next.js 15+ (if using that, but safe to assume standard usage or use hook)
    // Actually, create-next-app usually gives params as prop.
    // Using `use` hook for params if it's a promise (latest Next.js) or just hook.
    // Let's stick to standard `useParams` for client components to be safe.
    const { id } = useParams();
    const router = useRouter();

    const [summary, setSummary] = useState<SessionSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<"summary" | "map" | "crystallize">("summary");
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editContent, setEditContent] = useState("");

    useEffect(() => {
        if (!id) return;
        fetchSummary();
    }, [id]);

    const fetchSummary = async () => {
        try {
            const res = await fetch(`http://localhost:8000/api/v1/session/${id}/summary`);
            if (!res.ok) throw new Error("Failed to fetch summary");
            const data = await res.json();
            setSummary(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleEditStart = (item: TimelineEvent) => {
        setEditingId(item.id);
        setEditContent(item.type === "evidence" ? (item.full_content || item.content) : item.content);
    };

    const handleEditSave = async () => {
        if (!editingId || !id) return;
        try {
            const res = await fetch(`http://localhost:8000/api/v1/session/${id}/content`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ item_id: editingId, content: editContent })
            });
            if (!res.ok) throw new Error("Failed to update");

            // Refresh
            await fetchSummary();
            setEditingId(null);
        } catch (err) {
            alert("Failed to save changes");
        }
    };

    if (loading) return <div className="p-8 text-active">Loading Session Report...</div>;
    if (!summary) return <div className="p-8 text-red-400">Session not found.</div>;

    return (
        <div className="min-h-screen bg-black text-slate-200 p-8 custom-scrollbar">
            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-8"
            >
                <div className="flex justify-between items-start">
                    <div>
                        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500 mb-2">
                            {summary.title}
                        </h1>
                        <p className="text-slate-400 flex items-center gap-2">
                            <Brain className="w-4 h-4 text-purple-400" />
                            Goal: {summary.goal}
                        </p>
                    </div>
                    <div className="flex gap-4 text-sm text-slate-500">
                        <div className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {new Date(summary.created_at).toLocaleDateString()}
                        </div>
                        <div className="bg-white/5 px-3 py-1 rounded-full border border-white/10">
                            {summary.concept_count} Concepts
                        </div>
                        <div className="bg-white/5 px-3 py-1 rounded-full border border-white/10">
                            {summary.evidence_count} Evidence
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* Tabs */}
            <div className="flex gap-4 mb-8 border-b border-white/10 pb-4">
                {[
                    { id: "summary", label: "Session Timeline", icon: Calendar },
                    { id: "map", label: "4D Mindmap", icon: Share2 },
                    { id: "crystallize", label: "Crystallize", icon: Layers },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as any)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${activeTab === tab.id
                            ? "bg-teal-500 text-black font-semibold shadow-[0_0_15px_rgba(20,184,166,0.5)]"
                            : "text-slate-400 hover:text-white hover:bg-white/5"
                            }`}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            <AnimatePresence mode="wait">
                {activeTab === "summary" && (
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className="space-y-4 max-w-4xl"
                    >
                        {summary.timeline.map((item, idx) => (
                            <div key={item.id} className="glass-card p-6 rounded-xl border border-white/5 relative group">
                                {/* Connector Line */}
                                {idx !== summary.timeline.length - 1 && (
                                    <div className="absolute left-8 top-16 bottom-0 w-0.5 bg-white/10 -mb-6 z-0" />
                                )}

                                <div className="flex gap-4 relative z-10">
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${item.type === "evidence" ? "bg-orange-500/20 text-orange-400" : "bg-purple-500/20 text-purple-400"
                                        }`}>
                                        {item.type === "evidence" ? <FileText className="w-5 h-5" /> : <Brain className="w-5 h-5" />}
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className={`text-xs font-mono px-2 py-0.5 rounded ${item.type === "evidence" ? "bg-orange-900/30 text-orange-300" :
                                                item.type === "analysis" ? "bg-blue-900/30 text-blue-300" :
                                                    "bg-purple-900/30 text-purple-300"
                                                }`}>
                                                {item.type.toUpperCase()}
                                            </span>
                                            <span className="text-xs text-slate-500">
                                                {new Date(item.timestamp).toLocaleTimeString()}
                                            </span>
                                        </div>

                                        {editingId === item.id ? (
                                            <div className="mt-2">
                                                <textarea
                                                    value={editContent}
                                                    onChange={(e) => setEditContent(e.target.value)}
                                                    className="w-full bg-black/50 border border-active/50 rounded-lg p-3 text-sm focus:outline-none min-h-[100px]"
                                                />
                                                <div className="flex gap-2 mt-2 justify-end">
                                                    <button onClick={() => setEditingId(null)} className="p-2 hover:bg-white/10 rounded">
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                    <button onClick={handleEditSave} className="p-2 bg-active text-black rounded hover:bg-active/90">
                                                        <Check className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="group/content relative">
                                                <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
                                                    {item.full_content || item.content}
                                                </p>
                                                {item.source && (
                                                    <div className="mt-2 text-xs text-slate-500 italic">
                                                        Source: {item.source}
                                                    </div>
                                                )}

                                                <button
                                                    onClick={() => handleEditStart(item)}
                                                    className="absolute top-0 right-0 opacity-0 group-hover/content:opacity-100 p-2 text-slate-400 hover:text-active transition-opacity"
                                                >
                                                    <Edit2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </motion.div>
                )}

                {activeTab === "map" && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                    >
                        <ThreeDMindmap
                            graphData={summary.graph_data}
                            onNodeClick={(node: any) => alert(`Clicked ${node.label}`)}
                        />
                        <div className="mt-4 text-center text-slate-400 text-sm">
                            Full Knowledge Graph Context (Session View)
                        </div>
                    </motion.div>
                )}

                {activeTab === "crystallize" && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    >
                        <CrystallizationWizard
                            sessionId={id as string}
                            onComplete={() => {
                                alert("Session Crystalized and Archived. Redirecting to Brain...");
                                router.push('/');
                            }}
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
