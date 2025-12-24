import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { AuthProvider } from "@/components/providers/auth-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Cognitive Loom | Mission Control",
  description: "Metacognitive Interface for your Second Brain",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[url('/deep-space-bg.jpg')] bg-cover bg-fixed`}
        style={{
          backgroundImage: 'var(--image-deep-space)' // Fallback or strict usage
        }}
      >
        <AuthProvider>
          <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1 pt-20 px-6 container mx-auto">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
