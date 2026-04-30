"""
src/trellis_worker.py
---------------------
Script autónomo que corre bajo Python 3.12 (donde TRELLIS está instalado).
Es lanzado como subprocess por trellis_runner.py.

Protocolo de salida (stdout, UTF-8):
  LOG:<mensaje>               → línea de log libre
  PROGRESS:<0.xx>:<mensaje>   → actualización de progreso
  DONE:<ruta_glb>             → éxito, ruta del GLB generado
  ERROR:<mensaje>             → fallo
"""

import os
import sys
import argparse
import traceback


def _log(msg: str) -> None:
    print(f"LOG:{msg}", flush=True)


def _progress(prog: float, msg: str) -> None:
    print(f"PROGRESS:{prog:.3f}:{msg}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="TRELLIS image→GLB worker")
    parser.add_argument("--image",        required=True,  help="Ruta de la imagen de entrada")
    parser.add_argument("--output",       required=True,  help="Ruta del GLB de salida")
    parser.add_argument("--trellis-dir",  default=r"C:\Users\zeusc\TRELLIS",
                        help="Directorio raíz de TRELLIS")
    parser.add_argument("--model",        default="microsoft/TRELLIS-image-large",
                        help="Modelo HuggingFace de TRELLIS a usar")
    parser.add_argument("--remove-bg",    action="store_true",
                        help="Eliminar fondo con rembg antes de procesar")
    parser.add_argument("--simplify",     type=float, default=0.95,
                        help="Ratio de simplificación de malla (0-1)")
    parser.add_argument("--texture-size", type=int,   default=1024,
                        help="Tamaño de la textura del GLB")
    parser.add_argument("--seed",         type=int,   default=1,
                        help="Semilla aleatoria para la generación")
    args = parser.parse_args()

    # ── Configurar TRELLIS en sys.path ────────────────────────────────────────
    trellis_dir = args.trellis_dir
    if trellis_dir not in sys.path:
        sys.path.insert(0, trellis_dir)

    os.environ["SPCONV_ALGO"]  = "native"   # evita benchmarking lento
    os.environ["ATTN_BACKEND"] = "sdpa"     # PyTorch nativo; flash_attn y xformers no están instalados
    # NO ponemos HF_HUB_OFFLINE — los 4 modelos faltantes se descargarán de microsoft/TRELLIS-image-large

    try:
        # ── Importar dependencias ─────────────────────────────────────────────
        _progress(0.02, "Importando TRELLIS...")
        from trellis.pipelines import TrellisImageTo3DPipeline  # noqa: F401
        from trellis.utils import postprocessing_utils           # noqa: F401
        from PIL import Image
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _log(f"Device: {device}  |  torch {torch.__version__}")

        # ── Cargar modelo ─────────────────────────────────────────────────────
        _progress(0.05, f"Cargando modelo {args.model}...")
        _log("      Primera vez: descarga ~5 GB de modelos de HuggingFace (paciencia).")
        _log("      Siguientes ejecuciones: carga instantánea desde cache.")
        pipeline = TrellisImageTo3DPipeline.from_pretrained(args.model)
        pipeline.to(device)
        _log(f"Modelo cargado en {device}")

        # ── Cargar y preparar imagen ──────────────────────────────────────────
        _progress(0.22, "Cargando imagen...")
        image = Image.open(args.image).convert("RGBA")

        if args.remove_bg:
            _progress(0.25, "Eliminando fondo (rembg)...")
            try:
                from rembg import remove as rembg_remove
                image = rembg_remove(image)
                _log("Fondo eliminado con rembg")
            except ImportError:
                _log("rembg no disponible, se omite eliminación de fondo")
            except Exception as e:
                _log(f"rembg falló ({e}), se omite")

        # Convertir a RGB con fondo blanco para TRELLIS si no hay alpha significativo
        # (TRELLIS acepta RGBA directamente)

        # ── Ejecutar pipeline TRELLIS ─────────────────────────────────────────
        _progress(0.30, "Ejecutando pipeline TRELLIS (generando 3D)...")
        outputs = pipeline.run(
            image,
            seed=args.seed,
        )
        # outputs tiene: 'gaussian', 'radiance_field', 'mesh'
        _log(f"Pipeline completado. Gaussians: {len(outputs['gaussian'])}  Meshes: {len(outputs['mesh'])}")

        # ── Bake textura y exportar GLB ───────────────────────────────────────
        _progress(0.75, f"Generando GLB (texture_size={args.texture_size}, simplify={args.simplify})...")
        glb = postprocessing_utils.to_glb(
            outputs["gaussian"][0],
            outputs["mesh"][0],
            simplify=args.simplify,
            texture_size=args.texture_size,
        )

        _progress(0.95, f"Exportando a {args.output}...")
        glb.export(args.output)

        print(f"DONE:{args.output}", flush=True)

    except Exception:
        tb = traceback.format_exc()
        # Enviar traceback como líneas LOG para el GUI
        for line in tb.splitlines():
            _log(f"  {line}")
        print(f"ERROR:{sys.exc_info()[1]}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
