"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Code2, Eye, Brain, BookOpen, X, Loader2, Copy, Check } from 'lucide-react';

// Types
interface ConceptCardProps {
    conceptId: string;
    label: string;
    sessionId: string;
    onClose: () => void;
}

interface Scaffold {
    hands_on: { language: string; content: string };
    visual: { content: string };
    socratic: { questions: string[] };
    textual: { content: string; analogy: string };
}

type TabType = 'hands_on' | 'visual' | 'socratic' | 'textual';

// Tab Configuration
const TABS: { id: TabType; icon: React.ReactNode; label: string; color: string }[] = [
    { id: 'hands_on', icon: <Code2 className="w-4 h-4" />, label: 'Code', color: '#10B981' },
    { id: 'visual', icon: <Eye className="w-4 h-4" />, label: 'Visual', color: '#8B5CF6' },
    { id: 'socratic', icon: <Brain className="w-4 h-4" />, label: 'Think', color: '#F59E0B' },
    { id: 'textual', icon: <BookOpen className="w-4 h-4" />, label: 'Read', color: '#3B82F6' },
];

export default function ConceptCard({ conceptId, label, sessionId, onClose }: ConceptCardProps) {
    const [activeTab, setActiveTab] = useState<TabType>('textual');
    const [scaffold, setScaffold] = useState<Scaffold | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Phase 13: Track actual dwell time
    const [tabStartTime, setTabStartTime] = useState<number>(Date.now());

    // Phase 13.5: Mastery and fading
    const [fadingLevel, setFadingLevel] = useState<'novice' | 'learning' | 'proficient' | 'mastered'>('novice');
    const [showFadedContent, setShowFadedContent] = useState(false);

    // Guard against double fetch (React StrictMode in dev)
    const hasFetched = useRef(false);

    // Fetch preference then scaffold on mount
    useEffect(() => {
        // Prevent double fetch in React StrictMode
        if (hasFetched.current) return;
        hasFetched.current = true;

        initConceptCard();
    }, [conceptId]);

    const initConceptCard = async () => {
        setLoading(true);
        setError(null);

        try {
            // Phase 13.5: Fetch mastery level first
            try {
                const masteryRes = await fetch(`/api/v1/session/concept/${conceptId}/mastery`);
                if (masteryRes.ok) {
                    const { fading_level } = await masteryRes.json();
                    setFadingLevel(fading_level);
                    console.log(`[ConceptCard] Mastery level: ${fading_level}`);
                }
            } catch (e) {
                console.warn('Could not fetch mastery, using novice:', e);
            }

            // Phase 13: Fetch user's preferred format
            try {
                const prefRes = await fetch(`/api/v1/session/${sessionId}/preference`);
                if (prefRes.ok) {
                    const { preferred_format, confidence } = await prefRes.json();
                    if (confidence !== 'low' && preferred_format) {
                        setActiveTab(preferred_format);
                        console.log(`[ConceptCard] Using preferred format: ${preferred_format}`);
                    }
                }
            } catch (e) {
                console.warn('Could not fetch preference, using default:', e);
            }

            // Then fetch scaffold
            const res = await fetch(`/api/v1/session/concept/${conceptId}/scaffold`);
            if (!res.ok) throw new Error('Failed to load scaffold');
            const data = await res.json();
            setScaffold(data);

            // Log initial view signal
            setTabStartTime(Date.now());
            logSignal(activeTab, 'scaffold_click', 0);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    // Helper to log signals with dwell time
    const logSignal = async (
        format: TabType,
        interactionType: 'scaffold_click' | 'tab_switch' | 'content_scroll' | 'card_close',
        dwellTime: number = 0
    ) => {
        try {
            await fetch(`/api/v1/session/${sessionId}/signal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    concept_id: conceptId,
                    format_chosen: format,
                    dwell_time_ms: dwellTime,
                    time_since_last_interaction_ms: 0,
                    interaction_type: interactionType
                })
            });
        } catch (e) {
            console.warn('Failed to log signal:', e);
        }
    };

    // Log signal when tab changes (with actual dwell time)
    const handleTabClick = (tab: TabType) => {
        const now = Date.now();
        const dwellTime = now - tabStartTime;

        // Log PREVIOUS tab's dwell time
        logSignal(activeTab, 'tab_switch', dwellTime);

        setActiveTab(tab);
        setTabStartTime(now);
    };

    // Handle close with final dwell logging
    const handleClose = () => {
        const finalDwell = Date.now() - tabStartTime;
        logSignal(activeTab, 'card_close', finalDwell);
        onClose();
    };

    const activeTabConfig = TABS.find(t => t.id === activeTab);


    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div
                className="bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden"
                style={{ boxShadow: `0 0 60px ${activeTabConfig?.color}20` }}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-700">
                    <div>
                        <h2 className="text-lg font-bold text-white">{label}</h2>
                        <p className="text-xs text-slate-400">Explore this concept in different ways</p>
                    </div>
                    <button
                        onClick={handleClose}
                        className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-slate-700">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => handleTabClick(tab.id)}
                            className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 text-sm font-medium transition-all relative ${activeTab === tab.id
                                ? 'text-white'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                                }`}
                            style={{
                                color: activeTab === tab.id ? tab.color : undefined
                            }}
                        >
                            {tab.icon}
                            <span>{tab.label}</span>
                            {activeTab === tab.id && (
                                <div
                                    className="absolute bottom-0 left-0 right-0 h-0.5"
                                    style={{ backgroundColor: tab.color }}
                                />
                            )}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                            <Loader2 className="w-8 h-8 animate-spin mb-3" />
                            <p>Generating learning content...</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center h-64 text-red-400">
                            <p className="mb-3">{error}</p>
                            <button
                                onClick={initConceptCard}
                                className="px-4 py-2 bg-red-500/20 rounded-lg hover:bg-red-500/30 transition-colors"
                            >
                                Retry
                            </button>
                        </div>
                    ) : scaffold ? (
                        <>
                            {/* Phase 13.5: Fading overlay for proficient/mastered */}
                            {(fadingLevel === 'proficient' || fadingLevel === 'mastered') && !showFadedContent && (
                                <div className="mb-4 p-4 rounded-lg bg-gradient-to-r from-emerald-500/20 to-teal-500/20 border border-emerald-500/30">
                                    <p className="text-emerald-400 font-medium">
                                        {fadingLevel === 'mastered'
                                            ? '🏆 You\'ve mastered this concept!'
                                            : '📈 You\'re getting proficient!'}
                                    </p>
                                    <p className="text-slate-400 text-sm mt-1">
                                        Try recalling what you know before viewing the content.
                                    </p>
                                    <button
                                        onClick={() => setShowFadedContent(true)}
                                        className="mt-3 px-4 py-2 bg-slate-800 text-slate-200 rounded-lg hover:bg-slate-700 transition-colors text-sm"
                                    >
                                        Show content anyway
                                    </button>
                                </div>
                            )}

                            {/* Show content if novice/learning or user clicked reveal */}
                            {(fadingLevel === 'novice' || fadingLevel === 'learning' || showFadedContent) && (
                                <>
                                    {activeTab === 'hands_on' && <CodeBlock code={scaffold.hands_on} />}
                                    {activeTab === 'visual' && <MermaidDiagram code={scaffold.visual.content} />}
                                    {activeTab === 'socratic' && (
                                        <SocraticQuestions
                                            questions={scaffold.socratic.questions}
                                            conceptId={conceptId}
                                            sessionId={sessionId}
                                        />
                                    )}
                                    {activeTab === 'textual' && <TextContent content={scaffold.textual} />}
                                </>
                            )}
                        </>
                    ) : null}
                </div>
            </div>
        </div>
    );
}

// --- Scaffold Renderers ---

function CodeBlock({ code }: { code: { language: string; content: string } }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative">
            <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400 uppercase tracking-wider">{code.language}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                >
                    {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied!' : 'Copy'}
                </button>
            </div>
            <pre className="bg-slate-950 rounded-lg p-4 overflow-x-auto border border-slate-800">
                <code className="text-sm text-slate-200 font-mono whitespace-pre-wrap">{code.content}</code>
            </pre>
        </div>
    );
}

function MermaidDiagram({ code }: { code: string }) {
    const [svg, setSvg] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Reset state on code change
        setSvg(null);
        setError(null);
        setLoading(true);

        // Check for empty or invalid code
        if (!code || code.trim().length === 0) {
            setError('No diagram content was generated for this concept.');
            setLoading(false);
            return;
        }

        // Sanitize Mermaid code to fix common AI generation issues
        const sanitizeMermaidCode = (rawCode: string): string => {
            let sanitized = rawCode;

            // FIX: Replace double brackets [[ ]] with single [ ]
            // These cause "Unrecognized text" errors
            sanitized = sanitized.replace(/\[\[/g, '[');
            sanitized = sanitized.replace(/\]\]/g, ']');

            // Replace problematic characters in node labels
            // Mermaid doesn't like () inside labels - replace with []
            sanitized = sanitized.replace(/\(([^)]+)\)/g, '[$1]');

            // Escape quotes in labels
            sanitized = sanitized.replace(/["']/g, '');

            // Fix common issues with special characters
            sanitized = sanitized.replace(/[<>]/g, '');

            // Remove any stray % that might break
            sanitized = sanitized.replace(/%(?![A-Fa-f0-9]{2})/g, 'percent');

            // Remove pipe characters in node text (causes edge parsing issues)
            // But keep them for edges by only removing inside brackets
            sanitized = sanitized.replace(/\[([^\]]*?)\|([^\]]*?)\]/g, '[$1-$2]');

            return sanitized;
        };

        const renderMermaid = async () => {
            try {
                const mermaid = (await import('mermaid')).default;
                mermaid.initialize({
                    startOnLoad: false,
                    theme: 'dark',
                    securityLevel: 'loose',
                    themeVariables: {
                        primaryColor: '#8B5CF6',
                        primaryTextColor: '#fff',
                        primaryBorderColor: '#6D28D9',
                        lineColor: '#94A3B8',
                        secondaryColor: '#1E293B',
                        tertiaryColor: '#0F172A'
                    }
                });

                // Sanitize and render
                const sanitizedCode = sanitizeMermaidCode(code);
                const uniqueId = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                const { svg: renderedSvg } = await mermaid.render(uniqueId, sanitizedCode);
                setSvg(renderedSvg);
                setLoading(false);
            } catch (e) {
                console.error('Mermaid rendering error:', e);
                setError('Could not render diagram. The AI may have generated invalid syntax.');
                setLoading(false);
            }
        };

        renderMermaid();
    }, [code]);

    // Loading state
    if (loading) {
        return (
            <div className="flex items-center justify-center h-48">
                <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
        );
    }

    // Error state - show raw code as fallback
    if (error) {
        return (
            <div className="space-y-4">
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
                    <p className="text-amber-400 text-sm flex items-center gap-2">
                        <span>⚠️</span> {error}
                    </p>
                </div>

                {code && code.trim() && (
                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                        <p className="text-xs text-slate-500 uppercase mb-2">Raw Diagram Code (for debugging)</p>
                        <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap overflow-x-auto">{code}</pre>
                    </div>
                )}

                <p className="text-xs text-slate-500 text-center">
                    💡 Try the other tabs (Code, Think, Read) for this concept.
                </p>
            </div>
        );
    }

    // Success state
    return (
        <div
            className="bg-slate-950 rounded-lg p-6 border border-slate-800 flex items-center justify-center overflow-x-auto"
            dangerouslySetInnerHTML={{ __html: svg || '' }}
        />
    );
}

function SocraticQuestions({
    questions,
    conceptId,
    sessionId
}: {
    questions: string[];
    conceptId: string;
    sessionId: string;
}) {
    const [revealed, setRevealed] = useState<Set<number>>(new Set());
    const [answered, setAnswered] = useState<Set<number>>(new Set());
    const [answeredCorrectly, setAnsweredCorrectly] = useState<Set<number>>(new Set());

    const toggleReveal = (idx: number) => {
        setRevealed(prev => {
            const next = new Set(prev);
            if (next.has(idx)) next.delete(idx);
            else next.add(idx);
            return next;
        });
    };

    // Phase 13.5: Log answer and update mastery
    const handleAnswer = async (idx: number, understood: boolean, e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent toggle reveal

        try {
            await fetch(`/api/v1/session/${sessionId}/signal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    concept_id: conceptId,
                    format_chosen: 'socratic',
                    interaction_type: 'socratic_answer',
                    question_index: idx,
                    understood: understood,
                    dwell_time_ms: 0,
                    time_since_last_interaction_ms: 0
                })
            });
            console.log(`[SocraticQuestions] Q${idx + 1} answered: ${understood ? 'I got it' : 'Need practice'}`);
        } catch (e) {
            console.warn('Failed to log socratic answer:', e);
        }

        setAnswered(prev => new Set([...prev, idx]));

        // Track if they got it right for different feedback messages
        if (understood) {
            setAnsweredCorrectly(prev => new Set([...prev, idx]));
        }
    };

    const difficultyLabels = ['🟢 Warm-up', '🟡 Challenge', '🔴 Deep Dive'];

    return (
        <div className="space-y-4">
            <p className="text-slate-400 text-sm mb-4">
                Click each question to reveal, think through your answer, then tell us how you did.
            </p>
            {questions.map((q, idx) => (
                <div
                    key={idx}
                    onClick={() => !revealed.has(idx) && toggleReveal(idx)}
                    className={`p-4 rounded-lg border transition-all ${revealed.has(idx)
                        ? 'bg-amber-500/10 border-amber-500/50'
                        : 'bg-slate-800 border-slate-700 hover:border-amber-500/30 cursor-pointer'
                        }`}
                >
                    <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-lg ${answered.has(idx) ? 'bg-green-500/20' :
                            revealed.has(idx) ? 'bg-amber-500/20' : 'bg-slate-700'
                            }`}>
                            {answered.has(idx) ? '✓' : idx + 1}
                        </div>
                        <div className="flex-1">
                            <span className="text-xs text-slate-500 mb-1 block">{difficultyLabels[idx] || 'Question'}</span>
                            <p className={`text-white ${revealed.has(idx) ? '' : 'blur-sm select-none'}`}>
                                {q}
                            </p>
                            {!revealed.has(idx) && (
                                <p className="text-amber-400 text-sm mt-2">Click to reveal</p>
                            )}

                            {/* Phase 13.5: Answer buttons */}
                            {revealed.has(idx) && !answered.has(idx) && (
                                <div className="flex gap-2 mt-3">
                                    <button
                                        onClick={(e) => handleAnswer(idx, true, e)}
                                        className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors text-sm font-medium"
                                    >
                                        ✓ I got it
                                    </button>
                                    <button
                                        onClick={(e) => handleAnswer(idx, false, e)}
                                        className="px-3 py-1.5 bg-slate-700 text-slate-400 rounded-lg hover:bg-slate-600 transition-colors text-sm"
                                    >
                                        Need more practice
                                    </button>
                                </div>
                            )}

                            {/* Answered state - show different messages */}
                            {answered.has(idx) && (
                                <p className={`text-sm mt-2 ${answeredCorrectly.has(idx)
                                    ? 'text-green-400'
                                    : 'text-amber-400'
                                    }`}>
                                    {answeredCorrectly.has(idx)
                                        ? 'Great! Keep up the learning momentum.'
                                        : 'No worries! Review this concept again later.'}
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}

function TextContent({ content }: { content: { content: string; analogy: string } }) {
    return (
        <div className="space-y-6">
            <div className="prose prose-invert max-w-none">
                <p className="text-slate-200 leading-relaxed text-base whitespace-pre-wrap">
                    {content.content}
                </p>
            </div>

            {content.analogy && (
                <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <div className="p-2 rounded-full bg-blue-500/20 text-blue-400">
                            <BookOpen className="w-5 h-5" />
                        </div>
                        <div>
                            <h4 className="text-blue-400 font-medium text-sm mb-1">💡 Analogy</h4>
                            <p className="text-slate-200">{content.analogy}</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
