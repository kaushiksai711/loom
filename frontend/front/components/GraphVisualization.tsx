
import React, { useRef, useEffect, useCallback } from 'react';
import ForceGraph2D, { ForceGraphMethods, NodeObject, LinkObject } from 'react-force-graph-2d';
import { useWindowSize } from '@react-hook/window-size'; // Optional: for responsive sizing

interface GraphNode extends NodeObject {
    id: string;
    group: 'concept' | 'seed';
    status?: 'verified' | 'conflict' | 'neutral'; // Logic for "Toxic" edges
    val: number; // Influence size
}

interface GraphLink extends LinkObject {
    type: 'RELATED' | 'CONTRADICTS' | 'PREREQUISITE';
}

interface GraphProps {
    data: { nodes: GraphNode[]; links: GraphLink[] };
    isCrystallized: boolean; // Controls the Physics & Render Mode
    onNodeClick: (node: GraphNode) => void;
}

const GraphVisualization: React.FC<GraphProps> = ({ data, isCrystallized, onNodeClick }) => {
    const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
    const [width, height] = useWindowSize(); // Or just use hardcoded/parent dims

    // 1. PHYSICS ENGINE CONTROLLER
    useEffect(() => {
        const fg = fgRef.current as any; // Cast to any to access d3 internal methods
        if (!fg) return;

        if (isCrystallized) {
            // === CRYSTAL MODE (Rigid, Structured) ===
            fg.d3Force('charge')?.strength(-100);
            fg.d3Force('link')?.strength(1);
            if (fg.d3VelocityDecay) fg.d3VelocityDecay(0.1);

            // Stop the "breathing" animation after a moment
            if (fg.d3AlphaDecay) setTimeout(() => fg.d3AlphaDecay(0.2), 1000);
        } else {
            // === SLIME MODE (Fluid, Organic) ===
            fg.d3Force('charge')?.strength(-30);
            fg.d3Force('link')?.strength(0.1);
            if (fg.d3VelocityDecay) fg.d3VelocityDecay(0.6);
            if (fg.d3AlphaDecay) fg.d3AlphaDecay(0);

            // Kickstart movement
            fg.d3ReheatSimulation();
        }
    }, [isCrystallized, data]);

    // 2. RENDER: SLIME NODE (Glowing Blob)
    const paintSlime = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
        // Safety Check: If physics hasn't started, x/y might be undefined
        if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

        const radius = Math.max(3, Math.sqrt(node.val) * 2);
        const isConflict = node.status === 'conflict';

        // Color Palette
        const coreColor = isConflict ? 'rgba(255, 50, 50, 0.9)' : 'rgba(0, 255, 200, 0.9)'; // Red vs Teal
        const glowColor = isConflict ? 'rgba(255, 50, 50, 0.2)' : 'rgba(0, 255, 200, 0.3)';

        // A. Outer Glow (The "Jelly")
        const glowRadius = radius * 3;
        const gradient = ctx.createRadialGradient(node.x, node.y, radius, node.x, node.y, glowRadius);
        gradient.addColorStop(0, glowColor);
        gradient.addColorStop(1, 'rgba(0,0,0,0)');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI, false);
        ctx.fill();

        // B. Inner Nucleus
        ctx.fillStyle = coreColor;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
        ctx.fill();

        // Label (Only show on hover or high zoom)
        if (globalScale > 1.5) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = 'rgba(255,255,255,0.8)';
            ctx.font = `${12 / globalScale}px Sans-Serif`;
            ctx.fillText(node.id, node.x, node.y + radius + 4);
        }
    }, []);

    // 3. RENDER: CRYSTAL NODE (Geometric Diamond)
    const paintCrystal = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
        // Safety Check
        if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

        const size = Math.max(4, Math.sqrt(node.val) * 3);

        ctx.fillStyle = node.status === 'conflict' ? '#FF4444' : '#A020F0'; // Red vs Purple
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 1 / globalScale;

        // Draw Diamond Shape
        ctx.beginPath();
        ctx.moveTo(node.x, node.y - size); // Top
        ctx.lineTo(node.x + size, node.y); // Right
        ctx.lineTo(node.x, node.y + size); // Bottom
        ctx.lineTo(node.x - size, node.y); // Left
        ctx.closePath();

        ctx.fill();
        ctx.stroke();

        // Always show label in Crystal mode
        ctx.fillStyle = 'rgba(255,255,255, 1)';
        ctx.font = `bold ${14 / globalScale}px Sans-Serif`;
        ctx.fillText(node.id, node.x, node.y + size + 6);
    }, []);

    return (
        <div style={{ background: '#050510', border: '1px solid #1F1F30', borderRadius: '12px', overflow: 'hidden' }}> {/* Deep Space Container */}
            <ForceGraph2D
                ref={fgRef}
                width={width}
                height={height * 0.6} // Occupy 60% of viewport
                graphData={data}

                // --- Appearance ---
                backgroundColor="#00000000" // Transparent (let parent bg shine through)

                // --- Node Rendering Switch ---
                nodeCanvasObject={(node, ctx, scale) => {
                    if (isCrystallized) {
                        paintCrystal(node as GraphNode, ctx, scale);
                    } else {
                        paintSlime(node as GraphNode, ctx, scale);
                    }
                }}

                // --- Link Rendering ---
                linkWidth={link => (link as GraphLink).type === 'CONTRADICTS' ? 2 : 1}
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
                linkColor={link => {
                    const l = link as GraphLink;
                    if (l.type === 'CONTRADICTS') return '#FF0000'; // "Toxic" Edge
                    if (l.type === 'PREREQUISITE') return '#0088FF';
                    return isCrystallized ? '#444455' : '#222233'; // Faint connections
                }}

                // --- Interaction ---
                onNodeClick={(node) => onNodeClick(node as GraphNode)}
                cooldownTicks={isCrystallized ? 100 : Infinity} // Infinite cooldown = Slime movement
            />
        </div>
    );
};

export default GraphVisualization;
