"""
texture_cache.py
----------------
Descarga y cachea texturas de bloques de Minecraft desde mcasset.cloud.
Las texturas se guardan en ./textures_cache/ para no re-descargar.
"""

from __future__ import annotations

import threading
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from PIL import Image
import io

CACHE_DIR = Path(__file__).parent / "textures_cache"
TEXTURE_BASE = "https://assets.mcasset.cloud/1.21.4/assets/minecraft/textures/block/{name}.png"
ICON_SIZE = (32, 32)

# Textura de fallback: cuadrado de color sólido
_FALLBACK_COLOR = (120, 120, 120)

_cache: dict[str, Image.Image] = {}          # en memoria
_lock  = threading.Lock()
_downloading: set[str] = set()


def _block_name(block_id: str) -> str:
    """'minecraft:stone' -> 'stone'"""
    return block_id.split(":", 1)[-1]


def _fallback(rgb: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", ICON_SIZE, (*rgb, 255))
    return img


def get_texture(block_id: str, rgb: tuple[int, int, int]) -> Image.Image:
    """
    Devuelve la textura del bloque como PIL Image (32×32).
    Si no está cacheada en disco, la devuelve como fallback y descarga en background.
    """
    name = _block_name(block_id)
    cache_path = CACHE_DIR / f"{name}.png"

    with _lock:
        if block_id in _cache:
            return _cache[block_id]

    # Intentar cargar desde disco
    if cache_path.exists():
        try:
            img = Image.open(cache_path).convert("RGBA").resize(ICON_SIZE, Image.NEAREST)
            with _lock:
                _cache[block_id] = img
            return img
        except Exception:
            pass

    # No está en disco: disparar descarga en background
    with _lock:
        if block_id not in _downloading:
            _downloading.add(block_id)
            threading.Thread(
                target=_download,
                args=(block_id, name, cache_path, rgb),
                daemon=True,
            ).start()

    return _fallback(rgb)


def _download(block_id: str, name: str, cache_path: Path, rgb: tuple) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    url = TEXTURE_BASE.format(name=name)
    try:
        req = Request(url, headers={"User-Agent": "trellis-to-minecraft/1.0"})
        with urlopen(req, timeout=8) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.save(cache_path)
        resized = img.resize(ICON_SIZE, Image.NEAREST)
        with _lock:
            _cache[block_id] = resized
    except (URLError, Exception):
        # Guardar el fallback en caché para no reintentar en esta sesión
        with _lock:
            _cache[block_id] = _fallback(rgb)
    finally:
        with _lock:
            _downloading.discard(block_id)


def preload_all(blocks: list[dict], on_progress=None) -> None:
    """
    Descarga todas las texturas que faltan en paralelo.
    on_progress(done, total) se llama cada vez que termina una.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    pending = [b for b in blocks if not (CACHE_DIR / f"{_block_name(b['id'])}.png").exists()]
    if not pending:
        if on_progress:
            on_progress(len(blocks), len(blocks))
        return

    total = len(blocks)
    done_count = [len(blocks) - len(pending)]
    lock = threading.Lock()

    def _dl_one(b):
        name = _block_name(b["id"])
        cache_path = CACHE_DIR / f"{name}.png"
        _download(b["id"], name, cache_path, b["rgb"])
        with lock:
            done_count[0] += 1
            if on_progress:
                on_progress(done_count[0], total)

    threads = [threading.Thread(target=_dl_one, args=(b,), daemon=True) for b in pending]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
