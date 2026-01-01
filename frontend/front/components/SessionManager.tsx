"use client";

import { useState, useEffect } from "react";
import { FolderOpen, Plus, Trash2, Check, Clock, AlertTriangle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Session {
    _key: string;
    title: string;
    goal: string;
    status: "active" | "crystallized";
    created_at: string;
    concept_count?: number;
}

interface SessionManagerProps {
    currentSessionId: string;
    onSessionChange: (id: string) => void;
    onCreateSession: () => void;
}

export default function SessionManager({ currentSessionId, onSessionChange, onCreateSession }: SessionManagerProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    // Fetch sessions when modal opens
    useEffect(() => {
        if (isOpen) fetchSessions();
    }, [isOpen]);

    const fetchSessions = async () => {
        setLoading(true);
        try {
            const res = await fetch("http://127.0.0.1:8000/api/v1/session/");
            if (!res.ok) throw new Error("Failed to load sessions");
            const data = await res.json();
            setSessions(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (!confirm("PERMANENTLY DELETE this session? This cannot be undone.")) return;

        setDeletingId(id);
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/session/${id}`, { method: "DELETE" });
            if (res.ok) {
                setSessions(prev => prev.filter(s => s._key !== id));
                if (currentSessionId === id && sessions.length > 0) {
                    onSessionChange(sessions[0]._key); // Fallback to another session
                }
            }
        } catch (err) {
            alert("Failed to delete session");
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <div className="relative">
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-medium text-slate-300 border border-white/10 flex items-center gap-2 transition-colors"
            >
                <FolderOpen className="w-4 h-4 text-blue-400" />
                Sessions
            </button>

            {/* Dropdown / Modal */}
            <AnimatePresence>
                {isOpen && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
                            onClick={() => setIsOpen(false)}
                        />

                        {/* Content */}
                        <motion.div
                            initial={{ opacity: 0, y: 10, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="absolute top-full left-0 mt-2 w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden flex flex-col max-h-[80vh]"
                        >
                            <div className="p-3 border-b border-white/5 flex justify-between items-center bg-black/20">
                                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Your Brains</span>
                                <button
                                    onClick={() => { setIsOpen(false); onCreateSession(); }}
                                    className="p-1.5 bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 rounded transition-colors"
                                    title="New Session"
                                >
                                    <Plus className="w-4 h-4" />
                                </button>
                            </div>

                            <div className="overflow-y-auto custom-scrollbar flex-1 p-2 space-y-1">
                                {loading && sessions.length === 0 ? (
                                    <div className="p-4 text-center text-slate-500 text-xs">Loading...</div>
                                ) : sessions.length === 0 ? (
                                    <div className="p-4 text-center text-slate-500 text-xs italic">No sessions found. Start thinking!</div>
                                ) : (
                                    sessions.map((session) => (
                                        <div
                                            key={session._key}
                                            onClick={() => {
                                                onSessionChange(session._key);
                                                setIsOpen(false);
                                            }}
                                            className={`
                                                group flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all border border-transparent
                                                ${currentSessionId === session._key
                                                    ? "bg-blue-600/10 border-blue-500/30"
                                                    : "hover:bg-white/5 hover:border-white/5"
                                                }
                                            `}
                                        >
                                            <div className="shrink-0">
                                                {session.status === 'crystallized' ? (
                                                    <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                                                        <Check className="w-4 h-4 text-purple-400" />
                                                    </div>
                                                ) : (
                                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${currentSessionId === session._key ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
                                                        <Clock className="w-4 h-4" />
                                                    </div>
                                                )}
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <div className={`text-sm font-medium truncate ${currentSessionId === session._key ? "text-blue-200" : "text-slate-300"}`}>
                                                    {session.title || "Untitled Session"}
                                                </div>
                                                <div className="flex items-center gap-2 text-[10px] text-slate-500">
                                                    <span>{new Date(session.created_at).toLocaleDateString()}</span>
                                                    {session.concept_count !== undefined && (
                                                        <span>• {session.concept_count} concepts</span>
                                                    )}
                                                </div>
                                            </div>

                                            <button
                                                onClick={(e) => handleDelete(e, session._key)}
                                                className="opacity-0 group-hover:opacity-100 p-2 text-slate-600 hover:text-red-400 hover:bg-red-500/10 rounded transition-all"
                                                title="Delete Session"
                                            >
                                                {deletingId === session._key ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                                            </button>
                                        </div>
                                    ))
                                )}
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
}
