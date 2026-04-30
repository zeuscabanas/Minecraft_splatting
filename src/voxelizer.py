"""
voxelizer.py
------------
Convierte una malla 3D (trimesh.Trimesh) en un grid de vóxeles con colores.

Proceso:
1. Escala la malla al tamaño objetivo en bloques de Minecraft.
2. Voxeliza la superficie usando trimesh.
3. Identifica vóxeles de superficie (exteriores) vs. interiores.
4. Para cada vóxel de superficie, muestrea el color de la textura
   buscando el punto más cercano en la malla original.

Dependencias: trimesh, numpy, Pillow
"""

from __future__ import annotations

import numpy as np
from PIL import Image
import trimesh
import trimesh.proximity
import trimesh.voxel.ops as voxops


class VoxelGrid:
    """
    Contiene los datos voxelizados de un modelo 3D.

    Atributos
    ---------
    positions : np.ndarray, shape (N, 3), dtype int
        Coordenadas (x, y, z) de cada vóxel ocupado.
    colors : np.ndarray, shape (N, 4), dtype uint8
        Color RGBA de cada vóxel (promedio de la textura muestreada).
        Los vóxeles interiores tienen color [0, 0, 0, 0] (negro, opaco).
    is_surface : np.ndarray, shape (N,), dtype bool
        True para vóxeles en la superficie exterior, False para interiores.
    size : tuple (width, height, depth)
        Dimensiones del grid en bloques.
    """

    def __init__(
        self,
        positions: np.ndarray,
        colors: np.ndarray,
        is_surface: np.ndarray,
        size: tuple[int, int, int],
        shape_hints: np.ndarray | None = None,
    ):
        self.positions = positions
        self.colors = colors
        self.is_surface = is_surface
        self.size = size  # (W, H, D) = (X, Y, Z)
        # shape_hints: array of strings per voxel
        # Values: 'solid', 'slab_top', 'slab_bottom', 'wall',
        #         'stair_{east|west|north|south}_{bottom|top}'
        if shape_hints is None:
            self.shape_hints = np.full(len(positions), 'solid', dtype=object)
        else:
            self.shape_hints = shape_hints

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def depth(self) -> int:
        return self.size[2]


def voxelize(
    mesh: trimesh.Trimesh,
    texture: Image.Image | None,
    target_size: tuple[int, int, int],
    *,
    fill_interior: bool = True,
    shadow_removal: bool = True,
) -> VoxelGrid:
    """
    Voxeliza una malla 3D y extrae el color de cada vóxel.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Malla de entrada (puede tener UVs o no).
    texture : PIL.Image.Image or None
        Imagen de textura base color. Si es None, se usa el color de vértice
        o blanco como fallback.
    target_size : (width, height, depth)
        Tamaño objetivo en bloques de Minecraft (X, Y, Z).
    fill_interior : bool
        Si True, rellena el interior de la malla con vóxeles (produce
        estructuras sólidas más robustas).
    shadow_removal : bool
        Si True, aplica normalización de luminosidad CLAHE sobre el canal L
        del espacio LAB antes del matching de color. Compensa las sombras
        bakeadas en la textura por TRELLIS.

    Returns
    -------
    VoxelGrid
    """
    W, H, D = target_size

    # 1. Escalar la malla para que quepa exactamente en target_size
    mesh_scaled = _scale_mesh(mesh, W, H, D)

    # 2. Voxelizar con pitch=1.0 (1 vóxel = 1 bloque)
    vox = mesh_scaled.voxelized(pitch=1.0)

    if fill_interior:
        vox = vox.fill()

    # 3. Obtener posiciones de vóxeles ocupados como enteros
    # trimesh retorna centros de vóxeles; los redondeamos y convertimos a int
    centers = vox.points  # shape (N, 3), float
    positions = np.floor(centers).astype(int)

    # Clip para que estén dentro de los límites
    positions[:, 0] = np.clip(positions[:, 0], 0, W - 1)
    positions[:, 1] = np.clip(positions[:, 1], 0, H - 1)
    positions[:, 2] = np.clip(positions[:, 2], 0, D - 1)

    # 4. Construir grid de ocupación (se reutiliza en superficie + shape hints)
    occupied = np.zeros((W, H, D), dtype=bool)
    occupied[positions[:, 0], positions[:, 1], positions[:, 2]] = True

    # 5. Identificar vóxeles de superficie
    is_surface = _find_surface_voxels(positions, occupied, W, H, D)

    # 6. Calcular shape hints por vóxel (losa / escalera / muro)
    shape_hints = _compute_shape_hints(positions, is_surface, occupied, W, H, D)

    # 7. Extraer colores para los vóxeles de superficie
    colors = _extract_voxel_colors(
        mesh_scaled, texture, positions, is_surface
    )

    # 8. Corrección de sombras: normalización de luminosidad en superficie
    if shadow_removal:
        colors = _remove_shadow_from_colors(colors, is_surface)

    return VoxelGrid(positions, colors, is_surface, (W, H, D), shape_hints)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _scale_mesh(mesh: trimesh.Trimesh, W: int, H: int, D: int) -> trimesh.Trimesh:
    """
    Escala y traslada la malla para que su bounding box quede en [0,W]x[0,H]x[0,D].
    Preserva las proporciones (fit uniforme) y centra en las dimensiones sobrantes.
    """
    bb_min = mesh.bounds[0]
    bb_max = mesh.bounds[1]
    extent = bb_max - bb_min

    # Evitar división por cero en dimensiones degeneradas
    extent = np.where(extent < 1e-6, 1.0, extent)

    # Factor de escala uniforme (preservar proporciones)
    scale_factors = np.array([W, H, D], dtype=float) / extent
    scale = np.min(scale_factors)  # fit dentro de target_size

    # Trasladar al origen primero, escalar, luego centrar
    mesh_copy = mesh.copy()
    mesh_copy.vertices -= bb_min
    mesh_copy.vertices *= scale

    # Centrar en las dimensiones objetivo
    new_extent = (bb_max - bb_min) * scale
    offset = (np.array([W, H, D]) - new_extent) / 2.0
    mesh_copy.vertices += offset

    return mesh_copy


def _find_surface_voxels(
    positions: np.ndarray,
    occupied: np.ndarray,
    W: int, H: int, D: int,
) -> np.ndarray:
    """
    Determina cuáles vóxeles están en la superficie (tienen al menos
    un vecino en las 6 direcciones cardinales que es aire).
    Recibe el grid 3D booleano ya construido (reutilizable).
    """
    x, y, z = positions[:, 0], positions[:, 1], positions[:, 2]
    is_surface = np.zeros(len(positions), dtype=bool)

    for dx, dy, dz in [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]:
        nx = x + dx
        ny = y + dy
        nz = z + dz
        oob = (nx < 0) | (nx >= W) | (ny < 0) | (ny >= H) | (nz < 0) | (nz >= D)
        nx_safe = np.clip(nx, 0, W - 1)
        ny_safe = np.clip(ny, 0, H - 1)
        nz_safe = np.clip(nz, 0, D - 1)
        free = ~occupied[nx_safe, ny_safe, nz_safe]
        is_surface |= oob | free

    return is_surface


def _compute_shape_hints(
    positions: np.ndarray,
    is_surface: np.ndarray,
    occupied: np.ndarray,
    W: int, H: int, D: int,
) -> np.ndarray:
    """
    Calcula el tipo de forma óptima para cada vóxel de superficie basándose
    en la normal estimada (a partir de qué caras están expuestas al aire).

    Valores posibles:
      'solid'                          - bloque sólido completo
      'slab_bottom' / 'slab_top'       - losa inferior/superior
      'stair_{facing}_{half}'          - escalera: facing=east/west/north/south,
                                         half=bottom/top
      'wall'                           - muro/pared (poste aislado)
    """
    N = len(positions)
    hints = np.full(N, 'solid', dtype=object)

    surface_idx = np.where(is_surface)[0]
    if len(surface_idx) == 0:
        return hints

    sx = positions[surface_idx, 0]
    sy = positions[surface_idx, 1]
    sz = positions[surface_idx, 2]

    def face_exposed(dx: int, dy: int, dz: int) -> np.ndarray:
        """Devuelve bool array: True si la cara en dirección (dx,dy,dz) es aire."""
        nx_ = sx + dx
        ny_ = sy + dy
        nz_ = sz + dz
        oob = ((nx_ < 0) | (nx_ >= W) |
               (ny_ < 0) | (ny_ >= H) |
               (nz_ < 0) | (nz_ >= D))
        nx_c = np.clip(nx_, 0, W - 1)
        ny_c = np.clip(ny_, 0, H - 1)
        nz_c = np.clip(nz_, 0, D - 1)
        return oob | ~occupied[nx_c, ny_c, nz_c]

    # Componentes de la normal estimada (+1 si expuesta, -1 si tapada)
    norm_x = face_exposed( 1, 0, 0).astype(np.float32) - face_exposed(-1, 0, 0).astype(np.float32)  # East - West
    norm_y = face_exposed( 0, 1, 0).astype(np.float32) - face_exposed( 0,-1, 0).astype(np.float32)  # Up - Down
    norm_z = face_exposed( 0, 0, 1).astype(np.float32) - face_exposed( 0, 0,-1).astype(np.float32)  # South - North

    # Caras horizontales expuestas (para detectar postes)
    h_exp = (face_exposed(1,0,0).astype(int) + face_exposed(-1,0,0).astype(int) +
             face_exposed(0,0,1).astype(int) + face_exposed(0,0,-1).astype(int))

    abs_nx = np.abs(norm_x)
    abs_ny = np.abs(norm_y)
    abs_nz = np.abs(norm_z)
    abs_nh = np.maximum(abs_nx, abs_nz)  # componente horizontal dominante

    sh = np.full(len(surface_idx), 'solid', dtype=object)

    # Muro: todas las caras horizontales expuestas (poste/columna aislada)
    wall_mask = h_exp >= 4
    sh[wall_mask] = 'wall'

    remaining = ~wall_mask

    # Losa: normal vertical claramente dominante sobre la horizontal
    # norm_y > 0 = cara superior expuesta -> slab_top (queda a ras del bloque completo)
    # norm_y < 0 = cara inferior expuesta -> slab_bottom (volteada, como cielo raso)
    slab_mask = remaining & (abs_ny >= 1.5 * abs_nh) & (abs_ny >= 1.0)
    sh[slab_mask & (norm_y >= 0)] = 'slab_top'
    sh[slab_mask & (norm_y <  0)] = 'slab_bottom'

    # Escalera: mezcla de componente horizontal y vertical
    stair_mask = remaining & ~slab_mask & (abs_nh >= 0.5) & (abs_ny >= 0.5)
    x_dom = abs_nx >= abs_nz  # eje X más dominante que Z

    # En Minecraft, facing = direccion hacia donde SUBEN las escaleras (el lado alto).
    # Si la cara ESTE esta expuesta (norm_x > 0), el escalon visible mira al este
    # => las escaleras suben hacia el OESTE => facing=west (opuesto a la normal).
    sh[stair_mask & x_dom  & (norm_x >  0) & (norm_y >= 0)] = 'stair_west_bottom'
    sh[stair_mask & x_dom  & (norm_x >  0) & (norm_y <  0)] = 'stair_west_top'
    sh[stair_mask & x_dom  & (norm_x <= 0) & (norm_y >= 0)] = 'stair_east_bottom'
    sh[stair_mask & x_dom  & (norm_x <= 0) & (norm_y <  0)] = 'stair_east_top'
    sh[stair_mask & ~x_dom & (norm_z >  0) & (norm_y >= 0)] = 'stair_north_bottom'
    sh[stair_mask & ~x_dom & (norm_z >  0) & (norm_y <  0)] = 'stair_north_top'
    sh[stair_mask & ~x_dom & (norm_z <= 0) & (norm_y >= 0)] = 'stair_south_bottom'
    sh[stair_mask & ~x_dom & (norm_z <= 0) & (norm_y <  0)] = 'stair_south_top'

    hints[surface_idx] = sh
    return hints


def _remove_shadow_from_colors(
    colors: np.ndarray,
    is_surface: np.ndarray,
) -> np.ndarray:
    """
    Normaliza la luminosidad de los vóxeles de superficie para compensar
    sombras bakeadas en la textura.

    Estrategia:
      1. Convierte los colores RGB de superficie a espacio CIE LAB.
      2. Aplica CLAHE (Contrast Limited Adaptive Histogram Equalization)
         sobre el canal L — sube los tonos oscuros por sombra sin saturar
         las zonas ya brillantes, preservando los matices de color.
      3. Reconvierte a RGB y escribe de vuelta.
    """
    from skimage import color as _skc, exposure as _skexp

    result = colors.copy()
    surf_idx = np.where(is_surface)[0]
    if len(surf_idx) == 0:
        return result

    rgb = result[surf_idx, :3].astype(np.float32) / 255.0
    lab = _skc.rgb2lab(rgb.reshape(1, -1, 3)).reshape(-1, 3)  # (N, 3)

    # Canal L está en [0, 100]; normalizamos a [0,1] para CLAHE
    L = lab[:, 0] / 100.0  # → [0,1]
    L_eq = _skexp.equalize_adapthist(
        L.reshape(1, -1),   # 2D requerido por skimage
        clip_limit=0.03,
        nbins=256,
    ).reshape(-1)
    lab[:, 0] = L_eq * 100.0

    rgb_out = _skc.lab2rgb(lab.reshape(1, -1, 3)).reshape(-1, 3)
    rgb_out = np.clip(rgb_out * 255.0, 0, 255).astype(np.uint8)
    result[surf_idx, :3] = rgb_out
    return result


def _extract_voxel_colors(
    mesh: trimesh.Trimesh,
    texture: Image.Image | None,
    positions: np.ndarray,
    is_surface: np.ndarray,
) -> np.ndarray:
    """
    Para cada vóxel de superficie, obtiene el color RGBA muestreando la textura
    en el punto de la malla más cercano al centro del vóxel.

    Returns
    -------
    colors : np.ndarray, shape (N, 4), dtype uint8
        Colores RGBA. Vóxeles interiores tienen (128, 128, 128, 255) por defecto.
    """
    N = len(positions)
    colors = np.full((N, 4), (128, 128, 128, 255), dtype=np.uint8)

    surface_indices = np.where(is_surface)[0]
    if len(surface_indices) == 0:
        return colors

    # Centros de los vóxeles de superficie (offset de 0.5 al centro del cubo)
    surface_centers = positions[surface_indices].astype(float) + 0.5

    # Obtener el punto más cercano en la malla para cada centro
    try:
        closest_pts, distances, triangle_ids = trimesh.proximity.closest_point(
            mesh, surface_centers
        )
    except Exception:
        # Fallback: sin textura, usar color blanco
        colors[surface_indices] = (200, 200, 200, 255)
        return colors

    # Muestrear colores
    if texture is not None and _mesh_has_uvs(mesh):
        sampled = _sample_texture_at_triangles(
            mesh, texture, closest_pts, triangle_ids
        )
    else:
        # Fallback: color de vértice o blanco
        sampled = _sample_vertex_colors(mesh, closest_pts, triangle_ids)

    colors[surface_indices] = sampled
    return colors


def _mesh_has_uvs(mesh: trimesh.Trimesh) -> bool:
    """Comprueba si la malla tiene coordenadas UV válidas."""
    try:
        return (
            hasattr(mesh.visual, "uv")
            and mesh.visual.uv is not None
            and len(mesh.visual.uv) == len(mesh.vertices)
        )
    except Exception:
        return False


def _sample_texture_at_triangles(
    mesh: trimesh.Trimesh,
    texture: Image.Image,
    closest_pts: np.ndarray,
    triangle_ids: np.ndarray,
) -> np.ndarray:
    """
    Muestrea la textura interpolando las UVs de los vértices del triángulo
    usando coordenadas baricéntricas.
    Versión vectorizada con numpy (sin loops Python).

    Returns
    -------
    colors : np.ndarray, shape (N, 4), dtype uint8
    """
    N = len(closest_pts)

    tex_arr = np.array(texture.convert("RGBA"))
    tex_h, tex_w = tex_arr.shape[:2]

    uvs = mesh.visual.uv      # (V, 2)
    faces = mesh.faces        # (F, 3)
    vertices = mesh.vertices  # (V, 3)

    # Índices de vértices para cada triángulo
    tri_verts = faces[triangle_ids]          # (N, 3)
    v0 = vertices[tri_verts[:, 0]]           # (N, 3)
    v1 = vertices[tri_verts[:, 1]]           # (N, 3)
    v2 = vertices[tri_verts[:, 2]]           # (N, 3)

    uv0 = uvs[tri_verts[:, 0]]              # (N, 2)
    uv1 = uvs[tri_verts[:, 1]]              # (N, 2)
    uv2 = uvs[tri_verts[:, 2]]              # (N, 2)

    # Coordenadas baricéntricas vectorizadas
    e0 = v1 - v0  # (N, 3)
    e1 = v2 - v0  # (N, 3)
    e2 = closest_pts - v0  # (N, 3)

    d00 = (e0 * e0).sum(axis=1)
    d01 = (e0 * e1).sum(axis=1)
    d11 = (e1 * e1).sum(axis=1)
    d20 = (e2 * e0).sum(axis=1)
    d21 = (e2 * e1).sum(axis=1)

    denom = d00 * d11 - d01 * d01
    denom = np.where(np.abs(denom) < 1e-10, 1.0, denom)

    bary_v = (d11 * d20 - d01 * d21) / denom   # (N,)
    bary_w = (d00 * d21 - d01 * d20) / denom   # (N,)
    bary_u = 1.0 - bary_v - bary_w             # (N,)

    bary = np.stack([bary_u, bary_v, bary_w], axis=1)  # (N, 3)
    bary = np.clip(bary, 0.0, 1.0)
    bary /= bary.sum(axis=1, keepdims=True) + 1e-10

    # Interpolar UVs
    uv = (bary[:, 0:1] * uv0
          + bary[:, 1:2] * uv1
          + bary[:, 2:3] * uv2)  # (N, 2)

    # Convertir UV [0,1] → píxel (con wrap)
    px = np.floor(uv[:, 0] * tex_w).astype(int) % tex_w
    py = np.floor((1.0 - uv[:, 1]) * tex_h).astype(int) % tex_h

    colors = tex_arr[py, px]  # (N, 4)
    return colors.astype(np.uint8)


def _sample_vertex_colors(
    mesh: trimesh.Trimesh,
    closest_pts: np.ndarray,
    triangle_ids: np.ndarray,
) -> np.ndarray:
    """Fallback: usa colores de vértice si existen, o blanco si no."""
    N = len(closest_pts)
    colors = np.full((N, 4), 200, dtype=np.uint8)
    colors[:, 3] = 255

    try:
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
            vc = np.array(mesh.visual.vertex_colors)
            if len(vc) == len(mesh.vertices):
                for i in range(N):
                    tri_idx = triangle_ids[i]
                    if 0 <= tri_idx < len(mesh.faces):
                        v_ids = mesh.faces[tri_idx]
                        # Promedio de los 3 vértices del triángulo
                        avg = vc[v_ids].mean(axis=0).astype(np.uint8)
                        colors[i] = avg[:4] if len(avg) >= 4 else np.append(avg[:3], 255)
    except Exception:
        pass

    return colors
