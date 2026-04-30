"""
src/triposr_runner.py
---------------------
Convierte una imagen en un archivo GLB usando TripoSR.

Instalacion:
    pip install git+https://github.com/VAST-AI-Research/TripoSR.git
    pip install rembg  # opcional, para eliminacion de fondo automatica

El modelo (~1 GB) se descarga automaticamente de HuggingFace la primera vez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# ── Ruta al repo de TripoSR clonado localmente ────────────────────────────────
_TRIPOSR_DIR = Path(__file__).parent.parent / "TripoSR"

INSTALL_CMD = (
    "git clone https://github.com/VAST-AI-Research/TripoSR.git\n"
    "pip install -r TripoSR/requirements.txt rembg"
)


def _ensure_path() -> None:
    """Agrega el directorio TripoSR al sys.path si esta clonado localmente."""
    triposr_str = str(_TRIPOSR_DIR.resolve())
    if _TRIPOSR_DIR.exists() and triposr_str not in sys.path:
        sys.path.insert(0, triposr_str)


# Asegurar path al importar el modulo (necesario para threads worker)
_ensure_path()


def is_available() -> bool:
    """Devuelve True si TripoSR (tsr.system.TSR) esta disponible."""
    _ensure_path()
    try:
        from tsr.system import TSR  # noqa: F401
        return True
    except Exception:
        return False


def image_to_glb(
    image_path: str | Path,
    output_glb: str | Path,
    remove_bg: bool = True,
    foreground_ratio: float = 0.85,
    mc_resolution: int = 256,
    device: str | None = None,
    on_log=None,
) -> Path:
    """
    Convierte una imagen en un archivo GLB usando TripoSR.

    Parameters
    ----------
    image_path       : Imagen de entrada (PNG, JPG, WEBP, etc.)
    output_glb       : Ruta del archivo .glb de salida.
    remove_bg        : Eliminar fondo con rembg antes de procesar.
    foreground_ratio : Proporcion del objeto respecto al encuadre (0..1).
    mc_resolution    : Resolucion de la extraccion de malla (mayor = mas detalle).
    device           : 'cuda', 'cpu', o None (autodetect).
    on_log           : Funcion callback(str) para mensajes de progreso.

    Returns
    -------
    Path al archivo GLB generado.
    """
    def log(msg: str):
        if on_log:
            on_log(msg)

    _ensure_path()  # garantiza el path en hilos worker

    try:
        from tsr.system import TSR
        from tsr.utils import remove_background, resize_foreground
    except ImportError as exc:
        raise RuntimeError(
            f"TripoSR no esta instalado.\nInstala con:\n{INSTALL_CMD}"
        ) from exc

    import torch
    from PIL import Image

    # ── Device ──────────────────────────────────────────────────────────────
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"      Device: {device}")

    # ── Cargar modelo ────────────────────────────────────────────────────────
    log("      Cargando modelo TripoSR (primera vez ~1 GB desde HuggingFace)...")
    model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(device)
    log("      Modelo listo.")

    # ── Preprocesar imagen ───────────────────────────────────────────────────
    image_path = Path(image_path)
    log(f"      Cargando imagen: {image_path.name}")
    image = Image.open(str(image_path))

    if remove_bg:
        log("      Eliminando fondo (rembg)...")
        try:
            import rembg
            session = rembg.new_session()
            image = remove_background(image, session)
            log("      Fondo eliminado.")
        except ImportError:
            log("      Advertencia: rembg no instalado, salta eliminacion de fondo.")

    image = resize_foreground(image, foreground_ratio)

    # Composite sobre fondo blanco (TripoSR espera fondo blanco)
    bg_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    img_arr = np.array(image).astype(np.float32) / 255.0
    if img_arr.ndim == 3 and img_arr.shape[2] == 4:
        alpha = img_arr[:, :, 3:4]
        img_arr = img_arr[:, :, :3] * alpha + bg_color * (1.0 - alpha)
    image = Image.fromarray((img_arr * 255.0).astype(np.uint8))

    # ── Inferencia ───────────────────────────────────────────────────────────
    log("      Generando representacion 3D...")
    with torch.no_grad():
        scene_codes = model([image], device=device)

    # ── Extraer malla ────────────────────────────────────────────────────────
    log(f"      Extrayendo malla (resolucion={mc_resolution})...")
    meshes = model.extract_mesh(scene_codes, True, resolution=mc_resolution)
    if not meshes:
        raise RuntimeError("TripoSR no genero ninguna malla.")

    # ── Exportar GLB ─────────────────────────────────────────────────────────
    output_glb = Path(output_glb)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    log(f"      Guardando: {output_glb.name}")
    meshes[0].export(str(output_glb))
    log(f"      GLB guardado correctamente.")
    return output_glb
