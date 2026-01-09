from typing import List, Dict, Any
import numpy as np
from sklearn.decomposition import PCA

def compute_pca_layout(nodes: List[Dict[str, Any]], scale: float = 1000.0) -> Dict[str, Dict[str, float]]:
    """
    Computes 2D/3D coordinates for nodes based on their embeddings using PCA.
    Returns a dictionary mapping node ID to {fx, fy, (fz)} coordinates.
    
    Args:
        nodes: List of node dictionaries. Must contain 'embedding' (List[float]) and 'id' (or '_id').
        scale: Scaling factor for the coordinates (e.g., to fit in a 1000x1000 canvas).
    """
    valid_nodes = [n for n in nodes if n.get('embedding')]
    
    if not valid_nodes:
        return {}

    # Extract embeddings matrix
    embeddings = np.array([n['embedding'] for n in valid_nodes])
    ids = [n.get('id', n.get('_id')) for n in valid_nodes]

    # Handle edge case: Too few nodes for PCA
    n_samples = embeddings.shape[0]
    n_components = min(2, n_samples)
    
    if n_components < 2:
        # Fallback for single node: Center it
        return {ids[0]: {'fx': 0.0, 'fy': 0.0}}

    # Apply PCA
    pca = PCA(n_components=2)
    coords = pca.fit_transform(embeddings)

    # Normalize and Scale
    # We want cords roughly in [-scale/2, scale/2]
    # 1. Min-Max Normalize to [0, 1]
    min_vals = coords.min(axis=0)
    max_vals = coords.max(axis=0)
    range_vals = max_vals - min_vals
    
    # Avoid division by zero
    range_vals[range_vals == 0] = 1.0
    
    normalized = (coords - min_vals) / range_vals
    
    # 2. Shift to center [-0.5, 0.5] and Scale
    final_coords = (normalized - 0.5) * scale

    layout = {}
    for i, node_id in enumerate(ids):
        layout[node_id] = {
            'fx': float(final_coords[i, 0]),
            'fy': float(final_coords[i, 1])
        }
        
    return layout
