import logging, logging.config, os
import asyncore, socket, sys, signal, struct, logging.config, re, os.path, inspect, imp
import traceback, tempfile
from time import time, sleep
from optparse import OptionParser

dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(dir)

import mcproto
import plugins
from parsing import parse_unsigned_byte
from util import Stream, PartialPacketException

logger = logging.getLogger("mc3p")

def sigint_handler(signum, stack):
    print "Received signal %d, shutting down" % signum
    sys.exit(0)


def parse_args():
    """Return host and port, or print usage and exit."""
    usage = "usage: %prog [options] host [port]"
    desc = """
Create a Minecraft proxy listening for a client connection,
and forward that connection to <host>:<port>."""
    parser = OptionParser(usage=usage,
                          description=desc)
    parser.add_option("-l", "--log-level", dest="loglvl", metavar="LEVEL",
                      choices=["debug","info","warn","error"],
                      help="Override logging.conf root log level")
    parser.add_option("-p", "--local-port", dest="locport", metavar="PORT", default="34343",
                      type="int", help="Listen on this port")
    (opts,args) = parser.parse_args()

    if not 1 <= len(args) <= 2:
        parser.error("Incorrect number of arguments.") # Calls sys.exit()

    host = args[0]
    port = 25565

    if len(args) == 2:
        try:
            port = int(sys.argv[2])
        except:
            parser.error("Invalid port '%s'" % args[1])

    return (host, port, opts)


def wait_for_client(port):
    """Listen on port for client connection, return resulting socket."""
    srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srvsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srvsock.bind( ("", port) )
    srvsock.listen(1)
    logger.info("mitm_listener bound to %d" % port)
    (sock, addr) = srvsock.accept()
    srvsock.close()
    logger.info("mitm_listener accepted connection from %s" % repr(addr))
    return sock


def create_proxies(clientsock, dsthost, dstport):
    """Open connection to dsthost:dstport, and return client and server proxies."""
    logger.info("creating proxy from client to %s:%d" % (dsthost,dstport))
    srv_proxy = None
    cli_proxy = None
    shutting_down = [False]
    def shutdown(side):
        """Close proxies and exit."""
        if shutting_down[0]:
            return
        logger.warn("%s socket closed, shutting down.", side)
        shutting_down[0] = True
        if cli_proxy:
            cli_proxy.close()
        if srv_proxy:
            srv_proxy.close()
    try:
        serversock = socket.create_connection( (dsthost,dstport) )
    except Exception as e:
        clientsock.close()
        logger.error("Couldn't connect to %s:%d - %s", dsthost, dstport, str(e))
        sys.exit(1)
    cli_proxy = MinecraftProxy(clientsock, serversock, mcproto.cli_msgs, shutdown, 'client')
    srv_proxy = MinecraftProxy(serversock, clientsock, mcproto.srv_msgs, shutdown, 'server')
    return (cli_proxy, srv_proxy)


class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)


def call_handlers(packet,side):
    """Call handlers, return True if packet should be forwarded."""
    # Call all global handlers first.
    for (pname,hdlr) in plugins.global_handlers:
        if not call_handler(hdlr, packet, side):
            return False

    # Call all message-specific handlers next.
    msgtype = packet['msgtype']
    if not plugins.handlers.has_key(msgtype):
        return True
    for handler in plugins.handlers[msgtype]:
        if not call_handler(handler, packet, side):
            return False

    # All handlers allowed message
    return True

def call_handler(handler, packet, side):
    try:
        ret = handler(packet, side)
        if ret == False: # 'if not ret:' is incorrect, a None return value means 'allow'
            return False
    except plugins.PluginError as e:
        print "Error in plugin %s: %s" % (handler.__module__, str(e))
    except:
        logger.error("Exception in handler %s.%s"%(handler.__module__,handler.__name__))
        logger.info("current MC message: %s" % repr(packet))
        logger.error(traceback.format_exc())
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
        self.msg_queue = []

    def handle_read(self):
        """Read all available bytes, and process as many packets as possible.
        """
        t = time()
        if self.last_report + 5 < t and self.stream.tot_bytes > 0:
            self.last_report = t
            logger.debug("%s: total/wasted bytes is %d/%d (%f wasted)" % (
                 self.side, self.stream.tot_bytes, self.stream.wasted_bytes,
                 100 * float(self.stream.wasted_bytes) / self.stream.tot_bytes))
        self.stream.append(self.recv(4092))
        try:
            packet = parse_packet(self.stream, self.msg_spec, self.side)
            while packet != None:
                logger.debug("%s packet: %s" % (self.side,repr(packet)) )
                if call_handlers(packet, self.side):
                    self.dst_sock.sendall(packet['raw_bytes'])
                # Since we know we're at a message boundary, we can inject
                # any messages in the queue
                if len(self.msg_queue) > 0:
                    for msgbytes in self.msg_queue:
                        self.dst_sock.sendall(msgbytes)
                    self.msg_queue = []
                packet = parse_packet(self.stream,self.msg_spec, self.side)
        except PartialPacketException:
            pass # Not all data for the current packet is available.
        except Exception:
            logger.error("mitm_parser caught exception")
            logger.error(traceback.format_exc())
            logger.debug("Current stream buffer: %s" % repr(self.stream.buf))
            self.on_shutdown(self.side)

    def handle_close(self):
        """Call shutdown handler."""
        self.on_shutdown(self.side)

    def inject_msg(self, bytes):
        self.msg_queue.append(bytes)


def parse_packet(stream, msg_spec, side):
    """Parse a single packet out of stream, and return it."""
    # read Packet ID
    msgtype = parse_unsigned_byte(stream)
    if not msg_spec[msgtype]:
        raise UnsupportedPacketException(msgtype)
    logger.debug("Trying to parse message type %x" % msgtype)
    msg_parser = msg_spec[msgtype]
    msg = msg_parser(stream)
    msg['raw_bytes'] = stream.packet_finished()
    return msg


def write_default_logging_file():
    """Write a default logging.conf."""
    contents="""
[loggers]
keys=root,mc3p,plugins,parsing

[handlers]
keys=consoleHdlr

[formatters]
keys=defaultFormatter

[logger_root]
level=WARN
handlers=consoleHdlr

[logger_mc3p]
handlers=
qualname=mc3p

[logger_plugins]
handlers=
qualname=plugins

[logger_parsing]
handlers=
qualname=parsing

[handler_consoleHdlr]
class=StreamHandler
formatter=defaultFormatter
args=(sys.stdout,)

[formatter_defaultFormatter]
format=%(levelname)s|%(asctime)s|%(name)s - %(message)s
datefmt=%H:%M:%S
"""
    f=None
    try:
        f=open("logging.conf","w")
        f.write(contents)
    finally:
        if f: f.close()

if __name__ == "__main__":
    (host, port, opts) = parse_args()

    # Initialize logging.
    if not os.path.exists('logging.conf'):
        write_default_logging_file()
    logging.config.fileConfig('logging.conf')
    #logging.basicConfig(level=logging.INFO)

    if opts.loglvl:
        print opts.loglvl
        logging.root.setLevel(getattr(logging, opts.loglvl.upper()))

    # Install signal handler.
    signal.signal(signal.SIGINT, sigint_handler)

    while True:
        cli_sock = wait_for_client(port=34343)

        #plugins.load_plugins_with_precedence()

        # Set up client/server main-in-the-middle.
        sleep(0.05)
        (cli_proxy, srv_proxy) = create_proxies(cli_sock, host, port)

        # Initialize plugins.
        #plugins.init_plugins(cli_proxy, srv_proxy)

        # I/O event loop.
        asyncore.loop()

