"""
nbt_writer.py
-------------
Escribe el resultado del block_matcher en formato .nbt (Minecraft Structure Block).

Formato: NBT comprimido con GZip.
Compatible con Minecraft Java Edition (importar con Structure Block en modo Load
o con /place template).

Estructura NBT:
  root (Compound)
  ├── DataVersion: Int  (3953 = MC 1.21.4)
  ├── size: List[Int]   [width, height, depth]
  ├── palette: List[Compound]
  │     └── {Name: String}
  ├── blocks: List[Compound]
  │     └── {state: Int, pos: List[Int]}
  └── entities: List (vacío)

Dependencias: nbtlib
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from io import BytesIO

import nbtlib

# DataVersions de Minecraft Java Edition
MC_DATA_VERSIONS = {
    "1.20.1": 3465,
    "1.20.4": 3700,
    "1.21":   3953,
    "1.21.1": 3953,
    "1.21.4": 4189,
}
# Versión por defecto (Create mod más común = 1.20.1)
MC_DATA_VERSION = MC_DATA_VERSIONS["1.20.1"]


def write_nbt(
    block_assignments: list[dict],
    size: tuple[int, int, int],
    output_path: str,
    data_version: int = MC_DATA_VERSION,
) -> None:
    """
    Escribe la estructura en formato .nbt comprimido con GZip.

    Parameters
    ----------
    block_assignments : list[dict]
        Lista de dicts {"pos": (x, y, z), "block": "minecraft:xxx"}.
        Output de BlockMatcher.assign_blocks().
    size : (width, height, depth)
        Dimensiones de la estructura en bloques.
    output_path : str
        Ruta del archivo .nbt a crear.
    data_version : int
        DataVersion de Minecraft. Usar MC_DATA_VERSIONS para obtener el valor
        correcto para tu versión del juego.
    """
    W, H, D = size

    # 1. Construir la paleta con clave (nombre, propiedades_frozen)
    #    El mismo bloque con diferentes propiedades = entradas distintas en la paleta
    def _block_key(assignment: dict) -> tuple:
        props = assignment.get("properties", {})
        return (assignment["block"], tuple(sorted(props.items())))

    unique_keys = list(dict.fromkeys(_block_key(a) for a in block_assignments))
    air_key = ("minecraft:air", ())
    if air_key not in unique_keys:
        unique_keys.insert(0, air_key)
    key_to_idx = {k: i for i, k in enumerate(unique_keys)}

    # 2. Construir la lista NBT de palette
    palette_nbt = nbtlib.List[nbtlib.Compound]()
    for (block_name, props_tuple) in unique_keys:
        entry: dict = {"Name": nbtlib.String(block_name)}
        if props_tuple:
            entry["Properties"] = nbtlib.Compound(
                {k: nbtlib.String(v) for k, v in props_tuple}
            )
        palette_nbt.append(nbtlib.Compound(entry))

    # 3. Construir la lista NBT de blocks
    blocks_nbt = nbtlib.List[nbtlib.Compound]()
    for assignment in block_assignments:
        x, y, z = assignment["pos"]
        state_idx = key_to_idx[_block_key(assignment)]
        blocks_nbt.append(
            nbtlib.Compound({
                "state": nbtlib.Int(state_idx),
                "pos": nbtlib.List[nbtlib.Int]([
                    nbtlib.Int(x),
                    nbtlib.Int(y),
                    nbtlib.Int(z),
                ]),
            })
        )

    # 4. Construir el NBT raíz
    # NOTA: nbtlib.File ES el root compound — no anidar en Compound extra
    nbt_root = nbtlib.File({
        "DataVersion": nbtlib.Int(data_version),
        "size": nbtlib.List[nbtlib.Int]([
            nbtlib.Int(W),
            nbtlib.Int(H),
            nbtlib.Int(D),
        ]),
        "palette": palette_nbt,
        "blocks": blocks_nbt,
        "entities": nbtlib.List[nbtlib.Compound](),
    })

    # 5. Serializar y comprimir con GZip
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nbt_root.save(str(out_path), gzipped=True)

    print(f"[NBT] Escrito: {out_path}")
    print(f"      Tamaño: {W}×{H}×{D} bloques")
    print(f"      Bloques totales: {len(block_assignments)}")
    print(f"      Tipos únicos en paleta: {len(unique_keys)}")


# ---------------------------------------------------------------------------
# Fraccionamiento en octantes (8 fragmentos)
# ---------------------------------------------------------------------------

def split_into_octants(
    block_assignments: list[dict],
    size: tuple[int, int, int],
) -> list[tuple[list[dict], tuple[int, int, int], tuple[int, int, int]]]:
    """
    Divide la estructura en 8 octantes cortando por los planos medios X, Y, Z.

    Returns
    -------
    list of (fragment_assignments, fragment_size, fragment_offset)
        fragment_assignments : bloques del fragmento con posiciones relativas a su origen
        fragment_size        : (W, H, D) del fragmento
        fragment_offset      : (ox, oy, oz) — origen del fragmento en el grid global
                               (útil para colocarlos en el juego)
    """
    W, H, D = size

    mx = W // 2
    my = H // 2
    mz = D // 2

    # 8 octantes definidos por rangos (min_incl, max_excl) en X, Y, Z
    x_ranges = [(0, mx), (mx, W)]
    y_ranges = [(0, my), (my, H)]
    z_ranges = [(0, mz), (mz, D)]

    fragments = []

    for (x0, x1), (y0, y1), (z0, z1) in [
        (xr, yr, zr) for xr in x_ranges for yr in y_ranges for zr in z_ranges
    ]:
        frag_w = x1 - x0
        frag_h = y1 - y0
        frag_d = z1 - z0

        if frag_w <= 0 or frag_h <= 0 or frag_d <= 0:
            continue

        frag_assignments = []
        for a in block_assignments:
            px, py, pz = a["pos"]
            if x0 <= px < x1 and y0 <= py < y1 and z0 <= pz < z1:
                # Posición relativa al origen del fragmento
                entry = dict(a)
                entry["pos"] = (px - x0, py - y0, pz - z0)
                frag_assignments.append(entry)

        fragments.append((
            frag_assignments,
            (frag_w, frag_h, frag_d),
            (x0, y0, z0),
        ))

    return fragments
