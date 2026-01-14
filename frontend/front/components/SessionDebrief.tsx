"use client";

import React, { useState, useEffect } from 'react';
import { Trophy, BarChart3, Brain, Lightbulb, X, Loader2, Save, Sparkles } from 'lucide-react';

interface SessionDebriefProps {
    sessionId: string;
    onClose: () => void;
}

interface DebriefData {
    session_id: string;
    concepts_explored: number;
    total_interactions: number;
    total_time_ms: number;
    format_distribution: {
        hands_on: number;
        visual: number;
        socratic: number;
        textual: number;
    };
    preferred_format: string;
    reflection_prompt: string;
    technique_suggestion: string;
}

const FORMAT_CONFIG = {
    hands_on: { label: 'Code', color: '#10B981', icon: '💻' },
    visual: { label: 'Visual', color: '#8B5CF6', icon: '🎨' },
    socratic: { label: 'Think', color: '#F59E0B', icon: '🧠' },
    textual: { label: 'Read', color: '#3B82F6', icon: '📖' },
};

export default function SessionDebrief({ sessionId, onClose }: SessionDebriefProps) {
    const [debrief, setDebrief] = useState<DebriefData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reflection, setReflection] = useState('');
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        fetchDebrief();
    }, [sessionId]);

    const fetchDebrief = async () => {
        try {
            const res = await fetch(`/api/v1/session/${sessionId}/debrief`);
            if (!res.ok) throw new Error('Failed to load debrief');
            const data = await res.json();
            setDebrief(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        // In a real implementation, save the reflection to the backend
        // For now, just simulate a save
        await new Promise(r => setTimeout(r, 800));
        setSaved(true);
        setSaving(false);
        setTimeout(() => onClose(), 1500);
    };

    const getMaxCount = () => {
        if (!debrief) return 1;
        return Math.max(1, ...Object.values(debrief.format_distribution));
    };

    const formatTime = (ms: number) => {
        const minutes = Math.floor(ms / 60000);
        if (minutes < 1) return 'Less than a minute';
        return `${minutes} minute${minutes > 1 ? 's' : ''}`;
    };

    if (loading) {
        return (
            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                <div className="text-center">
                    <Loader2 className="w-10 h-10 animate-spin text-purple-400 mx-auto mb-4" />
                    <p className="text-slate-400">Preparing your learning summary...</p>
                </div>
            </div>
        );
    }

    if (error || !debrief) {
        return (
            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                <div className="bg-slate-900 p-6 rounded-xl border border-red-500/30 text-center">
                    <p className="text-red-400 mb-4">{error || 'No debrief data available'}</p>
                    <button onClick={onClose} className="px-4 py-2 bg-slate-700 rounded-lg text-white">
                        Close
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-gradient-to-b from-slate-900 to-slate-950 rounded-2xl border border-purple-500/30 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="relative p-6 text-center border-b border-slate-800">
                    <div className="absolute top-4 right-4">
                        <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors">
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 mb-4 shadow-lg shadow-purple-500/30">
                        <Trophy className="w-8 h-8 text-white" />
                    </div>

                    <h2 className="text-2xl font-bold text-white mb-1">Session Complete!</h2>
                    <p className="text-slate-400 text-sm">Here's your learning summary</p>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-4 p-6">
                    <div className="text-center p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                        <div className="text-3xl font-bold text-purple-400">{debrief.concepts_explored}</div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">Concepts</div>
                    </div>
                    <div className="text-center p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                        <div className="text-3xl font-bold text-blue-400">{debrief.total_interactions}</div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">Interactions</div>
                    </div>
                    <div className="text-center p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                        <div className="text-lg font-bold text-teal-400">{formatTime(debrief.total_time_ms)}</div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">Time Spent</div>
                    </div>
                </div>

                {/* Format Distribution Chart */}
                <div className="px-6 pb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <BarChart3 className="w-5 h-5 text-purple-400" />
                        <h3 className="text-lg font-semibold text-white">Learning Style Distribution</h3>
                    </div>

                    <div className="space-y-3">
                        {(Object.entries(debrief.format_distribution) as [keyof typeof FORMAT_CONFIG, number][]).map(([format, count]) => {
                            const config = FORMAT_CONFIG[format];
                            const percentage = debrief.total_interactions > 0
                                ? Math.round((count / debrief.total_interactions) * 100)
                                : 0;
                            const barWidth = (count / getMaxCount()) * 100;

                            return (
                                <div key={format} className="flex items-center gap-3">
                                    <span className="w-6 text-center">{config.icon}</span>
                                    <span className="w-16 text-sm text-slate-400">{config.label}</span>
                                    <div className="flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden relative">
                                        <div
                                            className="h-full rounded-lg transition-all duration-1000 ease-out flex items-center justify-end pr-3"
                                            style={{
                                                width: `${barWidth}%`,
                                                backgroundColor: config.color,
                                                minWidth: count > 0 ? '40px' : '0'
                                            }}
                                        >
                                            {count > 0 && (
                                                <span className="text-xs font-bold text-white">{count}</span>
                                            )}
                                        </div>
                                    </div>
                                    <span className="w-12 text-right text-sm text-slate-500">{percentage}%</span>
                                </div>
                            );
                        })}
                    </div>

                    {debrief.total_interactions > 0 && (
                        <div className="mt-4 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                            <p className="text-purple-300 text-sm flex items-center gap-2">
                                <Sparkles className="w-4 h-4" />
                                Your preferred style: <strong>{FORMAT_CONFIG[debrief.preferred_format as keyof typeof FORMAT_CONFIG]?.label || 'Unknown'}</strong>
                            </p>
                        </div>
                    )}
                </div>

                {/* Reflection Section */}
                <div className="px-6 pb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Brain className="w-5 h-5 text-amber-400" />
                        <h3 className="text-lg font-semibold text-white">Reflection</h3>
                    </div>

                    <p className="text-slate-300 mb-3">{debrief.reflection_prompt}</p>

                    <textarea
                        value={reflection}
                        onChange={(e) => setReflection(e.target.value)}
                        placeholder="Take a moment to reflect on what clicked for you..."
                        className="w-full h-24 px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 resize-none focus:outline-none focus:border-purple-500 transition-colors"
                    />
                </div>

                {/* Tip Section */}
                <div className="px-6 pb-6">
                    <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                        <div className="flex items-start gap-3">
                            <Lightbulb className="w-5 h-5 text-blue-400 mt-0.5" />
                            <div>
                                <h4 className="text-blue-400 font-medium text-sm mb-1">💡 Tip for Next Time</h4>
                                <p className="text-slate-300 text-sm">{debrief.technique_suggestion}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-slate-800 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
                    >
                        Skip
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving || saved}
                        className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-all ${saved
                                ? 'bg-green-500 text-white'
                                : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white shadow-lg shadow-purple-500/20'
                            }`}
                    >
                        {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : saved ? (
                            <>✓ Saved!</>
                        ) : (
                            <>
                                <Save className="w-4 h-4" />
                                Save & Close
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
