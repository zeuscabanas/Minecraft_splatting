"""
src/trellis_runner.py
---------------------
Wrapper para TRELLIS (C:\\Users\\zeusc\\TRELLIS) via subprocess.

TRELLIS requiere Python 3.12 con sus propias dependencias (spconv, flash_attn, etc.)
Por eso lanzamos el worker en un proceso separado con `py -3.12`.

La GUI corre en Python 3.13 (.venv) y usa este módulo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────────
_TRELLIS_DIR = Path(r"C:\Users\zeusc\TRELLIS")
_WORKER      = Path(__file__).parent / "trellis_worker.py"

# Python 3.12 vía el Windows Python Launcher
_PY312 = ["py", "-3.12"]


def _py312_exe() -> list[str]:
    """Devuelve el comando para ejecutar Python 3.12."""
    return _PY312


def is_available() -> bool:
    """True si TRELLIS está accesible y Python 3.12 puede importarlo."""
    if not _TRELLIS_DIR.exists():
        return False
    if not _WORKER.exists():
        return False
    try:
        r = subprocess.run(
            [*_py312_exe(), "-c",
             f"import sys; sys.path.insert(0,r'{_TRELLIS_DIR}');"
             "from trellis.pipelines import TrellisImageTo3DPipeline; print('ok')"],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode == 0 and "ok" in r.stdout
    except Exception:
        return False


def image_to_glb(
    image_path: str | Path,
    output_glb: str | Path,
    remove_bg: bool = True,
    simplify: float = 0.95,
    texture_size: int = 1024,
    seed: int = 1,
    model: str = "microsoft/TRELLIS-image-large",
    on_log=None,
    on_progress=None,
) -> Path:
    """
    Convierte una imagen en un archivo GLB usando TRELLIS.

    Lanza trellis_worker.py en Python 3.12 como subprocess y transmite
    las líneas de progreso/log a través de los callbacks.

    Parameters
    ----------
    image_path    : Imagen de entrada (PNG, JPG, WEBP, RGBA recomendado).
    output_glb    : Ruta del .glb de salida.
    remove_bg     : Usar rembg para eliminar el fondo antes de procesar.
    simplify      : Ratio de simplificación de la malla (0.0–1.0).
    texture_size  : Tamaño de textura del GLB bakeado.
    seed          : Semilla para reproducibilidad.
    model         : Nombre del modelo HuggingFace de TRELLIS.
    on_log        : Callback(str) para mensajes de texto libre.
    on_progress   : Callback(float, str) para actualizaciones de progreso.

    Returns
    -------
    Path al GLB generado.

    Raises
    ------
    RuntimeError si el proceso worker termina con error.
    """

    def _log(msg: str) -> None:
        if on_log:
            on_log(msg)

    def _prog(p: float, msg: str) -> None:
        if on_progress:
            on_progress(p, msg)

    cmd = [
        *_py312_exe(),
        str(_WORKER),
        "--image",        str(image_path),
        "--output",       str(output_glb),
        "--trellis-dir",  str(_TRELLIS_DIR),
        "--model",        model,
        "--simplify",     str(simplify),
        "--texture-size", str(texture_size),
        "--seed",         str(seed),
    ]
    if remove_bg:
        cmd.append("--remove-bg")

    _log(f"[TRELLIS] Lanzando worker con Python 3.12...")
    _log(f"[TRELLIS] Imagen: {image_path}")
    _log(f"[TRELLIS] Salida: {output_glb}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # mezclar stderr en stdout para capturarlo todo
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output_path: Path | None = None
    error_msg: str | None = None

    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        if not line:
            continue

        if line.startswith("PROGRESS:"):
            # Formato: PROGRESS:0.xx:mensaje
            parts = line.split(":", 2)
            if len(parts) == 3:
                try:
                    p = float(parts[1])
                except ValueError:
                    p = 0.0
                _prog(p, parts[2])
                _log(parts[2])
        elif line.startswith("DONE:"):
            output_path = Path(line[5:])
        elif line.startswith("ERROR:"):
            error_msg = line[6:]
            _log(f"[ERROR] {error_msg}")
        elif line.startswith("LOG:"):
            _log(line[4:])
        else:
            # Línea sin prefijo (stdout de librerías externas, etc.)
            _log(line)

    proc.wait()

    if proc.returncode != 0 or error_msg:
        raise RuntimeError(
            error_msg or f"Worker TRELLIS terminó con código {proc.returncode}"
        )

    if output_path is None:
        raise RuntimeError("Worker TRELLIS no reportó un archivo de salida (DONE:)")

    return output_path
