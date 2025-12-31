"use client";

import { useState, useEffect } from "react";
import { Loader2, Check, X, ArrowRight, Save, AlertTriangle, Layers } from "lucide-react";

interface MergeProposal {
    session_id: string;
    proposed_merges: {
        source_id: string;
        target_id: string;
        target_label: string;
        confidence: number;
        status: "auto_merge" | "ambiguous";
    }[];
    new_nodes: {
        _id?: string;
        text: string;
        comment?: string;
    }[];
    conflicts: {
        seed_text: string;
        conflicting_evidence: string;
        reason: string;
    }[];
}

interface CrystallizationWizardProps {
    sessionId: string;
    onComplete: () => void;
}

export default function CrystallizationWizard({ sessionId, onComplete }: CrystallizationWizardProps) {
    const [step, setStep] = useState<"preview" | "review" | "commit">("preview");
    const [proposal, setProposal] = useState<MergeProposal | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [approvedMerges, setApprovedMerges] = useState<Set<number>>(new Set());
    const [committing, setCommitting] = useState(false);

    useEffect(() => {
        fetchPreview();
    }, [sessionId]);

    const fetchPreview = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/session/crystallize/${sessionId}/preview`, {
                method: "POST"
            });

            if (!res.ok) throw new Error(`Preview fetch failed: ${res.statusText}`);

            const data = await res.json();
            if (!data) throw new Error("Received empty data from backend");

            console.log("Crystallization Preview Data:", data); // Debug

            setProposal(data);

            // Safety: Ensure arrays exist
            const merges = data.proposed_merges || [];
            if (!Array.isArray(merges)) throw new Error("Invalid format: proposed_merges is not an array");

            const autoIndices = merges
                .map((m: any, i: number) => m.status === "auto_merge" ? i : -1)
                .filter((i: number) => i !== -1);
            setApprovedMerges(new Set(autoIndices));

            setStep("review");
        } catch (err: any) {
            console.error("Preview Error:", err);
            setError(err.message || "Failed to load preview");
        } finally {
            setLoading(false);
        }
    };

    const toggleMerge = (index: number) => {
        const next = new Set(approvedMerges);
        if (next.has(index)) next.delete(index);
        else next.add(index);
        setApprovedMerges(next);
    };

    const handleCommit = async () => {
        if (!proposal) return;
        setCommitting(true);
        try {
            const payload = {
                approved_merges: proposal.proposed_merges.filter((_, i) => approvedMerges.has(i)),
                new_nodes: proposal.new_nodes
            };

            const res = await fetch(`http://127.0.0.1:8000/api/v1/session/crystallize/${sessionId}/commit`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                onComplete();
            } else {
                alert("Commit failed.");
            }
        } catch (err) {
            console.error(err);
        } finally {
            setCommitting(false);
        }
    };

    if (step === "preview" || loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                <Loader2 className="w-12 h-12 animate-spin mb-4 text-active" />
                <p>Analyzing Session Context...</p>
                <div className="text-xs mt-2 opacity-50">Running Entity Resolution & Conflict Detection</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-red-400">
                <AlertTriangle className="w-12 h-12 mb-4" />
                <p className="font-bold">Crystallization Protocol Failed</p>
                <p className="text-sm mt-2">{error}</p>
                <button onClick={fetchPreview} className="mt-6 px-4 py-2 bg-slate-800 rounded hover:bg-slate-700 text-white text-sm">
                    Retry Analysis
                </button>
            </div>
        );
    }

    if (!proposal) return <div className="text-red-400 p-10 text-center">No proposal data available.</div>;

    return (
        <div className="max-w-4xl mx-auto space-y-8 pb-20">
            {/* Header */}
            <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-white mb-2">Crystallization Protocol</h2>
                <p className="text-slate-400 text-sm">Review how this session will be integrated into your Long-Term Memory.</p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-4">
                <div className="glass-card p-4 rounded-xl text-center border-l-4 border-blue-500">
                    <div className="text-2xl font-bold text-white mb-1">{proposal.new_nodes.length}</div>
                    <div className="text-xs text-slate-400 uppercase tracking-wider">New Concepts</div>
                </div>
                <div className="glass-card p-4 rounded-xl text-center border-l-4 border-purple-500">
                    <div className="text-2xl font-bold text-white mb-1">{approvedMerges.size}</div>
                    <div className="text-xs text-slate-400 uppercase tracking-wider">Merges</div>
                </div>
                <div className="glass-card p-4 rounded-xl text-center border-l-4 border-orange-500">
                    <div className="text-2xl font-bold text-white mb-1">{proposal.conflicts.length}</div>
                    <div className="text-xs text-slate-400 uppercase tracking-wider">Conflicts</div>
                </div>
            </div>

            {/* Conflicts Section */}
            {proposal.conflicts.length > 0 && (
                <div className="bg-orange-500/5 border border-orange-500/20 rounded-xl p-6">
                    <h3 className="flex items-center gap-2 text-lg font-semibold text-orange-200 mb-4">
                        <AlertTriangle className="w-5 h-5 text-orange-500" />
                        Detected Contradictions
                    </h3>
                    <div className="space-y-3">
                        {proposal.conflicts.map((c, i) => (
                            <div key={i} className="bg-black/40 rounded-lg p-4 text-sm border border-orange-500/10">
                                <div className="flex justify-between mb-2">
                                    <span className="text-slate-300 font-medium">"{c.seed_text}"</span>
                                    <span className="text-orange-400 text-xs px-2 py-0.5 bg-orange-950 rounded">VS Existing</span>
                                </div>
                                <div className="text-slate-500 mb-2 italic">Conflict: {c.reason}</div>
                                <div className="text-xs text-slate-600">Consider creating a new variant if contexts differ.</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Merges Section */}
            <div>
                <h3 className="flex items-center gap-2 text-lg font-semibold text-slate-200 mb-4">
                    <Layers className="w-5 h-5 text-purple-400" />
                    Entity Resolution (Merges)
                </h3>
                {proposal.proposed_merges.length === 0 ? (
                    <div className="text-slate-500 italic p-4 text-center glass-card rounded-xl">No duplicate concepts found.</div>
                ) : (
                    <div className="space-y-3">
                        {proposal.proposed_merges.map((merge, i) => (
                            <div
                                key={i}
                                onClick={() => toggleMerge(i)}
                                className={`
                                    cursor-pointer p-4 rounded-xl border transition-all flex items-center justify-between group
                                    ${approvedMerges.has(i)
                                        ? "bg-purple-900/10 border-purple-500/50 hover:bg-purple-900/20"
                                        : "bg-black/40 border-white/10 opacity-60 hover:opacity-100"
                                    }
                                `}
                            >
                                <div className="flex items-center gap-4 flex-1">
                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center border ${approvedMerges.has(i) ? "bg-purple-500 border-purple-500" : "border-slate-600"}`}>
                                        {approvedMerges.has(i) && <Check className="w-4 h-4 text-black" />}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2 text-sm">
                                            <span className="text-slate-300">New Seed</span>
                                            <ArrowRight className="w-4 h-4 text-slate-600" />
                                            <span className="text-purple-300 font-semibold">{merge.target_label}</span>
                                        </div>
                                        <div className="text-xs text-slate-500 mt-1">
                                            Confidence: {(merge.confidence * 100).toFixed(1)}% • {merge.status === 'auto_merge' ? 'Auto-detected' : 'Ambiguous'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* New Concepts List (Review Section) */}
            {proposal.new_nodes.length > 0 && (
                <div>
                    <h3 className="flex items-center gap-2 text-lg font-semibold text-slate-200 mb-4">
                        <Save className="w-5 h-5 text-blue-400" />
                        New Knowledge to Crystalize
                    </h3>
                    <div className="bg-black/30 border border-white/10 rounded-xl p-4">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-60 overflow-y-auto custom-scrollbar">
                            {proposal.new_nodes.map((node: any, i) => {
                                const rawText = node.text || node.label || node.highlight || "Untitled Node";
                                const parts = rawText.includes(':') ? rawText.split(':') : [rawText, ''];
                                const title = parts[0].trim();
                                const desc = parts[1].trim() || parts[0].trim();

                                return (
                                    <div key={i} className="flex items-start gap-2 p-2 rounded hover:bg-white/5 transition-colors">
                                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-2 shrink-0" />
                                        <div>
                                            <div className="text-sm text-slate-200 font-medium">{title}</div>
                                            <div className="text-xs text-slate-500 line-clamp-1">{desc}</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        <div className="mt-2 text-xs text-center text-slate-600 border-t border-white/5 pt-2">
                            These {proposal.new_nodes.length} concepts will be permanently added to your Cognitive Graph.
                        </div>
                    </div>
                </div>
            )}

            {/* Action Bar */}
            <div className="flex items-center justify-end gap-4 pt-4 border-t border-white/10">
                <div className="text-right">
                    <div className="text-sm text-slate-400">
                        Ready to write <span className="text-white font-bold">{proposal.new_nodes.length} new concepts</span>
                    </div>
                    <div className="text-xs text-slate-600">
                        Session will be archived & un-editable.
                    </div>
                </div>
                <button
                    onClick={handleCommit}
                    disabled={committing}
                    className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-500 border border-blue-400 shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                    {committing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                    {committing ? "Crystallizing..." : "Commit Reasoning"}
                </button>
            </div>
        </div>
    );
}
