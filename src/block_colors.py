"""
block_colors.py
---------------
Base de datos de bloques de Minecraft con sus colores promedio.

Los colores son valores RGB promedio aproximados de las texturas de cada bloque
en Minecraft Java Edition (versión 1.21).

Estructura: lista de dicts con:
  - "id": nombre del bloque (minecraft:xxx)
  - "rgb": (R, G, B) color promedio
  - "tags": lista de etiquetas para filtrado (e.g. "opaque", "transparent")
"""

from __future__ import annotations
import numpy as np

# ---------------------------------------------------------------------------
# Base de datos de bloques
# ---------------------------------------------------------------------------
# Colores obtenidos promediando las texturas oficiales de Minecraft 1.21.
# Para bloques con múltiples texturas (top/side/bottom) se usa el promedio global.

BLOCK_DATABASE: list[dict] = [
    # ── CONCRETE (16 colores sólidos y saturados) ─────────────────────────
    {"id": "minecraft:white_concrete",      "rgb": (207, 213, 214), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:orange_concrete",     "rgb": (224,  97,   0), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:magenta_concrete",    "rgb": (169,  48, 159), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:light_blue_concrete", "rgb": ( 36, 137, 199), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:yellow_concrete",     "rgb": (240, 175,  21), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:lime_concrete",       "rgb": ( 94, 168,  24), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:pink_concrete",       "rgb": (213, 101, 142), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:gray_concrete",       "rgb": ( 54,  57,  61), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:light_gray_concrete", "rgb": (125, 125, 115), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:cyan_concrete",       "rgb": ( 21, 119, 136), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:purple_concrete",     "rgb": (100,  31, 156), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:blue_concrete",       "rgb": ( 44,  46, 143), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:brown_concrete",      "rgb": ( 96,  59,  31), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:green_concrete",      "rgb": ( 73,  91,  36), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:red_concrete",        "rgb": (142,  32,  32), "tags": ["opaque", "concrete"]},
    {"id": "minecraft:black_concrete",      "rgb": (  8,  10,  15), "tags": ["opaque", "concrete"]},

    # ── WOOL (16 colores, más suaves y texturizados) ──────────────────────
    {"id": "minecraft:white_wool",          "rgb": (233, 236, 236), "tags": ["opaque", "wool"]},
    {"id": "minecraft:orange_wool",         "rgb": (240, 118,  19), "tags": ["opaque", "wool"]},
    {"id": "minecraft:magenta_wool",        "rgb": (189,  68, 179), "tags": ["opaque", "wool"]},
    {"id": "minecraft:light_blue_wool",     "rgb": (58,  175, 217), "tags": ["opaque", "wool"]},
    {"id": "minecraft:yellow_wool",         "rgb": (248, 197,  39), "tags": ["opaque", "wool"]},
    {"id": "minecraft:lime_wool",           "rgb": (112, 185,  25), "tags": ["opaque", "wool"]},
    {"id": "minecraft:pink_wool",           "rgb": (237, 141, 172), "tags": ["opaque", "wool"]},
    {"id": "minecraft:gray_wool",           "rgb": ( 62,  68,  71), "tags": ["opaque", "wool"]},
    {"id": "minecraft:light_gray_wool",     "rgb": (142, 142, 134), "tags": ["opaque", "wool"]},
    {"id": "minecraft:cyan_wool",           "rgb": ( 22, 136, 152), "tags": ["opaque", "wool"]},
    {"id": "minecraft:purple_wool",         "rgb": (121,  42, 172), "tags": ["opaque", "wool"]},
    {"id": "minecraft:blue_wool",           "rgb": ( 55,  63, 161), "tags": ["opaque", "wool"]},
    {"id": "minecraft:brown_wool",          "rgb": (114,  71,  40), "tags": ["opaque", "wool"]},
    {"id": "minecraft:green_wool",          "rgb": ( 84, 109,  27), "tags": ["opaque", "wool"]},
    {"id": "minecraft:red_wool",            "rgb": (161,  39,  34), "tags": ["opaque", "wool"]},
    {"id": "minecraft:black_wool",          "rgb": ( 20,  21,  25), "tags": ["opaque", "wool"]},

    # ── TERRACOTTA (16 tonos tierra) ──────────────────────────────────────
    {"id": "minecraft:white_terracotta",        "rgb": (209, 177, 161), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:orange_terracotta",       "rgb": (162,  84,  38), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:magenta_terracotta",      "rgb": (149,  88, 108), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:light_blue_terracotta",   "rgb": (113, 108, 137), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:yellow_terracotta",       "rgb": (186, 133,  35), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:lime_terracotta",         "rgb": (103, 117,  52), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:pink_terracotta",         "rgb": (161,  78,  78), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:gray_terracotta",         "rgb": ( 57,  42,  35), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:light_gray_terracotta",   "rgb": (135, 106,  97), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:cyan_terracotta",         "rgb": ( 87,  91,  91), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:purple_terracotta",       "rgb": (118,  70,  86), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:blue_terracotta",         "rgb": ( 74,  59,  91), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:brown_terracotta",        "rgb": ( 77,  51,  35), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:green_terracotta",        "rgb": ( 76,  83,  42), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:red_terracotta",          "rgb": (143,  61,  46), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:black_terracotta",        "rgb": ( 37,  22,  16), "tags": ["opaque", "terracotta"]},
    {"id": "minecraft:terracotta",              "rgb": (152,  94,  67), "tags": ["opaque", "terracotta"]},

    # ── MADERA: TABLONES ──────────────────────────────────────────────────
    {"id": "minecraft:oak_planks",          "rgb": (162, 130,  78), "tags": ["opaque", "wood"]},
    {"id": "minecraft:birch_planks",        "rgb": (195, 179, 106), "tags": ["opaque", "wood"]},
    {"id": "minecraft:spruce_planks",       "rgb": (114,  84,  48), "tags": ["opaque", "wood"]},
    {"id": "minecraft:jungle_planks",       "rgb": (160, 115,  80), "tags": ["opaque", "wood"]},
    {"id": "minecraft:acacia_planks",       "rgb": (168,  90,  50), "tags": ["opaque", "wood"]},
    {"id": "minecraft:dark_oak_planks",     "rgb": ( 66,  43,  20), "tags": ["opaque", "wood"]},
    {"id": "minecraft:mangrove_planks",     "rgb": (117,  54,  48), "tags": ["opaque", "wood"]},
    {"id": "minecraft:cherry_planks",       "rgb": (228, 177, 164), "tags": ["opaque", "wood"]},
    {"id": "minecraft:bamboo_planks",       "rgb": (196, 163,  97), "tags": ["opaque", "wood"]},
    {"id": "minecraft:crimson_planks",      "rgb": (149,  53,  76), "tags": ["opaque", "wood"]},
    {"id": "minecraft:warped_planks",       "rgb": ( 43, 104, 100), "tags": ["opaque", "wood"]},

    # ── MADERA: TRONCOS ───────────────────────────────────────────────────
    {"id": "minecraft:oak_log",             "rgb": (102,  82,  51), "tags": ["opaque", "log"]},
    {"id": "minecraft:birch_log",           "rgb": (216, 209, 167), "tags": ["opaque", "log"]},
    {"id": "minecraft:spruce_log",          "rgb": ( 59,  40,  17), "tags": ["opaque", "log"]},
    {"id": "minecraft:jungle_log",          "rgb": ( 89,  65,  37), "tags": ["opaque", "log"]},
    {"id": "minecraft:acacia_log",          "rgb": (170, 170, 170), "tags": ["opaque", "log"]},
    {"id": "minecraft:dark_oak_log",        "rgb": ( 64,  52,  35), "tags": ["opaque", "log"]},
    {"id": "minecraft:mangrove_log",        "rgb": ( 83,  43,  30), "tags": ["opaque", "log"]},

    # ── PIEDRA Y VARIANTES ────────────────────────────────────────────────
    {"id": "minecraft:stone",               "rgb": (125, 125, 125), "tags": ["opaque", "stone"]},
    {"id": "minecraft:smooth_stone",        "rgb": (162, 162, 162), "tags": ["opaque", "stone"]},
    {"id": "minecraft:cobblestone",         "rgb": (127, 127, 127), "tags": ["opaque", "stone"]},
    {"id": "minecraft:stone_bricks",        "rgb": (122, 122, 122), "tags": ["opaque", "stone"]},
    {"id": "minecraft:mossy_stone_bricks",  "rgb": (115, 130, 105), "tags": ["opaque", "stone"]},
    {"id": "minecraft:cracked_stone_bricks","rgb": (118, 118, 118), "tags": ["opaque", "stone"]},
    {"id": "minecraft:granite",             "rgb": (153, 114,  99), "tags": ["opaque", "stone"]},
    {"id": "minecraft:polished_granite",    "rgb": (159, 118, 101), "tags": ["opaque", "stone"]},
    {"id": "minecraft:diorite",             "rgb": (188, 183, 183), "tags": ["opaque", "stone"]},
    {"id": "minecraft:polished_diorite",    "rgb": (193, 189, 189), "tags": ["opaque", "stone"]},
    {"id": "minecraft:andesite",            "rgb": (136, 136, 136), "tags": ["opaque", "stone"]},
    {"id": "minecraft:polished_andesite",   "rgb": (132, 132, 132), "tags": ["opaque", "stone"]},
    {"id": "minecraft:deepslate",           "rgb": ( 71,  71,  79), "tags": ["opaque", "stone"]},
    {"id": "minecraft:deepslate_bricks",    "rgb": ( 67,  67,  67), "tags": ["opaque", "stone"]},
    {"id": "minecraft:cobbled_deepslate",   "rgb": ( 72,  72,  75), "tags": ["opaque", "stone"]},
    {"id": "minecraft:calcite",             "rgb": (223, 220, 217), "tags": ["opaque", "stone"]},
    {"id": "minecraft:tuff",                "rgb": (111, 112, 103), "tags": ["opaque", "stone"]},

    # ── TIERRA, ARENA Y NATURALES ─────────────────────────────────────────
    {"id": "minecraft:dirt",                "rgb": (134,  96,  67), "tags": ["opaque", "natural"]},
    {"id": "minecraft:grass_block",         "rgb": (114, 135,  67), "tags": ["opaque", "natural"]},
    {"id": "minecraft:podzol",              "rgb": (131,  88,  40), "tags": ["opaque", "natural"]},
    {"id": "minecraft:mycelium",            "rgb": (111,  98, 102), "tags": ["opaque", "natural"]},
    {"id": "minecraft:sand",                "rgb": (219, 207, 163), "tags": ["opaque", "natural"]},
    {"id": "minecraft:red_sand",            "rgb": (190, 102,  33), "tags": ["opaque", "natural"]},
    {"id": "minecraft:gravel",              "rgb": (162, 162, 162), "tags": ["opaque", "natural"]},
    {"id": "minecraft:clay",                "rgb": (161, 164, 177), "tags": ["opaque", "natural"]},
    {"id": "minecraft:mud",                 "rgb": ( 60,  57,  60), "tags": ["opaque", "natural"]},
    {"id": "minecraft:moss_block",          "rgb": ( 90, 119,  58), "tags": ["opaque", "natural"]},
    {"id": "minecraft:snow_block",          "rgb": (247, 250, 255), "tags": ["opaque", "natural"]},
    {"id": "minecraft:ice",                 "rgb": (145, 183, 242), "tags": ["translucent", "natural"]},
    {"id": "minecraft:packed_ice",          "rgb": (141, 180, 250), "tags": ["opaque", "natural"]},
    {"id": "minecraft:blue_ice",            "rgb": ( 74, 144, 211), "tags": ["opaque", "natural"]},

    # ── BLOQUES MINERALES ─────────────────────────────────────────────────
    {"id": "minecraft:iron_block",          "rgb": (220, 220, 220), "tags": ["opaque", "metal"]},
    {"id": "minecraft:gold_block",          "rgb": (247, 233,  72), "tags": ["opaque", "metal"]},
    {"id": "minecraft:diamond_block",       "rgb": ( 98, 236, 221), "tags": ["opaque", "metal"]},
    {"id": "minecraft:emerald_block",       "rgb": ( 42, 196,  75), "tags": ["opaque", "metal"]},
    {"id": "minecraft:lapis_block",         "rgb": ( 32,  72, 154), "tags": ["opaque", "metal"]},
    {"id": "minecraft:coal_block",          "rgb": ( 14,  15,  17), "tags": ["opaque", "metal"]},
    {"id": "minecraft:copper_block",        "rgb": (196, 121,  87), "tags": ["opaque", "metal"]},
    {"id": "minecraft:exposed_copper",      "rgb": (168, 131, 103), "tags": ["opaque", "metal"]},
    {"id": "minecraft:weathered_copper",    "rgb": (107, 155, 106), "tags": ["opaque", "metal"]},
    {"id": "minecraft:oxidized_copper",     "rgb": ( 82, 163, 134), "tags": ["opaque", "metal"]},
    {"id": "minecraft:netherite_block",     "rgb": ( 68,  60,  59), "tags": ["opaque", "metal"]},
    {"id": "minecraft:amethyst_block",      "rgb": (143,  96, 188), "tags": ["opaque", "metal"]},
    {"id": "minecraft:raw_iron_block",      "rgb": (166, 136,  98), "tags": ["opaque", "metal"]},
    {"id": "minecraft:raw_gold_block",      "rgb": (220, 162,  35), "tags": ["opaque", "metal"]},
    {"id": "minecraft:raw_copper_block",    "rgb": (194, 104,  77), "tags": ["opaque", "metal"]},

    # ── QUARTZ Y NETHER ───────────────────────────────────────────────────
    {"id": "minecraft:quartz_block",        "rgb": (235, 229, 222), "tags": ["opaque", "nether"]},
    {"id": "minecraft:smooth_quartz",       "rgb": (238, 233, 225), "tags": ["opaque", "nether"]},
    {"id": "minecraft:quartz_bricks",       "rgb": (230, 225, 218), "tags": ["opaque", "nether"]},
    {"id": "minecraft:nether_bricks",       "rgb": ( 44,  21,  26), "tags": ["opaque", "nether"]},
    {"id": "minecraft:red_nether_bricks",   "rgb": ( 72,   7,   8), "tags": ["opaque", "nether"]},
    {"id": "minecraft:netherrack",          "rgb": ( 97,  35,  35), "tags": ["opaque", "nether"]},
    {"id": "minecraft:nether_wart_block",   "rgb": (115,   4,   4), "tags": ["opaque", "nether"]},
    {"id": "minecraft:warped_wart_block",   "rgb": ( 22, 118, 108), "tags": ["opaque", "nether"]},
    {"id": "minecraft:basalt",              "rgb": ( 82,  81,  86), "tags": ["opaque", "nether"]},
    {"id": "minecraft:polished_basalt",     "rgb": ( 83,  82,  87), "tags": ["opaque", "nether"]},
    {"id": "minecraft:blackstone",          "rgb": ( 43,  35,  43), "tags": ["opaque", "nether"]},
    {"id": "minecraft:gilded_blackstone",   "rgb": ( 59,  44,  32), "tags": ["opaque", "nether"]},
    {"id": "minecraft:soul_sand",           "rgb": ( 80,  62,  50), "tags": ["opaque", "nether"]},

    # ── END ───────────────────────────────────────────────────────────────
    {"id": "minecraft:end_stone",           "rgb": (219, 222, 158), "tags": ["opaque", "end"]},
    {"id": "minecraft:end_stone_bricks",    "rgb": (218, 220, 158), "tags": ["opaque", "end"]},
    {"id": "minecraft:purpur_block",        "rgb": (170, 125, 171), "tags": ["opaque", "end"]},
    {"id": "minecraft:purpur_pillar",       "rgb": (174, 130, 174), "tags": ["opaque", "end"]},

    # ── OCEAN / PRISMARINE ────────────────────────────────────────────────
    {"id": "minecraft:prismarine",          "rgb": ( 99, 171, 158), "tags": ["opaque", "ocean"]},
    {"id": "minecraft:prismarine_bricks",   "rgb": (101, 168, 149), "tags": ["opaque", "ocean"]},
    {"id": "minecraft:dark_prismarine",     "rgb": ( 51,  93,  77), "tags": ["opaque", "ocean"]},

    # ── VIDRIO (transparentes/translúcidos) ───────────────────────────────
    {"id": "minecraft:glass",                   "rgb": (186, 213, 220), "tags": ["transparent", "glass"]},
    {"id": "minecraft:white_stained_glass",     "rgb": (255, 255, 255), "tags": ["transparent", "glass"]},
    {"id": "minecraft:orange_stained_glass",    "rgb": (216,  96,   0), "tags": ["transparent", "glass"]},
    {"id": "minecraft:magenta_stained_glass",   "rgb": (178,  76, 216), "tags": ["transparent", "glass"]},
    {"id": "minecraft:light_blue_stained_glass","rgb": ( 74, 128, 255), "tags": ["transparent", "glass"]},
    {"id": "minecraft:yellow_stained_glass",    "rgb": (255, 255,   0), "tags": ["transparent", "glass"]},
    {"id": "minecraft:lime_stained_glass",      "rgb": (128, 255,   0), "tags": ["transparent", "glass"]},
    {"id": "minecraft:pink_stained_glass",      "rgb": (255, 178, 178), "tags": ["transparent", "glass"]},
    {"id": "minecraft:gray_stained_glass",      "rgb": ( 76,  76,  76), "tags": ["transparent", "glass"]},
    {"id": "minecraft:light_gray_stained_glass","rgb": (153, 153, 153), "tags": ["transparent", "glass"]},
    {"id": "minecraft:cyan_stained_glass",      "rgb": (  0, 178, 178), "tags": ["transparent", "glass"]},
    {"id": "minecraft:purple_stained_glass",    "rgb": (178,   0, 178), "tags": ["transparent", "glass"]},
    {"id": "minecraft:blue_stained_glass",      "rgb": (  0,   0, 178), "tags": ["transparent", "glass"]},
    {"id": "minecraft:brown_stained_glass",     "rgb": (102,  76,  51), "tags": ["transparent", "glass"]},
    {"id": "minecraft:green_stained_glass",     "rgb": (  0, 178,   0), "tags": ["transparent", "glass"]},
    {"id": "minecraft:red_stained_glass",       "rgb": (178,   0,   0), "tags": ["transparent", "glass"]},
    {"id": "minecraft:black_stained_glass",     "rgb": ( 25,  25,  25), "tags": ["transparent", "glass"]},

    # ── MISCELÁNEOS ───────────────────────────────────────────────────────
    {"id": "minecraft:bookshelf",           "rgb": (162, 130,  78), "tags": ["opaque", "misc"]},
    {"id": "minecraft:sponge",              "rgb": (194, 193,  59), "tags": ["opaque", "misc"]},
    {"id": "minecraft:wet_sponge",          "rgb": (172, 184,  47), "tags": ["opaque", "misc"]},
    {"id": "minecraft:honey_block",         "rgb": (235, 168,  41), "tags": ["opaque", "misc"]},
    {"id": "minecraft:slime_block",         "rgb": (112, 184,  98), "tags": ["translucent", "misc"]},
    {"id": "minecraft:shroomlight",         "rgb": (238, 160,  64), "tags": ["opaque", "misc", "emissive"]},
    {"id": "minecraft:glowstone",           "rgb": (181, 137,  63), "tags": ["opaque", "misc", "emissive"]},
    {"id": "minecraft:sea_lantern",         "rgb": (172, 207, 196), "tags": ["opaque", "misc", "emissive"]},
    {"id": "minecraft:magma_block",         "rgb": (141,  57,  20), "tags": ["opaque", "misc", "emissive"]},
    {"id": "minecraft:obsidian",            "rgb": ( 21,  18,  30), "tags": ["opaque", "misc"]},
    {"id": "minecraft:crying_obsidian",     "rgb": ( 26,   7,  54), "tags": ["opaque", "misc", "emissive"]},
    {"id": "minecraft:bedrock",             "rgb": ( 84,  84,  84), "tags": ["opaque", "misc"]},
    {"id": "minecraft:tnt",                 "rgb": (192,  51,  40), "tags": ["opaque", "misc"]},
    {"id": "minecraft:hay_block",           "rgb": (175, 155,  19), "tags": ["opaque", "misc"]},
    {"id": "minecraft:melon",               "rgb": (143, 179,  40), "tags": ["opaque", "misc"]},
    {"id": "minecraft:pumpkin",             "rgb": (194, 105,  17), "tags": ["opaque", "misc"]},
    {"id": "minecraft:carved_pumpkin",      "rgb": (167,  94,  15), "tags": ["opaque", "misc"]},
    {"id": "minecraft:jack_o_lantern",      "rgb": (167,  94,  15), "tags": ["opaque", "misc", "emissive"]},
]


# ---------------------------------------------------------------------------
# Mapa de bloques sólidos → variantes con forma (escaleras, losas, muros)
# ---------------------------------------------------------------------------
# Para cada bloque sólido de BLOCK_DATABASE, lista las variantes disponibles.
# Solo se incluyen bloques cuya variante existe en Minecraft 1.21.
SHAPED_BLOCK_MAP: dict[str, dict[str, str]] = {
    # ── Madera (tablones) ──────────────────────────────────────────────────
    "minecraft:oak_planks":        {"stair": "minecraft:oak_stairs",         "slab": "minecraft:oak_slab"},
    "minecraft:birch_planks":      {"stair": "minecraft:birch_stairs",        "slab": "minecraft:birch_slab"},
    "minecraft:spruce_planks":     {"stair": "minecraft:spruce_stairs",       "slab": "minecraft:spruce_slab"},
    "minecraft:jungle_planks":     {"stair": "minecraft:jungle_stairs",       "slab": "minecraft:jungle_slab"},
    "minecraft:acacia_planks":     {"stair": "minecraft:acacia_stairs",       "slab": "minecraft:acacia_slab"},
    "minecraft:dark_oak_planks":   {"stair": "minecraft:dark_oak_stairs",     "slab": "minecraft:dark_oak_slab"},
    "minecraft:mangrove_planks":   {"stair": "minecraft:mangrove_stairs",     "slab": "minecraft:mangrove_slab"},
    "minecraft:cherry_planks":     {"stair": "minecraft:cherry_stairs",       "slab": "minecraft:cherry_slab"},
    "minecraft:bamboo_planks":     {"stair": "minecraft:bamboo_stairs",       "slab": "minecraft:bamboo_slab"},
    "minecraft:crimson_planks":    {"stair": "minecraft:crimson_stairs",      "slab": "minecraft:crimson_slab"},
    "minecraft:warped_planks":     {"stair": "minecraft:warped_stairs",       "slab": "minecraft:warped_slab"},
    # ── Piedra ─────────────────────────────────────────────────────────────
    "minecraft:stone":             {"stair": "minecraft:stone_stairs",        "slab": "minecraft:stone_slab"},
    "minecraft:smooth_stone":      {"slab":  "minecraft:smooth_stone_slab"},
    "minecraft:cobblestone":       {"stair": "minecraft:cobblestone_stairs",  "slab": "minecraft:cobblestone_slab",   "wall": "minecraft:cobblestone_wall"},
    "minecraft:stone_bricks":      {"stair": "minecraft:stone_brick_stairs",  "slab": "minecraft:stone_brick_slab",   "wall": "minecraft:stone_brick_wall"},
    "minecraft:mossy_stone_bricks":{"stair": "minecraft:mossy_stone_brick_stairs", "slab": "minecraft:mossy_stone_brick_slab", "wall": "minecraft:mossy_stone_brick_wall"},
    "minecraft:granite":           {"stair": "minecraft:granite_stairs",      "slab": "minecraft:granite_slab",       "wall": "minecraft:granite_wall"},
    "minecraft:polished_granite":  {"stair": "minecraft:polished_granite_stairs", "slab": "minecraft:polished_granite_slab"},
    "minecraft:diorite":           {"stair": "minecraft:diorite_stairs",      "slab": "minecraft:diorite_slab",       "wall": "minecraft:diorite_wall"},
    "minecraft:polished_diorite":  {"stair": "minecraft:polished_diorite_stairs", "slab": "minecraft:polished_diorite_slab"},
    "minecraft:andesite":          {"stair": "minecraft:andesite_stairs",     "slab": "minecraft:andesite_slab",      "wall": "minecraft:andesite_wall"},
    "minecraft:polished_andesite": {"stair": "minecraft:polished_andesite_stairs", "slab": "minecraft:polished_andesite_slab"},
    "minecraft:tuff":              {"stair": "minecraft:tuff_stairs",         "slab": "minecraft:tuff_slab",          "wall": "minecraft:tuff_wall"},
    "minecraft:deepslate_bricks":  {"stair": "minecraft:deepslate_brick_stairs", "slab": "minecraft:deepslate_brick_slab", "wall": "minecraft:deepslate_brick_wall"},
    "minecraft:cobbled_deepslate": {"stair": "minecraft:cobbled_deepslate_stairs", "slab": "minecraft:cobbled_deepslate_slab", "wall": "minecraft:cobbled_deepslate_wall"},
    # ── Prismarine ─────────────────────────────────────────────────────────
    "minecraft:prismarine":        {"stair": "minecraft:prismarine_stairs",   "slab": "minecraft:prismarine_slab",    "wall": "minecraft:prismarine_wall"},
    "minecraft:prismarine_bricks": {"stair": "minecraft:prismarine_brick_stairs", "slab": "minecraft:prismarine_brick_slab"},
    "minecraft:dark_prismarine":   {"stair": "minecraft:dark_prismarine_stairs", "slab": "minecraft:dark_prismarine_slab"},
    # ── End ────────────────────────────────────────────────────────────────
    "minecraft:end_stone_bricks":  {"stair": "minecraft:end_stone_brick_stairs", "slab": "minecraft:end_stone_brick_slab", "wall": "minecraft:end_stone_brick_wall"},
    "minecraft:purpur_block":      {"stair": "minecraft:purpur_stairs",       "slab": "minecraft:purpur_slab"},
    # ── Quartz y Nether ────────────────────────────────────────────────────
    "minecraft:quartz_block":      {"stair": "minecraft:quartz_stairs",       "slab": "minecraft:quartz_slab"},
    "minecraft:smooth_quartz":     {"stair": "minecraft:smooth_quartz_stairs","slab": "minecraft:smooth_quartz_slab"},
    "minecraft:nether_bricks":     {"stair": "minecraft:nether_brick_stairs", "slab": "minecraft:nether_brick_slab",  "wall": "minecraft:nether_brick_wall"},
    "minecraft:red_nether_bricks": {"stair": "minecraft:red_nether_brick_stairs", "slab": "minecraft:red_nether_brick_slab"},
    "minecraft:blackstone":        {"stair": "minecraft:blackstone_stairs",   "slab": "minecraft:blackstone_slab",    "wall": "minecraft:blackstone_wall"},
    # ── Cobre ──────────────────────────────────────────────────────────────
    "minecraft:copper_block":      {"stair": "minecraft:copper_stairs",       "slab": "minecraft:copper_slab"},
    "minecraft:exposed_copper":    {"stair": "minecraft:exposed_copper_stairs","slab": "minecraft:exposed_copper_slab"},
    "minecraft:weathered_copper":  {"stair": "minecraft:weathered_copper_stairs", "slab": "minecraft:weathered_copper_slab"},
    "minecraft:oxidized_copper":   {"stair": "minecraft:oxidized_copper_stairs", "slab": "minecraft:oxidized_copper_slab"},
}

# ---------------------------------------------------------------------------
# Presets de paleta de bloques
# ---------------------------------------------------------------------------
# Cada preset es una lista de block IDs (o None = todos los bloques).
PRESETS: dict[str, list[str] | None] = {
    "Todo": None,
    "Medieval": [
        "minecraft:stone", "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
        "minecraft:cracked_stone_bricks", "minecraft:cobblestone",
        "minecraft:granite", "minecraft:andesite", "minecraft:diorite",
        "minecraft:oak_planks", "minecraft:spruce_planks", "minecraft:dark_oak_planks",
        "minecraft:oak_log", "minecraft:spruce_log", "minecraft:dark_oak_log",
        "minecraft:gravel", "minecraft:dirt", "minecraft:grass_block", "minecraft:sand",
        "minecraft:iron_block", "minecraft:glass", "minecraft:obsidian",
        "minecraft:hay_block", "minecraft:brown_wool", "minecraft:gray_wool",
        "minecraft:white_wool", "minecraft:black_wool",
    ],
    "Moderno": [
        "minecraft:white_concrete", "minecraft:light_gray_concrete",
        "minecraft:gray_concrete", "minecraft:black_concrete",
        "minecraft:quartz_block", "minecraft:smooth_quartz", "minecraft:quartz_bricks",
        "minecraft:polished_diorite", "minecraft:polished_andesite",
        "minecraft:polished_granite", "minecraft:iron_block", "minecraft:calcite",
        "minecraft:birch_planks", "minecraft:white_wool", "minecraft:light_gray_wool",
        "minecraft:glass", "minecraft:white_stained_glass",
        "minecraft:obsidian", "minecraft:tuff",
    ],
    "Nether": [
        "minecraft:netherrack", "minecraft:nether_bricks", "minecraft:red_nether_bricks",
        "minecraft:blackstone", "minecraft:basalt", "minecraft:polished_basalt",
        "minecraft:nether_wart_block", "minecraft:warped_wart_block",
        "minecraft:soul_sand", "minecraft:gilded_blackstone",
        "minecraft:netherite_block", "minecraft:magma_block",
        "minecraft:obsidian", "minecraft:crying_obsidian",
        "minecraft:shroomlight", "minecraft:glowstone",
    ],
    "Fantasy": (
        [b["id"] for b in BLOCK_DATABASE if "concrete" in b["tags"]]
        + [b["id"] for b in BLOCK_DATABASE if "wool" in b["tags"]]
        + [
            "minecraft:amethyst_block", "minecraft:purpur_block",
            "minecraft:purpur_pillar", "minecraft:crying_obsidian",
            "minecraft:prismarine", "minecraft:prismarine_bricks",
            "minecraft:dark_prismarine", "minecraft:emerald_block",
            "minecraft:diamond_block", "minecraft:lapis_block",
            "minecraft:gold_block", "minecraft:sea_lantern",
            "minecraft:shroomlight", "minecraft:glowstone",
        ]
    ),
    "Solo Concreto": [b["id"] for b in BLOCK_DATABASE if "concrete" in b["tags"]],
    "Solo Lana":     [b["id"] for b in BLOCK_DATABASE if "wool"     in b["tags"]],
    "Solo Piedra":   [b["id"] for b in BLOCK_DATABASE if "stone"    in b["tags"]],
}


def get_opaque_blocks() -> list[dict]:
    """Retorna solo los bloques opacos (útil como set primario de matching)."""
    return [b for b in BLOCK_DATABASE if "opaque" in b["tags"]]


def get_all_blocks() -> list[dict]:
    """Retorna todos los bloques de la base de datos."""
    return list(BLOCK_DATABASE)


def block_rgb_array(blocks: list[dict]) -> np.ndarray:
    """
    Convierte la lista de bloques en un array numpy de colores RGB.

    Returns
    -------
    np.ndarray, shape (N, 3), dtype float32, values [0, 1]
    """
    colors = np.array([b["rgb"] for b in blocks], dtype=np.float32)
    return colors / 255.0
