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

class stream(object):
    """Represent a stream of bytes."""

    def __init__(self):
        """Initialize the stream."""
        self.buf = ""
        self.i = 0
        self.tot_bytes = 0
        self.wasted_bytes = 0
        self.last_report = 0

    def append(self,str):
        """Append a string to the stream."""
        self.buf += str

    def read(self,n):
        """Read n bytes, returned as a string."""
        if self.i + n > len(self.buf):
            self.wasted_bytes += self.i
            self.i = 0
            raise PartialPacketException()
        str = self.buf[self.i:self.i+n]
        self.i += n
        return str

    def packet_finished(self):
        """Mark the completion of a packet, and return its bytes as a string."""
        # Discard all data that was read for the previous packet,
        # and reset i.
        data = ""
        if self.i > 0:
            data = self.buf[:self.i]
            self.buf = self.buf[self.i:]
            self.tot_bytes += self.i
            self.i = 0
        return data


class mitm_parser(asyncore.dispatcher):
    """Parses a packet stream from a Minecraft client or server.
    """

    def __init__(self, sock, side, packet_hdlr, close_hdlr,name='Parser'):
        asyncore.dispatcher.__init__(self,sock)
        self.side = side
        self.packet_hdlr = packet_hdlr
        self.close_hdlr = close_hdlr
        self.name = name
        self.parse = stream()

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        t = time()
        if self.parse.last_report + 5 < t and self.parse.tot_bytes > 0:
            self.parse.last_report = t
            logging.debug("%s: total/wasted bytes is %d/%d (%f wasted)" % (
                 self.name, self.parse.tot_bytes, self.parse.wasted_bytes,
                 100 * float(self.parse.wasted_bytes) / self.parse.tot_bytes))
        self.parse.append(self.recv(4092))
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

def parse_packet(stream, side):
    """Try to parse a single packet out of stream.

    If stream contains a complete packet, we parse it,
    and return its data as a dictionary. If not, stream
    will throw an exception, and we'll give up and return None.
    """
    try:
        packet={}
        # read Packet ID
        pid = parse_unsigned_byte(stream)
        spec = mcproto.packet_spec[side]
        if not spec.has_key(pid):
            raise UnsupportedPacketException(pid)
        logging.debug("Trying to parse packet %x" % pid)
        packet['id'] = pid
        fmt = spec[pid]
        for name,type in fmt:
            if parsefn.has_key(type):
                packet['name'] = parsefn[type](stream)
            else:
                raise Exception("Unknown data type %d" % type)
        packet['packet_bytes'] = stream.packet_finished()
        return packet
    except PartialPacketException:
        return None

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

