"use client";

import { useState } from "react";
import { Send, AlertTriangle, BookOpen, Loader2, Save } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Conflict {
    seed_text: string;
    reason: string;
}

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    conflicts?: string[];
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [savingWisdom, setSavingWisdom] = useState<string | null>(null);

    const sendMessage = async () => {
        if (!input.trim()) return;

        const userMsg: Message = { id: Date.now().toString(), role: "user", content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const res = await fetch("/api/v1/session/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userMsg.content, session_id: "default" })
            });
            const data = await res.json();

            const aiMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: data.response,
                conflicts: data.conflicts || []
            };
            setMessages(prev => [...prev, aiMsg]);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const saveWisdom = async (text: string, id: string) => {
        setSavingWisdom(id);
        try {
            await fetch("/api/v1/seeds", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, comment: "Saved from Chat", confidence: "High" })
            });
            // Show success toast (omitted for brevity)
        } finally {
            setSavingWisdom(null);
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500 mb-6">
                Neurosymbolic Chat
            </h1>

            <div className="flex-1 overflow-y-auto space-y-6 pr-4 mb-4 custom-scrollbar">
                {messages.map((msg) => (
                    <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div className={`max-w-[80%] rounded-2xl p-4 ${msg.role === "user"
                            ? "bg-primary/20 border border-primary/20 text-white rounded-tr-none"
                            : "glass-card border-white/5 text-slate-200 rounded-tl-none"
                            }`}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>

                            {/* User: Save Wisdom Button */}
                            {msg.role === "user" && (
                                <button
                                    onClick={() => saveWisdom(msg.content, msg.id)}
                                    disabled={savingWisdom === msg.id}
                                    className="mt-2 text-xs flex items-center gap-1 text-slate-400 hover:text-primary transition-colors"
                                >
                                    {savingWisdom === msg.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                                    Crystallize Wisdom
                                </button>
                            )}

                            {/* Assistant: Conflict Warnings */}
                            {msg.conflicts && msg.conflicts.length > 0 && (
                                <div className="mt-4 space-y-2">
                                    {msg.conflicts.map((warning, i) => (
                                        <div key={i} className="bg-orange-500/10 border border-orange-500/30 p-3 rounded-lg flex gap-3 text-sm text-orange-200">
                                            <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" />
                                            <div>{warning}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </motion.div>
                ))}
                {loading && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                        <div className="glass-card px-4 py-2 rounded-2xl flex items-center gap-2 text-slate-400">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Thinking...
                        </div>
                    </motion.div>
                )}
            </div>

            <div className="glass-card p-2 rounded-xl flex items-center gap-2 border border-white/10">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Ask about your knowledge..."
                    className="flex-1 bg-transparent border-none outline-none text-white placeholder-slate-500 p-2"
                />
                <button
                    onClick={sendMessage}
                    disabled={loading || !input.trim()}
                    className="p-2 bg-primary text-black rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                    <Send className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}
