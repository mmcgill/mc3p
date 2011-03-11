import asyncore
import socket
import sys
import signal
import struct

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
        print "mitm_listener bound to %d" % srcport

    def handle_accept(self):
        sock,addr = self.accept()
        print "mitm_listener accepted connection from %s" % repr(addr)
        chan = mitm_channel(sock,self.dsthost,self.dstport)
        

class mitm_channel:
    """Handles a Minecraft client-server connection.
    """

    def __init__(self, clientsock, dsthost, dstport):
        print "creating mitm_channel from client to %s:%d" % (dsthost,dstport)
        self.mitm_client = mitm_parser(clientsock, CLIENT_SIDE,
                                       self.handle_client_packet,
                                       self.client_closed)
        self.mitm_server = None
        serversock = socket.create_connection((dsthost,dstport))
        self.mitm_server = mitm_parser(serversock, SERVER_SIDE,
                                       self.handle_server_packet,
                                       self.server_closed)
        self.client_buf = ""

    def handle_client_packet(self,packet):
        """Handle a packet from the client.
        """
        print "client packet: %s" % repr(packet)
        if (self.mitm_server):
            #print "sending %d bytes from client to server" % len(data)
            self.mitm_server.send(packet['packet_bytes'])
        else:
            print "dropping %d bytes from client" % len(packet['packet_bytes'])

    def handle_server_packet(self,packet):
        """Handle a packet from the server.
        """
        print "server packet: %s" % repr(packet)
        if (self.mitm_client):
            #print "sending %d bytes from client to server" % len(data)
            self.mitm_client.send(packet['packet_bytes'])
        else:
            print "dropping %d bytes from server" % len(packet['packet_bytes'])

    def client_closed(self):
        print "mitm_channel: client socket closed"
        self.mitm_client = None
        if (self.mitm_server):
            print "mitm_channel: closing server socket"
            self.mitm_server.close()
            self.mitm_server = None

    def server_closed(self):
        print "mitm_channel: server socket closed"
        self.mitm_server = None
        if (self.mitm_client):
            print "mitm_channel: closing client scoket"
            self.mitm_client.close()
            self.mitm_client = None

class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)

class PartialPacketException(Exception):
    pass

CLIENT_SIDE = 0
SERVER_SIDE = 1

TYPE_BYTE = 0
TYPE_SHORT = 1
TYPE_INT = 2
TYPE_LONG = 3
TYPE_FLOAT = 4
TYPE_DOUBLE = 5
TYPE_STRING = 6
TYPE_BOOL = 7
TYPE_METADATA = 8
TYPE_INVENTORY = 9
TYPE_SET_SLOT = 10
TYPE_WINDOW_CLICK = 11
TYPE_CHUNK = 12
TYPE_MULTI_BLOCK_CHANGE = 13
TYPE_ITEM_DETAILS = 14
TYPE_EXPLOSION_RECORD = 15

client_packet_spec = {
    0x00: [],   # Keep-alive packet
    0x01: [('proto_version',TYPE_INT),
           ('username',TYPE_STRING),
           ('password',TYPE_STRING),
           ('map_seed',TYPE_LONG),
           ('dimension',TYPE_BYTE)],
    0x02: [('username',TYPE_STRING)],
    0x03: [('chat_msg',TYPE_STRING)],
    0x05: [('eid',TYPE_INT),
           ('slot',TYPE_SHORT),
           ('item_id',TYPE_SHORT),
           ('unknown',TYPE_SHORT)],
    0x07: [('eid',TYPE_INT),
           ('target_eid',TYPE_INT),
           ('left_click',TYPE_BOOL)],
    0x09: [], # Respawnn packet
    0x0a: [('on_ground',TYPE_BOOL)],
    0x0b: [('x',TYPE_DOUBLE),
           ('y',TYPE_DOUBLE),
           ('stance',TYPE_DOUBLE),
           ('z',TYPE_DOUBLE),
           ('on_ground',TYPE_BOOL)],
    0x0c: [('yaw',TYPE_FLOAT),
           ('pitch',TYPE_FLOAT),
           ('on_ground',TYPE_BOOL)],
    0x0d: [('x',TYPE_DOUBLE),
           ('y',TYPE_DOUBLE),
           ('stance',TYPE_DOUBLE),
           ('z',TYPE_DOUBLE),
           ('yaw',TYPE_FLOAT),
           ('pitch',TYPE_FLOAT),
           ('on_ground',TYPE_BOOL)],
    0x0e: [('status',TYPE_BYTE),
           ('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('face',TYPE_BYTE)],
    0x0f: [('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('dir',TYPE_BYTE),
           ('id',TYPE_SHORT),
           ('details',TYPE_ITEM_DETAILS)],
    0x10: [('slot_id', TYPE_SHORT)],
    0x12: [('eid',TYPE_INT),
           ('animation',TYPE_BYTE)],
    0x13: [('eid',TYPE_INT),
           ('action', TYPE_BYTE)],
    0x15: [('eid',TYPE_INT),
           ('item',TYPE_SHORT),
           ('count',TYPE_BYTE),
           ('data',TYPE_SHORT),
           ('x',TYPE_INT),
           ('y',TYPE_INT),
           ('z',TYPE_INT),
           ('rotation',TYPE_BYTE),
           ('pitch',TYPE_BYTE),
           ('roll',TYPE_BYTE)],
    0x1b: [('d1', TYPE_FLOAT),
           ('d2', TYPE_FLOAT),
           ('d3', TYPE_FLOAT),
           ('d4', TYPE_FLOAT),
           ('d5', TYPE_BOOL),
           ('d6', TYPE_BOOL)],
    0x1c: [('eid',TYPE_INT),
           ('vel_x',TYPE_SHORT),
           ('vel_y',TYPE_SHORT),
           ('vel_z',TYPE_SHORT)],
    0x27: [('eid',TYPE_INT),
           ('vehicle_id',TYPE_INT)],
    0x28: [('eid',TYPE_INT),
           ('metadata',TYPE_METADATA)],
    0x34: [('chunk_x',TYPE_INT),
           ('chunk_z',TYPE_INT),
           ('array_lengths',TYPE_SHORT),
           ('arrays',TYPE_MULTI_BLOCK_CHANGE)],
    0x35: [('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('block_type',TYPE_BYTE),
           ('block_metadata',TYPE_BYTE)],
    0x65: [('window_id', TYPE_BYTE)],
    0x66: [('window_id', TYPE_BYTE),
           ('slot', TYPE_SHORT),
           ('is_right_click', TYPE_BOOL),
           ('action_num', TYPE_SHORT),
           ('item_id', TYPE_SHORT),
           ('item_details', TYPE_ITEM_DETAILS)],
    0x6a: [('window_id', TYPE_BYTE),
           ('action_num', TYPE_SHORT),
           ('accepted', TYPE_BOOL)],
    0x82: [('x', TYPE_INT),
           ('y', TYPE_SHORT),
           ('z', TYPE_INT),
           ('text1', TYPE_STRING),
           ('text2', TYPE_STRING),
           ('text3', TYPE_STRING),
           ('text4', TYPE_STRING)],
    0xff: [('reason', TYPE_STRING)]}

server_packet_spec = {
    0x00: [],
    0x01: [('eid',TYPE_INT),
           ('reserved',TYPE_STRING),
           ('reserved',TYPE_STRING),
           ('map_seed',TYPE_LONG),
           ('dimension',TYPE_BYTE)],
    0x02: [('hash',TYPE_STRING)],
    0x03: [('chat_msg',TYPE_STRING)],
    0x04: [('time',TYPE_LONG)],
    0x05: [('eid', TYPE_INT),
           ('slot_id', TYPE_SHORT),
           ('item_id', TYPE_SHORT),
           ('unknown', TYPE_SHORT)],
    0x06: [('x',TYPE_INT),
           ('y',TYPE_INT),
           ('z',TYPE_INT)],
    0x08: [('health',TYPE_SHORT)],
    0x0b: [('x',TYPE_DOUBLE),
           ('y',TYPE_DOUBLE),
           ('stance',TYPE_DOUBLE),
           ('z',TYPE_DOUBLE),
           ('on_ground',TYPE_BOOL)],
    0x0d: [('x',TYPE_DOUBLE),
           ('stance',TYPE_DOUBLE),
           ('y',TYPE_DOUBLE),
           ('z',TYPE_DOUBLE),
           ('yaw',TYPE_FLOAT),
           ('pitch',TYPE_FLOAT),
           ('on_ground',TYPE_BOOL)],
    0x0e: [('status',TYPE_BYTE),
           ('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('face',TYPE_BYTE)],
    0x0f: [('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('dir',TYPE_BYTE),
           ('id',TYPE_SHORT),
           ('details',TYPE_ITEM_DETAILS)],
    0x10: [('slot_id', TYPE_SHORT)],
    0x11: [('eid', TYPE_INT),
           ('unknown', TYPE_BYTE),
           ('x', TYPE_INT),
           ('y', TYPE_BYTE),
           ('z', TYPE_INT)],
    0x12: [('eid',TYPE_INT),
           ('animation',TYPE_BYTE)],
    0x13: [('eid',TYPE_INT),
           ('action', TYPE_BYTE)],
    0x14: [('eid', TYPE_INT),
           ('name', TYPE_STRING),
           ('x', TYPE_INT),
           ('y', TYPE_INT),
           ('z', TYPE_INT),
           ('rotation', TYPE_BYTE),
           ('pitch', TYPE_BYTE),
           ('curr_item', TYPE_SHORT)],
    0x15: [('eid',TYPE_INT),
           ('item',TYPE_SHORT),
           ('count',TYPE_BYTE),
           ('data',TYPE_SHORT),
           ('x',TYPE_INT),
           ('y',TYPE_INT),
           ('z',TYPE_INT),
           ('rotation',TYPE_BYTE),
           ('pitch',TYPE_BYTE),
           ('roll',TYPE_BYTE)],
    0x16: [('item_eid',TYPE_INT),
           ('collector_eid',TYPE_INT)],
    0x17: [('eid',TYPE_INT),
           ('type',TYPE_BYTE),
           ('x',TYPE_INT),
           ('y',TYPE_INT),
           ('z',TYPE_INT)],
    0x18: [('eid',TYPE_INT),
           ('mob_type',TYPE_BYTE),
           ('x',TYPE_INT),
           ('y',TYPE_INT),
           ('z',TYPE_INT),
           ('yaw',TYPE_BYTE),
           ('pitch',TYPE_BYTE),
           ('metadata',TYPE_METADATA)],
    0x19: [('eid', TYPE_INT),
           ('title', TYPE_STRING),
           ('x', TYPE_INT),
           ('y', TYPE_INT),
           ('z', TYPE_INT),
           ('type', TYPE_INT)],
    0x1b: [('d1', TYPE_FLOAT),
           ('d2', TYPE_FLOAT),
           ('d3', TYPE_FLOAT),
           ('d4', TYPE_FLOAT),
           ('d5', TYPE_BOOL),
           ('d6', TYPE_BOOL)],
    0x1c: [('eid',TYPE_INT),
           ('vel_x',TYPE_SHORT),
           ('vel_y',TYPE_SHORT),
           ('vel_z',TYPE_SHORT)],
    0x1d: [('eid',TYPE_INT)],
    0x1e: [('eid', TYPE_INT)],
    0x1f: [('eid',TYPE_INT),
           ('dx',TYPE_BYTE),
           ('dy',TYPE_BYTE),
           ('dz',TYPE_BYTE)],
    0x20: [('eid', TYPE_INT),
           ('yaw', TYPE_BYTE),
           ('pitch', TYPE_BYTE)],
    0x21: [('eid',TYPE_INT),
           ('dx',TYPE_BYTE),
           ('dy',TYPE_BYTE),
           ('dz',TYPE_BYTE),
           ('yaw',TYPE_BYTE),
           ('pitch',TYPE_BYTE)],
    0x22: [('eid', TYPE_INT),
           ('x', TYPE_INT),
           ('y', TYPE_INT),
           ('z', TYPE_INT),
           ('yaw', TYPE_BYTE),
           ('pitch', TYPE_BYTE)],
    0x26: [('eid',TYPE_INT),
           ('status',TYPE_BYTE)],
    0x27: [('eid', TYPE_INT),
           ('vehicle_id', TYPE_INT)],
    0x28: [('eid',TYPE_INT),
           ('metadata',TYPE_METADATA)],
    0x32: [('x',TYPE_INT),
           ('z',TYPE_INT),
           ('mode',TYPE_BOOL)],
    0x33: [('x',TYPE_INT),
           ('y',TYPE_SHORT),
           ('z',TYPE_INT),
           ('size_x',TYPE_BYTE),
           ('size_y',TYPE_BYTE),
           ('size_z',TYPE_BYTE),
           ('data_size',TYPE_INT),
           ('data',TYPE_CHUNK)],
    0x34: [('chunk_x',TYPE_INT),
           ('chunk_z',TYPE_INT),
           ('array_lengths',TYPE_SHORT),
           ('arrays',TYPE_MULTI_BLOCK_CHANGE)],
    0x35: [('x',TYPE_INT),
           ('y',TYPE_BYTE),
           ('z',TYPE_INT),
           ('block_type',TYPE_BYTE),
           ('block_metadata',TYPE_BYTE)],
    0x36: [('x', TYPE_INT),
           ('y', TYPE_SHORT),
           ('z', TYPE_INT),
           ('instrument_type', TYPE_BYTE),
           ('pitch', TYPE_BYTE)],
    0x3c: [('x', TYPE_DOUBLE),
           ('y', TYPE_DOUBLE),
           ('z', TYPE_DOUBLE),
           ('unknown', TYPE_FLOAT),
           ('count', TYPE_INT),
           ('records', TYPE_EXPLOSION_RECORD)],
    0x64: [('window_id', TYPE_BYTE),
           ('inv_type', TYPE_BYTE),
           ('window_title', TYPE_STRING),
           ('num_slots', TYPE_BYTE)],
    0x65: [('window_id', TYPE_BYTE)],
    0x67: [('window_id',TYPE_BYTE),
           ('slot',TYPE_SHORT),
           ('item_id',TYPE_SHORT),
           ('count_uses',TYPE_SET_SLOT)],
    0x68: [('window_id',TYPE_BYTE),
           ('count',TYPE_SHORT),
           ('inventory',TYPE_INVENTORY)],
    0x69: [('window_id', TYPE_BYTE),
           ('progress_bar',TYPE_SHORT),
           ('value',TYPE_SHORT)],
    0x6a: [('window_id', TYPE_BYTE),
           ('action_num', TYPE_SHORT),
           ('accepted', TYPE_BOOL)],
    0x82: [('x', TYPE_INT),
           ('y', TYPE_SHORT),
           ('z', TYPE_INT),
           ('text1', TYPE_STRING),
           ('text2', TYPE_STRING),
           ('text3', TYPE_STRING),
           ('text4', TYPE_STRING)],
    0xff: [('reason', TYPE_STRING)]}

packet_spec = [ client_packet_spec, server_packet_spec ]

class mitm_parser(asyncore.dispatcher):
    """Parses a packet stream from a Minecraft client or server.
    """

    def __init__(self, sock, side, packet_hdlr, close_hdlr):
        asyncore.dispatcher.__init__(self,sock)
        self.side = side
        self.packet_hdlr = packet_hdlr
        self.close_hdlr = close_hdlr
        self.buf = ""
        self.i = 0

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        self.buf += self.recv(4092)
        try:
            packet = self.parse_packet()
            while packet != None:
                self.packet_hdlr(packet)
                packet = self.parse_packet()
        except Exception:
            print "mitm_parser caught exception"
            self.handle_close()
            raise

    def handle_close(self):
        print "mitm_socket closed"
        self.close()
        self.close_hdlr()

    def parse_packet(self):
        """Try to parse a single packet out of self.buf.

        If self.buf contains a complete packet, we parse it,
        remove it's data from self.buf, and return it as a dictionary.
        Otherwise, we leave self.buf alone and return None.
        """
        self.i=0
        try:
            packet={}
            # read Packet ID
            pid = self.parse_unsigned_byte()
            spec = packet_spec[self.side]
            if not spec.has_key(pid):
                raise UnsupportedPacketException(pid)
            print "Trying to parse packet %x" % pid
            packet['id'] = pid
            fmt = spec[pid]
            for name,type in fmt:
                if type == TYPE_BYTE:
                    packet[name]=self.parse_byte()
                elif type == TYPE_SHORT:
                    packet[name]=self.parse_short()
                elif type == TYPE_INT:
                    packet[name]=self.parse_int()
                elif type == TYPE_LONG:
                    packet[name]=self.parse_long()
                elif type == TYPE_FLOAT:
                    packet[name]=self.parse_float()
                elif type == TYPE_DOUBLE:
                    packet[name]=self.parse_double()
                elif type == TYPE_STRING:
                    packet[name]=self.parse_string()
                elif type == TYPE_BOOL:
                    packet[name]=self.parse_bool()
                elif type == TYPE_METADATA:
                    packet[name]=self.parse_metadata()
                elif type == TYPE_INVENTORY:
                    packet[name]=self.parse_inventory()
                elif type == TYPE_SET_SLOT:
                    if packet['item_id'] != -1:
                        packet[name]=self.parse_set_slot()
                elif type == TYPE_CHUNK:
                    packet[name]=self.parse_chunk()
                elif type == TYPE_MULTI_BLOCK_CHANGE:
                    packet[name]=self.parse_multi_block_change()
                elif type == TYPE_ITEM_DETAILS:
                    packet[name]=self.parse_item_details()
                elif type == TYPE_EXPLOSION_RECORD:
                    packet[name]=self.parse_explosion_record()
                else:
                    raise "Unknown data type %d" % type
            packet['packet_bytes']=self.buf[:self.i]
            self.buf = self.buf[self.i:]
            return packet
        except PartialPacketException:
            return None

    def parse_byte(self):
        if (self.i+1 > len(self.buf)):
            raise PartialPacketException()
        byte = struct.unpack_from(">b",self.buf,self.i)[0]
        self.i += 1
        return byte

    def parse_unsigned_byte(self):
        if (self.i+1 > len(self.buf)):
            raise PartialPacketException()
        byte = struct.unpack_from(">B",self.buf,self.i)[0]
        self.i += 1
        return byte

    def parse_short(self):
        if (self.i+2 > len(self.buf)):
            raise PartialPacketException()
        short = struct.unpack_from(">h",self.buf,self.i)[0]
        self.i += 2
        return short

    def parse_int(self):
        if (self.i+4 > len(self.buf)):
            raise PartialPacketException()
        num = struct.unpack_from(">i",self.buf,self.i)[0]
        self.i += 4
        return num

    def parse_long(self):
        if (self.i+8 > len(self.buf)):
            raise PartialPacketException()
        num = struct.unpack_from(">l",self.buf,self.i)[0]
        self.i += 8
        return num

    def parse_float(self):
        if (self.i+4 > len(self.buf)):
            raise PartialPacketException()
        num = struct.unpack_from(">f",self.buf,self.i)[0]
        self.i += 4
        return num
   
    def parse_double(self):
        if (self.i+8 > len(self.buf)):
            raise PartialPacketException()
        num = struct.unpack_from(">d",self.buf,self.i)[0]
        self.i += 8
        return num

    def parse_string(self):
        length = self.parse_short()
        if (length == 0):
            return ""
        if (self.i + length > len(self.buf)):
            raise PartialPacketException()
        str = self.buf[self.i:self.i+length]
        self.i += length
        return str

    def parse_bool(self):
        if (self.i+1 > len(self.buf)):
            raise PartialPacketException()
        b = struct.unpack_from(">B",self.buf,self.i)[0]
        if b==0:
            b=False
        else:
            b=True
        self.i += 1
        return b
    
    def parse_metadata(self):
        if (self.i+1 > len(self.buf)):
            raise PartialPacketException()
        data=[]
        type = self.parse_byte()
        while (type != 127):
            type = type >> 5
            if type == 0:
                data.append(self.parse_byte())
            elif type == 1:
                data.append(self.parse_short())
            elif type == 2:
                data.append(self.parse_int())
            elif type == 3:
                data.append(self.parse_float())
            elif type == 4:
                data.append(self.parse_string())
            elif type == 5:
                data.append(self.parse_short())
                data.append(self.parse_byte())
                data.append(self.parse_short())
            else:
                print repr(self.buf[:self.i])
                raise Exception("Unknown metadata type %d" % type)
            type = self.parse_byte()
        return data

    def parse_inventory(self):
        # The previously parsed short is the count of slots.
        self.i -= 2
        count = self.parse_short()
        payload = {}
        for j in xrange(0,count):
            item_id = self.parse_short()
            if item_id != -1:
                c = self.parse_byte()
                u = self.parse_short()
                payload[j] = (item_id,c,u)
            else:
                payload[j] = None
        return payload

    def parse_set_slot(self):
        return (self.parse_byte(), self.parse_short())

    def parse_chunk(self):
        self.i -= 4
        length = self.parse_int()
        if (self.i + length > len(self.buf)):
            raise PartialPacketException()
        data = self.buf[self.i:self.i+length]
        self.i += length
        return data

    def parse_multi_block_change(self):
        self.i -= 2
        length = self.parse_short()
        coord_array = []
        for j in xrange(0,length):
            coord_array.append(self.parse_short())
        type_array = []
        for j in xrange(0,length):
            type_array.append(self.parse_byte())
        metadata_array = []
        for j in xrange(0,length):
            metadata_array.append(self.parse_byte())
        return {'coord_array': coord_array,
                'type_array': type_array,
                'metadata_array': metadata_array}

    def parse_item_details(self):
        self.i -= 2
        id = self.parse_short()
        if (id >= 0):
            return {'count':self.parse_byte(),'uses':self.parse_short()}
        else:
            return None

    def parse_explosion_record(self):
        self.i -= 4
        c = parse_int()
        records = []
        for j in xrange(0,c):
            records.append( (parse_byte(),parse_byte(),parse_byte() ))
        return records

def sigint_handler(signum, stack):
    print "Received SIGINT, shutting down"
    sys.exit(0) 

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    lstnr = mitm_listener(34343, sys.argv[1], int(sys.argv[2]))
    asyncore.loop()

