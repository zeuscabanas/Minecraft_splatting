"""
schem_writer.py
---------------
Escribe el resultado del block_matcher en formato .schem (Sponge Schematic v3).

Compatible con WorldEdit, Litematica, Schematica (Minecraft Java Edition).
Formato más flexible que .nbt para estructuras grandes (sin límite de 48 bloques).

Estructura NBT (Sponge Schematic v3):
  root (Compound)
  ├── Version: Int (3)
  ├── DataVersion: Int  (MC data version)
  ├── Metadata: Compound
  │     ├── Name: String
  │     ├── Author: String
  │     └── Date: Long (timestamp ms)
  ├── Width: Short
  ├── Height: Short
  ├── Length: Short
  ├── Offset: IntArray [0, 0, 0]
  ├── PaletteMax: Int
  ├── Palette: Compound  {"minecraft:air": 0, "minecraft:stone": 1, ...}
  ├── BlockData: ByteArray  (índices en VarInt encoding)
  └── BlockEntities: List (vacío)

Nota sobre VarInt:
  Los índices de paleta se codifican como VarInt (variable-length integer).
  Valores < 128: 1 byte. Valores < 16384: 2 bytes, etc.

Dependencias: nbtlib, numpy
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import nbtlib

# DataVersion de Minecraft Java Edition 1.21.4
MC_DATA_VERSION = 3953
SCHEM_VERSION = 3


def write_schem(
    block_assignments: list[dict],
    size: tuple[int, int, int],
    output_path: str,
    name: str = "trellis_structure",
    author: str = "trellis-to-minecraft",
) -> None:
    """
    Escribe la estructura en formato .schem (Sponge Schematic v3).

    Parameters
    ----------
    block_assignments : list[dict]
        Lista de dicts {"pos": (x, y, z), "block": "minecraft:xxx"}.
    size : (width, height, depth)
        Dimensiones de la estructura.
    output_path : str
        Ruta del archivo .schem a crear.
    name : str
        Nombre de la estructura (metadata).
    author : str
        Autor de la estructura (metadata).
    """
    W, H, D = size

    # 1. Construir mapa posición → bloque para acceso O(1)
    pos_to_block: dict[tuple[int, int, int], str] = {}
    for assignment in block_assignments:
        pos_to_block[assignment["pos"]] = assignment["block"]

    # 2. Construir paleta (bloques únicos)
    unique_blocks = list(dict.fromkeys(a["block"] for a in block_assignments))
    if "minecraft:air" not in unique_blocks:
        unique_blocks.insert(0, "minecraft:air")
    block_to_idx = {b: i for i, b in enumerate(unique_blocks)}

    palette_nbt = nbtlib.Compound(
        {b: nbtlib.Int(i) for b, i in block_to_idx.items()}
    )

    # 3. Codificar BlockData en VarInt
    # Orden: X aumenta más rápido, luego Z, luego Y (YZX)
    # Index = (Y * Length + Z) * Width + X
    block_indices = np.zeros(W * H * D, dtype=np.int32)
    air_idx = block_to_idx["minecraft:air"]

    for (x, y, z), block_id in pos_to_block.items():
        linear_idx = (y * D + z) * W + x
        if 0 <= linear_idx < len(block_indices):
            block_indices[linear_idx] = block_to_idx.get(block_id, air_idx)

    varint_bytes = _encode_varint_array(block_indices)
    block_data_nbt = nbtlib.ByteArray(np.frombuffer(varint_bytes, dtype=np.int8))

    # 4. Construir NBT raíz
    now_ms = int(time.time() * 1000)

    nbt_root = nbtlib.File({
        "": nbtlib.Compound({
            "Version": nbtlib.Int(SCHEM_VERSION),
            "DataVersion": nbtlib.Int(MC_DATA_VERSION),
            "Metadata": nbtlib.Compound({
                "Name": nbtlib.String(name),
                "Author": nbtlib.String(author),
                "Date": nbtlib.Long(now_ms),
            }),
            "Width": nbtlib.Short(W),
            "Height": nbtlib.Short(H),
            "Length": nbtlib.Short(D),
            "Offset": nbtlib.IntArray([0, 0, 0]),
            "PaletteMax": nbtlib.Int(len(unique_blocks)),
            "Palette": palette_nbt,
            "BlockData": block_data_nbt,
            "BlockEntities": nbtlib.List[nbtlib.Compound](),
        })
    })

    # 5. Guardar comprimido con GZip
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nbt_root.save(str(out_path), gzipped=True)

    print(f"[SCHEM] Escrito: {out_path}")
    print(f"        Tamaño: {W}×{H}×{D} bloques")
    print(f"        Bloques totales: {len(block_assignments)}")
    print(f"        Tipos únicos: {len(unique_blocks)}")


# ---------------------------------------------------------------------------
# VarInt encoding
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    """Codifica un entero en formato VarInt (little-endian, 7 bits por byte)."""
    buf = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value != 0:
            b |= 0x80
        buf.append(b)
        if value == 0:
            break
    return bytes(buf)


def _encode_varint_array(values: np.ndarray) -> bytes:
    """Codifica un array de enteros como secuencia de VarInts."""
    parts = [_encode_varint(int(v)) for v in values]
    return b"".join(parts)
