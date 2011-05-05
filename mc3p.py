import asyncore, socket, sys, signal, struct, logging, re, os.path, inspect, imp
from traceback import print_exc
from time import time

import mcproto
from parsing import parse_unsigned_byte

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
        """Handle a packet from the client."""
        logging.debug("client packet: %s" % repr(packet))
        if self.call_handlers(packet,'client'):
            self.mitm_server.send(packet['packet_bytes'])

    def handle_server_packet(self,packet):
        """Handle a packet from the server."""
        logging.debug("server packet: %s" % repr(packet))
        if self.call_handlers(packet,'client'):
            self.mitm_client.send(packet['packet_bytes'])

    def call_handlers(self,packet,side):
        msgtype = packet['msgtype']
        if not handlers.has_key(msgtype):
            return True
        for handler in handlers[msgtype]:
            try:
                ret = handler(packet, side)
                if ret != None and ret == False:
                    return False
            except:
                print "Exception in handler %s.%s"%(handler.__module__,handler.__name__)
                print "message: %s" % repr(packet)
                print_exc()
        return True

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
        self.stream = stream()
        self.last_report = 0

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        t = time()
        if self.last_report + 5 < t and self.stream.tot_bytes > 0:
            self.last_report = t
            logging.debug("%s: total/wasted bytes is %d/%d (%f wasted)" % (
                 self.name, self.stream.tot_bytes, self.stream.wasted_bytes,
                 100 * float(self.stream.wasted_bytes) / self.stream.tot_bytes))
        self.stream.append(self.recv(4092))
        try:
            packet = parse_packet(self.stream,self.side)
            while packet != None:
                self.packet_hdlr(packet)
                packet = parse_packet(self.stream,self.side)
        except PartialPacketException:
            pass # Not all data for the current packet is available.
        except Exception:
            logging.info("mitm_parser caught exception")
            self.handle_close()
            raise

    def handle_close(self):
        logging.info("mitm_socket closed")
        self.close()
        self.close_hdlr()


def parse_packet(stream, side):
    """Parse a single packet out of stream, and return it."""
    packet={}
    # read Packet ID
    pid = parse_unsigned_byte(stream)
    spec = mcproto.packet_spec[side]
    if not spec.has_key(pid):
        raise UnsupportedPacketException(pid)
    logging.debug("Trying to parse packet %x" % pid)
    packet['msgtype'] = pid
    fmt = spec[pid]
    for name,fn in fmt:
        packet[name] = fn(stream)
    packet['packet_bytes'] = stream.packet_finished()
    return packet


def sigint_handler(signum, stack):
    print "Received SIGINT, shutting down"
    sys.exit(0) 

class ConfigException(Exception):
    def __init__(self,msg):
        Exception.__init__(self)
        self.msg = msg
    def __str__(self):
        return self.msg

plugins = {}
handlers = {}

def load_plugins_with_precedence():
    """Load active plugins, return a map of message type to handler list."""
    # Read active plugin and message handler sections.
    f = open("plugins.conf","r")
    try:
        (active,hdlrs) = read_plugins_conf(f)
    except ConfigException as e:
        print "Error reading plugins.conf:"
        print e.msg
        sys.exit(1)
    finally:
        f.close()

    # Load active plugin modules.
    pdir = os.path.dirname(os.path.abspath(__file__))
    pdir = os.path.join(pdir,"plugins")
    for (lnum,pname) in active:
        try:
            ppath = os.path.join(pdir,pname)+".py"
            mod = imp.load_source(pname, ppath)
            print "Loaded %s"%os.path.abspath(mod.__file__)
        except:
            print "ERROR: Failed to load plugin '%s' (from plugin.conf:%d)."%(pname,lnum)
            print_exc()
            continue
        plugins[pname] = mod

    # Load message handlers.
    for (lnum,pname) in active:
        if not plugins.has_key(pname):
            continue
        for f in filter(inspect.isfunction, plugins[pname].__dict__.values()):
            match = msg_re.match(f.__name__)
            if not match:
                continue
            msgtype = int(match.group(1),16)
            if not handlers.has_key(msgtype):
                handlers[msgtype] = []
            handlers[msgtype].append(f)
            print "Registered %s.%s"%(pname,f.__name__)

    # Process message handler sections.
    for (msgtype,lst) in hdlrs.items():
        if not handlers.has_key(msgtype):
            continue
        for lnum,mname in reversed(lst):
            # Find the handler for this module/msgtype.
            found = False
            hlst = handlers[msgtype]
            for i in xrange(len(hlst)):
                if hlst[i].__module__ == mname:
                    found = True
                    f = hlst[i]
                    del hlst[i]
                    hlst.insert(0,f)
                    break
            if not found:
                print "plugin.conf line %d: module %s has no function msg%02X" % (lnum,mname,msgtype)

def read_plugins_conf(f):
    """Read plugin config file f, return plugin config data structure.
    The plugins.conf config file is divided into sections. A
    header of the form "[name]" marks the start of a section. Each line in
    the body of a section must, after removal of whitespace and
    comments, contain the name of a plugin or be blank.

    The first section must be [active]. This section defines the active
    plugins. The order of the plugins defines the default message handler
    precedence. When two plugins each have a handler for the same message,
    precedence goes to the plugin listed first in the [active] list,
    unless the default is overridden in a following message precedence
    section.

    Each section after the [active] section is a message precedence
    section, and must start with a header of the form [msgXX], where
    XX is a Minecraft message type, in base 16. The body of a message
    precedence section is a list of plugins with handlers for Minecraft
    message type XX. The order of plugins defines the precedence of
    the message handlers.

    This function returns a tuple (active,hdlrs). active is a list
    of (lnum,name) pairs. hdlrs maps message types (int) to
    lists of (lnum,name) pairs. In each case, lnum is the corresponding
    line number in the config file, useful for generating error messages.
    """
    # TODO: Possibly check that each non-header line is a syntactically valid module name.
    active = []
    hdlrs = {}

    # [active] section must be first
    lnum = 0
    (lines,(lnum,hdr)) = read_to_next_hdr(f, lnum)
    if len(lines) > 0:
        lnum,line = lines[0]
        raise ConfigException("Line %d: non-empty lines before [active] section are not allowed."%lnum)
    if hdr == None:
        raise ConfigException("The [active] section is missing.")
    if hdr != "active":
        raise ConfigException("[active] must be the first section.")
    (lines,(lnum,hdr)) = read_to_next_hdr(f, lnum)
    active = lines

    # Read remaining message precedence sections.
    while hdr != None:
        type = hdr_msg_type(lnum,hdr)
        (lines,(lnum,hdr)) = read_to_next_hdr(f, lnum)
        hdlrs[type] = lines

    return (active,hdlrs)

msg_re = re.compile("msg([0-9a-fA-F]{2})")

def hdr_msg_type(lnum, hdr):
    """Extract message type from handler section header."""
    match = msg_re.match(hdr)
    if match:
        num_str = match.group(1)
        try:
            return int(num_str,16)
        except ValueError:
            pass
    raise ConfigException("Line %d: Invalid section header '[%s]'"%(lnum,hdr))

def read_to_next_hdr(f, last_lnum):
    """Read lines up to next header line or EOF.

    Strips comments and leading/trailing whitespace. Returns (lines,hdr),
    where lines is a list of (lnum,string) pairs, and hdr is a (lnum,string) pair
    where the string is the header name, or None if EOF was reached.
    The lnum part of each pair is the corresponding line number, for giving
    useful error messages."""
    re_hdr = re.compile("\\[(\w+)\\]")
    lines = []
    line = f.readline()
    lnum = last_lnum + 1
    hdr_match = re_hdr.match(line)
    while not hdr_match and line != "":
        if line.count("#") > 0:
            line = line[:line.find("#")]
        line = line.strip()
        if line != "":
            lines.append( (lnum,line) )
        line = f.readline()
        lnum += 1
        hdr_match = re_hdr.match(line)
    hdr = None
    if hdr_match:
        hdr = hdr_match.group(1)
    return (lines,(lnum,hdr))

if __name__ == "__main__":
    logging.basicConfig(
        #filename='mitm.log',
        level=logging.INFO)
    signal.signal(signal.SIGINT, sigint_handler)
    load_plugins_with_precedence()
    lstnr = mitm_listener(34343, sys.argv[1], int(sys.argv[2]))
    asyncore.loop()

