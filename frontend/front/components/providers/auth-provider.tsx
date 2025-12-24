"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface User {
    id: string;
    name: string;
    role: string;
}

interface AuthContextType {
    user: User | null;
    login: () => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);

    useEffect(() => {
        // Simulate auto-login for "The Architect"
        setUser({
            id: "user_architect_01",
            name: "Architect",
            role: "admin",
        });
    }, []);

    const login = () => {
        setUser({ id: "user_architect_01", name: "Architect", role: "admin" });
    };

    const logout = () => setUser(null);

    return (
        <AuthContext.Provider value={{ user, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
