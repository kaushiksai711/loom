"use client";

import { useState, useEffect } from "react";
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function IngestPage() {
    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0]) return;

        const file = e.target.files[0];
        setUploading(true);
        setStatus(null);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/v1/ingest/upload", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) throw new Error("Upload failed");

            const data = await res.json();
            setStatus({
                type: "success",
                message: `Successfully processed ${file.name}. Generated ${data.chunks_count} knowledge chunks.`,
            });
        } catch (error) {
            setStatus({
                type: "error",
                message: "Failed to upload document. Please ensure the backend is running.",
            });
        } finally {
            setUploading(false);
        }
    };

    const [history, setHistory] = useState<any[]>([]);

    useEffect(() => {
        fetch("/api/v1/ingest/history")
            .then(res => res.json())
            .then(data => setHistory(data))
            .catch(err => console.error("Failed to load history", err));
    }, [status]); // Reload when status changes

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <div>
                <h1 className="text-3xl font-bold text-white mb-2">Evidence Locker</h1>
                <p className="text-slate-400">Upload documents to expand your Second Brain's context window.</p>
            </div>

            <div className="glass-card p-12 rounded-xl border-dashed border-2 border-white/10 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors relative">
                <input
                    type="file"
                    onChange={handleFileUpload}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={uploading}
                />

                {uploading ? (
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-12 h-12 text-primary animate-spin" />
                        <p className="text-white font-medium">Chunking & Vectorizing...</p>
                    </div>
                ) : (
                    <>
                        <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6">
                            <Upload className="w-8 h-8 text-primary" />
                        </div>
                        <h3 className="text-xl font-semibold text-white mb-2">Drop Evidence Here</h3>
                        <p className="text-slate-400 max-w-sm">
                            Support for PDF, Markdown, and Text files. Documents are automatically chunked and linked to relevant concepts.
                        </p>
                    </>
                )}
            </div>

            <AnimatePresence>
                {status && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={`p-4 rounded-lg flex items-center gap-3 ${status.type === "success" ? "bg-green-500/10 border border-green-500/20 text-green-400" : "bg-red-500/10 border border-red-500/20 text-red-400"
                            }`}
                    >
                        {status.type === "success" ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        <span>{status.message}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="mt-12">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-slate-400" />
                    Recent Ingestions
                </h3>
                <div className="glass-card rounded-lg overflow-hidden">
                    {history.length === 0 ? (
                        <div className="p-8 text-center text-slate-500">
                            No ingestion history found. All systems ready.
                        </div>
                    ) : (
                        <div className="divide-y divide-white/5">
                            {history.map((item: any, i) => (
                                <div key={i} className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded bg-blue-500/10 text-blue-400">
                                            <FileText className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <p className="text-white font-medium">{item.filename}</p>
                                            <p className="text-xs text-slate-500">Last processed: {new Date(item.latest_chunk).toLocaleTimeString()}</p>
                                        </div>
                                    </div>
                                    <span className="text-xs px-2 py-1 rounded bg-white/5 text-slate-300 border border-white/10">
                                        {item.count} chunks
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
