import React, { useState } from 'react';
import { Send, AlertTriangle, BookOpen, Search } from 'lucide-react';

export type ChatIntent = 'GENERAL' | 'FACT_CHECK' | 'LEARNING';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface ChatInterfaceProps {
    messages: Message[];
    onSendMessage: (message: string, intent: ChatIntent) => void;
    isLoading: boolean;
    onEndSession: () => void;
    isCrystallized: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSendMessage, isLoading, onEndSession, isCrystallized }) => {
    const [message, setMessage] = useState('');
    const [intent, setIntent] = useState<ChatIntent>('GENERAL');
    const scrollRef = React.useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    React.useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = () => {
        if (!message.trim()) return;
        onSendMessage(message, intent);
        setMessage('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="flex flex-col h-full bg-black/40 backdrop-blur-md rounded-xl border border-white/10 overflow-hidden">
            {/* Header / Mode Selector */}
            <div className="p-4 border-b border-white/10 flex flex-wrap gap-2 items-center justify-between">
                <div className="flex gap-2">
                    <button
                        onClick={() => setIntent('GENERAL')}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${intent === 'GENERAL'
                            ? 'bg-zinc-700 text-white shadow-lg shadow-zinc-500/20'
                            : 'bg-zinc-900/50 text-zinc-400 hover:bg-zinc-800'
                            }`}
                    >
                        <Search size={14} /> Global
                    </button>
                    <button
                        onClick={() => setIntent('FACT_CHECK')}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${intent === 'FACT_CHECK'
                            ? 'bg-red-900/80 text-red-100 border border-red-500/50 shadow-lg shadow-red-500/20'
                            : 'bg-zinc-900/50 text-zinc-400 hover:bg-zinc-800'
                            }`}
                    >
                        <AlertTriangle size={14} /> Fact Check
                    </button>
                    <button
                        onClick={() => setIntent('LEARNING')}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${intent === 'LEARNING'
                            ? 'bg-blue-900/80 text-blue-100 border border-blue-500/50 shadow-lg shadow-blue-500/20'
                            : 'bg-zinc-900/50 text-zinc-400 hover:bg-zinc-800'
                            }`}
                    >
                        <BookOpen size={14} /> Learning
                    </button>
                </div>

                {!isCrystallized && (
                    <button
                        onClick={onEndSession}
                        className="px-3 py-1.5 rounded-full bg-purple-900/20 text-purple-300 text-xs hover:bg-purple-900/40 border border-purple-500/30 transition-all"
                    >
                        Crystallize Session
                    </button>
                )}
            </div>

            {/* Chat Stream (Placeholder for now, usually fed by parent) */}
            <div className="flex-1 p-4 overflow-y-auto space-y-4" ref={scrollRef}>
                {messages.length === 0 ? (
                    <div className="text-center text-zinc-600 text-sm mt-10">
                        System Ready. Select a mode and begin.
                    </div>
                ) : (
                    messages.map((msg, idx) => (
                        <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${msg.role === 'user'
                                    ? 'bg-zinc-700 text-white rounded-br-none'
                                    : 'bg-zinc-800/80 text-zinc-200 border border-white/5 rounded-bl-none'
                                }`}>
                                {msg.content}
                            </div>
                        </div>
                    ))
                )}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-zinc-800/50 rounded-2xl px-4 py-2 text-xs text-zinc-500 animate-pulse">
                            Neural synthesis in progress...
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-white/10 bg-black/20">
                <div className="relative">
                    <input
                        type="text"
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={`Ask in ${intent.toLowerCase().replace('_', ' ')} mode...`}
                        disabled={isLoading || isCrystallized}
                        className="w-full bg-zinc-900/50 border border-white/5 rounded-lg pl-4 pr-12 py-3 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                    />
                    <button
                        onClick={handleSend}
                        disabled={isLoading || !message.trim() || isCrystallized}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-teal-600/20 text-teal-400 rounded-md hover:bg-teal-600/40 disabled:opacity-50 transition-colors"
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;
