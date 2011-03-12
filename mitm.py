import asyncore
import socket
import sys
import signal
import struct
import logging

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
        self.mitm_client = mitm_parser(clientsock, mcproto.CLIENT_SIDE,
                                       self.handle_client_packet,
                                       self.client_closed)
        self.mitm_server = None
        try:
            serversock = socket.create_connection((dsthost,dstport))
        except:
            self.mitm_client.close()
            raise
        self.mitm_server = mitm_parser(serversock, mcproto.SERVER_SIDE,
                                       self.handle_server_packet,
                                       self.server_closed)
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
            logging.info("mitm_parser caught exception")
            self.handle_close()
            raise

    def handle_close(self):
        logging.info("mitm_socket closed")
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
            spec = mcproto.packet_spec[self.side]
            if not spec.has_key(pid):
                raise UnsupportedPacketException(pid)
            logging.debug("Trying to parse packet %x" % pid)
            packet['id'] = pid
            fmt = spec[pid]
            for name,type in fmt:
                if type == mcproto.TYPE_BYTE:
                    packet[name]=self.parse_byte()
                elif type == mcproto.TYPE_SHORT:
                    packet[name]=self.parse_short()
                elif type == mcproto.TYPE_INT:
                    packet[name]=self.parse_int()
                elif type == mcproto.TYPE_LONG:
                    packet[name]=self.parse_long()
                elif type == mcproto.TYPE_FLOAT:
                    packet[name]=self.parse_float()
                elif type == mcproto.TYPE_DOUBLE:
                    packet[name]=self.parse_double()
                elif type == mcproto.TYPE_STRING:
                    packet[name]=self.parse_string()
                elif type == mcproto.TYPE_BOOL:
                    packet[name]=self.parse_bool()
                elif type == mcproto.TYPE_METADATA:
                    packet[name]=self.parse_metadata()
                elif type == mcproto.TYPE_INVENTORY:
                    packet[name]=self.parse_inventory()
                elif type == mcproto.TYPE_SET_SLOT:
                    if packet['item_id'] != -1:
                        packet[name]=self.parse_set_slot()
                elif type == mcproto.TYPE_CHUNK:
                    packet[name]=self.parse_chunk()
                elif type == mcproto.TYPE_MULTI_BLOCK_CHANGE:
                    packet[name]=self.parse_multi_block_change()
                elif type == mcproto.TYPE_ITEM_DETAILS:
                    packet[name]=self.parse_item_details()
                elif type == mcproto.TYPE_EXPLOSION_RECORD:
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
                logging.info(repr(self.buf[:self.i]))
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
    logging.basicConfig(
        #filename='mitm.log',
        level=logging.INFO)
    signal.signal(signal.SIGINT, sigint_handler)
    lstnr = mitm_listener(34343, sys.argv[1], int(sys.argv[2]))
    asyncore.loop()

