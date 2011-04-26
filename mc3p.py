import asyncore
import socket
import sys
import signal
import struct
import logging
from time import time

import mcproto

class mitm_listener(asyncore.dispatcher):
    """Listens for incoming Minecraft client connections to create mitm_channels for.
    """

    def __init__(self, srcport, dsthost, dstport):
        """Create a server that forwards local srcport to dsthost:dstport.
        """
        asyncore.dispatcher.__init__(self)
        self.dsthost = dsthost
        self.dstport = dstport
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("",srcport))
        self.listen(5)
        logging.info("mitm_listener bound to %d" % srcport)

    def handle_accept(self):
        sock,addr = self.accept()
        logging.info("mitm_listener accepted connection from %s" % repr(addr))
        try:
            chan = mitm_channel(sock,self.dsthost,self.dstport)
        except Exception as e:
            print str(e)


class mitm_channel:
    """Handles a Minecraft client-server connection.
    """

    def __init__(self, clientsock, dsthost, dstport):
        logging.info("creating mitm_channel from client to %s:%d" % (dsthost,dstport))
        self.mitm_server = None
        self.mitm_client = mitm_parser(clientsock, mcproto.CLIENT_SIDE,
                                       self.handle_client_packet,
                                       self.client_closed,
                                       'Client parser')
        try:
            serversock = socket.create_connection((dsthost,dstport))
        except:
            self.mitm_client.close()
            raise
        self.mitm_server = mitm_parser(serversock, mcproto.SERVER_SIDE,
                                       self.handle_server_packet,
                                       self.server_closed,
                                       'Server parser')
        self.client_buf = ""

    def handle_client_packet(self,packet):
        """Handle a packet from the client.
        """
        logging.debug("client packet: %s" % repr(packet))
        self.mitm_server.send(packet['packet_bytes'])

    def handle_server_packet(self,packet):
        """Handle a packet from the server.
        """
        logging.debug("server packet: %s" % repr(packet))
        if packet['id'] == 0x03:
            print packet['chat_msg']
        else:
            self.mitm_client.send(packet['packet_bytes'])

    def client_closed(self):
        logging.info("mitm_channel: client socket closed")
        self.mitm_client = None
        if (self.mitm_server):
            logging.info("mitm_channel: closing server socket")
            self.mitm_server.close()
            self.mitm_server = None

    def server_closed(self):
        logging.info("mitm_channel: server socket closed")
        self.mitm_server = None
        if (self.mitm_client):
            logging.info("mitm_channel: closing client scoket")
            self.mitm_client.close()
            self.mitm_client = None

class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)

class PartialPacketException(Exception):
    pass

class state(object):
    """Hold parsing state.

    This class is a simple container for the pieces of state
    to be threaded through the parsing functions.
    """

    def __init__(self):
        """Initialize parsing state."""
        self.buf = ""
        self.i = 0
        self.tot_bytes = 0
        self.wasted_bytes = 0
        self.last_report = 0

class mitm_parser(asyncore.dispatcher):
    """Parses a packet stream from a Minecraft client or server.
    """

    def __init__(self, sock, side, packet_hdlr, close_hdlr,name='Parser'):
        asyncore.dispatcher.__init__(self,sock)
        self.side = side
        self.packet_hdlr = packet_hdlr
        self.close_hdlr = close_hdlr
        self.name = name
        self.parse = state()

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        t = time()
        if self.parse.last_report + 5 < t and self.parse.tot_bytes > 0:
            self.parse.last_report = t
            logging.debug("%s: total/wasted bytes is %d/%d (%f wasted)" % (
                 self.name, self.parse.tot_bytes, self.parse.wasted_bytes,
                 100 * float(self.parse.wasted_bytes) / self.parse.tot_bytes))
        self.parse.buf += self.recv(4092)
        try:
            packet = parse_packet(self.parse,self.side)
            while packet != None:
                self.packet_hdlr(packet)
                packet = parse_packet(self.parse,self.side)
        except Exception:
            logging.info("mitm_parser caught exception")
            self.handle_close()
            raise

    def handle_close(self):
        logging.info("mitm_socket closed")
        self.close()
        self.close_hdlr()


## Parsing functions ##

def parse_packet(parse, side):
    """Try to parse a single packet out of parse.buf.

    If parse.buf contains a complete packet, we parse it,
    remove it's data from parse.buf, and return it as a dictionary.
    Otherwise, we leave parse.buf alone and return None.
    """
    parse.i=0
    try:
        packet={}
        # read Packet ID
        pid = parse_unsigned_byte(parse)
        spec = mcproto.packet_spec[side]
        if not spec.has_key(pid):
            raise UnsupportedPacketException(pid)
        logging.debug("Trying to parse packet %x" % pid)
        packet['id'] = pid
        fmt = spec[pid]
        for name,type in fmt:
            if parsefn.has_key(type):
                packet['name'] = parsefn[type](parse)
            else:
                raise Exception("Unknown data type %d" % type)
        packet['packet_bytes']=parse.buf[:parse.i]
        parse.buf = parse.buf[parse.i:]
        return packet
    except PartialPacketException:
        parse.wasted_bytes += parse.i
        return None
    finally:
        parse.tot_bytes += parse.i

def parse_byte(parse):
    if (parse.i+1 > len(parse.buf)):
        raise PartialPacketException()
    byte = struct.unpack_from(">b",parse.buf,parse.i)[0]
    parse.i += 1
    return byte

def parse_unsigned_byte(parse):
    if (parse.i+1 > len(parse.buf)):
        raise PartialPacketException()
    byte = struct.unpack_from(">B",parse.buf,parse.i)[0]
    parse.i += 1
    return byte

def parse_short(parse):
    if (parse.i+2 > len(parse.buf)):
        raise PartialPacketException()
    short = struct.unpack_from(">h",parse.buf,parse.i)[0]
    parse.i += 2
    return short

def parse_int(parse):
    if (parse.i+4 > len(parse.buf)):
        raise PartialPacketException()
    num = struct.unpack_from(">i",parse.buf,parse.i)[0]
    parse.i += 4
    return num

def parse_long(parse):
    if (parse.i+8 > len(parse.buf)):
        raise PartialPacketException()
    num = struct.unpack_from(">l",parse.buf,parse.i)[0]
    parse.i += 8
    return num

def parse_float(parse):
    if (parse.i+4 > len(parse.buf)):
        raise PartialPacketException()
    num = struct.unpack_from(">f",parse.buf,parse.i)[0]
    parse.i += 4
    return num

def parse_double(parse):
    if (parse.i+8 > len(parse.buf)):
        raise PartialPacketException()
    num = struct.unpack_from(">d",parse.buf,parse.i)[0]
    parse.i += 8
    return num

def parse_string(parse):
    length = parse_short(parse)
    if (length == 0):
        return ""
    if (parse.i + length > len(parse.buf)):
        raise PartialPacketException()
    str = parse.buf[parse.i:parse.i+length]
    parse.i += length
    return str

def parse_bool(parse):
    if (parse.i+1 > len(parse.buf)):
        raise PartialPacketException()
    b = struct.unpack_from(">B",parse.buf,parse.i)[0]
    if b==0:
        b=False
    else:
        b=True
    parse.i += 1
    return b

def parse_metadata(parse):
    if (parse.i+1 > len(parse.buf)):
        raise PartialPacketException()
    data=[]
    type = parse_unsigned_byte(parse)
    while (type != 127):
        type = type >> 5
        if type == 0:
            data.append(parse_byte(parse))
        elif type == 1:
            data.append(parse_short(parse))
        elif type == 2:
            data.append(parse_int(parse))
        elif type == 3:
            data.append(parse_float(parse))
        elif type == 4:
            data.append(parse_string(parse))
        elif type == 5:
            data.append(parse_short(parse))
            data.append(parse_byte(parse))
            data.append(parse_short(parse))
        else:
            logging.error(repr(parse.buf[:parse.i]))
            raise Exception("Unknown metadata type %d" % type)
        type = parse_byte(parse)
    return data

def parse_inventory(parse):
    # The previously parsed short is the count of slots.
    parse.i -= 2
    count = parse_short(parse)
    payload = {}
    for j in xrange(0,count):
        item_id = parse_short(parse)
        if item_id != -1:
            c = parse_byte(parse)
            u = parse_short(parse)
            payload[j] = (item_id,c,u)
        else:
            payload[j] = None
    return payload

def parse_set_slot(parse):
    # The previously parsed short tells us if we need to parse anything else.
    parse.i -= 2
    id = parse_short(parse)
    if id != -1:
        return (parse_byte(parse), parse_short(parse))
    else:
        return None

def parse_chunk(parse):
    parse.i -= 4
    length = parse_int(parse)
    if (parse.i + length > len(parse.buf)):
        raise PartialPacketException()
    data = parse.buf[parse.i:parse.i+length]
    parse.i += length
    return data

def parse_multi_block_change(parse):
    parse.i -= 2
    length = parse_short(parse)
    coord_array = []
    for j in xrange(0,length):
        coord_array.append(parse_short(parse))
    type_array = []
    for j in xrange(0,length):
        type_array.append(parse_byte(parse))
    metadata_array = []
    for j in xrange(0,length):
        metadata_array.append(parse_byte(parse))
    return {'coord_array': coord_array,
            'type_array': type_array,
            'metadata_array': metadata_array}

def parse_item_details(parse):
    parse.i -= 2
    id = parse_short(parse)
    if (id >= 0):
        return {'count':parse_byte(parse),'uses':parse_short(parse)}
    else:
        return None

def parse_explosion_record(parse):
    parse.i -= 4
    c = parse_int(parse)
    records = []
    for j in xrange(0,c):
        records.append( (parse_byte(parse),parse_byte(parse),parse_byte(parse) ))
    return records

# Map of data types to parsing functions.
parsefn = {}
parsefn[mcproto.TYPE_BYTE] = parse_byte
parsefn[mcproto.TYPE_SHORT] = parse_short
parsefn[mcproto.TYPE_INT] = parse_int
parsefn[mcproto.TYPE_LONG] = parse_long
parsefn[mcproto.TYPE_FLOAT] = parse_float
parsefn[mcproto.TYPE_DOUBLE] = parse_double
parsefn[mcproto.TYPE_STRING] = parse_string
parsefn[mcproto.TYPE_BOOL]  = parse_bool
parsefn[mcproto.TYPE_METADATA]  = parse_metadata
parsefn[mcproto.TYPE_INVENTORY] = parse_inventory
parsefn[mcproto.TYPE_SET_SLOT] = parse_set_slot
parsefn[mcproto.TYPE_CHUNK] = parse_chunk
parsefn[mcproto.TYPE_MULTI_BLOCK_CHANGE] = parse_multi_block_change
parsefn[mcproto.TYPE_ITEM_DETAILS] = parse_item_details
parsefn[mcproto.TYPE_EXPLOSION_RECORD] = parse_explosion_record

def sigint_handler(signum, stack):
    print "Received SIGINT, shutting down"
    sys.exit(0) 

if __name__ == "__main__":
    logging.basicConfig(
        #filename='mitm.log',
        level=logging.INFO)
    signal.signal(signal.SIGINT, sigint_handler)
    lstnr = mitm_listener(34343, sys.argv[1], int(sys.argv[2]))
    asyncore.loop()

