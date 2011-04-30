import struct, logging

def parse_byte(stream):
    return struct.unpack_from(">b",stream.read(1))[0]

def parse_unsigned_byte(stream):
    return struct.unpack(">B",stream.read(1))[0]

def parse_short(stream):
    return struct.unpack_from(">h",stream.read(2))[0]

def parse_int(stream):
    return struct.unpack_from(">i",stream.read(4))[0]

def parse_long(stream):
    return struct.unpack_from(">l",stream.read(8))[0]

def parse_float(stream):
    return struct.unpack_from(">f",stream.read(4))[0]

def parse_double(stream):
    return struct.unpack_from(">d",stream.read(8))[0]

def parse_string(stream):
    n = parse_short(stream)
    if n == 0:
        return ""
    return stream.read(n)

def parse_bool(stream):
    b = struct.unpack_from(">B",stream.read(1))[0]
    if b==0:
        return False
    else:
        return True

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

def parse_inventory(stream):
    # The previously parsed short is the count of slots.
    stream.i -= 2
    count = parse_short(stream)
    payload = {}
    for j in xrange(0,count):
        item_id = parse_short(stream)
        if item_id != -1:
            c = parse_byte(stream)
            u = parse_short(stream)
            payload[j] = (item_id,c,u)
        else:
            payload[j] = None
    return payload

def parse_set_slot(stream):
    # The previously parsed short tells us if we need to parse anything else.
    stream.i -= 2
    id = parse_short(stream)
    if id != -1:
        return (parse_byte(stream), parse_short(stream))
    else:
        return None

def parse_chunk(stream):
    stream.i -= 4
    n = parse_int(stream)
    return stream.read(n)

def parse_multi_block_change(stream):
    stream.i -= 2
    length = parse_short(stream)
    coord_array = []
    for j in xrange(0,length):
        coord_array.append(parse_short(stream))
    type_array = []
    for j in xrange(0,length):
        type_array.append(parse_byte(stream))
    metadata_array = []
    for j in xrange(0,length):
        metadata_array.append(parse_byte(stream))
    return {'coord_array': coord_array,
            'type_array': type_array,
            'metadata_array': metadata_array}

def parse_item_details(stream):
    stream.i -= 2
    id = parse_short(stream)
    if (id >= 0):
        return {'count':parse_byte(stream),'uses':parse_short(stream)}
    else:
        return None

def parse_explosion_record(stream):
    stream.i -= 4
    c = parse_int(stream)
    records = []
    for j in xrange(0,c):
        records.append( (parse_byte(stream),parse_byte(stream),parse_byte(stream) ))
    return records

