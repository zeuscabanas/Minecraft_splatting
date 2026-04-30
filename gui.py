"""
gui.py
------
Interfaz gráfica para el conversor Trellis -> Minecraft.
Ejecutar con:  python gui.py
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, Canvas, Scrollbar
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

# ── Tema ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ── Categorías de la paleta ──────────────────────────────────────────────────
CAT_ORDER: list[tuple[str, str, str]] = [
    # (tag,           label,               emoji)
    ("concrete",   "Concreto",            "🟫"),
    ("wool",       "Lana",                "🐑"),
    ("terracotta", "Terracota",           "🏺"),
    ("wood",       "Madera",              "🪵"),
    ("log",        "Troncos",             "🌲"),
    ("stone",      "Piedra",              "⛏"),
    ("natural",    "Natural",             "🌿"),
    ("metal",      "Metales",             "⚙"),
    ("nether",     "Nether",              "🔥"),
    ("end",        "End",                 "🌌"),
    ("ocean",      "Océano",              "🌊"),
    ("glass",      "Vidrio",              "🪟"),
    ("misc",       "Misceláneos",         "📦"),
]

ICON_PX  = 36    # tamaño del icono en la grid
BORDER_W = 2     # borde cuando está seleccionado
PAD      = 3     # espacio entre celdas

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de imagen
# ──────────────────────────────────────────────────────────────────────────────

def _make_cell_image(pil_img: Image.Image, selected: bool) -> ImageTk.PhotoImage:
    """Crea la imagen de la celda con fondo oscuro y borde opcional."""
    cell = Image.new("RGBA", (ICON_PX, ICON_PX), (42, 42, 42, 255))
    inner = ICON_PX - 4
    icon = pil_img.resize((inner, inner), Image.NEAREST)
    cell.paste(icon, (2, 2), icon)
    if selected:
        draw = ImageDraw.Draw(cell)
        draw.rectangle([0, 0, ICON_PX - 1, ICON_PX - 1],
                        outline=(80, 220, 100), width=BORDER_W)
    return ImageTk.PhotoImage(cell)


# ──────────────────────────────────────────────────────────────────────────────
# Widget: PaletteGrid  (Canvas con scroll)
# ──────────────────────────────────────────────────────────────────────────────

class PaletteGrid(tk.Frame):
    """
    Grid estilo inventario creativo de Minecraft.
    Muestra bloques con su textura real, resalta los seleccionados.
    """

    def __init__(self, master, blocks: list[dict], selected: set[str],
                 on_toggle, **kwargs):
        super().__init__(master, bg="#1e1e1e", **kwargs)
        self._blocks   = blocks
        self._selected = selected    # set mutable compartido con App
        self._on_toggle = on_toggle
        self._imgs: dict[str, ImageTk.PhotoImage] = {}
        self._positions: list[tuple[int, int, int]] = []  # (x, y, idx)
        self._tooltip_win: tk.Toplevel | None = None
        self._last_hover: int | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas = Canvas(self, bg="#1e1e1e", highlightthickness=0)
        sb = Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", self._on_leave)
        self._canvas.bind("<MouseWheel>", lambda e: self._canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

    def set_blocks(self, blocks: list[dict]):
        self._blocks = blocks
        self._redraw()

    def _on_resize(self, _=None):
        self._redraw()

    def _redraw(self):
        from texture_cache import get_texture
        self._canvas.delete("all")
        self._positions.clear()
        self._imgs.clear()

        w = self._canvas.winfo_width()
        if w < 2:
            w = 9 * (ICON_PX + PAD) + PAD
        cols = max(1, (w - PAD) // (ICON_PX + PAD))

        for i, block in enumerate(self._blocks):
            col = i % cols
            row = i // cols
            x = PAD + col * (ICON_PX + PAD)
            y = PAD + row * (ICON_PX + PAD)
            self._positions.append((x, y, i))
            bid = block["id"]
            pil = get_texture(bid, block["rgb"])
            sel = bid in self._selected
            photo = _make_cell_image(pil, sel)
            tag = f"cell_{i}"
            self._canvas.create_image(x, y, anchor="nw", image=photo, tags=(tag, bid))
            self._imgs[tag] = photo

        rows = (len(self._blocks) + cols - 1) // cols if self._blocks else 1
        total_h = rows * (ICON_PX + PAD) + PAD
        self._canvas.configure(scrollregion=(0, 0, w, total_h))

    def _draw_cell(self, idx: int, block: dict):
        if idx >= len(self._positions):
            return
        from texture_cache import get_texture
        x, y, _ = self._positions[idx]
        bid = block["id"]
        pil = get_texture(bid, block["rgb"])
        sel = bid in self._selected
        photo = _make_cell_image(pil, sel)
        tag = f"cell_{idx}"
        self._canvas.delete(tag)
        self._canvas.create_image(x, y, anchor="nw", image=photo, tags=(tag, bid))
        self._imgs[tag] = photo

    def _hit_test(self, ex: int, ey: int) -> int | None:
        ey_adj = ey + int(self._canvas.canvasy(0))
        for x, y, i in self._positions:
            if x <= ex < x + ICON_PX and y <= ey_adj < y + ICON_PX:
                return i
        return None

    def _on_click(self, event):
        idx = self._hit_test(event.x, event.y)
        if idx is None:
            return
        bid = self._blocks[idx]["id"]
        if bid in self._selected:
            self._selected.discard(bid)
        else:
            self._selected.add(bid)
        self._draw_cell(idx, self._blocks[idx])
        self._on_toggle()

    def _on_motion(self, event):
        idx = self._hit_test(event.x, event.y)
        if idx == self._last_hover:
            return
        self._last_hover = idx
        self._hide_tooltip()
        if idx is None:
            return
        bid = self._blocks[idx]["id"]
        name = bid.replace("minecraft:", "").replace("_", " ").title()
        self._show_tooltip(event, name)

    def _on_leave(self, _=None):
        self._last_hover = None
        self._hide_tooltip()

    def _show_tooltip(self, event, text: str):
        win = tk.Toplevel(self)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{event.x_root + 14}+{event.y_root - 10}")
        tk.Label(win, text=text, background="#222222", foreground="#eeeeee",
                 font=("Consolas", 10), padx=6, pady=3,
                 relief="flat", borderwidth=0).pack()
        self._tooltip_win = win

    def _hide_tooltip(self):
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None


# ──────────────────────────────────────────────────────────────────────────────
# App principal
# ──────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Trellis  →  Minecraft  ·  Conversor 3D")
        self.geometry("1240x820")
        self.minsize(1000, 680)

        self._q: queue.Queue = queue.Queue()

        from src.block_colors import BLOCK_DATABASE
        self._all_blocks  = BLOCK_DATABASE
        self._selected: set[str] = {b["id"] for b in BLOCK_DATABASE}
        self._active_cat: str = CAT_ORDER[0][0]

        self._build_ui()
        threading.Thread(target=self._preload_textures, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # Construcción de la UI
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, padx=(10, 4), pady=10, sticky="nsew")
        self._build_left(left)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, padx=(4, 10), pady=10, sticky="nsew")
        self._build_right(right)

        bottom = ctk.CTkFrame(self)
        bottom.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self._build_bottom(bottom)

    # ── Panel izquierdo ───────────────────────────────────────────────────────

    def _build_left(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(1, weight=1)
        r = 0

        ctk.CTkLabel(
            p, text="Trellis  →  Minecraft",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=r, column=0, columnspan=3, padx=14, pady=(14, 6), sticky="w")
        r += 1

        # ── Sección TRELLIS ───────────────────────────────────────────────────
        self._section(p, r, "PASO 0: IMAGEN  \u2192  GLB  (TRELLIS)")
        r += 1

        from src.trellis_runner import is_available as _tsr_avail
        _tsr_ok = _tsr_avail()
        tsr_status = ctk.CTkFrame(p, fg_color="transparent")
        tsr_status.grid(row=r, column=0, columnspan=3, padx=14, pady=(0, 2), sticky="ew")
        if _tsr_ok:
            ctk.CTkLabel(tsr_status, text="\u2705 TRELLIS disponible (Python 3.12)",
                         text_color="#4caf50",
                         font=ctk.CTkFont(size=11)).pack(side="left")
        else:
            ctk.CTkLabel(tsr_status,
                         text=("\u274c TRELLIS no encontrado  |  "
                               r"Requiere C:\Users\zeusc\TRELLIS y Python 3.12"),
                         text_color="#ff6b6b",
                         font=ctk.CTkFont(size=10),
                         wraplength=440).pack(side="left")
        r += 1

        ctk.CTkLabel(p, text="Imagen:").grid(
            row=r, column=0, padx=(14, 4), pady=3, sticky="e")
        self._img_var = ctk.StringVar()
        ctk.CTkEntry(p, textvariable=self._img_var,
                     placeholder_text="ruta/a/foto.png  (PNG / JPG / WEBP)").grid(
            row=r, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkButton(p, text="\U0001f4c2", width=38,
                      command=self._browse_img).grid(
            row=r, column=2, padx=(4, 14), pady=3)
        r += 1

        tsr_opts = ctk.CTkFrame(p, fg_color="transparent")
        tsr_opts.grid(row=r, column=0, columnspan=3, padx=14, pady=(0, 10), sticky="ew")
        self._rmbg = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(tsr_opts, text="Eliminar fondo (rembg)",
                        variable=self._rmbg).pack(side="left", padx=(0, 14))
        self._tsr_btn = ctk.CTkButton(
            tsr_opts, text="\u25b6  Generar GLB",
            width=150, height=30,
            state="normal" if _tsr_ok else "disabled",
            command=self._start_triposr,
        )
        self._tsr_btn.pack(side="right")
        r += 1

        self._section(p, r, "ENTRADA / SALIDA")
        r += 1

        ctk.CTkLabel(p, text="Modelo GLB:").grid(
            row=r, column=0, padx=(14, 4), pady=3, sticky="e")
        self._glb_var = ctk.StringVar()
        ctk.CTkEntry(p, textvariable=self._glb_var,
                     placeholder_text="ruta/al/modelo.glb").grid(
            row=r, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkButton(p, text="📂", width=38,
                      command=self._browse_glb).grid(
            row=r, column=2, padx=(4, 14), pady=3)
        r += 1

        ctk.CTkLabel(p, text="Archivo salida:").grid(
            row=r, column=0, padx=(14, 4), pady=3, sticky="e")
        self._out_var = ctk.StringVar()
        ctk.CTkEntry(p, textvariable=self._out_var,
                     placeholder_text="salida.nbt").grid(
            row=r, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkButton(p, text="📂", width=38,
                      command=self._browse_out).grid(
            row=r, column=2, padx=(4, 14), pady=3)
        r += 1

        self._section(p, r, "TAMAÑO")
        r += 1

        sf1 = ctk.CTkFrame(p, fg_color="transparent")
        sf1.grid(row=r, column=0, columnspan=3, padx=14, pady=2, sticky="ew")
        self._size_mode = ctk.StringVar(value="wxhxd")
        ctk.CTkRadioButton(sf1, text="W × H × D:",
                           variable=self._size_mode, value="wxhxd",
                           command=self._on_size_mode).pack(side="left", padx=(0, 8))
        self._wv = ctk.StringVar(value="64")
        self._hv = ctk.StringVar(value="64")
        self._dv = ctk.StringVar(value="64")
        self._we = ctk.CTkEntry(sf1, textvariable=self._wv, width=56)
        self._we.pack(side="left", padx=2)
        ctk.CTkLabel(sf1, text="×").pack(side="left")
        self._he = ctk.CTkEntry(sf1, textvariable=self._hv, width=56)
        self._he.pack(side="left", padx=2)
        ctk.CTkLabel(sf1, text="×").pack(side="left")
        self._de = ctk.CTkEntry(sf1, textvariable=self._dv, width=56)
        self._de.pack(side="left", padx=2)
        r += 1

        sf2 = ctk.CTkFrame(p, fg_color="transparent")
        sf2.grid(row=r, column=0, columnspan=3, padx=14, pady=2, sticky="ew")
        ctk.CTkRadioButton(sf2, text="Máximo (preserva proporciones):",
                           variable=self._size_mode, value="max",
                           command=self._on_size_mode).pack(side="left", padx=(0, 8))
        self._maxv = ctk.StringVar(value="64")
        self._maxe = ctk.CTkEntry(sf2, textvariable=self._maxv, width=66, state="disabled")
        self._maxe.pack(side="left", padx=2)
        ctk.CTkLabel(sf2, text="bloques").pack(side="left", padx=4)
        r += 1

        self._section(p, r, "OPCIONES")
        r += 1

        of1 = ctk.CTkFrame(p, fg_color="transparent")
        of1.grid(row=r, column=0, columnspan=3, padx=14, pady=2, sticky="ew")
        ctk.CTkLabel(of1, text="Versión MC:").pack(side="left", padx=(0, 4))
        self._mc_ver = ctk.StringVar(value="1.21")
        from src.nbt_writer import MC_DATA_VERSIONS
        ctk.CTkComboBox(of1, values=list(MC_DATA_VERSIONS.keys()),
                        variable=self._mc_ver, width=100).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(of1, text="Formato:").pack(side="left", padx=(0, 4))
        self._fmt = ctk.StringVar(value="nbt")
        ctk.CTkComboBox(of1, values=["nbt", "schem"],
                        variable=self._fmt, width=88,
                        command=self._on_fmt_change).pack(side="left")
        r += 1

        of2 = ctk.CTkFrame(p, fg_color="transparent")
        of2.grid(row=r, column=0, columnspan=3, padx=14, pady=3, sticky="ew")
        self._hollow = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(of2, text="Hueco (sin relleno)",
                        variable=self._hollow).pack(side="left", padx=(0, 14))
        self._shapes = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(of2, text="Escaleras / Losas / Muros",
                        variable=self._shapes).pack(side="left")
        r += 1

        of3 = ctk.CTkFrame(p, fg_color="transparent")
        of3.grid(row=r, column=0, columnspan=3, padx=14, pady=(0, 2), sticky="ew")
        self._transp = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(of3, text="Incluir vidrio / translúcidos en el matching",
                        variable=self._transp).pack(side="left")
        r += 1

        of4 = ctk.CTkFrame(p, fg_color="transparent")
        of4.grid(row=r, column=0, columnspan=3, padx=14, pady=(0, 2), sticky="ew")
        self._shadow_removal = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(of4, text="Corrección de sombras (normalizar luminosidad)",
                        variable=self._shadow_removal).pack(side="left")
        r += 1

        of5 = ctk.CTkFrame(p, fg_color="transparent")
        of5.grid(row=r, column=0, columnspan=3, padx=14, pady=(0, 4), sticky="ew")
        self._split_octants = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(of5, text="Fraccionar en 8 partes (estructuras grandes)",
                        variable=self._split_octants).pack(side="left")
        r += 1

        # ── Consistencia contextual ───────────────────────────────────────
        self._section(p, r, "Consistencia contextual de bloques")
        r += 1

        cc1 = ctk.CTkFrame(p, fg_color="transparent")
        cc1.grid(row=r, column=0, columnspan=3, padx=14, pady=(2, 1), sticky="ew")
        cc1.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cc1, text="ΔE región:", width=90, anchor="w").grid(row=0, column=0)
        self._region_de = ctk.DoubleVar(value=8.0)
        ctk.CTkSlider(cc1, from_=0, to=30, variable=self._region_de,
                      width=160).grid(row=0, column=1, padx=6)
        self._region_de_lbl = ctk.StringVar(value="8.0")
        ctk.CTkLabel(cc1, textvariable=self._region_de_lbl, width=36).grid(row=0, column=2)
        self._region_de.trace_add("write",
            lambda *_: self._region_de_lbl.set(f"{self._region_de.get():.1f}"))
        r += 1

        cc2 = ctk.CTkFrame(p, fg_color="transparent")
        cc2.grid(row=r, column=0, columnspan=3, padx=14, pady=(1, 1), sticky="ew")
        cc2.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cc2, text="Región mín:", width=90, anchor="w").grid(row=0, column=0)
        self._min_region = ctk.IntVar(value=4)
        ctk.CTkSlider(cc2, from_=1, to=30, variable=self._min_region,
                      width=160).grid(row=0, column=1, padx=6)
        self._min_region_lbl = ctk.StringVar(value="4")
        ctk.CTkLabel(cc2, textvariable=self._min_region_lbl, width=36).grid(row=0, column=2)
        self._min_region.trace_add("write",
            lambda *_: self._min_region_lbl.set(str(int(self._min_region.get()))))
        r += 1

        cc3 = ctk.CTkFrame(p, fg_color="transparent")
        cc3.grid(row=r, column=0, columnspan=3, padx=14, pady=(1, 1), sticky="ew")
        cc3.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cc3, text="ΔE línea:", width=90, anchor="w").grid(row=0, column=0)
        self._run_de = ctk.DoubleVar(value=10.0)
        ctk.CTkSlider(cc3, from_=0, to=30, variable=self._run_de,
                      width=160).grid(row=0, column=1, padx=6)
        self._run_de_lbl = ctk.StringVar(value="10.0")
        ctk.CTkLabel(cc3, textvariable=self._run_de_lbl, width=36).grid(row=0, column=2)
        self._run_de.trace_add("write",
            lambda *_: self._run_de_lbl.set(f"{self._run_de.get():.1f}"))
        r += 1

        cc4 = ctk.CTkFrame(p, fg_color="transparent")
        cc4.grid(row=r, column=0, columnspan=3, padx=14, pady=(1, 4), sticky="ew")
        cc4.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cc4, text="Run mín:", width=90, anchor="w").grid(row=0, column=0)
        self._min_run = ctk.IntVar(value=3)
        ctk.CTkSlider(cc4, from_=1, to=15, variable=self._min_run,
                      width=160).grid(row=0, column=1, padx=6)
        self._min_run_lbl = ctk.StringVar(value="3")
        ctk.CTkLabel(cc4, textvariable=self._min_run_lbl, width=36).grid(row=0, column=2)
        self._min_run.trace_add("write",
            lambda *_: self._min_run_lbl.set(str(int(self._min_run.get()))))
        r += 1

    # ── Panel derecho: inventario creativo ────────────────────────────────────

    def _build_right(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(4, weight=1)

        # ── Vista previa GLB ──────────────────────────────────────────────
        prev_frame = ctk.CTkFrame(p, corner_radius=8)
        prev_frame.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        prev_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prev_frame, text="Vista Previa GLB",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="gray").grid(row=0, column=0, pady=(6, 2))

        import tkinter as _tk
        self._preview_canvas = _tk.Canvas(
            prev_frame,
            width=460, height=300,
            bg="#1a1a1a", highlightthickness=0,
        )
        self._preview_canvas.grid(row=1, column=0, padx=10, pady=(0, 4))
        self._preview_canvas_img = None  # PhotoImage reference (prevent GC)

        # ── Rotation state ─────────────────────────────────────────────────
        self._prev_yaw: float = 45.0
        self._prev_pitch: float = -35.26
        self._prev_drag_xy = None
        self._prev_rendering = False   # True while background render thread is live
        self._prev_dirty = False       # another re-render needed when current finishes
        self._prev_mesh_cache = None   # (verts_norm, faces_sub, vc_or_None) or None
        self._prev_mesh_path = ""
        self._prev_glb_path = ""
        self._prev_zoom: float = 1.0   # 0.2 – 4.0

        self._preview_canvas.bind("<Button-1>", self._on_preview_drag_start)
        self._preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self._preview_canvas.bind("<ButtonRelease-1>", self._on_preview_drag_end)
        self._preview_canvas.bind("<MouseWheel>", self._on_preview_zoom)
        self._preview_canvas.configure(cursor="fleur")

        self._preview_info = ctk.StringVar(value="Sin GLB cargado")
        ctk.CTkLabel(prev_frame, textvariable=self._preview_info,
                     font=ctk.CTkFont(size=10), text_color="gray",
                     wraplength=460).grid(row=2, column=0, pady=(0, 6))

        # Draw initial placeholder
        self._draw_preview_placeholder()

        ctk.CTkLabel(
            p, text="Paleta de Bloques",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=1, column=0, pady=(8, 4), padx=10)

        # ── Fila superior: preset + Todo/Nada ────────────────────────────
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.grid(row=2, column=0, padx=8, pady=(0, 4), sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Preset:").grid(row=0, column=0, padx=(0, 4), sticky="w")
        self._preset = ctk.StringVar(value="Todo")
        from src.block_colors import PRESETS
        ctk.CTkComboBox(
            top, values=list(PRESETS.keys()),
            variable=self._preset, width=130,
            command=self._apply_preset,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkButton(top, text="Todo", width=54, height=26,
                      command=self._sel_all).grid(row=0, column=2, padx=(0, 3))
        ctk.CTkButton(top, text="Nada", width=54, height=26,
                      fg_color="#4a4a4a", hover_color="#5a5a5a",
                      command=self._sel_none).grid(row=0, column=3)

        # ── Búsqueda + tabs de categoría ─────────────────────────────────
        tab_outer = ctk.CTkFrame(p, fg_color="transparent")
        tab_outer.grid(row=3, column=0, padx=8, pady=(0, 2), sticky="ew")

        search_row = ctk.CTkFrame(tab_outer, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 3))
        self._search = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self._refresh_grid())
        ctk.CTkLabel(search_row, text="🔍", width=22).pack(side="left")
        ctk.CTkEntry(search_row, textvariable=self._search,
                     placeholder_text="Buscar bloque...").pack(side="left", fill="x", expand=True)

        tab_row = ctk.CTkFrame(tab_outer, fg_color="transparent")
        tab_row.pack(fill="x", pady=(0, 4))
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for tag, label, emoji in CAT_ORDER:
            btn = ctk.CTkButton(
                tab_row,
                text=emoji,
                width=30, height=30,
                fg_color="#3a3a3a",
                hover_color="#2a8a4a",
                corner_radius=4,
                command=lambda t=tag: self._set_category(t),
            )
            btn.pack(side="left", padx=2, pady=1)
            self._tab_btns[tag] = btn
        self._set_category_style(self._active_cat)

        # ── Grid ─────────────────────────────────────────────────────────
        grid_container = tk.Frame(p, bg="#1e1e1e")
        grid_container.grid(row=4, column=0, padx=8, pady=(0, 4), sticky="nsew")
        grid_container.grid_columnconfigure(0, weight=1)
        grid_container.grid_rowconfigure(0, weight=1)

        self._grid = PaletteGrid(
            grid_container,
            blocks=self._cat_blocks(self._active_cat),
            selected=self._selected,
            on_toggle=self._update_count,
        )
        self._grid.grid(row=0, column=0, sticky="nsew")

        # Contador
        self._count_var = ctk.StringVar(value="")
        ctk.CTkLabel(p, textvariable=self._count_var,
                     font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=5, column=0, pady=(0, 8))
        self._update_count()

    # ── Barra inferior ────────────────────────────────────────────────────────

    def _build_bottom(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)

        pr = ctk.CTkFrame(p, fg_color="transparent")
        pr.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
        pr.grid_columnconfigure(0, weight=1)
        self._pbar = ctk.CTkProgressBar(pr, height=16)
        self._pbar.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self._pbar.set(0)
        self._status = ctk.StringVar(value="Listo.")
        ctk.CTkLabel(pr, textvariable=self._status, width=260,
                     anchor="w").grid(row=0, column=1)

        self._log = ctk.CTkTextbox(p, height=82, state="disabled",
                                    font=ctk.CTkFont(family="Consolas", size=11))
        self._log.grid(row=1, column=0, padx=10, pady=(2, 4), sticky="ew")

        gf = ctk.CTkFrame(p, fg_color="transparent")
        gf.grid(row=2, column=0, padx=10, pady=(2, 10), sticky="e")
        self._gen = ctk.CTkButton(
            gf, text="  ▶  GENERAR  ",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=44, width=200,
            command=self._start,
        )
        self._gen.pack()

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers UI
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_preview_placeholder(self):
        """Draw a dashed-border placeholder on the preview canvas."""
        c = self._preview_canvas
        w, h = 460, 300
        c.delete("all")
        # Dark background is set by canvas bg; draw a subtle border + text
        c.create_rectangle(4, 4, w - 4, h - 4,
                           outline="#444444", width=1, dash=(6, 4))
        c.create_text(w // 2, h // 2 - 10, text="Sin GLB cargado",
                      fill="#555555", font=("Consolas", 11))
        c.create_text(w // 2, h // 2 + 10,
                      text="Selecciona o genera un .glb",
                      fill="#444444", font=("Consolas", 9))

    def _load_mesh_cache(self, path: str):
        """Load, normalise, and cache the mesh geometry for fast re-renders.
        Returns (verts_norm, faces_sub, vc_or_None) or None if no geometry.
        Safe to call from a background thread (only one render thread runs at
        a time, guarded by self._prev_rendering).
        """
        if self._prev_mesh_path == path and self._prev_mesh_cache is not None:
            return self._prev_mesh_cache

        import trimesh
        import numpy as np

        scene = trimesh.load(path, force="scene")
        if isinstance(scene, trimesh.Scene):
            meshes = [g for g in scene.geometry.values()
                      if hasattr(g, "vertices") and len(g.vertices) > 0]
        elif hasattr(scene, "vertices"):
            meshes = [scene]
        else:
            meshes = []

        if not meshes:
            self._prev_mesh_cache = None
            self._prev_mesh_path = path
            return None

        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]

        center = mesh.bounds.mean(axis=0)
        verts = (mesh.vertices - center).astype(np.float32)
        scale = float(np.max(mesh.extents))
        if scale > 0:
            verts /= scale

        faces = mesh.faces
        if len(faces) > 25000:
            idx = np.random.default_rng(0).choice(len(faces), 25000, replace=False)
            faces = faces[idx]

        try:
            vc = mesh.visual.to_color().vertex_colors[:, :3].astype(np.float32)
        except Exception:
            vc = None

        result = (verts, faces, vc)
        self._prev_mesh_cache = result
        self._prev_mesh_path = path
        return result

    def _render_glb_preview_image(self, path: str, yaw: float = 45.0, pitch: float = -35.26, zoom: float = 1.0):
        """Render a thumbnail of a GLB using trimesh + PIL.
        Returns a PIL.Image.Image of size (320, 180).
        """
        import numpy as np
        from PIL import Image, ImageDraw

        SIZE = (460, 300)
        W, H = SIZE

        cache = self._load_mesh_cache(path)
        if cache is None:
            img = Image.new("RGB", SIZE, (28, 28, 28))
            ImageDraw.Draw(img).text((10, H // 2), "Sin geometría", fill="#555555")
            return img

        verts, faces, vc = cache

        # ── Rotation (yaw around Y, then pitch around X) ──────────────────
        ay, ax = np.radians(yaw), np.radians(pitch)
        Ry = np.array([[np.cos(ay), 0, np.sin(ay)],
                       [0, 1, 0],
                       [-np.sin(ay), 0, np.cos(ay)]], dtype=np.float32)
        Rx = np.array([[1, 0, 0],
                       [0, np.cos(ax), -np.sin(ax)],
                       [0, np.sin(ax), np.cos(ax)]], dtype=np.float32)
        R = Rx @ Ry
        vr = verts @ R.T  # (N, 3)

        # ── 2D orthographic projection ────────────────────────────────────
        margin = 0.82 * zoom
        x2d = (vr[:, 0] * margin * W / 2 + W / 2).astype(np.float32)
        y2d = (-vr[:, 1] * margin * H / 2 + H / 2).astype(np.float32)

        face_vr = vr[faces]
        face_z = face_vr[:, :, 2].mean(axis=1)

        # ── Flat shading ──────────────────────────────────────────────────
        v0, v1, v2 = face_vr[:, 0], face_vr[:, 1], face_vr[:, 2]
        normals = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normals /= norms
        light = np.array([0.5, 0.8, 0.3], dtype=np.float32)
        light /= np.linalg.norm(light)
        diffuse = np.clip(normals @ light, 0, 1).astype(np.float32)

        has_vc = vc is not None
        if has_vc:
            face_base = vc[faces].mean(axis=1)

        # ── Painter's sort (back → front) ─────────────────────────────────
        order = np.argsort(face_z)

        img = Image.new("RGB", SIZE, (28, 28, 28))
        draw = ImageDraw.Draw(img)
        DEFAULT = np.array([160, 175, 195], dtype=np.float32)

        for i in order:
            f = faces[i]
            pts = [(float(x2d[f[j]]), float(y2d[f[j]])) for j in range(3)]
            base = face_base[i] if has_vc else DEFAULT
            d = float(diffuse[i])
            color = tuple(int(c * (0.15 + 0.85 * d)) for c in base)
            draw.polygon(pts, fill=color)

        return img

    def _update_glb_preview(self, path: str = ""):
        """Trigger a background render and update the preview canvas."""
        if not path:
            path = self._glb_var.get().strip()

        if not path or not Path(path).exists():
            self._draw_preview_placeholder()
            self._preview_info.set("Sin GLB cargado")
            return

        # Reset rotation and mesh cache when switching to a different file
        if path != self._prev_glb_path:
            self._prev_glb_path = path
            self._prev_yaw = 45.0
            self._prev_pitch = -35.26
            self._prev_zoom = 1.0
            self._prev_mesh_cache = None
            self._prev_mesh_path = ""

        self._preview_info.set("Cargando preview…")

        yaw, pitch, zoom = self._prev_yaw, self._prev_pitch, self._prev_zoom

        def _render():
            try:
                img = self._render_glb_preview_image(path, yaw, pitch, zoom)
            except Exception as exc:
                self.after(0, lambda: self._preview_info.set(f"Error preview: {exc}"))
                return

            # Build stats from cache (mesh already loaded by render)
            try:
                cache = self._prev_mesh_cache
                if cache and self._prev_mesh_path == path:
                    tv = len(cache[0])
                    tf = len(cache[1])
                    info = f"{Path(path).name}  |  {tv:,} v  ·  {tf:,} f  —  arrastra / rueda para rotar y zoom"
                else:
                    info = Path(path).name
            except Exception:
                info = Path(path).name

            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)

            def _apply():
                self._preview_canvas_img = photo  # prevent GC
                self._preview_canvas.delete("all")
                self._preview_canvas.create_image(0, 0, anchor="nw", image=photo)
                self._preview_info.set(info)

            self.after(0, _apply)

        threading.Thread(target=_render, daemon=True).start()

    # ── Preview rotation ──────────────────────────────────────────────────

    def _on_preview_drag_start(self, event):
        self._prev_drag_xy = (event.x, event.y)

    def _on_preview_drag(self, event):
        if self._prev_drag_xy is None or not self._prev_glb_path:
            return
        x0, y0 = self._prev_drag_xy
        dx, dy = event.x - x0, event.y - y0
        self._prev_drag_xy = (event.x, event.y)
        self._prev_yaw   = (self._prev_yaw + dx * 0.5) % 360
        self._prev_pitch = max(-89.0, min(89.0, self._prev_pitch - dy * 0.5))
        self._preview_rerender()

    def _on_preview_drag_end(self, _event):
        self._prev_drag_xy = None

    def _preview_rerender(self):
        """Re-render the preview with current yaw/pitch. Throttled to one
        background thread at a time; if a render is already running the new
        angles are flagged as dirty and a fresh render starts when it ends.
        """
        path = self._prev_glb_path
        if not path:
            return
        if self._prev_rendering:
            self._prev_dirty = True
            return
        self._prev_rendering = True
        self._prev_dirty = False

        yaw, pitch, zoom = self._prev_yaw, self._prev_pitch, self._prev_zoom

        def _work():
            try:
                img = self._render_glb_preview_image(path, yaw, pitch, zoom)
            except Exception:
                self._prev_rendering = False
                return
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)

            def _apply():
                self._preview_canvas_img = photo
                self._preview_canvas.delete("all")
                self._preview_canvas.create_image(0, 0, anchor="nw", image=photo)
                self._prev_rendering = False
                if self._prev_dirty:
                    self._preview_rerender()

            self.after(0, _apply)

        threading.Thread(target=_work, daemon=True).start()

    def _on_preview_zoom(self, event):
        if not self._prev_glb_path:
            return
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self._prev_zoom = max(0.2, min(4.0, self._prev_zoom * factor))
        self._preview_rerender()

    def _section(self, parent, row: int, text: str):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=row, column=0, columnspan=3, padx=14, pady=(10, 0), sticky="w")

    def _append_log(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    # Lógica de paleta
    # ──────────────────────────────────────────────────────────────────────────

    def _cat_blocks(self, cat: str) -> list[dict]:
        search = self._search.get().lower() if hasattr(self, "_search") else ""
        blocks = [b for b in self._all_blocks if cat in b["tags"]]
        if search:
            blocks = [b for b in blocks if search in b["id"].replace("_", " ")]
        return blocks

    def _set_category(self, tag: str):
        self._active_cat = tag
        self._set_category_style(tag)
        self._refresh_grid()

    def _set_category_style(self, active: str):
        for tag, btn in self._tab_btns.items():
            if tag == active:
                btn.configure(fg_color="#2a8a4a", hover_color="#2a8a4a")
            else:
                btn.configure(fg_color="#3a3a3a", hover_color="#2a8a4a")

    def _refresh_grid(self):
        if hasattr(self, "_grid"):
            self._grid.set_blocks(self._cat_blocks(self._active_cat))
        self._update_count()

    def _sel_all(self):
        self._selected.update(b["id"] for b in self._all_blocks)
        self._refresh_grid()

    def _sel_none(self):
        self._selected.clear()
        self._refresh_grid()

    def _apply_preset(self, name: str | None = None):
        from src.block_colors import PRESETS
        if name is None:
            name = self._preset.get()
        ids = PRESETS.get(name)
        self._selected.clear()
        if ids is None:
            self._selected.update(b["id"] for b in self._all_blocks)
        else:
            self._selected.update(ids)
        self._refresh_grid()

    def _update_count(self):
        n = len(self._selected)
        self._count_var.set(f"{n} / {len(self._all_blocks)} bloques seleccionados")

    def _get_allowed(self) -> list[str] | None:
        if len(self._selected) == len(self._all_blocks):
            return None
        return list(self._selected) or None

    # ──────────────────────────────────────────────────────────────────────────
    # Precarga de texturas en background
    # ──────────────────────────────────────────────────────────────────────────

    def _preload_textures(self):
        from texture_cache import preload_all
        total = len(self._all_blocks)

        def on_progress(done, _total):
            self.after(0, lambda: self._status.set(
                f"Descargando texturas... {done}/{_total}"))
            self.after(0, self._grid._redraw)

        preload_all(self._all_blocks, on_progress=on_progress)
        self.after(0, lambda: self._status.set("Listo."))
        self.after(0, self._grid._redraw)

    # ──────────────────────────────────────────────────────────────────────────
    # Pickers de archivo
    # ──────────────────────────────────────────────────────────────────────────

    def _browse_glb(self):
        p = filedialog.askopenfilename(
            title="Seleccionar modelo GLB",
            filetypes=[("GLB / GLTF", "*.glb *.gltf"), ("Todos", "*.*")],
        )
        if p:
            self._glb_var.set(p)
            if not self._out_var.get():
                self._out_var.set(
                    str(Path(p).with_name(f"{Path(p).stem}.{self._fmt.get()}"))
                )
            self._update_glb_preview(p)

    def _browse_out(self):
        fmt = self._fmt.get()
        p = filedialog.asksaveasfilename(
            title="Guardar estructura",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("Todos", "*.*")],
        )
        if p:
            self._out_var.set(p)

    def _browse_img(self):
        p = filedialog.askopenfilename(
            title="Seleccionar imagen para TRELLIS",
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos", "*.*")],
        )
        if p:
            self._img_var.set(p)

    def _start_triposr(self):
        img = self._img_var.get().strip()
        if not img or not Path(img).exists():
            messagebox.showerror("Error", f"Imagen no encontrada:\n{img or '(vacio)'}")
            return

        output_glb = str(Path(img).with_suffix(".glb"))
        remove_bg  = self._rmbg.get()

        self._tsr_btn.configure(state="disabled")
        self._pbar.set(0)
        self._status.set("Iniciando TRELLIS...")
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._append_log("[TRELLIS] Convirtiendo imagen a GLB...")

        def worker():
            try:
                from src.trellis_runner import image_to_glb

                def on_log(msg):
                    self._q.put(("log", msg))

                def on_progress(prog: float, msg: str):
                    self._q.put(("prog", prog, msg))

                result = image_to_glb(
                    image_path=img,
                    output_glb=output_glb,
                    remove_bg=remove_bg,
                    on_log=on_log,
                    on_progress=on_progress,
                )
                self._q.put(("prog", 1.0, f"GLB generado: {result.name}"))
                self._q.put(("tsr_done", str(result)))
            except Exception as exc:
                import traceback
                self._q.put(("log", traceback.format_exc()))
                self._q.put(("tsr_err", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self._poll()

    def _on_fmt_change(self, v: str):
        out = self._out_var.get()
        if out:
            self._out_var.set(str(Path(out).with_suffix(f".{v}")))

    def _on_size_mode(self):
        wxhxd = self._size_mode.get() == "wxhxd"
        for e in (self._we, self._he, self._de):
            e.configure(state="normal" if wxhxd else "disabled")
        self._maxe.configure(state="disabled" if wxhxd else "normal")

    # ──────────────────────────────────────────────────────────────────────────
    # Conversión
    # ──────────────────────────────────────────────────────────────────────────

    def _start(self):
        glb = self._glb_var.get().strip()
        out = self._out_var.get().strip()

        if not glb or not Path(glb).exists():
            messagebox.showerror("Error", f"Archivo GLB no encontrado:\n{glb or '(vacío)'}")
            return
        if not out:
            messagebox.showerror("Error", "Indica la ruta del archivo de salida.")
            return

        fmt     = self._fmt.get()
        mc_ver  = self._mc_ver.get()
        hollow  = self._hollow.get()
        shapes  = self._shapes.get()
        transp  = self._transp.get()
        shadow  = self._shadow_removal.get()
        split8  = self._split_octants.get()
        allowed = self._get_allowed()
        region_de   = float(self._region_de.get())
        min_region  = int(self._min_region.get())
        run_de      = float(self._run_de.get())
        min_run     = int(self._min_run.get())

        if self._size_mode.get() == "wxhxd":
            try:
                target = (int(self._wv.get()), int(self._hv.get()), int(self._dv.get()))
                max_s  = None
            except ValueError:
                messagebox.showerror("Error", "Tamaño W×H×D inválido.")
                return
        else:
            try:
                target = None
                max_s  = int(self._maxv.get())
            except ValueError:
                messagebox.showerror("Error", "Tamaño máximo inválido.")
                return

        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._pbar.set(0)
        self._status.set("Iniciando...")
        self._gen.configure(state="disabled")

        def worker():
            class _Writer:
                def __init__(self, q): self.q = q
                def write(self, t):
                    if t.strip():
                        self.q.put(("log", t.rstrip()))
                def flush(self): pass

            _orig = sys.stdout
            sys.stdout = _Writer(self._q)
            try:
                t0 = time.perf_counter()
                self._q.put(("prog", 0.05, "[1/4] Cargando GLB..."))

                from src.glb_loader import load_glb, get_mesh_info
                mesh, texture = load_glb(glb)
                info = get_mesh_info(mesh)

                _tgt = target
                if _tgt is None:
                    import numpy as np
                    ext = np.array(info["extent"])
                    sc  = max_s / ext.max()
                    _tgt = tuple(
                        int(v) for v in np.maximum((ext * sc).round().astype(int), 1)
                    )

                W2, H2, D2 = _tgt
                self._q.put(("log", f"      {info['vertices']:,} vértices  |  objetivo: {W2}x{H2}x{D2}"))
                self._q.put(("prog", 0.10, f"[2/4] Voxelizando {W2}x{H2}x{D2}..."))

                from src.voxelizer import voxelize
                grid = voxelize(mesh, texture, _tgt, fill_interior=not hollow,
                                shadow_removal=shadow)
                self._q.put(("log",
                    f"      {len(grid.positions):,} voxeles  "
                    f"(superficie: {grid.is_surface.sum():,})"))
                self._q.put(("prog", 0.55, "[3/4] Asignando bloques..."))

                from src.block_matcher import BlockMatcher
                matcher = BlockMatcher(
                    use_transparent=transp,
                    use_shapes=shapes,
                    allowed_blocks=allowed,
                    region_delta_e=region_de,
                    min_region_size=min_region,
                    run_delta_e=run_de,
                    min_run_length=min_run,
                )
                assignments = matcher.assign_blocks(grid)

                from collections import Counter
                top5 = Counter(a["block"] for a in assignments).most_common(5)
                self._q.put(("log",
                    "      Top: " + "  .  ".join(
                        f"{b.split(':')[1]}x{c}" for b, c in top5)))

                self._q.put(("prog", 0.80, "[4/4] Escribiendo archivo..."))

                if split8:
                    from src.nbt_writer import write_nbt, split_into_octants, MC_DATA_VERSIONS, MC_DATA_VERSION
                    dv = MC_DATA_VERSIONS.get(mc_ver, MC_DATA_VERSION)
                    fragments = split_into_octants(assignments, _tgt)
                    base = Path(out).with_suffix("")
                    ext = ".nbt"  # octants always nbt; schem fragmentation not supported
                    written = []
                    for idx, (frag_a, frag_sz, frag_off) in enumerate(fragments, 1):
                        frag_path = str(base) + f"_parte{idx}.nbt"
                        if frag_a:
                            write_nbt(frag_a, frag_sz, frag_path, data_version=dv)
                        else:
                            # Empty fragment: write a 1-block air placeholder
                            write_nbt([{"pos": (0,0,0), "block": "minecraft:air"}],
                                      (1,1,1), frag_path, data_version=dv)
                        ox, oy, oz = frag_off
                        written.append(f"parte{idx} ({frag_sz[0]}×{frag_sz[1]}×{frag_sz[2]}) @ {ox},{oy},{oz}")
                    self._q.put(("log", "      Fragmentos escritos:"))
                    for w in written:
                        self._q.put(("log", f"        {w}"))
                elif fmt == "nbt":
                    from src.nbt_writer import write_nbt, MC_DATA_VERSIONS, MC_DATA_VERSION
                    dv = MC_DATA_VERSIONS.get(mc_ver, MC_DATA_VERSION)
                    write_nbt(assignments, _tgt, out, data_version=dv)
                else:
                    from src.schem_writer import write_schem
                    write_schem(assignments, _tgt, out)

                elapsed = time.perf_counter() - t0
                self._q.put(("prog", 1.0,
                    f"Listo en {elapsed:.1f}s  ->  {Path(out).name}"))
                self._q.put(("done",))

            except Exception as exc:
                import traceback
                self._q.put(("log", traceback.format_exc()))
                self._q.put(("err", str(exc)))
            finally:
                sys.stdout = _orig

        threading.Thread(target=worker, daemon=True).start()
        self._poll()

    def _poll(self):
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "prog":
                    self._pbar.set(msg[1])
                    self._status.set(msg[2])
                    self._append_log(msg[2])
                elif kind == "log":
                    self._append_log(msg[1])
                elif kind == "done":
                    self._gen.configure(state="normal")
                    return
                elif kind == "err":
                    self._gen.configure(state="normal")
                    messagebox.showerror("Error en la conversion", msg[1])
                    return
                elif kind == "tsr_done":
                    self._tsr_btn.configure(state="normal")
                    glb_path = msg[1]
                    self._glb_var.set(glb_path)
                    if not self._out_var.get():
                        self._out_var.set(
                            str(Path(glb_path).with_suffix(f".{self._fmt.get()}"))
                        )
                    self._update_glb_preview(glb_path)
                    return
                elif kind == "tsr_err":
                    self._tsr_btn.configure(state="normal")
                    messagebox.showerror("Error TRELLIS", msg[1])
                    return
        except queue.Empty:
            pass
        self.after(80, self._poll)


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
