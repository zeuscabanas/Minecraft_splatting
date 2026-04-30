"""
block_matcher.py
----------------
Mapea colores RGBA de vóxeles al bloque de Minecraft más parecido.

Algoritmo:
  1. Convierte los colores de la base de datos a espacio CIE LAB
     (perceptualmente uniforme: distancia euclidiana ≈ diferencia visual).
  2. Construye un KD-Tree sobre esos colores.
  3. Para cada vóxel, busca el vecino más cercano en LAB → bloque óptimo.

Dependencias: numpy, scipy, scikit-image
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import KDTree
from skimage import color as skcolor

from .block_colors import BLOCK_DATABASE, get_opaque_blocks, block_rgb_array, SHAPED_BLOCK_MAP, PRESETS
from .voxelizer import VoxelGrid


class BlockMatcher:
    """
    Gestiona el matching color→bloque usando KD-Tree en espacio LAB.

    Parameters
    ----------
    use_transparent : bool
        Si True, incluye bloques de vidrio y translúcidos en el pool.
        Útil para zonas semi-transparentes del modelo.
    interior_block : str
        Bloque de Minecraft para el relleno interior.
        Por defecto 'minecraft:stone'.
    use_shapes : bool
        Si True, usa variantes con forma (escaleras, losas, muros).
    allowed_blocks : list[str] | None
        Lista de block IDs permitidos. Si es None, se usan todos.
        Si la lista filtrada queda vacía, se ignora el filtro.
    """

    def __init__(
        self,
        use_transparent: bool = False,
        interior_block: str = "minecraft:stone",
        use_shapes: bool = True,
        allowed_blocks: list[str] | None = None,
        # ── Contextual consistency ────────────────────────────────────────
        region_delta_e: float = 8.0,
        min_region_size: int = 4,
        run_delta_e: float = 10.0,
        min_run_length: int = 3,
    ):
        self.interior_block = interior_block
        self.use_shapes = use_shapes
        self.region_delta_e = region_delta_e
        self.min_region_size = min_region_size
        self.run_delta_e = run_delta_e
        self.min_run_length = min_run_length

        # Seleccionar pool de bloques
        if use_transparent:
            pool = list(BLOCK_DATABASE)
        else:
            pool = get_opaque_blocks()

        # Filtrar por paleta permitida
        if allowed_blocks is not None:
            allowed_set = set(allowed_blocks)
            filtered = [b for b in pool if b["id"] in allowed_set]
            if filtered:          # ignorar filtro si dejaría la paleta vacía
                pool = filtered

        self._blocks = pool

        # Construir KD-Tree en LAB
        rgb_arr = block_rgb_array(self._blocks)          # (N, 3), [0,1]
        rgb_img = rgb_arr.reshape(1, -1, 3)              # (1, N, 3) para skimage
        lab_arr = skcolor.rgb2lab(rgb_img).reshape(-1, 3)  # (N, 3)
        self._tree = KDTree(lab_arr)
        self._lab_colors = lab_arr

        # Mapa id_bloque → índice de paleta (se construye al generar la estructura)
        self._block_ids: list[str] = [b["id"] for b in self._blocks]

    def match(self, rgba_color: np.ndarray) -> str:
        """
        Retorna el ID del bloque más parecido al color dado.

        Parameters
        ----------
        rgba_color : np.ndarray, shape (4,), dtype uint8

        Returns
        -------
        str: e.g. "minecraft:white_concrete"
        """
        rgb_norm = rgba_color[:3].astype(np.float32) / 255.0
        lab = skcolor.rgb2lab(rgb_norm.reshape(1, 1, 3)).reshape(3)
        _, idx = self._tree.query(lab)
        return self._block_ids[int(idx)]

    def match_batch(self, rgba_colors: np.ndarray) -> list[str]:
        """
        Versión vectorizada de match().

        Parameters
        ----------
        rgba_colors : np.ndarray, shape (N, 4), dtype uint8

        Returns
        -------
        list[str]: lista de IDs de bloques, longitud N
        """
        rgb_norm = rgba_colors[:, :3].astype(np.float32) / 255.0
        # skimage espera (H, W, 3)
        lab_arr = skcolor.rgb2lab(rgb_norm.reshape(1, -1, 3)).reshape(-1, 3)
        _, indices = self._tree.query(lab_arr)
        return [self._block_ids[int(i)] for i in indices]

    def assign_blocks(self, grid: VoxelGrid) -> list[dict]:
        """
        Asigna un bloque a cada vóxel del VoxelGrid.

        Los vóxeles de superficie reciben el bloque de color más cercano.
        Los vóxeles interiores reciben self.interior_block.

        Parameters
        ----------
        grid : VoxelGrid

        Returns
        -------
        list[dict]: Lista de dicts {"pos": (x,y,z), "block": "minecraft:xxx"}
        """
        result: list[dict] = []
        N = len(grid.positions)

        # Matching en batch para los vóxeles de superficie
        surface_mask = grid.is_surface
        surface_colors = grid.colors[surface_mask]

        matched_blocks = self.match_batch(surface_colors) if len(surface_colors) > 0 else []
        matched_iter = iter(matched_blocks)

        # Construir result e índice pos→idx
        pos_to_idx: dict[tuple, int] = {}
        surface_indices: list[int] = []

        for i in range(N):
            pos = tuple(int(v) for v in grid.positions[i])
            pos_to_idx[pos] = i
            if surface_mask[i]:
                block_id = next(matched_iter)
                if self.use_shapes:
                    hint = str(grid.shape_hints[i])
                    block_id, props = _apply_shape(block_id, hint)
                else:
                    props = {}
                surface_indices.append(i)
            else:
                block_id = self.interior_block
                props = {}
            entry: dict = {"pos": pos, "block": block_id}
            if props:
                entry["properties"] = props
            result.append(entry)

        # ── Pasada 2: consistencia regional (flood-fill) ──────────────────
        if surface_indices and (self.region_delta_e > 0 or self.run_delta_e > 0):
            surf_colors_rgba = grid.colors[surface_mask]
            rgb_norm = surf_colors_rgba[:, :3].astype(np.float32) / 255.0
            from skimage import color as _skcolor
            lab_surf = _skcolor.rgb2lab(rgb_norm.reshape(1, -1, 3)).reshape(-1, 3)

            if self.region_delta_e > 0:
                _apply_region_consistency(
                    result, pos_to_idx, lab_surf, surface_indices,
                    self.region_delta_e, self.min_region_size,
                )

            # ── Pasada 3: consistencia de línea horizontal ────────────────
            if self.run_delta_e > 0:
                _apply_run_consistency(
                    result, pos_to_idx, lab_surf, surface_indices,
                    self.run_delta_e, self.min_run_length,
                )

        # Calcular conexiones de muros según vecinos en la estructura
        if self.use_shapes:
            _fix_wall_connections(result)

        return result


# ---------------------------------------------------------------------------
# Pasada 2: Consistencia regional (flood-fill por color + geometría)
# ---------------------------------------------------------------------------

def _apply_region_consistency(
    assignments: list[dict],
    pos_to_idx: dict[tuple, int],
    lab_colors: np.ndarray,       # (N,3) — solo vóxeles de superficie, mismo orden que assignments filtrado
    surface_indices: list[int],   # índices en assignments[] que son superficie
    region_delta_e: float,
    min_region_size: int,
) -> None:
    """
    Flood-fill sobre la superficie: agrupa vóxeles adyacentes cuyo color LAB
    difiere en menos de region_delta_e. Dentro de cada región >= min_region_size
    vóxeles, elige el bloque de la moda y lo asigna a todos los miembros.
    Los bloques con forma (propiedades no vacías) mantienen sus properties;
    solo se sustituye el block_id base.
    """
    if not surface_indices:
        return

    # Mapa pos → índice local en surface_indices (para lab_colors)
    surf_set = set(surface_indices)
    pos_to_surf: dict[tuple, int] = {}
    for local_i, global_i in enumerate(surface_indices):
        pos_to_surf[assignments[global_i]["pos"]] = local_i

    region_id = np.full(len(surface_indices), -1, dtype=np.int32)
    current_region = 0

    NEIGHBORS_6 = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]

    for start_local in range(len(surface_indices)):
        if region_id[start_local] != -1:
            continue

        # BFS
        queue = [start_local]
        region_id[start_local] = current_region
        members = [start_local]

        head = 0
        while head < len(queue):
            cur = queue[head]; head += 1
            cur_pos = assignments[surface_indices[cur]]["pos"]
            cur_lab = lab_colors[cur]

            for dx, dy, dz in NEIGHBORS_6:
                nb_pos = (cur_pos[0]+dx, cur_pos[1]+dy, cur_pos[2]+dz)
                nb_local = pos_to_surf.get(nb_pos)
                if nb_local is None or region_id[nb_local] != -1:
                    continue
                delta = float(np.linalg.norm(lab_colors[nb_local] - cur_lab))
                if delta <= region_delta_e:
                    region_id[nb_local] = current_region
                    queue.append(nb_local)
                    members.append(nb_local)

        # Si la región es suficientemente grande → moda de bloques
        if len(members) >= min_region_size:
            # Extraer los block IDs base (sin variantes de forma para la votación)
            base_ids = [assignments[surface_indices[m]]["block"] for m in members]
            from collections import Counter
            winner = Counter(base_ids).most_common(1)[0][0]
            for m in members:
                gi = surface_indices[m]
                assignments[gi]["block"] = winner

        current_region += 1


# ---------------------------------------------------------------------------
# Pasada 3: Consistencia de línea horizontal
# ---------------------------------------------------------------------------

def _apply_run_consistency(
    assignments: list[dict],
    pos_to_idx: dict[tuple, int],
    lab_colors: np.ndarray,
    surface_indices: list[int],
    run_delta_e: float,
    min_run_length: int,
) -> None:
    """
    Para cada línea horizontal (eje X fijo: recorre Z, y también eje Z fijo:
    recorre X) detecta runs de vóxeles adyacentes de superficie cuyo color
    varía menos de run_delta_e. Si el run tiene >= min_run_length vóxeles,
    asigna a todos el bloque de la moda del run.
    Esto corrige alternancias residuales en filas uniformes después del flood-fill.
    """
    if not surface_indices:
        return

    from collections import Counter

    pos_to_surf: dict[tuple, int] = {}
    for local_i, global_i in enumerate(surface_indices):
        pos_to_surf[assignments[global_i]["pos"]] = local_i

    def _process_run(run: list[int]) -> None:
        if len(run) < min_run_length:
            return
        base_ids = [assignments[surface_indices[m]]["block"] for m in run]
        winner = Counter(base_ids).most_common(1)[0][0]
        for m in run:
            assignments[surface_indices[m]]["block"] = winner

    # Agrupar posiciones por (Y, Z) → barrer eje X
    from collections import defaultdict
    yz_groups: dict[tuple, list[tuple]] = defaultdict(list)
    xy_groups: dict[tuple, list[tuple]] = defaultdict(list)

    for local_i, global_i in enumerate(surface_indices):
        x, y, z = assignments[global_i]["pos"]
        yz_groups[(y, z)].append((x, local_i))
        xy_groups[(x, y)].append((z, local_i))

    def _scan_axis(groups: dict) -> None:
        for coords in groups.values():
            coords.sort(key=lambda t: t[0])
            run: list[int] = []
            prev_coord = None
            prev_lab = None

            for coord, local_i in coords:
                cur_lab = lab_colors[local_i]
                if (prev_coord is not None
                        and coord == prev_coord + 1
                        and float(np.linalg.norm(cur_lab - prev_lab)) <= run_delta_e):
                    run.append(local_i)
                else:
                    _process_run(run)
                    run = [local_i]
                prev_coord = coord
                prev_lab = cur_lab

            _process_run(run)

    _scan_axis(yz_groups)   # runs en eje X
    _scan_axis(xy_groups)   # runs en eje Z


# ---------------------------------------------------------------------------
# Funciones auxiliares de formas
# ---------------------------------------------------------------------------

def _apply_shape(block_id: str, hint: str) -> tuple[str, dict]:
    """
    Dado el ID del bloque sólido y el hint de forma, devuelve
    (block_id_final, properties_dict).
    Si no existe variante para la forma pedida, devuelve el bloque sólido.
    """
    if hint == 'solid':
        return block_id, {}

    variants = SHAPED_BLOCK_MAP.get(block_id, {})

    if hint == 'wall':
        wall = variants.get('wall')
        if wall:
            # Las conexiones se calculan en _fix_wall_connections
            return wall, {"east": "none", "north": "none", "south": "none",
                          "up": "true", "west": "none", "waterlogged": "false"}

    elif hint in ('slab_bottom', 'slab_top'):
        slab = variants.get('slab')
        if slab:
            half = 'bottom' if hint == 'slab_bottom' else 'top'
            return slab, {"type": half, "waterlogged": "false"}

    elif hint.startswith('stair_'):
        parts = hint.split('_')  # ['stair', 'east'/'west'/..., 'bottom'/'top']
        stair = variants.get('stair')
        if stair and len(parts) >= 3:
            facing = parts[1]
            half = parts[2]
            return stair, {"facing": facing, "half": half,
                           "shape": "straight", "waterlogged": "false"}

    return block_id, {}


def _fix_wall_connections(assignments: list[dict]) -> None:
    """
    Post-proceso: calcula las propiedades de conexión de los bloques de muro
    (east/west/north/south) mirando qué bloques hay en las posiciones adyacentes.
    """
    pos_to_block: dict[tuple, str] = {a["pos"]: a["block"] for a in assignments}

    def connects(nb: str) -> bool:
        return bool(nb) and nb != "minecraft:air"

    for a in assignments:
        if "properties" not in a or "east" not in a["properties"]:
            continue
        x, y, z = a["pos"]
        p = a["properties"]
        p["east"]  = "low" if connects(pos_to_block.get((x + 1, y, z), "")) else "none"
        p["west"]  = "low" if connects(pos_to_block.get((x - 1, y, z), "")) else "none"
        p["south"] = "low" if connects(pos_to_block.get((x, y, z + 1), "")) else "none"
        p["north"] = "low" if connects(pos_to_block.get((x, y, z - 1), "")) else "none"
