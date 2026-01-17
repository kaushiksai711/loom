"use client";

import React, { useState, useEffect } from 'react';
import { Clock, Brain, ChevronRight, ChevronDown, BookOpen, Zap, Timer, CheckCircle2, Calendar, ArrowRight } from 'lucide-react';
import Link from 'next/link';

interface ReviewConcept {
    _id: string;
    _key: string;
    label: string;
    definition: string;
    mastery: number;
    next_review: string;
    last_reviewed: string;
    review_count: number;
    origin_session: string;
    session_title: string;
}

interface UpcomingConcept {
    _id: string;
    label: string;
    mastery: number;
    next_review: string;
    session_title: string;
}

interface Scaffold {
    hands_on?: { language: string; content: string };
    visual?: { content: string };
    socratic?: { questions: string[] };
    textual?: { content: string; analogy?: string };
}

const SESSION_DURATIONS = [
    { label: "5 min", minutes: 5, icon: "⚡" },
    { label: "10 min", minutes: 10, icon: "🎯" },
    { label: "20 min", minutes: 20, icon: "📚" },
    { label: "All Due", minutes: null, icon: "🔥" },
];

export default function ReviewPage() {
    const [queue, setQueue] = useState<ReviewConcept[]>([]);
    const [filteredQueue, setFilteredQueue] = useState<ReviewConcept[]>([]);
    const [upcoming, setUpcoming] = useState<UpcomingConcept[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [totalDue, setTotalDue] = useState(0);

    // Session state
    const [sessionStarted, setSessionStarted] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
    const [reviewedCount, setReviewedCount] = useState(0);

    // Filter state
    const [selectedSession, setSelectedSession] = useState<string | null>(null);

    // Card state
    const [revealed, setRevealed] = useState(false);
    const [assessed, setAssessed] = useState(false);
    const [showScaffold, setShowScaffold] = useState(false);
    const [scaffold, setScaffold] = useState<Scaffold | null>(null);
    const [loadingScaffold, setLoadingScaffold] = useState(false);

    // Fetch data on mount
    useEffect(() => {
        fetchQueue();
        fetchUpcoming();
    }, []);

    // Apply session filter
    useEffect(() => {
        if (selectedSession) {
            setFilteredQueue(queue.filter(c => c.session_title === selectedSession));
        } else {
            setFilteredQueue(queue);
        }
    }, [selectedSession, queue]);

    // Timer logic
    useEffect(() => {
        if (!sessionStarted || timeRemaining === null) return;
        if (timeRemaining <= 0) {
            endSession();
            return;
        }

        const timer = setInterval(() => {
            setTimeRemaining(prev => prev !== null ? prev - 1 : null);
        }, 1000);

        return () => clearInterval(timer);
    }, [sessionStarted, timeRemaining]);

    // Check if session should end (no more concepts)
    useEffect(() => {
        if (sessionStarted && currentIndex >= filteredQueue.length && filteredQueue.length > 0) {
            endSession();
        }
    }, [currentIndex, filteredQueue.length, sessionStarted]);

    const fetchQueue = async () => {
        try {
            const res = await fetch('/api/v1/review/queue?limit=100');
            if (!res.ok) throw new Error('Failed to fetch queue');
            const data = await res.json();
            const concepts = data.concepts || [];
            setQueue(concepts);
            setFilteredQueue(concepts);
            setTotalDue(data.total_due || 0);
        } catch (e) {
            console.error('Failed to fetch review queue:', e);
        } finally {
            setLoading(false);
        }
    };

    const fetchUpcoming = async () => {
        try {
            const res = await fetch('/api/v1/review/upcoming?limit=10');
            if (!res.ok) return;
            const data = await res.json();
            setUpcoming(data.upcoming || []);
        } catch (e) {
            console.warn('Failed to fetch upcoming:', e);
        }
    };

    const startSession = (duration: number | null) => {
        setTimeRemaining(duration ? duration * 60 : null);
        setSessionStarted(true);
        setCurrentIndex(0);
        setReviewedCount(0);
        resetCardState();
    };

    const endSession = () => {
        setSessionStarted(false);
        setSelectedSession(null);
        // Refresh data
        fetchQueue();
        fetchUpcoming();
    };

    const resetCardState = () => {
        setRevealed(false);
        setAssessed(false);
        setShowScaffold(false);
        setScaffold(null);
    };

    const revealDefinition = () => {
        setRevealed(true);
    };

    const fetchScaffold = async () => {
        const concept = filteredQueue[currentIndex];
        if (!concept || scaffold) return;

        setLoadingScaffold(true);
        try {
            const res = await fetch(`/api/v1/session/concept/${concept._id}/scaffold`);
            if (res.ok) {
                const data = await res.json();
                setScaffold(data);
            }
        } catch (e) {
            console.warn('Failed to fetch scaffold:', e);
        } finally {
            setLoadingScaffold(false);
        }
    };

    const toggleScaffold = () => {
        if (!showScaffold && !scaffold) {
            fetchScaffold();
        }
        setShowScaffold(!showScaffold);
    };

    const assessConcept = async (difficulty: 'hard' | 'good' | 'easy' | 'mastered') => {
        const concept = filteredQueue[currentIndex];
        if (!concept) return;

        try {
            await fetch(`/api/v1/review/assess/${concept._id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    difficulty: difficulty === 'mastered' ? 'easy' : difficulty,
                    mastered: difficulty === 'mastered'
                })
            });

            setAssessed(true);
            setReviewedCount(prev => prev + 1);

            // Move to next after brief delay
            setTimeout(() => {
                if (currentIndex < filteredQueue.length - 1) {
                    setCurrentIndex(prev => prev + 1);
                    resetCardState();
                } else {
                    // Session complete
                    endSession();
                }
            }, 600);

        } catch (e) {
            console.error('Failed to assess concept:', e);
        }
    };

    const formatTime = (seconds: number): string => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    const formatDate = (dateStr: string): string => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Tomorrow';
        if (diffDays < 7) return `In ${diffDays} days`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const currentConcept = filteredQueue[currentIndex];

    // Group concepts by session for display
    const conceptsBySession = queue.reduce((acc, c) => {
        const session = c.session_title || 'Unknown Session';
        if (!acc[session]) acc[session] = [];
        acc[session].push(c);
        return acc;
    }, {} as Record<string, ReviewConcept[]>);

    // Main review page (not in session)
    if (!sessionStarted) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
                <div className="max-w-5xl mx-auto">
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-900/40 rounded-full text-indigo-300 text-sm mb-4">
                            <Brain className="w-4 h-4" />
                            Spaced Repetition
                        </div>
                        <h1 className="text-4xl font-bold text-white mb-2">Daily Review</h1>
                        <p className="text-slate-400">Reinforce your knowledge with spaced repetition</p>
                    </div>

                    {loading ? (
                        <div className="text-center text-slate-400 py-12">Loading review queue...</div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                            {/* Left Column: Quick Start & Stats */}
                            <div className="lg:col-span-1 space-y-6">
                                {/* Due Now Section */}
                                {queue.length > 0 ? (
                                    <>
                                        <div>
                                            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                                <Timer className="w-5 h-5 text-amber-400" />
                                                {totalDue} Due Now
                                            </h2>
                                            <div className="space-y-3">
                                                {SESSION_DURATIONS.map((option) => (
                                                    <button
                                                        key={option.label}
                                                        onClick={() => startSession(option.minutes)}
                                                        className="w-full p-4 bg-slate-800 border border-slate-700 rounded-xl hover:border-indigo-500/50 transition-all flex items-center justify-between group"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-xl">{option.icon}</span>
                                                            <div className="text-left">
                                                                <div className="text-white font-medium">{option.label}</div>
                                                                <div className="text-slate-500 text-xs">
                                                                    {option.minutes ? `~${Math.ceil(option.minutes / 1.5)} concepts` : `${totalDue} concepts`}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400" />
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Stats */}
                                        <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700/50">
                                            <div className="grid grid-cols-2 gap-4 text-center">
                                                <div>
                                                    <div className="text-2xl font-bold text-amber-400">{totalDue}</div>
                                                    <div className="text-slate-500 text-xs">Due Now</div>
                                                </div>
                                                <div>
                                                    <div className="text-2xl font-bold text-indigo-400">
                                                        {queue.length > 0 ? Math.round(queue.reduce((sum, c) => sum + c.mastery * 100, 0) / queue.length) : 0}%
                                                    </div>
                                                    <div className="text-slate-500 text-xs">Avg Mastery</div>
                                                </div>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="text-center py-8 bg-slate-800/30 rounded-xl border border-slate-700/30">
                                        <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                                            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                                        </div>
                                        <h3 className="text-white font-medium mb-1">All Caught Up!</h3>
                                        <p className="text-slate-400 text-sm">No concepts due for review</p>
                                    </div>
                                )}
                            </div>

                            {/* Middle Column: Review by Session */}
                            <div className="lg:col-span-1">
                                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                    <BookOpen className="w-5 h-5 text-indigo-400" />
                                    Review by Session
                                </h2>
                                {Object.keys(conceptsBySession).length > 0 ? (
                                    <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                                        {Object.entries(conceptsBySession).map(([session, concepts]) => (
                                            <button
                                                key={session}
                                                onClick={() => { setSelectedSession(session); startSession(null); }}
                                                className="w-full p-4 bg-slate-800/50 border border-slate-700/50 rounded-xl hover:border-indigo-500/50 transition-all text-left"
                                            >
                                                <div className="flex justify-between items-start mb-2">
                                                    <span className="text-white font-medium text-sm">{session}</span>
                                                    <span className="text-indigo-300 text-sm">{concepts.length}</span>
                                                </div>
                                                <div className="flex flex-wrap gap-1">
                                                    {concepts.slice(0, 3).map(c => (
                                                        <span key={c._id} className="px-2 py-0.5 bg-slate-700/50 text-slate-400 text-xs rounded">
                                                            {c.label.slice(0, 15)}...
                                                        </span>
                                                    ))}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-slate-500 text-sm">No sessions with due concepts</p>
                                )}
                            </div>

                            {/* Right Column: Upcoming Schedule */}
                            <div className="lg:col-span-1">
                                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                    <Calendar className="w-5 h-5 text-purple-400" />
                                    Upcoming Reviews
                                </h2>
                                {upcoming.length > 0 ? (
                                    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
                                        {upcoming.map(c => (
                                            <div key={c._id} className="p-3 bg-slate-800/30 border border-slate-700/30 rounded-lg">
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <div className="text-white text-sm font-medium">{c.label}</div>
                                                        <div className="text-slate-500 text-xs">{Math.round(c.mastery * 100)}% mastery</div>
                                                    </div>
                                                    <div className="text-right">
                                                        <div className="text-purple-300 text-xs font-medium">{formatDate(c.next_review)}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-slate-500 text-sm">No upcoming reviews scheduled</p>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Review card screen (in session)
    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
            <div className="max-w-3xl mx-auto">
                {/* Progress Header */}
                <div className="flex justify-between items-center mb-6">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={endSession}
                            className="text-slate-400 hover:text-white text-sm"
                        >
                            ← Exit
                        </button>
                        <div className="w-32 bg-slate-700 rounded-full h-2">
                            <div
                                className="bg-gradient-to-r from-indigo-500 to-purple-500 h-2 rounded-full transition-all"
                                style={{ width: `${(currentIndex / filteredQueue.length) * 100}%` }}
                            />
                        </div>
                        <span className="text-slate-300 font-mono text-sm">{currentIndex + 1}/{filteredQueue.length}</span>
                    </div>
                    {timeRemaining !== null && (
                        <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${timeRemaining < 60 ? 'bg-red-900/40 text-red-300' : 'bg-slate-800 text-slate-300'
                            }`}>
                            <Clock className="w-4 h-4" />
                            <span className="font-mono">{formatTime(timeRemaining)}</span>
                        </div>
                    )}
                </div>

                {/* Review Card */}
                {currentConcept && (
                    <div className="bg-gradient-to-br from-slate-800 to-slate-850 rounded-2xl shadow-2xl border border-slate-700/50 overflow-hidden">
                        {/* Card Header */}
                        <div className="p-6 border-b border-slate-700/50">
                            <div className="flex items-start justify-between">
                                <div>
                                    <h2 className="text-2xl font-bold text-white mb-1">{currentConcept.label}</h2>
                                    <div className="flex items-center gap-2 text-sm">
                                        <span className="px-2 py-0.5 bg-indigo-900/40 text-indigo-300 rounded text-xs">
                                            {currentConcept.session_title}
                                        </span>
                                        <span className="text-slate-500">Review #{currentConcept.review_count + 1}</span>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-lg font-bold text-indigo-300">{Math.round(currentConcept.mastery * 100)}%</div>
                                    <div className="text-slate-500 text-xs">mastery</div>
                                </div>
                            </div>
                        </div>

                        {/* Definition */}
                        <div className="p-6">
                            <div className={`bg-slate-900/50 rounded-lg p-5 border border-slate-700/30 ${!revealed ? 'blur-sm select-none' : ''}`}>
                                <p className="text-slate-300 leading-relaxed">{currentConcept.definition}</p>
                            </div>

                            {!revealed && (
                                <button
                                    onClick={revealDefinition}
                                    className="mt-4 w-full py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors flex items-center justify-center gap-2 font-medium"
                                >
                                    <Zap className="w-4 h-4" />
                                    Reveal Definition
                                </button>
                            )}
                        </div>

                        {/* Inline Scaffold (Expandable) */}
                        {revealed && (
                            <div className="border-t border-slate-700/50">
                                <button
                                    onClick={toggleScaffold}
                                    className="w-full p-4 flex items-center justify-between hover:bg-slate-700/20 transition-colors"
                                >
                                    <div className="flex items-center gap-2 text-indigo-400">
                                        <BookOpen className="w-4 h-4" />
                                        <span className="font-medium">View Full Scaffold</span>
                                    </div>
                                    <ChevronDown className={`w-5 h-5 text-slate-400 transition-transform ${showScaffold ? 'rotate-180' : ''}`} />
                                </button>

                                {showScaffold && (
                                    <div className="p-6 pt-0 space-y-4">
                                        {loadingScaffold ? (
                                            <div className="text-center text-slate-400 py-8">Loading scaffold...</div>
                                        ) : scaffold ? (
                                            <>
                                                {scaffold.textual && (
                                                    <div className="bg-slate-900/30 rounded-lg p-4 border border-slate-700/30">
                                                        <h4 className="text-xs font-semibold text-teal-400 uppercase mb-2">📖 Explanation</h4>
                                                        <p className="text-slate-300 text-sm">{scaffold.textual.content}</p>
                                                        {scaffold.textual.analogy && (
                                                            <p className="text-slate-400 text-sm mt-2 italic">💡 {scaffold.textual.analogy}</p>
                                                        )}
                                                    </div>
                                                )}
                                                {scaffold.socratic?.questions && (
                                                    <div className="bg-slate-900/30 rounded-lg p-4 border border-slate-700/30">
                                                        <h4 className="text-xs font-semibold text-amber-400 uppercase mb-2">🤔 Think About</h4>
                                                        <ul className="space-y-2">
                                                            {scaffold.socratic.questions.map((q, i) => (
                                                                <li key={i} className="text-slate-300 text-sm flex gap-2">
                                                                    <span className="text-amber-400">{i + 1}.</span> {q}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                                {scaffold.hands_on && (
                                                    <div className="bg-slate-900/30 rounded-lg p-4 border border-slate-700/30">
                                                        <h4 className="text-xs font-semibold text-blue-400 uppercase mb-2">💻 Code Example</h4>
                                                        <pre className="text-slate-300 text-xs overflow-x-auto bg-black/30 p-3 rounded">
                                                            {scaffold.hands_on.content}
                                                        </pre>
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            <div className="text-center text-slate-500 py-4">No scaffold available</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Assessment Buttons */}
                        {revealed && !assessed && (
                            <div className="p-6 border-t border-slate-700/50 bg-slate-900/30">
                                <p className="text-slate-400 text-sm mb-4 text-center">How well did you recall this?</p>
                                <div className="grid grid-cols-4 gap-2">
                                    <button
                                        onClick={() => assessConcept('hard')}
                                        className="py-3 bg-rose-900/30 text-rose-300 rounded-lg hover:bg-rose-900/50 transition-colors font-medium text-sm"
                                    >
                                        ❌ Hard
                                        <div className="text-xs opacity-70">2 days</div>
                                    </button>
                                    <button
                                        onClick={() => assessConcept('good')}
                                        className="py-3 bg-amber-900/30 text-amber-300 rounded-lg hover:bg-amber-900/50 transition-colors font-medium text-sm"
                                    >
                                        ⚡ Good
                                        <div className="text-xs opacity-70">7 days</div>
                                    </button>
                                    <button
                                        onClick={() => assessConcept('easy')}
                                        className="py-3 bg-emerald-900/30 text-emerald-300 rounded-lg hover:bg-emerald-900/50 transition-colors font-medium text-sm"
                                    >
                                        ✅ Easy
                                        <div className="text-xs opacity-70">14 days</div>
                                    </button>
                                    <button
                                        onClick={() => assessConcept('mastered')}
                                        className="py-3 bg-purple-900/30 text-purple-300 rounded-lg hover:bg-purple-900/50 transition-colors font-medium text-sm"
                                    >
                                        ⭐ Mastered
                                        <div className="text-xs opacity-70">30 days</div>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Assessed Confirmation */}
                        {assessed && (
                            <div className="p-6 text-center bg-emerald-900/20 border-t border-emerald-700/30">
                                <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
                                <span className="text-emerald-300">Next review scheduled!</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
