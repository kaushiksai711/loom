"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Network, FileText, Settings, Activity, MessageSquare, Brain } from "lucide-react";

const navItems = [
    { name: "Mission Control", href: "/", icon: LayoutDashboard },
    { name: "Neuro Chat", href: "/chat", icon: MessageSquare },
    { name: "Knowledge Graph", href: "/graph", icon: Network },
    { name: "Review", href: "/review", icon: Brain },  // Phase 15: Spaced Repetition
    { name: "Evidence Locker", href: "/ingest", icon: FileText },
    { name: "Settings", href: "/settings", icon: Settings },
];

export function Navbar() {
    const pathname = usePathname();

    return (
        <nav className="fixed top-0 left-0 right-0 z-50 glass h-16 flex items-center justify-between px-6">
            <div className="flex items-center gap-2">
                <Activity className="text-primary w-6 h-6 animate-pulse" />
                <span className="font-bold text-lg tracking-wider text-white">COGNITIVE LOOM</span>
            </div>

            <div className="flex items-center gap-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-300 text-sm font-medium",
                                isActive
                                    ? "bg-primary/20 text-primary border border-primary/30 shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                                    : "text-slate-400 hover:text-white hover:bg-white/5"
                            )}
                        >
                            <item.icon className="w-4 h-4" />
                            {item.name}
                        </Link>
                    );
                })}
            </div>

            <div className="flex items-center gap-4">
                {/* User Profile / Status Placeholder */}
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_10px_#22c55e]" />
                    <span>SYSTEM ONLINE</span>
                </div>
            </div>
        </nav>
    );
}
