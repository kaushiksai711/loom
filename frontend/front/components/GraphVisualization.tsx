
import React, { useRef, useEffect, useCallback } from 'react';
import ForceGraph2D, { ForceGraphMethods, NodeObject, LinkObject } from 'react-force-graph-2d';
import { useWindowSize } from '@react-hook/window-size'; // Optional: for responsive sizing

interface GraphNode extends NodeObject {
    id: string;
    group: 'concept' | 'seed' | 'source' | 'session' | 'evidence' | 'thought' | 'user_seed';
    status?: 'verified' | 'conflict' | 'neutral'; // Logic for "Toxic" edges
    val: number; // Influence size
}

interface GraphLink extends LinkObject {
    type: 'RELATED' | 'CONTRADICTS' | 'PREREQUISITE' | 'HAS_PART' | 'IS_PART_OF' | 'ENABLES' | 'RELATED_TO' | 'CREATED_BY' | 'CONTRIBUTES_TO' | 'USES' | 'PROVIDED_BY' | 'CRYSTALLIZED_AS' | 'UPLOADED_IN';
}

interface GraphProps {
    data: { nodes: GraphNode[]; links: GraphLink[] };
    isCrystallized: boolean; // Controls the Physics & Render Mode
    onNodeClick: (node: GraphNode) => void;
    focusedNodeId?: string | null;
}

const GraphVisualization: React.FC<GraphProps & { searchTerm?: string }> = ({ data, isCrystallized, onNodeClick, searchTerm, focusedNodeId }) => {
    const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
    const [width, height] = useWindowSize(); // Or just use hardcoded/parent dims

    // 0. CAMERA FOCUS CONTROLLER
    useEffect(() => {
        if (!focusedNodeId || !fgRef.current) return;

        const node = data.nodes.find(n => n.id === focusedNodeId);
        if (node && typeof node.x === 'number' && typeof node.y === 'number') {
            fgRef.current.centerAt(node.x, node.y, 1000);
            fgRef.current.zoom(6, 2000); // Close up zoom
        }
    }, [focusedNodeId, data.nodes]);

    // 1. PHYSICS ENGINE CONTROLLER
    useEffect(() => {
        const fg = fgRef.current as any; // Cast to any to access d3 internal methods
        if (!fg) return;

        // A. MODE SWITCHING (Fix vs Unfix)
        // We manually manipulate the d3 nodes to lock/unlock them based on mode.
        data.nodes.forEach((node: any) => {
            if (isCrystallized && node.pcaX !== undefined && node.pcaY !== undefined) {
                // LOCK to Semantic Position
                node.fx = node.pcaX;
                node.fy = node.pcaY;
            } else {
                // UNLOCK for Organic Movement
                node.fx = undefined;
                node.fy = undefined;
            }
        });

        if (isCrystallized) {
            // === CRYSTAL MODE (Rigid, Structured) ===
            fg.d3Force('charge')?.strength(-10); // Low repulsion, position is fixed
            fg.d3Force('link')?.strength(0.1); // Weak links
            fg.d3Force('center', null);

            // Reheat to ensure nodes travel to their fx/fy destinations
            if (fg.d3VelocityDecay) fg.d3VelocityDecay(0.1);
            if (fg.d3AlphaDecay) fg.d3AlphaDecay(0.02); // Slow decay to allow travel time
            fg.d3ReheatSimulation();

        } else {
            // === SLIME MODE (Fluid, Organic) ===
            // Tuned for "Dense Brain" Look
            fg.d3Force('charge')?.strength(-60); // Moderate repulsion
            fg.d3Force('link')?.distance(40); // Pull related nodes closer
            fg.d3Force('link')?.strength(0.2); // Elastic links
            fg.d3Force('center', null);

            if (fg.d3VelocityDecay) fg.d3VelocityDecay(0.6); // Damping
            if (fg.d3AlphaDecay) fg.d3AlphaDecay(0); // Keep moving

            // Kickstart movement to break out of crystal formation
            fg.d3ReheatSimulation();
        }
    }, [isCrystallized, data]);

    // Helper: Check if node matches search (for dimming)
    const isDimmed = useCallback((node: GraphNode) => {
        if (!searchTerm) return false;
        const term = searchTerm.toLowerCase();
        const label = (node.label || node.id).toLowerCase();
        const content = (node as any).content?.toLowerCase() || "";
        return !label.includes(term) && !content.includes(term);
    }, [searchTerm]);

    // 2. RENDER: SLIME NODE (Glowing Blob)
    const paintSlime = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
        // Safety Check: If physics hasn't started, x/y might be undefined
        if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

        // Dimming Logic
        const dimmed = isDimmed(node);
        const opacityMult = dimmed ? 0.1 : 1.0;

        // Size Tuning
        const radius = Math.max(2, Math.sqrt(node.val) * 1.5); // Smaller nodes
        const isConflict = node.status === 'conflict';

        // Color Palette (Group based)
        let coreColor = 'rgba(0, 255, 200, 0.9)'; // Concept (Teal)
        let glowColor = 'rgba(0, 255, 200, 0.3)';

        if (isConflict) {
            coreColor = 'rgba(255, 50, 50, 0.9)'; // Conflict (Red)
            glowColor = 'rgba(255, 50, 50, 0.2)';
        } else if (node.group === 'source' || node.group === 'evidence' || node.group === 'seed') {
            coreColor = 'rgba(255, 165, 0, 0.9)'; // Evidence (Orange)
            glowColor = 'rgba(255, 165, 0, 0.3)';
        } else if (node.group === 'thought' || node.group === 'user_seed') {
            coreColor = 'rgba(160, 32, 240, 0.9)'; // Thought (Purple)
            glowColor = 'rgba(160, 32, 240, 0.3)';
        } else if (node.group === 'session') {
            coreColor = 'rgba(255, 215, 0, 0.9)'; // Gold for Sessions (Hubs)
            glowColor = 'rgba(255, 215, 0, 0.3)';
        }

        // Apply Opacity
        if (dimmed) {
            ctx.globalAlpha = 0.1;
        }

        // A. Outer Glow (The "Jelly")
        const glowRadius = radius * 2.5; // Reduced glow
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

        // Label (Adaptive Visibility)
        // If searching, show label of match even if small
        const isMatch = !dimmed && searchTerm;
        const showLabel = isMatch || (globalScale > 0.9 || data.nodes.length < 30);

        if (showLabel) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Text Background for readability
            const label = node.label || node.id;
            const textWidth = ctx.measureText(label).width;
            ctx.fillStyle = `rgba(0,0,0,${dimmed ? 0.1 : 0.6})`;
            ctx.fillRect(node.x - textWidth / 2 - 2, node.y + radius + 2, textWidth + 4, 12);

            ctx.fillStyle = `rgba(255,255,255,${dimmed ? 0.2 : 0.9})`;
            ctx.font = `${10 / globalScale}px Sans-Serif`; // Finer font
            ctx.fillText(label, node.x, node.y + radius + 8);
        }

        // Restore Alpha
        ctx.globalAlpha = 1.0;

    }, [data.nodes.length, searchTerm, isDimmed]);

    // 3. RENDER: CRYSTAL NODE (Geometric Diamond)
    const paintCrystal = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
        // Safety Check
        if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

        const dimmed = isDimmed(node);
        if (dimmed) ctx.globalAlpha = 0.1;

        const size = Math.max(4, Math.sqrt(node.val) * 3);

        // Color Logic (Same as Slime but solid)
        let color = '#00FFC8';
        if (node.status === 'conflict') color = '#FF4444';
        else if (node.group === 'evidence' || node.group === 'seed' || node.group === 'source') color = '#FFA500'; // Orange
        else if (node.group === 'thought' || node.group === 'user_seed') color = '#A020F0'; // Purple
        else if (node.group === 'session') color = '#FFD700'; // Gold

        ctx.fillStyle = color;
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

        // Label (Adaptive Visibility) via Crystal Mode
        const isMatch = !dimmed && searchTerm;
        const showLabel = isMatch || (globalScale > 1.2 || data.nodes.length < 30);

        if (showLabel) {
            ctx.fillStyle = `rgba(255,255,255, ${dimmed ? 0.2 : 1})`;
            ctx.font = `bold ${14 / globalScale}px Sans-Serif`;
            ctx.fillText(node.label || node.id, node.x, node.y + size + 6);
        }

        ctx.globalAlpha = 1.0;
    }, [isDimmed, searchTerm, data.nodes.length]);

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
                    const type = l.type;

                    // Critical Semantic Edges
                    if (type === 'CONTRADICTS') return '#FF0055'; // Red (Conflict)
                    if (type === 'PREREQUISITE' || type === 'ENABLES' || type === 'CONTRIBUTES_TO') return '#00AAFF'; // Blue (Flow/Dependency)
                    if (type === 'HAS_PART' || type === 'IS_PART_OF') return '#00FFC8'; // Teal (Structure)
                    if (type === 'USES' || type === 'PROVIDED_BY') return '#AA00FF'; // Purple (Usage)

                    // Context/Meta Edges
                    if (type === 'UPLOADED_IN' || type === 'CREATED_BY' || type === 'CRYSTALLIZED_AS') return '#FFD700'; // Gold (Meta)

                    // Default / Generic
                    return isCrystallized ? '#444455' : 'rgba(0, 255, 255, 0.5)'; // Cyan "Synapse" Look (Brighter)
                }}

                // --- Interaction ---
                linkLabel={link => (link as GraphLink).type || "RELATED"} // Show Relationship Type on Hover
                linkHoverPrecision={6} // Easier to hover thin lines
                onNodeClick={(node) => onNodeClick(node as GraphNode)}
                cooldownTicks={isCrystallized ? 100 : Infinity} // Infinite cooldown = Slime movement
            />
        </div>
    );
};

export default GraphVisualization;
