import json
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from scipy.spatial import Delaunay
import os

try:
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    _HAS_3D = True
except Exception:
    _HAS_3D = False
    print("Warning: 3D projection unavailable (mpl_toolkits conflict). Falling back to 2D.")

# --- Configuration ---
_HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(_HERE, 'vectors.json')
OUTPUT_IMAGE = os.path.join(_HERE, 'system_topology_signature.png')


def load_vectors(filepath):
    """Loads vectors from JSON. Assumes format [[v1_1, v1_2...], [v2_1...]]"""
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found. Ensure the pipeline has generated vectors.json.")
        exit(1)
    with open(filepath, 'r') as f:
        data = json.load(f)
    return np.array(data)


def project_to_nd(vectors, n=3):
    """Uses PCA to reduce high-dimensional vectors to n dimensions."""
    n_samples, n_features = vectors.shape
    print(f"Loaded {n_samples} vectors with {n_features} dimensions.")

    target = min(n, n_features, n_samples)
    if n_features <= target:
        padded = np.zeros((n_samples, target))
        padded[:, :n_features] = vectors
        return padded, 1.0

    print(f"Projecting to {target}D using PCA (capturing maximum variance)...")
    pca = PCA(n_components=target)
    projected = pca.fit_transform(vectors)
    variance_ratio = float(np.sum(pca.explained_variance_ratio_))
    print(f"Captured {variance_ratio:.2%} of system variance in {target}D representation.")
    return projected, variance_ratio


def _build_edges(points):
    """Compute unique edges from Delaunay triangulation."""
    edges = set()
    if len(points) < points.shape[1] + 1:
        return edges
    try:
        tri = Delaunay(points)
        for simplex in tri.simplices:
            n = len(simplex)
            for i in range(n):
                for j in range(i + 1, n):
                    edges.add(tuple(sorted((simplex[i], simplex[j]))))
        print(f"Generated mesh with {len(edges)} unique edges (logical pathways).")
    except Exception as e:
        print(f"Could not generate triangulation: {e}. Plotting points only.")
    return edges


def plot_3d(points, variance_ratio):
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               c='royalblue', marker='o', s=50, alpha=0.8,
               label='System States (0-simplices)')

    if len(points) >= 4:
        print("Generating simplicial mesh (Delaunay triangulation)...")
        edges = _build_edges(points)
        for edge in edges:
            ax.plot(points[list(edge), 0],
                    points[list(edge), 1],
                    points[list(edge), 2],
                    c='gray', alpha=0.3, linewidth=0.5)

    ax.set_title(
        'VeriBound\u2122 Topological Signature\nStructural Map of System Logic (3D)',
        fontsize=16,
    )
    ax.set_xlabel('Logical Axis 1 (PCA1)')
    ax.set_ylabel('Logical Axis 2 (PCA2)')
    ax.set_zlabel('Logical Axis 3 (PCA3)')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    plt.figtext(
        0.15, 0.05,
        f"Note: This 3D view preserves {variance_ratio:.1%} of total structural variance.",
        fontsize=10, color='gray', ha='left',
    )
    return fig


def plot_2d(points, variance_ratio):
    """2D fallback when mpl_toolkits 3D is unavailable."""
    fig, ax = plt.subplots(figsize=(12, 9))

    ax.scatter(points[:, 0], points[:, 1],
               c='royalblue', marker='o', s=50, alpha=0.8,
               label='System States (0-simplices)')

    if len(points) >= 3:
        print("Generating simplicial mesh (Delaunay triangulation, 2D)...")
        edges = _build_edges(points[:, :2])
        for edge in edges:
            ax.plot(points[list(edge), 0],
                    points[list(edge), 1],
                    c='gray', alpha=0.3, linewidth=0.5)

    ax.set_title(
        'VeriBound\u2122 Topological Signature\nStructural Map of System Logic (2D projection)',
        fontsize=16,
    )
    ax.set_xlabel('Logical Axis 1 (PCA1)')
    ax.set_ylabel('Logical Axis 2 (PCA2)')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    plt.figtext(
        0.15, 0.02,
        f"Note: This 2D view preserves {variance_ratio:.1%} of total structural variance.",
        fontsize=10, color='gray', ha='left',
    )
    return fig


if __name__ == "__main__":
    print("--- VeriBound Topological Visualizer ---")

    vectors_raw = load_vectors(INPUT_FILE)

    if _HAS_3D:
        points, variance_ratio = project_to_nd(vectors_raw, n=3)
        fig = plot_3d(points, variance_ratio)
    else:
        points, variance_ratio = project_to_nd(vectors_raw, n=2)
        fig = plot_2d(points, variance_ratio)

    print(f"Saving visualization to {OUTPUT_IMAGE}...")
    plt.savefig(OUTPUT_IMAGE, dpi=150, bbox_inches='tight')
    print(f"Saved: {OUTPUT_IMAGE}")
    print("Showing plot (interactive window)...")
    plt.show()
