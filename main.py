"""
main.py
-------
CLI para convertir modelos 3D de Trellis (.glb) a estructuras de Minecraft (.nbt / .schem).

Uso:
    python main.py input.glb --size 64x64x64 --output estructura.nbt
    python main.py input.glb --size 100x80x100 --format schem --output estructura.schem
    python main.py input.glb --max-size 64 --output estructura.nbt
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def parse_size(size_str: str) -> tuple[int, int, int]:
    """Parsea un string 'WxHxD' en una tupla de 3 enteros."""
    try:
        parts = size_str.lower().split("x")
        if len(parts) != 3:
            raise ValueError
        w, h, d = int(parts[0]), int(parts[1]), int(parts[2])
        if w <= 0 or h <= 0 or d <= 0:
            raise ValueError
        return w, h, d
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(
            f"Formato de tamaño inválido: '{size_str}'. Use WxHxD, e.g. 64x64x64"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trellis-to-minecraft",
        description="Convierte modelos 3D de Trellis (.glb) a estructuras de Minecraft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Convertir a .nbt (importar con Structure Block):
  python main.py trellis/sample.glb --size 64x64x64 --output mi_build.nbt

  # Convertir a .schem (para WorldEdit):
  python main.py trellis/sample.glb --size 100x80x100 --format schem --output mi_build.schem

  # Tamaño máximo 48 bloques (límite del Structure Block vanilla):
  python main.py trellis/sample.glb --max-size 48 --output mi_build.nbt

  # Con bloques transparentes para vidrios/cristales:
  python main.py trellis/sample.glb --size 64x64x64 --transparent --output mi_build.nbt
        """,
    )

    parser.add_argument(
        "input",
        help="Ruta al archivo .glb de Trellis",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Ruta del archivo de salida. Por defecto: <input>.<formato>",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["nbt", "schem"],
        default="nbt",
        help="Formato de salida: 'nbt' (Structure Block) o 'schem' (WorldEdit). Default: nbt",
    )

    size_group = parser.add_mutually_exclusive_group(required=True)
    size_group.add_argument(
        "--size", "-s",
        type=parse_size,
        metavar="WxHxD",
        help="Tamaño objetivo en bloques de Minecraft, e.g. 64x64x64",
    )
    size_group.add_argument(
        "--max-size",
        type=int,
        metavar="N",
        help="Tamaño máximo en bloques en cualquier eje (preserva proporciones)",
    )

    parser.add_argument(
        "--hollow",
        action="store_true",
        default=False,
        help="Generar estructura hueca (solo superficie). Por defecto es sólida.",
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        default=False,
        help="Incluir bloques de vidrio/transparentes en el matching",
    )
    parser.add_argument(
        "--interior-block",
        default="minecraft:stone",
        metavar="BLOCK_ID",
        help="Bloque para el relleno interior. Default: minecraft:stone",
    )
    parser.add_argument(
        "--no-shapes",
        action="store_true",
        default=False,
        help="Desactivar bloques con forma (escaleras, losas, muros). Usa solo bloques sólidos.",
    )
    parser.add_argument(
        "--mc-version",
        default="1.20.1",
        metavar="VERSION",
        help=(
            "Versión de Minecraft para el DataVersion del NBT. "
            "Valores: 1.20.1, 1.20.4, 1.21, 1.21.1, 1.21.4. "
            "Default: 1.20.1 (compatible con Create mod más común)"
        ),
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Nombre de la estructura (solo para .schem). Default: nombre del archivo",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar información detallada del proceso",
    )

    palette_group = parser.add_mutually_exclusive_group()
    palette_group.add_argument(
        "--palette",
        metavar="FILE",
        help="Archivo de texto con block IDs permitidos (uno por línea). Limita el matching.",
    )
    palette_group.add_argument(
        "--preset",
        metavar="NAME",
        help="Preset de paleta integrado. Opciones: Todo, Medieval, Moderno, Nether, Fantasy, "
             "Solo Concreto, Solo Lana, Solo Piedra",
    )

    return parser


def _resolve_palette(args) -> list[str] | None:
    """Resuelve allowed_blocks desde --palette o --preset."""
    if args.palette:
        try:
            lines = Path(args.palette).read_text(encoding="utf-8").splitlines()
            ids = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
            if not ids:
                print(f"Advertencia: el archivo de paleta '{args.palette}' está vacío.")
                return None
            print(f"      Paleta cargada: {len(ids)} bloques desde '{args.palette}'")
            return ids
        except OSError as e:
            print(f"Error al leer paleta: {e}", file=sys.stderr)
            return None

    if args.preset:
        from src.block_colors import PRESETS
        ids = PRESETS.get(args.preset)
        if ids is None and args.preset != "Todo":
            available = ", ".join(PRESETS.keys())
            print(f"Advertencia: preset '{args.preset}' no reconocido. Disponibles: {available}")
            return None
        if ids is not None:
            print(f"      Preset '{args.preset}': {len(ids)} bloques")
        return ids

    return None


def compute_size_from_max(mesh_extent: list[float], max_size: int) -> tuple[int, int, int]:
    """Calcula el tamaño objetivo preservando proporciones dado un máximo."""
    import numpy as np
    extent = np.array(mesh_extent)
    scale = max_size / extent.max()
    w, h, d = np.maximum((extent * scale).round().astype(int), 1)
    return int(w), int(h), int(d)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: El archivo '{input_path}' no existe.", file=sys.stderr)
        return 1
    if input_path.suffix.lower() != ".glb":
        print(f"Advertencia: El archivo no tiene extensión .glb: '{input_path}'")

    # Importar módulos (lazy para evitar carga lenta si hay error de CLI)
    print("Cargando módulos...")
    from src.glb_loader import load_glb, get_mesh_info, GLBLoadError
    from src.voxelizer import voxelize
    from src.block_matcher import BlockMatcher
    from src.nbt_writer import write_nbt
    from src.schem_writer import write_schem

    # ── Paso 1: Cargar GLB ────────────────────────────────────────────────
    print(f"\n[1/4] Cargando {input_path.name}...")
    t0 = time.perf_counter()
    try:
        mesh, texture = load_glb(str(input_path))
    except GLBLoadError as e:
        print(f"Error al cargar GLB: {e}", file=sys.stderr)
        return 1

    mesh_info = get_mesh_info(mesh)
    if args.verbose:
        print(f"      Vértices: {mesh_info['vertices']:,}")
        print(f"      Caras: {mesh_info['faces']:,}")
        print(f"      Extensión: {[f'{v:.3f}' for v in mesh_info['extent']]}")
        print(f"      Tiene UVs: {mesh_info['has_uvs']}")
        print(f"      Tiene textura: {texture is not None}")
    print(f"      OK ({time.perf_counter() - t0:.1f}s)")

    # ── Calcular tamaño objetivo ──────────────────────────────────────────
    if args.max_size:
        target_size = compute_size_from_max(mesh_info["extent"], args.max_size)
        print(f"      Tamaño calculado (max={args.max_size}): {target_size[0]}x{target_size[1]}x{target_size[2]}")
    else:
        target_size = args.size

    W, H, D = target_size
    print(f"      Tamaño objetivo: {W}×{H}×{D} bloques")

    # ── Paso 2: Voxelizar ─────────────────────────────────────────────────
    print(f"\n[2/4] Voxelizando ({W}×{H}×{D})...")
    t1 = time.perf_counter()
    try:
        grid = voxelize(
            mesh,
            texture,
            target_size,
            fill_interior=not args.hollow,
        )
    except Exception as e:
        print(f"Error durante la voxelización: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    n_total = len(grid.positions)
    n_surface = grid.is_surface.sum()
    n_interior = n_total - n_surface
    print(f"      Vóxeles totales: {n_total:,}")
    print(f"      Superficie: {n_surface:,}  |  Interior: {n_interior:,}")
    print(f"      OK ({time.perf_counter() - t1:.1f}s)")

    # ── Paso 3: Asignar bloques ───────────────────────────────────────────
    print(f"\n[3/4] Asignando bloques (matching de color en LAB)...")
    t2 = time.perf_counter()
    matcher = BlockMatcher(
        use_transparent=args.transparent,
        interior_block=args.interior_block,
        use_shapes=not args.no_shapes,
        allowed_blocks=_resolve_palette(args),
    )
    assignments = matcher.assign_blocks(grid)
    print(f"      OK ({time.perf_counter() - t2:.1f}s)")

    # Mostrar estadísticas de bloques usados
    if args.verbose:
        from collections import Counter
        counts = Counter(a["block"] for a in assignments)
        print("      Top 10 bloques más usados:")
        for block, count in counts.most_common(10):
            print(f"        {block}: {count:,}")

    # ── Paso 4: Escribir archivo ──────────────────────────────────────────
    # Determinar ruta de salida
    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_suffix(f".{args.format}"))

    struct_name = args.name or input_path.stem

    print(f"\n[4/4] Escribiendo {args.format.upper()} -> {output_path}...")
    t3 = time.perf_counter()
    try:
        if args.format == "nbt":
            from src.nbt_writer import MC_DATA_VERSIONS, MC_DATA_VERSION
            data_version = MC_DATA_VERSIONS.get(args.mc_version)
            if data_version is None:
                print(f"Advertencia: versión '{args.mc_version}' no reconocida, usando DataVersion {MC_DATA_VERSION} (1.20.1)")
                data_version = MC_DATA_VERSION
            else:
                print(f"      DataVersion: {data_version} (MC {args.mc_version})")
            write_nbt(assignments, target_size, output_path, data_version=data_version)
        else:
            write_schem(assignments, target_size, output_path, name=struct_name)
    except Exception as e:
        print(f"Error al escribir el archivo: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    total_time = time.perf_counter() - t0
    print(f"\nListo! Tiempo total: {total_time:.1f}s")

    if args.format == "nbt":
        print("\nCómo importar en Minecraft / Create mod:")
        print("  — Con Create mod (Schematic Cannon):")
        print("    1. Copia el .nbt a: .minecraft/schematics/")
        print("    2. En el juego: crafea 'Schematic and Quill' + 'Schematic Table'")
        print("    3. Abre la Schematic Table y selecciona el archivo")
        print("  — Con Structure Block (vanilla):")
        print("    1. Copia el .nbt a: .minecraft/saves/<mundo>/generated/minecraft/structures/")
        print("    2. Coloca un Structure Block -> modo 'Load' -> introduce el nombre (sin .nbt)")
        print(f"    * Versión NBT usada: MC {args.mc_version} (DataVersion {data_version})")
        print("    * Si no carga, usa --mc-version con la versión correcta de tu juego")
    else:
        print("\nCómo importar con WorldEdit:")
        print("  1. Copia el .schem a: plugins/WorldEdit/schematics/ (en servidor)")
        print("     o a: config/worldedit/schematics/ (en singleplayer con Forge/Fabric)")
        print("  2. En el juego: //schem load <nombre>")
        print("  3. Luego: //paste")

    return 0


if __name__ == "__main__":
    sys.exit(main())
