import React, { useRef, useEffect } from 'react';

export type AvatarState = 'IDLE' | 'LISTENING' | 'THINKING' | 'ALERT' | 'INSIGHT';

interface AvatarProps {
    state: AvatarState;
}

const AvatarSlime: React.FC<AvatarProps> = ({ state }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const timeRef = useRef(0);
    const animationFrameRef = useRef<number | undefined>(undefined);

    // State Config (Color, Speed, Turbulence)
    const getConfig = (s: AvatarState) => {
        switch (s) {
            case 'IDLE': return { color: [0, 255, 200], speed: 0.02, turbulence: 1 }; // Teal, Slow
            case 'LISTENING': return { color: [0, 255, 255], speed: 0.05, turbulence: 2 }; // Cyan, Attentive
            case 'THINKING': return { color: [160, 32, 240], speed: 0.1, turbulence: 5 }; // Purple, Fast
            case 'ALERT': return { color: [255, 50, 50], speed: 0.15, turbulence: 10 }; // Red, Agitated
            case 'INSIGHT': return { color: [255, 215, 0], speed: 0.02, turbulence: 3 }; // Gold, Radiant
            default: return { color: [0, 255, 200], speed: 0.02, turbulence: 1 };
        }
    };

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const render = () => {
            const { color, speed, turbulence } = getConfig(state);
            timeRef.current += speed;
            const t = timeRef.current;

            // Clear
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const cx = canvas.width / 2;
            const cy = canvas.height / 2;
            const baseRadius = 60;

            // Create Gradient (Glow)
            const gradient = ctx.createRadialGradient(cx, cy, baseRadius * 0.5, cx, cy, baseRadius * 2);
            gradient.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.8)`);
            gradient.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);
            ctx.fillStyle = gradient;

            // Draw Blobs (Metaball-ish simulation using sine waves)
            ctx.beginPath();
            for (let i = 0; i <= 360; i += 5) {
                const rad = (i * Math.PI) / 180;
                // Noise function simulation
                const noise = Math.sin(t + rad * 3) * Math.cos(t * 0.5 + rad * 5) * turbulence;
                const r = baseRadius + noise + (state === 'INSIGHT' ? Math.sin(t * 5) * 10 : 0);

                const x = cx + Math.cos(rad) * r;
                const y = cy + Math.sin(rad) * r;

                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.fill();

            // Inner Core
            ctx.beginPath();
            ctx.arc(cx, cy, baseRadius * 0.4, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.9)`;
            ctx.fill();

            animationFrameRef.current = requestAnimationFrame(render);
        };

        render();

        return () => {
            if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        };
    }, [state]);

    return (
        <canvas
            ref={canvasRef}
            width={300}
            height={300}
            className="w-full h-64 object-contain"
        />
    );
};

export default AvatarSlime;
