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

from parsing import *

protocol = {}

### GENERIC MESSAGES - Independent of protocol version ###

protocol[0] = [None] * 256, [None] * 256
cli_msgs, srv_msgs = protocol[0]

cli_msgs[0x01] = defmsg(0x01,"Login Request",[
    ('proto_version',MC_int),
    ('username',MC_string),
    ('nu1',MC_long),
    ('nu2', MC_int),
    ('nu3', MC_byte),
    ('nu4', MC_byte),
    ('nu5', MC_unsigned_byte),
    ('nu6', MC_unsigned_byte)])
srv_msgs[0x01] = defmsg(0x01,"Login Response",[
    ('eid',MC_int),
    ('reserved',MC_string),
    ('map_seed',MC_long),
    ('server_mode', MC_int),
    ('dimension', MC_byte),
    ('difficulty', MC_byte),
    ('world_height', MC_unsigned_byte),
    ('max_players', MC_unsigned_byte)])

cli_msgs[0x02] = defmsg(0x02,"Handshake",[
    ('username',MC_string)])
srv_msgs[0x02] = defmsg(0x02, "Handshake", [
    ('hash',MC_string)])

cli_msgs[0xfe] = defmsg(0xfe, "Server List Ping", [])

cli_msgs[0xff] = \
srv_msgs[0xff] = defmsg(0xff, "Disconnect/Kick", [
    ('reason', MC_string)])

### VERSION 17 - Corresponds to Beta 1.8

protocol[17] = tuple(map(list, protocol[0]))
cli_msgs, srv_msgs = protocol[17]

cli_msgs[0x00] = \
srv_msgs[0x00] = defmsg(0x00,"Keep Alive",[
    ('id', MC_int)])

cli_msgs[0x03] = \
srv_msgs[0x03] = defmsg(0x03, "Chat",[
    ('chat_msg',MC_string)])

srv_msgs[0x04] = defmsg(0x04, "Time", [
    ('time',MC_long)])

cli_msgs[0x05] = \
srv_msgs[0x05] = defmsg(0x05, "Entity Equipment Spawn",[
    ('eid',MC_int),
    ('slot',MC_short),
    ('item_id',MC_short),
    ('unknown',MC_short)])

srv_msgs[0x06] = defmsg(0x06, "Spawn position",[
    ('x',MC_int),
    ('y',MC_int),
    ('z',MC_int)])

cli_msgs[0x07] = defmsg(0x07, "Use entity", [
    ('eid',MC_int),
    ('target_eid',MC_int),
    ('left_click',MC_bool)])

srv_msgs[0x08] = defmsg(0x08, "Update health", [
    ('health',MC_short),
    ('food', MC_short),
    ('food_saturation', MC_float)])

cli_msgs[0x09] = \
srv_msgs[0x09] = defmsg(0x09, "Respawn", [
    ('world', MC_byte),
    ('difficulty', MC_byte),
    ('mode', MC_byte),
    ('world_height', MC_short),
    ('map_seed', MC_long)])

cli_msgs[0x0a] = defmsg(0x0a, "Player state", [
    ('on_ground',MC_bool)])

cli_msgs[0x0b] = \
srv_msgs[0x0b] = defmsg(0x0b, "Player position", [
    ('x',MC_double),
    ('y',MC_double),
    ('stance',MC_double),
    ('z',MC_double),
    ('on_ground',MC_bool)])

cli_msgs[0x0c] = defmsg(0x0c, "Player look", [
    ('yaw',MC_float),
    ('pitch',MC_float),
    ('on_ground',MC_bool)])

# Note the difference in ordering of 'stance'!
cli_msgs[0x0d] = defmsg(0x0d, "Player position and look",[
    ('x',MC_double),
    ('y',MC_double),
    ('stance',MC_double),
    ('z',MC_double),
    ('yaw',MC_float),
    ('pitch',MC_float),
    ('on_ground',MC_bool)])
srv_msgs[0x0d] = defmsg(0x0d, "Player position and look", [
    ('x',MC_double),
    ('stance',MC_double),
    ('y',MC_double),
    ('z',MC_double),
    ('yaw',MC_float),
    ('pitch',MC_float),
    ('on_ground',MC_bool)])

cli_msgs[0x0e] = \
srv_msgs[0x0e] = defmsg(0x0e, "Digging", [
    ('status',MC_byte),
    ('x',MC_int),
    ('y',MC_byte),
    ('z',MC_int),
    ('face',MC_byte)])

cli_msgs[0x0f] = \
srv_msgs[0x0f] = defmsg(0x0f, "Block placement", [
    ('x',MC_int),
    ('y',MC_byte),
    ('z',MC_int),
    ('dir',MC_byte),
    ('details',MC_slot_update)])

cli_msgs[0x10] = \
srv_msgs[0x10] = defmsg(0x10, "Held item selection",[
    ('slot_id', MC_short)])

srv_msgs[0x11] = defmsg(0x11, "Use bed", [
    ('eid', MC_int),
    ('in_bed', MC_bool),
    ('x', MC_int),
    ('y', MC_byte),
    ('z', MC_int)])

cli_msgs[0x12] = \
srv_msgs[0x12] = defmsg(0x12, "Change animation",[
    ('eid',MC_int),
    ('animation',MC_byte)])

cli_msgs[0x13] = \
srv_msgs[0x13] = defmsg(0x13, "Entity action", [
    ('eid',MC_int),
    ('action', MC_byte)])

srv_msgs[0x14] = defmsg(0x14, "Entity spawn", [
    ('eid', MC_int),
    ('name', MC_string),
    ('x', MC_int),
    ('y', MC_int),
    ('z', MC_int),
    ('rotation', MC_byte),
    ('pitch', MC_byte),
    ('curr_item', MC_short)])

cli_msgs[0x15] = \
srv_msgs[0x15] = defmsg(0x15, "Pickup spawn", [
    ('eid',MC_int),
    ('item',MC_short),
    ('count',MC_byte),
    ('data',MC_short),
    ('x',MC_int),
    ('y',MC_int),
    ('z',MC_int),
    ('rotation',MC_byte),
    ('pitch',MC_byte),
    ('roll',MC_byte)])

srv_msgs[0x16] = defmsg(0x16, "Collect item", [
    ('item_eid',MC_int),
    ('collector_eid',MC_int)])

srv_msgs[0x17] = defmsg(0x17, "Add vehicle/object", [
    ('eid',MC_int),
    ('type',MC_byte),
    ('x',MC_int),
    ('y',MC_int),
    ('z',MC_int),
    ('fireball_data',MC_fireball_data)])

srv_msgs[0x18] = defmsg(0x18, "Mob spawn", [
    ('eid',MC_int),
    ('mob_type',MC_byte),
    ('x',MC_int),
    ('y',MC_int),
    ('z',MC_int),
    ('yaw',MC_byte),
    ('pitch',MC_byte),
    ('metadata',parse_metadata)])

srv_msgs[0x19] = defmsg(0x19, "Painting", [
    ('eid', MC_int),
    ('title', MC_string),
    ('x', MC_int),
    ('y', MC_int),
    ('z', MC_int),
    ('type', MC_int)])

srv_msgs[0x1a] = defmsg(0x1a, "Experience orb", [
    ('eid', MC_int),
    ('x', MC_int),
    ('y', MC_int),
    ('z', MC_int),
    ('count', MC_short)])

cli_msgs[0x1b] = \
srv_msgs[0x1b] = defmsg(0x1b, "???", [
    ('d1', MC_float),
    ('d2', MC_float),
    ('d3', MC_float),
    ('d4', MC_float),
    ('d5', MC_bool),
    ('d6', MC_bool)])

cli_msgs[0x1c] = \
srv_msgs[0x1c] = defmsg(0x1c, "Entity velocity", [
    ('eid',MC_int),
    ('vel_x',MC_short),
    ('vel_y',MC_short),
    ('vel_z',MC_short)])

srv_msgs[0x1d] = defmsg(0x1d, "Destroy entity", [
    ('eid',MC_int)])

srv_msgs[0x1e] = defmsg(0x1e, "Entity", [
    ('eid', MC_int)])

srv_msgs[0x1f] = defmsg(0x1f, "Entity relative move", [
    ('eid',MC_int),
    ('dx',MC_byte),
    ('dy',MC_byte),
    ('dz',MC_byte)])

srv_msgs[0x20] = defmsg(0x20, "Entity look", [
    ('eid', MC_int),
    ('yaw', MC_byte),
    ('pitch', MC_byte)])

srv_msgs[0x21] = defmsg(0x21, "Entity look/relative move", [
    ('eid',MC_int),
    ('dx',MC_byte),
    ('dy',MC_byte),
    ('dz',MC_byte),
    ('yaw',MC_byte),
    ('pitch',MC_byte)])

srv_msgs[0x22] = defmsg(0x22, "Entity teleport", [
    ('eid', MC_int),
    ('x', MC_int),
    ('y', MC_int),
    ('z', MC_int),
    ('yaw', MC_byte),
    ('pitch', MC_byte)])

srv_msgs[0x26] = defmsg(0x26, "Entity status", [
    ('eid',MC_int),
    ('status',MC_byte)])

cli_msgs[0x27] = \
srv_msgs[0x27] = defmsg(0x27, "Attach entity", [
    ('eid',MC_int),
    ('vehicle_id',MC_int)])

cli_msgs[0x28] = \
srv_msgs[0x28] = defmsg(0x28, "Entity metadata", [
    ('eid',MC_int),
    ('metadata',parse_metadata)])

cli_msgs[0x29] = \
srv_msgs[0x29] = defmsg(0x29, "Entity Effect", [
    ('eid', MC_int),
    ('effect_id', MC_byte),
    ('aplifier', MC_byte),
    ('duration', MC_short)])

cli_msgs[0x2a] = \
srv_msgs[0x2a] = defmsg(0x2a, "Remove entity effect", [
    ('eid', MC_int),
    ('effect_id', MC_byte)])

srv_msgs[0x2b] = defmsg(0x2b, "Experience", [
    ('curr_exp', MC_byte),
    ('level', MC_byte),
    ('tot_exp', MC_short)])

srv_msgs[0x32] = defmsg(0x32, "Pre-chunk", [
    ('x',MC_int),
    ('z',MC_int),
    ('mode',MC_bool)])

srv_msgs[0x33] = defmsg(0x33, "Chunk", [
    ('x',MC_int),
    ('y',MC_short),
    ('z',MC_int),
    ('size_x',MC_byte),
    ('size_y',MC_byte),
    ('size_z',MC_byte),
    ('chunk',MC_chunk)])

cli_msgs[0x34] = \
srv_msgs[0x34] = defmsg(0x34, "Multi-block change", [
    ('chunk_x',MC_int),
    ('chunk_z',MC_int),
    ('changes',MC_multi_block_change)])

cli_msgs[0x35] = \
srv_msgs[0x35] = defmsg(0x35, "Block change", [
    ('x',MC_int),
    ('y',MC_byte),
    ('z',MC_int),
    ('block_type',MC_byte),
    ('block_metadata',MC_byte)])

srv_msgs[0x36] = defmsg(0x36, "Play note block",[
    ('x', MC_int),
    ('y', MC_short),
    ('z', MC_int),
    ('instrument_type', MC_byte),
    ('pitch', MC_byte)])

srv_msgs[0x3c] = defmsg(0x3c, "Explosion", [
    ('x', MC_double),
    ('y', MC_double),
    ('z', MC_double),
    ('unknown', MC_float),
    ('records', MC_explosion_records)])

srv_msgs[0x3d] = defmsg(0x3d, "Sound effect", [
    ('effect_id', MC_int),
    ('x', MC_int),
    ('y', MC_byte),
    ('z', MC_int),
    ('data', MC_int)])

cli_msgs[0x46] = \
srv_msgs[0x46] = defmsg(0x46, "New/Invalid State", [
    ('reason', MC_byte),
    ('game_mode', MC_byte)])

srv_msgs[0x47] = defmsg(0x47, "Weather", [
    ('eid', MC_int),
    ('raining', MC_bool),
    ('x', MC_int),
    ('y', MC_int),
    ('z', MC_int)])

srv_msgs[0x64] = defmsg(0x64, "Open window", [
    ('window_id', MC_byte),
    ('inv_type', MC_byte),
    ('window_title', MC_string),
    ('num_slots', MC_byte)])

cli_msgs[0x65] = \
srv_msgs[0x65] = defmsg(0x65, "Close window", [
    ('window_id', MC_byte)])

cli_msgs[0x66] = defmsg(0x66, "Window click", [
    ('window_id', MC_byte),
    ('slot', MC_short),
    ('is_right_click', MC_bool),
    ('action_num', MC_short),
    ('shift', MC_bool),
    ('details', MC_slot_update)])

srv_msgs[0x67] = defmsg(0x67, "Set slot", [
    ('window_id',MC_byte),
    ('slot',MC_short),
    ('slot_update',MC_slot_update)])

srv_msgs[0x68] = defmsg(0x68, "Window items", [
    ('window_id',MC_byte),
    ('inventory',MC_inventory)])

srv_msgs[0x69] = defmsg(0x69, "Update progress bar", [
    ('window_id', MC_byte),
    ('progress_bar',MC_short),
    ('value',MC_short)])

cli_msgs[0x6a] = \
srv_msgs[0x6a] = defmsg(0x6a, "Transaction", [
    ('window_id', MC_byte),
    ('action_num', MC_short),
    ('accepted', MC_bool)])

cli_msgs[0x6b] = \
srv_msgs[0x6b] = defmsg(0x6b, "Creative inventory action", [
    ('slot', MC_short),
    ('item_id', MC_short),
    ('quantity', MC_short),
    ('damage', MC_short)])

cli_msgs[0x82] = \
srv_msgs[0x82] = defmsg(0x82, "Update sign", [
    ('x', MC_int),
    ('y', MC_short),
    ('z', MC_int),
    ('text1', MC_string),
    ('text2', MC_string),
    ('text3', MC_string),
    ('text4', MC_string)])

cli_msgs[0x83] = \
srv_msgs[0x83] = defmsg(0x83, "Item data", [
    ('item_type', MC_short),
    ('item_id', MC_short),
    ('data', MC_item_data)])

srv_msgs[0xc8] = defmsg(0xc8, "Increment statistic", [
    ('stat_id', MC_int),
    ('amount', MC_byte)])

srv_msgs[0xc9] = defmsg(0xc9, "Player list item", [
    ('name', MC_string),
    ('online', MC_bool),
    ('ping', MC_short)])

### Version 18 - Beta 1.9pre1 (UNTESTED)
protocol[18] = tuple(map(list, protocol[17]))
cli_msgs, srv_msgs = protocol[18]

# According to http://mc.kev009.com/Pre-release_protocol, there were no
# message format changes in this release.

### Version 19 - Beta 1.9pre2 (UNTESTED)
protocol[19] = tuple(map(list, protocol[18]))
cli_msgs, srv_msgs = protocol[19]

cli_msgs[0x0f] = \
srv_msgs[0x0f] = defmsg(0x0f, "Block placement", [
    ('x',MC_int),
    ('y',MC_byte),
    ('z',MC_int),
    ('dir',MC_byte),
    ('details',MC_slot_update2)])

cli_msgs[0x66] = defmsg(0x66, "Window click", [
    ('window_id', MC_byte),
    ('slot', MC_short),
    ('is_right_click', MC_bool),
    ('action_num', MC_short),
    ('shift', MC_bool),
    ('details', MC_slot_update2)])

srv_msgs[0x67] = defmsg(0x67, "Set slot", [
    ('window_id',MC_byte),
    ('slot',MC_short),
    ('slot_update',MC_slot_update2)])

srv_msgs[0x68] = defmsg(0x68, "Window items", [
    ('window_id',MC_byte),
    ('inventory',MC_inventory2)])

### Version 20 - Beta 1.9pre4
protocol[20] = tuple(map(list, protocol[19]))
cli_msgs, srv_msgs = protocol[20]

srv_msgs[0x2b] = defmsg(0x2b, "Experience", [
    ('curr_exp', MC_float),
    ('level', MC_short),
    ('tot_exp', MC_short)])

cli_msgs[0x6c] = defmsg(0x6c, "Enchant Item", [
    ('window_id', MC_byte),
    ('enchantment', MC_byte)])

### Version 21 - Beta 1.9pre5.

protocol[21] = tuple(map(list, protocol[20]))
cli_msgs, srv_msgs = protocol[21]

cli_msgs[0x6b] = \
srv_msgs[0x6b] = defmsg(0x6b, "Creative inventory action", [
    ('slot', MC_short),
    ('details', MC_slot_update2)])

