import struct, logging, inspect

class Parsem(object):
    """Parser/emitter."""

    def __init__(self,parser,emitter):
        setattr(self,'parse',parser)
        setattr(self,'emit',emitter)

    def __call__(self,arg):
        if hasattr(arg,'read') and callable(arg.read):
            # arg is a stream, and we're parsing
            return self.parse(arg)
        else:
            # Assume we're emitting.
            return self.emit(arg)

def parse_byte(stream):
    return struct.unpack_from(">b",stream.read(1))[0]

def emit_byte(b):
    return struct.pack(">b",b)


def defmsg(msgtype, name, pairs):
    """Build a Parsem for a message out of (name,Parsem) pairs."""
    def parse(stream):
        msg = {'msgtype': msgtype}
        for (name,parsem) in pairs:
            msg[name] = parsem(stream)
        return msg
    def emit(msg):
        return ''.join([emit_unsigned_byte(msgtype),
                        ''.join([parsem(msg[name]) for (name,parsem) in pairs])])
    return Parsem(parse,emit)

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
    return struct.unpack_from(">l",stream.read(8))[0]

def emit_long(l):
    return struct.pack(">l",l)

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
            logging.error(repr(stream.buf[:parse.i]))
            raise Exception("Unknown metadata type %d" % type)
        type = parse_byte(stream)
    return data

def _parse_slot(stream):
    item_id = parse_short(stream)
    if item_id == -1:
        return None
    return (item_id,parse_byte(stream),parse_short(stream))

def _emit_slot(slot):
    if not slot:
        return emit_short(-1)
    item_id, c, u = slot
    return ''.join([emit_short(item_id),emit_byte(c),emit_short(u)])

def parse_inventory(stream):
    n = parse_short(stream)
    inv = { "count": n }
    inv["slots"] = [_parse_slot(stream) for i in xrange(0,n)]
    return inv

def emit_inventory(inv):
    slotstr = ''.join([_emit_slot(slot) for slot in inv['slots']])
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

def parse_chunk(stream):
    n = parse_int(stream)
    return { 'size': n, 'data': stream.read(n) }

def emit_chunk(ch):
    return ''.join([emit_int(ch['size']),emit_string(ch['data'])])

MC_chunk = Parsem(parse_chunk, emit_chunk)

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

def parse_item_details(stream):
    id = parse_short(stream)
    if id == -1:
        return None
    return {'count':parse_byte(stream),'uses':parse_short(stream)}

def emit_item_details(details):
    if details == None:
        return emit_short(-1)
    return ''.join([emit_byte(details['count']), emit_short(details['uses'])])

MC_item_details = Parsem(parse_item_details, emit_item_details)

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

