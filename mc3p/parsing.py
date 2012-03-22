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

import sys, struct, logging, inspect

logger = logging.getLogger('parsing')

class Parsem(object):
    """Parser/emitter."""

    def __init__(self,parser,emitter):
        setattr(self,'parse',parser)
        setattr(self,'emit',emitter)

def parse_byte(stream):
    return struct.unpack_from(">b",stream.read(1))[0]

def emit_byte(b):
    return struct.pack(">b",b)


def with_defaults(tuple):
    if len(tuple) == 2:
        x,y = tuple
        return x,y,0,sys.maxint
    elif len(tuple) == 3:
        x,y,z = tuple
        return x,y,z,sys.maxint
    else:
        return tuple

def defmsg(msgtype, name, pairs):
    """Build a Parsem for a message out of (name,Parsem) pairs."""
    def parse(stream):
        msg = {'msgtype': msgtype}
        for (name,parsem) in pairs:
            msg[name] = parsem.parse(stream)
        return msg
    def emit(msg):
        return ''.join([emit_unsigned_byte(msgtype),
                        ''.join([parsem.emit(msg[name]) for (name,parsem) in pairs])])
    return Parsem(parse,emit)

def defloginmsg(tuples):
    """One-off used to define login message.
       The login message must be parsed before we know which protocol
       version is in use, but its format differs across protocol versions.
       We build a Parsem out of (name,min_version,max_version,Parsem) quads.
       We assume the first field of the message is an int containing the
       protocol version. For the remaining fields, min_version and max_version
       (inclusive) define the range of versions in which the field is present.
       """
    def parse(stream):
        msg = {'msgtype': 0x01}
        proto_version = parse_int(stream)
        msg['proto_version'] = proto_version
        for (name,parsem,min,max) in map(with_defaults, tuples):
            if min <= proto_version <= max:
                msg[name] = parsem.parse(stream)
        return msg
    def emit(msg):
        proto_version = msg['proto_version']
        pairs = ((name,parsem) for (name,parsem,x,y) in map(with_defaults, tuples)
                               if x <= proto_version <= y)
        return ''.join([emit_unsigned_byte(0x01),
                        emit_int(msg['proto_version']),
                        ''.join([parsem.emit(msg[name]) for (name,parsem) in pairs])])
    return Parsem(parse, emit)

MC_byte = Parsem(parse_byte,emit_byte)

def parse_unsigned_byte(stream):
    return struct.unpack(">B",stream.read(1))[0]

def emit_unsigned_byte(b):
    return struct.pack(">B",b)

MC_unsigned_byte = Parsem(parse_unsigned_byte, emit_unsigned_byte)

def parse_short(stream):
    return struct.unpack_from(">h",stream.read(2))[0]

def emit_short(s):
    return struct.pack(">h",s)

MC_short = Parsem(parse_short, emit_short)

def parse_int(stream):
    return struct.unpack_from(">i",stream.read(4))[0]

def emit_int(i):
    return struct.pack(">i",i)

MC_int = Parsem(parse_int, emit_int)

def parse_long(stream):
    return struct.unpack_from(">q",stream.read(8))[0]

def emit_long(l):
    return struct.pack(">q",l)

MC_long = Parsem(parse_long, emit_long)

def parse_float(stream):
    return struct.unpack_from(">f",stream.read(4))[0]

def emit_float(f):
    return struct.pack(">f",f)

MC_float = Parsem(parse_float, emit_float)

def parse_double(stream):
    return struct.unpack_from(">d",stream.read(8))[0]

def emit_double(d):
    return struct.pack(">d",d)

MC_double = Parsem(parse_double, emit_double)

def parse_string(stream):
    n = parse_short(stream)
    if n == 0:
        return unicode("", encoding="utf-16-be")
    return unicode(stream.read(2*n), encoding="utf-16-be")

def emit_string(s):
    return ''.join([emit_short(len(s)), s.encode("utf-16-be")])

MC_string = Parsem(parse_string, emit_string)

def parse_string8(stream):
    n = parse_short(stream)
    if n == 0:
        return ''
    return stream.read(n)

def emit_string8(s):
    return ''.join([emit_short(len(s)),s])

MC_string8 = Parsem(parse_string8, emit_string8)

def parse_bool(stream):
    b = struct.unpack_from(">B",stream.read(1))[0]
    if b==0:
        return False
    else:
        return True

def emit_bool(b):
    if b:
        return emit_unsigned_byte(1)
    else:
        return emit_unsigned_byte(0)

MC_bool = Parsem(parse_bool, emit_bool)

def parse_metadata(stream):
    data=[]
    type = parse_unsigned_byte(stream)
    while (type != 127):
        type = type >> 5
        if type == 0:
            data.append(parse_byte(stream))
        elif type == 1:
            data.append(parse_short(stream))
        elif type == 2:
            data.append(parse_int(stream))
        elif type == 3:
            data.append(parse_float(stream))
        elif type == 4:
            data.append(parse_string(stream))
        elif type == 5:
            data.append(parse_short(stream))
            data.append(parse_byte(stream))
            data.append(parse_short(stream))
        else:
            logger.error(repr(stream.buf[:parse.i]))
            raise Exception("Unknown metadata type %d" % type)
        type = parse_byte(stream)
    return data

def emit_metadata(md):
    raise NotImplementedError

MC_metadata = Parsem(parse_metadata, emit_metadata)

def parse_inventory(stream):
    n = parse_short(stream)
    inv = { "count": n }
    inv["slots"] = [parse_slot_update(stream) for i in xrange(0,n)]
    return inv

def emit_inventory(inv):
    slotstr = ''.join([emit_slot_update(slot) for slot in inv['slots']])
    return ''.join([emit_short(inv['count']),slotstr])

MC_inventory = Parsem(parse_inventory,emit_inventory)

def parse_slot_update(stream):
    id = parse_short(stream)
    if id == -1:
        return None
    return { "item_id": id, "count": parse_byte(stream), "uses": parse_short(stream) }

def emit_slot_update(update):
    if not update:
        return emit_short(-1)
    return ''.join([emit_short(update['item_id']), emit_byte(update['count']), emit_short(update['uses'])])

MC_slot_update = Parsem(parse_slot_update, emit_slot_update)

SLOT_UPDATE_2_ITEM_IDS = set([
    0x15A, #Fishing rod
    0x167, #Shears

    #TOOLS
    #sword, shovel, pickaxe, axe, hoe
    0x10C, 0x10D, 0x10E, 0x10F, 0x122, #WOOD
    0x110, 0x111, 0x112, 0x113, 0x123, #STONE
    0x10B, 0x100, 0x101, 0x102, 0x124, #IRON
    0x114, 0x115, 0x116, 0x117, 0x125, #DIAMOND
    0x11B, 0x11C, 0x11D, 0x11E, 0x126, #GOLD

    #ARMOUR
    #helmet, chestplate, leggings, boots
    0x12A, 0x12B, 0x12C, 0x12D, #LEATHER
    0x12E, 0x12F, 0x130, 0x131, #CHAIN
    0x132, 0x133, 0x134, 0x135, #IRON
    0x136, 0x137, 0x138, 0x139, #DIAMOND
    0x13A, 0x13B, 0x13C, 0x14D  #GOLD
])

def parse_slot_update2(stream):
    r = parse_slot_update(stream)
    if r is not None and r['item_id'] in SLOT_UPDATE_2_ITEM_IDS:
        n = parse_short(stream)
        r['nbt_size'] = n
        if n > 0:
            r['nbt_data'] = stream.read(n)
        else:
            r['nbt_data'] = None
    return r

def emit_slot_update2(update):
    if not update:
        return emit_short(-1)
    s = emit_slot_update(update)
    if update['item_id'] in SLOT_UPDATE_2_ITEM_IDS:
        size = update['nbt_size']
        s = ''.join(s, emit_short(size))
        if size >= 0:
            data = update['nbt_data']
        s = ''.join([s, nbtdata])
    return s

MC_slot_update2 = Parsem(parse_slot_update2, emit_slot_update2)

def parse_inventory2(stream):
    n = parse_short(stream)
    inv = { "count": n }
    inv["slots"] = [parse_slot_update2(stream) for i in xrange(0,n)]
    return inv

def emit_inventory2(inv):
    slotstr = ''.join([emit_slot_update2(slot) for slot in inv['slots']])
    return ''.join([emit_short(inv['count']),slotstr])

MC_inventory2 = Parsem(parse_inventory2,emit_inventory2)

def parse_chunk(stream):
    n = parse_int(stream)
    return { 'size': n, 'data': stream.read(n) }

def emit_chunk(ch):
    return ''.join([emit_int(ch['size']), ch['data']])

MC_chunk = Parsem(parse_chunk, emit_chunk)

def parse_chunk2(stream):
    n = parse_int(stream)
    parse_int(stream)
    return { 'size': n, 'data': stream.read(n) }

def emit_chunk2(ch):
    return ''.join([emit_int(ch['size']), emit_int(0), ch['data']])

MC_chunk2 = Parsem(parse_chunk2, emit_chunk2)

def parse_multi_block_change(stream):
    n = parse_short(stream)
    return {'coord_array': [parse_short(stream) for j in xrange(0,n)],
            'type_array': [parse_byte(stream) for j in xrange(0,n)],
            'metadata_array': [parse_byte(stream) for j in xrange(0,n)]}

def emit_multi_block_change(changes):
    return ''.join([emit_short(len(changes['coord_array'])),
                    ''.join([emit_short(x) for x in changes['coord_array']]),
                    ''.join([emit_byte(x)  for x in changes['type_array']]),
                    ''.join([emit_byte(x)  for x in changes['metadata_array']])])

MC_multi_block_change = Parsem(parse_multi_block_change, emit_multi_block_change)

def parse_multi_block_change2(stream):
    n = parse_int(stream)/4
    return [parse_int(stream) for i in range(n)]

def emit_multi_block_change2(changes):
    return ''.join([emit_int(len(changes)*4),
           ''.join([emit_int(c) for c in changes])])

MC_multi_block_change2 = Parsem(parse_multi_block_change2, emit_multi_block_change2)

def parse_explosion_records(stream):
    n = parse_int(stream)
    return { 'count': n,
             'data': [(parse_byte(stream),parse_byte(stream),parse_byte(stream))
                      for i in xrange(0,n)]}

def emit_explosion_records(msg):
    return ''.join([emit_int(msg['count']),
                    ''.join([(emit_byte(rec[0]), emit_byte(rec[1]), emit_byte(rec[2]))
                             for rec in msg['data']])])

MC_explosion_records = Parsem(parse_explosion_records, emit_explosion_records)

def parse_vehicle_data(stream):
    x = parse_int(stream)
    data = { 'unknown1': x }
    if x > 0:
        data['unknown2'] = parse_short(stream)
        data['unknown3'] = parse_short(stream)
        data['unknown4'] = parse_short(stream)
    return data

def emit_vehicle_data(data):
    x = data['unknown1']
    str = emit_int(x)
    if x > 0:
        str = ''.join([str, emit_int(data['unknown2']), emit_int(data['unknown3']), emit_int(data['unknown4'])])
    return str

MC_vehicle_data = Parsem(parse_vehicle_data, emit_vehicle_data)

def parse_item_data(stream):
    n = parse_unsigned_byte(stream)
    if n == 0:
        return ''
    return stream.read(n)

def emit_item_data(s):
    assert len(s) < 265
    return ''.join([emit_unsigned_byte(len(s)),s])

MC_item_data = Parsem(parse_item_data, emit_item_data)

def parse_fireball_data(stream):
    data = {}
    data['thrower_id'] = parse_int(stream)
    if data['thrower_id'] > 0:
        data['u1'] = parse_short(stream)
        data['u2'] = parse_short(stream)
        data['u3'] = parse_short(stream)
    return data

def emit_fireball_data(data):
    str = emit_int(data['thrower_id'])
    if data['thrower_id'] > 0:
        str = ''.join(str, emit_short(data['u1']),
                           emit_short(data['u2']),
                           emit_short(data['u3']))
    return str

MC_fireball_data = Parsem(parse_fireball_data, emit_fireball_data)
