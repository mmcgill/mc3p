# This source file is part of mc3p, the Minecraft Protocol Parsing Proxy.
#
# Copyright (C) 2011 Matthew J. McGill

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License v2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Data and helper functions pertaining to Minecraft blocks."""

AIR_BLOCK           = 0x00
STONE_BLOCK         = 0x01
GRASS_BLOCK         = 0x02
DIRT_BLOCK          = 0x03
COBBLE_BLOCK        = 0x04
PLANK_BLOCK         = 0x05
SAPLING_BLOCK       = 0x06
BEDROCK_BLOCK       = 0X07
WATER_BLOCK         = 0X08
STILL_WATER_BLOCK   = 0x09
LAVA_BLOCK          = 0X0a
STILL_LAVA_BLOCK    = 0x0b
SAND_BLOCK          = 0x0c
GRAVEL_BLOCK        = 0x0d
GOLD_ORE_BLOCK      = 0x0e
IRON_ORE_BLOCK      = 0x0f
COAL_ORE_BLOCK      = 0x10
WOOD_BLOCK          = 0x11
LEAF_BLOCK          = 0x12
SPONGE_BLOCK        = 0x13
GLASS_BLOCK         = 0x14
LAPIS_ORE_BLOCK     = 0x15
LAPIS_BLOCK         = 0x16
DISPENSER_BLOCK     = 0x17
SANDSTONE_BLOCK     = 0x18
NOTE_BLOCK          = 0x19
BED_BLOCK           = 0x1a
POWERED_RAIL_BLOCK  = 0x1b
DETECTOR_RAIL_BLOCK = 0x1c
STICKY_PISTON_BLOCK = 0x1d
COBWEB_BLOCK        = 0x1e
TALL_GRASS_BLOCK    = 0x1f
DEAD_BUSH_BLOCK     = 0x20
PISTON_BLOCK        = 0x21
PISTON_ARM_BLOCK    = 0x22
WOOL_BLOCK          = 0x23
MOVED_BLOCK         = 0x24
DANDELION_BLOCK     = 0x25
ROSE_BLOCK          = 0x26
BROWN_SHROOM_BLOCK  = 0x27
RED_SHROOM_BLOCK    = 0x28
GOLD_BLOCK          = 0x29
IRON_BLOCK          = 0x2a
DOUBLE_SLAB_BLOCK   = 0x2b
SLAB_BLOCK          = 0x2c
BRICK_BLOCK         = 0x2d
TNT_BLOCK           = 0x2e
BOOKSHELF_BLOCK     = 0x2f
MOSSY_COBBLE_BLOCK  = 0x30
OBSIDIAN_BLOCK      = 0x31
TORCH_BLOCK         = 0x32
FIRE_BLOCK          = 0x33
SPAWNER_BLOCK       = 0x34
PLANK_STAIRS_BLOCK  = 0x35
CHEST_BLOCK         = 0x36
WIRE_BLOCK          = 0x37
DIAMOND_ORE_BLOCK   = 0x38
DIAMOND_BLOCK       = 0x39
CRAFTBENCH_BLOCK    = 0x3a
SEEDS_BLOCK         = 0x3b
FARMLAND_BLOCK      = 0x3c
FURNACE_BLOCK       = 0x3d
LIT_FURNACE_BLOCK   = 0x3e
SIGN_BLOCK          = 0x3f
WOOD_DOOR_BLOCK     = 0x40
LADDER_BLOCK        = 0x41
RAIL_BLOCK          = 0x42
COBBLE_STAIRS_BLOCK = 0x43
WALL_SIGN_BLOCK     = 0x44
LEVER_BLOCK         = 0x45
STONE_PLATE_BLOCK   = 0x46
IRON_DOOR_BLOCK     = 0x47
WOOD_PLATE_BLOCK    = 0x48
REDSTONE_ORE_BLOCK  = 0x49
LIT_REDSTONE_ORE_BLOCK = 0x4a
REDSTONE_TORCH_BLOCK = 0x4b
LIT_REDSTONE_TORCH_BLOCK = 0x4c
STONE_BUTTON_BLOCK = 0x4d
SNOW_COVER_BLOCK    = 0x4e
ICE_BLOCK           = 0x4f
SNOW_BLOCK          = 0x50
CACTUS_BLOCK        = 0x51
CLAY_BLOCK          = 0x52
SUGAR_CANE_BLOCK    = 0x53
JUKEBOX_BLOCK       = 0x54
FENCE_BLOCK         = 0x55
PUMPKIN_BLOCK       = 0x56
NETHERRACK_BLOCK    = 0x57
SOULSAND_BLOCK      = 0x58
GLOWSTONE_BLOCK     = 0x59
PORTAL_BLOCK        = 0x5a
JACKOLANTERN_BLOCK  = 0x5b
CAKE_BLOCK          = 0x5c
REPEATER_BLOCK      = 0x5d
LIT_REPEATER_BLOCK  = 0x5e
LOCKED_CHEST_BLOCK  = 0x5f
TRAPDOOR_BLOCK      = 0x60
SILVERFISH_BLOCK    = 0x61
STONE_BRICK_BLOCK   = 0x62
BIG_BROWN_SHROOM_BLOCK = 0x63
BIG_RED_SHROOM_BLOCK = 0x64
IRON_BARS_BLOCK     = 0x65
GLASS_PANE_BLOCK    = 0x66
MELON_BLOCK         = 0x67
PUMPKIN_STEM_BLOCK  = 0x68
MELON_VINE_BLOCK    = 0x69
VINES_BLOCK         = 0x6a
FENCE_GATE_BLOCK    = 0x6b
BRICK_STAIRS_BLOCK  = 0x6c
STONE_BRICK_STAIRS_BLOCK = 0x6d
MYCELIUM_BLOCK      = 0x6e
LILYPAD_BLOCK       = 0x6f
NETHER_BRICK_BLOCK  = 0x70
NETHER_BRICK_STAIRS_BLOCK = 0x71
NETHER_WART_BLOCK   = 0x72
ENCHANTING_TABLE_BLOCK = 0x73
BREWING_STAND_BLOCK = 0x74
CAULDRON_BLOCK      = 0x75
AIR_PORTAL_BLOCK    = 0x76
AIR_PORTAL_FRAME_BLOCK = 0x77

def tile_offset(row, col):
    return (row, col)

TILE_OFFSETS = {
    STONE_BLOCK:            tile_offset(0, 1),
    GRASS_BLOCK:            tile_offset(0, 0),
    DIRT_BLOCK:             tile_offset(0, 2),
    COBBLE_BLOCK:           tile_offset(1, 0),
    PLANK_BLOCK:            tile_offset(0, 4),
    BEDROCK_BLOCK:          tile_offset(1, 1),
    WATER_BLOCK:            tile_offset(13, 15),
    STILL_WATER_BLOCK:      tile_offset(13, 15),
    LAVA_BLOCK:             tile_offset(15, 15),
    STILL_LAVA_BLOCK:       tile_offset(15, 15),
    SAND_BLOCK:             tile_offset(1, 2),
    GRAVEL_BLOCK:           tile_offset(1, 3),
    GOLD_ORE_BLOCK:         tile_offset(2, 0),
    IRON_ORE_BLOCK:         tile_offset(2, 1),
    COAL_ORE_BLOCK:         tile_offset(2, 2),
    WOOD_BLOCK:             tile_offset(1, 5),
    SPONGE_BLOCK:           tile_offset(3, 0),
    GLASS_BLOCK:            tile_offset(3, 1),
    LAPIS_ORE_BLOCK:        tile_offset(10, 0),
    LAPIS_BLOCK:            tile_offset(9, 0),
    DISPENSER_BLOCK:        tile_offset(3, 14),
    SANDSTONE_BLOCK:        tile_offset(11, 0),
    NOTE_BLOCK:             tile_offset(4, 10),
    STICKY_PISTON_BLOCK:    tile_offset(6, 12),
    PISTON_BLOCK:           tile_offset(6, 12),
    WOOL_BLOCK:             tile_offset(4, 0),
    GOLD_BLOCK:             tile_offset(1, 7),
    IRON_BLOCK:             tile_offset(1, 6),
    DOUBLE_SLAB_BLOCK:      tile_offset(0, 6),
    SLAB_BLOCK:             tile_offset(0, 6),
    BRICK_BLOCK:            tile_offset(0, 7),
    TNT_BLOCK:              tile_offset(0, 9),
    BOOKSHELF_BLOCK:        tile_offset(0, 4),
    MOSSY_COBBLE_BLOCK:     tile_offset(2, 4),
    OBSIDIAN_BLOCK:         tile_offset(2, 5),
    SPAWNER_BLOCK:          tile_offset(4, 1),
    PLANK_STAIRS_BLOCK:     tile_offset(0, 4),
    CHEST_BLOCK:            tile_offset(1, 9),
    DIAMOND_ORE_BLOCK:      tile_offset(3, 2),
    DIAMOND_BLOCK:          tile_offset(1, 8),
    CRAFTBENCH_BLOCK:       tile_offset(2, 11),
    FARMLAND_BLOCK:         tile_offset(5, 7),
    FURNACE_BLOCK:          tile_offset(3, 14),
    LIT_FURNACE_BLOCK:      tile_offset(3, 14),
    COBBLE_STAIRS_BLOCK:    tile_offset(1, 0),
    REDSTONE_ORE_BLOCK:     tile_offset(3, 3),
    LIT_REDSTONE_ORE_BLOCK: tile_offset(3, 3),
    ICE_BLOCK:              tile_offset(4, 3),
    SNOW_BLOCK:             tile_offset(4, 2),
    CACTUS_BLOCK:           tile_offset(4, 5),
    CLAY_BLOCK:             tile_offset(4, 8),
    JUKEBOX_BLOCK:          tile_offset(4, 11),
    PUMPKIN_BLOCK:          tile_offset(6, 6),
    NETHERRACK_BLOCK:       tile_offset(6, 7),
    SOULSAND_BLOCK:         tile_offset(6, 8),
    GLOWSTONE_BLOCK:        tile_offset(6, 9),
    JACKOLANTERN_BLOCK:     tile_offset(6, 6),
    LOCKED_CHEST_BLOCK:     tile_offset(1, 9),
    SILVERFISH_BLOCK:       tile_offset(0, 1),
    #STONE_BRICK_BLOCK:
    BIG_BROWN_SHROOM_BLOCK: tile_offset(7, 14),
    BIG_RED_SHROOM_BLOCK:   tile_offset(7, 13),
    MELON_BLOCK:            tile_offset(8, 9),
    BRICK_STAIRS_BLOCK:     tile_offset(0, 7),
    #STONE_BRICK_STAIRS_BLOCK:
    #MYCELIUM_BLOCK:
    #NETHER_BRICK_BLOCK:
    #NETHER_BRICK_STAIRS_BLOCK:
}


SOLID_BLOCK_TYPES = set([
    STONE_BLOCK, GRASS_BLOCK, DIRT_BLOCK, COBBLE_BLOCK, PLANK_BLOCK,
    BEDROCK_BLOCK, WATER_BLOCK, STILL_WATER_BLOCK, LAVA_BLOCK,
    STILL_LAVA_BLOCK, SAND_BLOCK, GRAVEL_BLOCK, GOLD_ORE_BLOCK,
    IRON_ORE_BLOCK, COAL_ORE_BLOCK, WOOD_BLOCK, SPONGE_BLOCK,
    LAPIS_ORE_BLOCK, LAPIS_BLOCK, DISPENSER_BLOCK, SANDSTONE_BLOCK,
    NOTE_BLOCK, STICKY_PISTON_BLOCK, PISTON_BLOCK, WOOL_BLOCK, MOVED_BLOCK,
    GOLD_BLOCK, IRON_BLOCK, DOUBLE_SLAB_BLOCK, SLAB_BLOCK, BRICK_BLOCK,
    TNT_BLOCK, BOOKSHELF_BLOCK, MOSSY_COBBLE_BLOCK, OBSIDIAN_BLOCK,
    SPAWNER_BLOCK, PLANK_STAIRS_BLOCK, CHEST_BLOCK, DIAMOND_ORE_BLOCK,
    DIAMOND_BLOCK, CRAFTBENCH_BLOCK, FARMLAND_BLOCK, FURNACE_BLOCK,
    LIT_FURNACE_BLOCK, COBBLE_STAIRS_BLOCK, REDSTONE_ORE_BLOCK,
    LIT_REDSTONE_ORE_BLOCK, ICE_BLOCK, SNOW_BLOCK, CACTUS_BLOCK, CLAY_BLOCK,
    JUKEBOX_BLOCK, PUMPKIN_BLOCK, NETHERRACK_BLOCK, SOULSAND_BLOCK,
    GLOWSTONE_BLOCK, JACKOLANTERN_BLOCK, LOCKED_CHEST_BLOCK,
    SILVERFISH_BLOCK, STONE_BRICK_BLOCK, BIG_BROWN_SHROOM_BLOCK,
    BIG_RED_SHROOM_BLOCK, MELON_BLOCK, BRICK_STAIRS_BLOCK,
    STONE_BRICK_STAIRS_BLOCK, MYCELIUM_BLOCK, NETHER_BRICK_BLOCK,
    NETHER_BRICK_STAIRS_BLOCK
])

def is_solid(blocktype):
    return blocktype in SOLID_BLOCK_TYPES

