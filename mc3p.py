import logging, logging.config, os
import asyncore, socket, sys, signal, struct, logging.config, re, os.path, inspect, imp
import traceback, tempfile
from time import time, sleep
from optparse import OptionParser

dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(dir)

import mcproto
from plugins import PluginConfig, PluginManager
from parsing import parse_unsigned_byte
from util import Stream, PartialPacketException
import util

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
    parser.add_option("--plugin", dest="plugins", metavar="ID:PLUGIN(ARGS)", type="string",
                      action="append", help="Configure a plugin", default=[])
    (opts,args) = parser.parse_args()

    if not 1 <= len(args) <= 2:
        parser.error("Incorrect number of arguments.") # Calls sys.exit()

    host = args[0]
    port = 25565
    pcfg = PluginConfig('plugin')
    pregex = re.compile('(?P<id>\\w+):(?P<plugin_name>\\w+)(\\((?P<argstr>.*)\\))?$')
    for pstr in opts.plugins:
        m = pregex.match(pstr)
        if not m:
            logger.error('Invalid --plugin option: %s' % pstr)
            sys.exit(1)
        else:
            parts = m.groupdict({'argstr': ''})
            pcfg.add(**parts)

    if len(args) == 2:
        try:
            port = int(sys.argv[2])
        except:
            parser.error("Invalid port '%s'" % args[1])

    return (host, port, opts, pcfg)


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


class MinecraftSession(object):
    """A client-server Minecraft session."""

    def __init__(self, pcfg, clientsock, dsthost, dstport):
        """Open connection to dsthost:dstport, and return client and server proxies."""
        logger.info("creating proxy from client to %s:%d" % (dsthost,dstport))
        self.srv_proxy = None
        self.cli_proxy = None
        self.shutting_down = False
        try:
            serversock = socket.create_connection( (dsthost,dstport) )
        except Exception as e:
            clientsock.close()
            logger.error("Couldn't connect to %s:%d - %s", dsthost, dstport, str(e))
            sys.exit(1)
        self.cli_proxy = MinecraftProxy(clientsock, serversock,
                                        mcproto.cli_msgs, self.shutdown, 'client')
        self.srv_proxy = MinecraftProxy(serversock, clientsock,
                                        mcproto.srv_msgs, self.shutdown, 'server')
        self.plugin_mgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.cli_proxy.plugin_mgr = self.plugin_mgr
        self.srv_proxy.plugin_mgr = self.plugin_mgr

    def shutdown(self, side):
        """Close proxies and exit."""
        if self.shutting_down:
            return
        logger.warn("%s socket closed, shutting down.", side)
        self.plugin_mgr.destroy()
        self.shutting_down = True
        if self.cli_proxy:
            self.cli_proxy.close()
        if self.srv_proxy:
            self.srv_proxy.close()

class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)


class MinecraftProxy(asyncore.dispatcher):
    """Proxies a packet stream from a Minecraft client or server.
    """

    def __init__(self, src_sock, dst_sock, msg_spec, on_shutdown, side):
        asyncore.dispatcher.__init__(self,src_sock)
        self.plugin_mgr = None
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
                if not self.plugin_mgr or self.plugin_mgr.filter(packet, self.side):
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


if __name__ == "__main__":
    (host, port, opts, pcfg) = parse_args()

    util.config_logging()

    if opts.loglvl:
        logging.root.setLevel(getattr(logging, opts.loglvl.upper()))

    # Install signal handler.
    signal.signal(signal.SIGINT, sigint_handler)

    while True:
        cli_sock = wait_for_client(opts.locport)

        # Set up client/server main-in-the-middle.
        sleep(0.05)
        MinecraftSession(pcfg, cli_sock, host, port)

        # I/O event loop.
        asyncore.loop()

