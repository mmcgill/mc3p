import asyncore, socket, sys, signal, struct, logging, re, os.path, inspect, imp
import traceback, tempfile
from time import time

import mcproto, plugins
from parsing import parse_unsigned_byte


def sigint_handler(signum, stack):
    print "Received signal %d, shutting down" % signum
    sys.exit(0)


def parse_args():
    """Return host and port, or print usage and exit."""
    if len(sys.argv) != 3:
        print_usage()
    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except:
        print "Invalid port '%s'" % sys.argv[2]
        print_usage()
    return (host, port)


def print_usage():
    print "Usage: %s host port" % sys.argv[0]
    sys.exit(0)


def wait_for_client(port):
    """Listen on port for client connection, return resulting socket."""
    srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srvsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srvsock.bind( ("", port) )
    srvsock.listen(1)
    logging.info("mitm_listener bound to %d" % port)
    (sock, addr) = srvsock.accept()
    srvsock.close()
    logging.info("mitm_listener accepted connection from %s" % repr(addr))
    return sock


def create_proxies(clientsock, dsthost, dstport):
    """Open connection to dsthost:dstport, and return client and server proxies."""
    logging.info("creating proxy from client to %s:%d" % (dsthost,dstport))
    srv_proxy = None
    cli_proxy = None
    shutting_down = [False]
    def shutdown(side):
        """Close proxies and exit."""
        if shutting_down[0]:
            return
        print "%s socket closed, shutting down." % side
        shutting_down[0] = True
        if cli_proxy:
            cli_proxy.close()
        if srv_proxy:
            srv_proxy.close()
        sys.exit(0)
    try:
        serversock = socket.create_connection( (dsthost,dstport) )
    except Exception as e:
        clientsock.close()
        print "Couldn't connect to %s:%d - %s" % (dsthost,dstport,str(e))
        sys.exit(1)
    cli_proxy = MinecraftProxy(clientsock, serversock, mcproto.cli_msgs, shutdown, 'client')
    srv_proxy = MinecraftProxy(serversock, clientsock, mcproto.srv_msgs, shutdown, 'server')
    return (cli_proxy, srv_proxy)


class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)


class PartialPacketException(Exception):
    """Thrown during parsing when not a complete packet is not available."""
    pass


class Stream(object):
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

    def __len__(self):
        return len(self.buf) - i


def call_handlers(handlers,packet,side):
    """Call handlers, return True if packet should be forwarded."""
    msgtype = packet['msgtype']
    if not handlers.has_key(msgtype):
        return True
    for handler in handlers[msgtype]:
        try:
            ret = handler(packet, side)
            if ret != None and ret == False:
                return False
        except:
            logging.error("Exception in handler %s.%s"%(handler.__module__,handler.__name__))
            logging.info("current MC message: %s" % repr(packet))
            logging.error(traceback.format_exc())
    return True


class MinecraftProxy(asyncore.dispatcher):
    """Proxies a packet stream from a Minecraft client or server.
    """

    def __init__(self, src_sock, dst_sock, msg_spec, on_shutdown, side):
        asyncore.dispatcher.__init__(self,src_sock)
        self.dst_sock = dst_sock
        self.msg_spec = msg_spec
        self.on_shutdown = on_shutdown
        self.side = side
        self.stream = Stream()
        self.last_report = 0

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        t = time()
        if self.last_report + 5 < t and self.stream.tot_bytes > 0:
            self.last_report = t
            logging.debug("%s: total/wasted bytes is %d/%d (%f wasted)" % (
                 self.side, self.stream.tot_bytes, self.stream.wasted_bytes,
                 100 * float(self.stream.wasted_bytes) / self.stream.tot_bytes))
        self.stream.append(self.recv(4092))
        try:
            packet = parse_packet(self.stream, self.msg_spec, self.side)
            while packet != None:
                logging.debug("%s packet: %s" % (self.side,repr(packet)) )
                if call_handlers(plugins.handlers, packet, self.side):
                    self.dst_sock.sendall(packet['raw_bytes'])
                packet = parse_packet(self.stream,self.msg_spec, self.side)
        except PartialPacketException:
            pass # Not all data for the current packet is available.
        except Exception:
            logging.error("mitm_parser caught exception")
            logging.error(traceback.format_exc())
            logging.debug("Current stream buffer: %s" % repr(self.stream.buf))
            self.on_shutdown(self.side)

    def handle_close(self):
        """Call shutdown handler."""
        self.on_shutdown(self.side)


def parse_packet(stream, msg_spec, side):
    """Parse a single packet out of stream, and return it."""
    # read Packet ID
    msgtype = parse_unsigned_byte(stream)
    if not msg_spec[msgtype]:
        raise UnsupportedPacketException(msgtype)
    logging.debug("Trying to parse message type %x" % msgtype)
    msg_parser = msg_spec[msgtype]
    msg = msg_parser(stream)
    msg['raw_bytes'] = stream.packet_finished()
    return msg


if __name__ == "__main__":
    (host, port) = parse_args()

    # Initialize logging.
    logging.basicConfig(
        #filename='mitm.log',
        level=logging.INFO)

    # Install signal handler.
    signal.signal(signal.SIGINT, sigint_handler)

    cli_sock = wait_for_client(port=34343)

    plugins.load_plugins_with_precedence()

    # Set up client/server main-in-the-middle.
    (cli_proxy, srv_proxy) = create_proxies(cli_sock, host, port)

    client_plugin_lstnr = plugins.PluginListener(cli_proxy, "client")
    server_plugin_lstnr = plugins.PluginListener(srv_proxy, "server")

    # Initialize plugins.
    plugins.init_plugins()

    # I/O event loop.
    asyncore.loop()

