"use client";

import dynamic from 'next/dynamic';
import { useRef, useCallback } from 'react';

const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
    ssr: false,
    loading: () => <div className="text-active animate-pulse">Loading Graph...</div>
});

const ThreeDMindmap = ({ graphData, onNodeClick }) => {
    const fgRef = useRef();

    const handleNodeClick = useCallback(node => {
        // Aim at node from outside it
        const distance = 40;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

        if (fgRef.current) {
            fgRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, // new position
                node, // lookAt ({ x, y, z })
                3000  // ms transition duration
            );
        }

        if (onNodeClick) onNodeClick(node);
    }, [onNodeClick]);

    return (
        <div className="w-full h-[600px] border border-white/10 rounded-xl overflow-hidden bg-black/50">
            <ForceGraph3D
                ref={fgRef}
                graphData={graphData}
                nodeLabel="label"
                nodeColor="color"
                nodeVal="val"
                linkColor={() => 'rgba(255,255,255,0.2)'}
                linkOpacity={0.3}
                linkWidth={1}
                onNodeClick={handleNodeClick}
                backgroundColor="rgba(0,0,0,0)"
            />
        </div>
    );
};

export default ThreeDMindmap;
