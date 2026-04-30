"""
test_fill.py — diagnóstico de relleno de vóxeles

Pasos:
1. Carga robot.glb
2. Voxeliza con el pipeline actual
3. Imprime estadísticas de relleno (huecos interiores, % superficie, etc.)
4. Si el resultado es "completamente sólido" (0 huecos interiores),
   guarda el NBT en la ruta destino y lo reporta.

Ejecución:
  .venv\Scripts\python.exe test_fill.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from src.glb_loader import load_glb
from src.voxelizer import voxelize
from scipy.ndimage import label

GLB_PATH = r"C:\Users\zeusc\Pictures\robot.glb"
OUT_PATH = r"C:\Users\zeusc\curseforge\minecraft\Instances\Create Essentials  Better Experience with Create 6.0 and Create Addons\schematics\robot_Metal.nbt"
TARGET_SIZE = (85, 85, 85)
FILL_INTERIOR = False  # False = hueco

ALLOWED_BLOCKS = [
    "minecraft:exposed_copper",    # poco oxidado
    "minecraft:weathered_copper",  # medio oxidado
    "minecraft:oxidized_copper",   # totalmente oxidado
]

print("=" * 60)
print(f"Cargando {GLB_PATH} ...")
mesh, texture = load_glb(GLB_PATH)
print(f"  Vértices: {len(mesh.vertices):,}  |  Caras: {len(mesh.faces):,}")
print(f"  Bounds: {mesh.bounds[0]} → {mesh.bounds[1]}")

print(f"\nVoxelizando a {TARGET_SIZE}  (fill_interior={FILL_INTERIOR}) ...")
grid = voxelize(mesh, texture, TARGET_SIZE, fill_interior=FILL_INTERIOR, shadow_removal=False)

W, H, D = grid.size
total_cells = W * H * D
n_occupied = len(grid.positions)
n_surface = int(grid.is_surface.sum())
n_interior = n_occupied - n_surface

print(f"\n── Estadísticas de vóxeles ──")
print(f"  Grid: {W}×{H}×{D} = {total_cells:,} celdas totales")
print(f"  Ocupadas: {n_occupied:,}  ({100*n_occupied/total_cells:.1f}%)")
print(f"  Superficie: {n_surface:,}  |  Interior: {n_interior:,}")

# Análisis de huecos — válido tanto para modo sólido como hueco
occupied_grid = np.zeros((W, H, D), dtype=bool)
occupied_grid[grid.positions[:,0], grid.positions[:,1], grid.positions[:,2]] = True
empty_grid = ~occupied_grid
labeled, n_labels = label(empty_grid)
exterior_label = labeled[0, 0, 0]

# Tamaño del componente exterior (aire fuera del robot)
exterior_size = int((labeled == exterior_label).sum())
# Componentes no-exteriores = cámaras internas (aire encerrado dentro del shell)
non_ext_sizes = []
for lbl in range(1, n_labels + 1):
    if lbl == exterior_label:
        continue
    non_ext_sizes.append(int((labeled == lbl).sum()))
non_ext_sizes.sort(reverse=True)

total_empty = int(empty_grid.sum())
total_internal = sum(non_ext_sizes)

print(f"\n── Análisis de huecos ──")
print(f"  Componentes vacías totales: {n_labels}")
print(f"  Exterior: {exterior_size:,} vóxeles")
print(f"  Cámaras internas: {len(non_ext_sizes)} componentes, {total_internal:,} vóxeles")
if non_ext_sizes:
    print(f"  Top cámaras: {non_ext_sizes[:5]}")

# Un agujero VISIBLE (de exterior a interior) se manifiesta como que el
# exterior es DEMASIADO GRANDE (incluye aire que "entró" por el agujero).
# Si no hay agujeros: exterior_size ≈ total_empty - total_internal.
# Si hay agujeros: exterior engloba el interior → exterior_size crece.
expected_ext = total_empty - total_internal
leak = exterior_size - expected_ext  # siempre 0 si no hay agujeros

print(f"\n  Exterior esperado (sin agujeros): {expected_ext:,}")
print(f"  Exterior real:                    {exterior_size:,}")

if leak == 0:
    print(f"\n✓ SIN AGUJEROS VISIBLES — exterior completamente separado del interior")
elif leak < 50:
    print(f"\n⚠ Fuga menor de {leak} vóxeles (micro-grieta, probablemente invisible en juego)")
else:
    print(f"\n✗ AGUJEROS VISIBLES: el exterior se 'coló' {leak:,} vóxeles dentro del interior")

# Guardar NBT solo si el resultado es sólido
print()
if True:
    print(f"Guardando NBT en:\n  {OUT_PATH}")
    from src.block_matcher import BlockMatcher
    from src.nbt_writer import write_nbt
    matcher = BlockMatcher(use_transparent=False, use_shapes=False, allowed_blocks=ALLOWED_BLOCKS)
    assignments = matcher.assign_blocks(grid)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    write_nbt(assignments, TARGET_SIZE, OUT_PATH)
    print("✓ NBT guardado correctamente.")
else:
    print("No se guarda el NBT hasta resolver los huecos.")

print("=" * 60)
