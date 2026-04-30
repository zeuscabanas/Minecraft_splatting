"""
glb_loader.py
-------------
Carga un archivo .glb (output de Trellis) y extrae:
  - La malla 3D combinada (vértices + caras + UVs)
  - La imagen de textura base color (baseColorTexture PBR)

Dependencias: trimesh, Pillow, numpy
"""

import numpy as np
from PIL import Image
import trimesh
from trimesh.visual.material import PBRMaterial, SimpleMaterial


class GLBLoadError(Exception):
    pass


def load_glb(path: str) -> tuple[trimesh.Trimesh, Image.Image | None]:
    """
    Carga un archivo .glb y retorna (mesh, texture_image).

    Parameters
    ----------
    path : str
        Ruta al archivo .glb

    Returns
    -------
    mesh : trimesh.Trimesh
        Malla combinada con UVs y referencia a la textura.
    texture : PIL.Image.Image or None
        Imagen de textura base color en modo RGBA.
        None si el modelo no tiene texturas.
    """
    try:
        loaded = trimesh.load(path, force="scene", process=False)
    except Exception as e:
        raise GLBLoadError(f"No se pudo cargar {path}: {e}") from e

    # Extraer mallas de la escena o malla directa
    if isinstance(loaded, trimesh.Scene):
        meshes = list(loaded.geometry.values())
        if not meshes:
            raise GLBLoadError(f"El archivo {path} no contiene geometría.")
        # Combinar todas las mallas en una sola
        mesh = trimesh.util.concatenate(meshes)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise GLBLoadError(f"Formato inesperado al cargar {path}: {type(loaded)}")

    if len(mesh.faces) == 0:
        raise GLBLoadError("La malla no tiene caras (está vacía).")

    # Extraer la textura base color
    texture = _extract_base_color_texture(mesh)

    return mesh, texture


def _extract_base_color_texture(mesh: trimesh.Trimesh) -> Image.Image | None:
    """
    Extrae la imagen de textura base color del material de la malla.
    Intenta PBRMaterial primero, luego SimpleMaterial.
    """
    visual = mesh.visual

    # trimesh puede guardar el material en visual.material
    if hasattr(visual, "material"):
        mat = visual.material
        if isinstance(mat, PBRMaterial):
            img = _pil_from_pbr(mat)
            if img:
                return img.convert("RGBA")
        if isinstance(mat, SimpleMaterial):
            img = _pil_from_simple(mat)
            if img:
                return img.convert("RGBA")

    # Alternativa: obtener la imagen a través de visual.to_color()
    # (fallback: color vertex o color plano)
    if hasattr(visual, "kind"):
        if visual.kind == "texture":
            try:
                img = visual.material.image
                if img is not None:
                    return img.convert("RGBA")
            except AttributeError:
                pass

    return None


def _pil_from_pbr(mat: PBRMaterial) -> Image.Image | None:
    """Extrae baseColorTexture de un PBRMaterial."""
    if mat.baseColorTexture is not None:
        img = mat.baseColorTexture
        if isinstance(img, Image.Image):
            return img
    # Si no hay textura, crear imagen de 1x1 con baseColorFactor
    if mat.baseColorFactor is not None:
        factor = np.array(mat.baseColorFactor, dtype=np.uint8)
        factor = (factor * 255).clip(0, 255).astype(np.uint8) if factor.max() <= 1.0 else factor
        return Image.fromarray(factor.reshape(1, 1, -1), mode="RGBA")
    return None


def _pil_from_simple(mat: SimpleMaterial) -> Image.Image | None:
    """Extrae la textura de un SimpleMaterial."""
    if mat.image is not None:
        return mat.image
    if mat.diffuse is not None:
        color = np.array(mat.diffuse, dtype=np.uint8)
        return Image.fromarray(color.reshape(1, 1, -1), mode="RGBA")
    return None


def get_mesh_info(mesh: trimesh.Trimesh) -> dict:
    """Retorna información básica de la malla."""
    bb_min = mesh.bounds[0]
    bb_max = mesh.bounds[1]
    extent = bb_max - bb_min
    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "bounds_min": bb_min.tolist(),
        "bounds_max": bb_max.tolist(),
        "extent": extent.tolist(),
        "has_uvs": hasattr(mesh.visual, "uv") and mesh.visual.uv is not None,
    }
