# Minecraft Splatting 🎮

Convert any image or 3D model into a **Minecraft structure** (.nbt / .schem) using [TRELLIS](https://github.com/microsoft/TRELLIS) as the AI 3D reconstruction backend.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## What it does

1. **Image → 3D model** — Feed a photo or AI-generated image into TRELLIS; it generates a textured GLB mesh.
2. **3D model → Voxels** — The mesh is voxelized to any target block size (e.g. 32×32×32).
3. **Voxels → Minecraft blocks** — Each voxel's color is matched to the closest Minecraft block using perceptual color distance (CIE LAB + KD-Tree).
4. **Export** — Output as `.nbt` (Structure Block / Create mod) or `.schem` (WorldEdit / Litematica).

---

## Features

- **Interactive GUI** built with CustomTkinter
- **3D GLB preview** with mouse drag rotation and scroll zoom
- **TRELLIS integration** — runs the AI pipeline in a separate Python 3.12 subprocess
- **Perceptual color matching** — CIE LAB color space + KD-Tree for fast, accurate block selection
- **3-pass contextual consistency**:
  - Flood-fill region segmentation (groups similar-color adjacent voxels)
  - Horizontal run consistency (smooths same-material lines)
- **Shadow removal** — CLAHE luminosity normalization to compensate baked shadows in TRELLIS textures
- **Shape variants** — automatic stairs, slabs and walls based on voxel geometry
- **Transparent block support** — glass and translucent blocks for semi-transparent zones
- **Structure splitting** — fracture into 8 spatial octants for large builds (bypasses the 250 KB NBT limit in Create mod)
- **Minecraft version selector** (1.20.1 → 1.21.4)
- **Block palette editor** — enable/disable individual blocks or use presets

---

## Requirements

### GUI / Python 3.13 environment

```
customtkinter>=5.2
trimesh>=4.0
Pillow>=10.0
numpy
scipy
scikit-image
nbtlib
```

Install into the `.venv` virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install customtkinter trimesh Pillow numpy scipy scikit-image nbtlib
```

### TRELLIS (Python 3.12 environment)

TRELLIS requires Python 3.12 and its own dependencies (PyTorch, spconv, etc.).  
Follow the official setup: https://github.com/microsoft/TRELLIS

Expected install path: `C:\Users\<user>\TRELLIS`

> **Note:** `flash_attn` and `xformers` are **not required**. This project patches TRELLIS sparse attention to use PyTorch native SDPA (`torch.nn.functional.scaled_dot_product_attention`).

---

## Setup

```bash
git clone https://github.com/zeuscabanas/Minecraft_splatting.git
cd Minecraft_splatting
python -m venv .venv
.venv\Scripts\activate
pip install customtkinter trimesh Pillow numpy scipy scikit-image nbtlib
```

Run the GUI:

```bash
.venv\Scripts\python.exe gui.py
```

---

## Usage

### PASO 0 — Image → GLB (TRELLIS)
1. Select an input image (PNG/JPG)
2. Adjust simplification and texture size
3. Click **Generar GLB** — TRELLIS will run in the background and generate a `.glb` file
4. The GLB preview panel will show the result; drag to rotate, scroll to zoom

### PASO 1 — GLB → Minecraft structure
1. Select or confirm the GLB path
2. Set the output path (`.nbt` or `.schem`)
3. Configure options:
   - Target size (W×H×D or max dimension)
   - Hollow / filled interior
   - Stairs, slabs, walls
   - Transparent blocks
   - Shadow correction
   - Contextual consistency sliders (ΔE region, run length…)
   - Split into 8 parts (for large structures)
4. Click **Convertir a Minecraft**

### Loading in Minecraft
- `.nbt` → place with a **Structure Block** (Load mode) or use [Create mod](https://modrinth.com/mod/create) schematic cannon
- `.schem` → import with **WorldEdit** (`//schem load`) or **Litematica**

---

## Project Structure

```
trellis-to-minecraft/
├── gui.py                  # Main GUI application (CustomTkinter)
├── main.py                 # CLI entrypoint
├── src/
│   ├── trellis_runner.py   # Subprocess bridge → TRELLIS Python 3.12
│   ├── trellis_worker.py   # TRELLIS pipeline worker (runs under py -3.12)
│   ├── glb_loader.py       # GLB → trimesh loader
│   ├── voxelizer.py        # Mesh → VoxelGrid + shadow removal
│   ├── block_matcher.py    # Color → Minecraft block (KD-Tree + consistency)
│   ├── nbt_writer.py       # VoxelGrid → .nbt + octant splitter
│   ├── schem_writer.py     # VoxelGrid → .schem (Sponge v3)
│   ├── block_colors.py     # Minecraft block color database
│   └── texture_cache.py    # Texture caching utilities
└── texture_cache.py
```

---

## TRELLIS Patches

This project patches 4 files inside the TRELLIS installation to add SDPA attention backend support (required when `flash_attn` / `xformers` are not installed):

| File | Change |
|---|---|
| `trellis/modules/sparse/__init__.py` | Accept `'sdpa'` as valid attention backend |
| `trellis/modules/sparse/attention/full_attn.py` | SDPA compute path |
| `trellis/modules/sparse/attention/serialized_attn.py` | SDPA compute path (uniform + variable length) |
| `trellis/modules/sparse/attention/windowed_attn.py` | SDPA compute path (uniform + variable length) |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgements

- [TRELLIS](https://github.com/microsoft/TRELLIS) by Microsoft Research — 3D generation model
- [trimesh](https://github.com/mikedh/trimesh) — mesh processing
- [nbtlib](https://github.com/vberlier/nbtlib) — NBT file format
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — modern Tkinter UI
