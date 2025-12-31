import React, { useState, useEffect } from "react";
import AvatarSlime, { AvatarState } from "./AvatarSlime";

interface Metric {
    label: string;
    value: string | number;
    trend?: "up" | "down" | "neutral";
    color?: string;
}

interface AlertCard {
    id: string;
    type: "conflict" | "insight" | "info";
    title: string;
    message: string;
    timestamp: Date;
}

interface RightSidebarProps {
    avatarState: AvatarState;
    metrics: {
        concepts: number;
        sources: number;
        confidence: number;
        gaps: number;
    };
    alerts: AlertCard[];
    onClearAlert: (id: string) => void;
}

const RightSidebar: React.FC<RightSidebarProps> = ({ avatarState, metrics, alerts, onClearAlert }) => {
    return (
        <div className="h-full flex flex-col bg-slate-950/50 backdrop-blur-sm rounded-xl border border-white/5 overflow-hidden">
            {/* 1. Avatar Zone (Top) */}
            <div className="relative h-48 shrink-0 flex items-center justify-center bg-gradient-to-b from-teal-900/10 to-slate-900/50">
                <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
                    <div className="w-32 h-32 rounded-full bg-teal-500/10 blur-3xl animate-pulse" />
                </div>

                <AvatarSlime state={avatarState} />

                {/* State Label */}
                <div className="absolute bottom-4 left-0 right-0 text-center">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-white/40 font-mono">
                        System State: <span className="text-teal-400 font-bold">{avatarState}</span>
                    </span>
                </div>
            </div>

            {/* 2. Live Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 p-2 border-y border-white/5 bg-black/20 shrink-0">
                <MetricItem label="Concepts" value={metrics.concepts} color="text-teal-400" />
                <MetricItem label="Sources" value={metrics.sources} color="text-blue-400" />
                <MetricItem label="Confidence" value={`${metrics.confidence}%`} color={metrics.confidence > 70 ? 'text-green-400' : 'text-yellow-400'} />
                <MetricItem label="Gaps" value={metrics.gaps} color={metrics.gaps > 0 ? 'text-orange-400' : 'text-slate-500'} />
            </div>

            {/* 3. Alert/Insight Stack (Scrollable) */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 sticky top-0 bg-slate-950/90 py-1 z-10 backdrop-blur">
                    Cognitive Feed
                </h3>

                {alerts.length === 0 && (
                    <div className="text-center py-8 text-slate-600 text-xs italic">
                        No active alerts. System stable.
                    </div>
                )}

                {alerts.map(alert => (
                    <div
                        key={alert.id}
                        className={`relative p-3 rounded-lg border text-xs shadow-lg animate-in slide-in-from-right-4 fade-in duration-300 ${alert.type === 'conflict' ? 'bg-red-900/10 border-red-500/20 text-red-100' :
                            alert.type === 'insight' ? 'bg-amber-900/10 border-amber-500/20 text-amber-100' :
                                'bg-slate-800/50 border-white/10 text-slate-300'
                            }`}
                    >
                        <div className="flex justify-between items-start mb-1">
                            <strong className={`uppercase text-[10px] tracking-wider ${alert.type === 'conflict' ? 'text-red-400' :
                                alert.type === 'insight' ? 'text-amber-400' : 'text-blue-400'
                                }`}>
                                {alert.type}
                            </strong>
                            <button
                                onClick={() => onClearAlert(alert.id)}
                                className="text-white/20 hover:text-white transition-colors"
                            >
                                ×
                            </button>
                        </div>
                        <p className="font-semibold mb-1">{alert.title}</p>
                        <p className="opacity-80 leading-relaxed">{alert.message}</p>
                        <p className="text-[10px] text-white/20 mt-2 text-right">
                            {alert.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                    </div>
                ))}
            </div>

            {/* Footer */}
            <div className="p-2 border-t border-white/5 text-[10px] text-center text-slate-600 font-mono">
                COGNITIVE LOOM v0.5 [PHASE 5]
            </div>
        </div>
    );
};

const MetricItem: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => (
    <div className="bg-white/5 rounded p-2 flex flex-col items-center justify-center border border-white/5 hover:bg-white/10 transition-colors">
        <span className={`text-xl font-bold ${color || 'text-white'}`}>{value}</span>
        <span className="text-[10px] text-slate-500 uppercase">{label}</span>
    </div>
);

export default RightSidebar;
