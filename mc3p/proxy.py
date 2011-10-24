# This source file is part of mc3p, the Minecraft Protocol Parsing Proxy.
#
# Copyright (C) 2011 Matthew J. McGill

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License v2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import logging, logging.config, os
import asyncore, socket, sys, signal, struct, logging.config, re, os.path, inspect, imp
import traceback, tempfile
from time import time, sleep
from optparse import OptionParser

import messages
from plugins import PluginConfig, PluginManager
from parsing import parse_unsigned_byte, parse_int
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
    parser.add_option("--profile", dest="perf_data", metavar="FILE", default=None,
                      help="Enable profiling, save profiling data to FILE")
    (opts,args) = parser.parse_args()

    if not 1 <= len(args) <= 2:
        parser.error("Incorrect number of arguments.") # Calls sys.exit()

    host = args[0]
    port = 25565
    pcfg = PluginConfig()
    pregex = re.compile('((?P<id>\\w+):)?(?P<plugin_name>[\\w\\.\\d_]+)(\\((?P<argstr>.*)\\))?$')
    for pstr in opts.plugins:
        m = pregex.match(pstr)
        if not m:
            logger.error('Invalid --plugin option: %s' % pstr)
            sys.exit(1)
        else:
            parts = {'argstr': ''}
            parts.update(m.groupdict())
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
        try:
            serversock = socket.create_connection( (dsthost,dstport) )
            self.cli_proxy = MinecraftProxy(clientsock)
        except Exception as e:
            clientsock.close()
            logger.error("Couldn't connect to %s:%d - %s", dsthost, dstport, str(e))
            logger.info(traceback.format_exc())
            return
        self.srv_proxy = MinecraftProxy(serversock, self.cli_proxy)
        self.plugin_mgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.cli_proxy.plugin_mgr = self.plugin_mgr
        self.srv_proxy.plugin_mgr = self.plugin_mgr

class UnsupportedPacketException(Exception):
    def __init__(self,pid):
        Exception.__init__(self,"Unsupported packet id 0x%x" % pid)

class MinecraftProxy(asyncore.dispatcher_with_send):
    """Proxies a packet stream from a Minecraft client or server.
    """

    def __init__(self, src_sock, other_side=None):
        """Proxies one side of a client-server connection.

        MinecraftProxy instances are created in pairs that have references to
        one another. Since a client initiates a connection, the client side of
        the pair is always created first, with other_side = None. The creator
        of the client proxy is then responsible for connecting to the server
        and creating a server proxy with other_side=client. Finally, the
        proxy creator should do client_proxy.other_side = server_proxy.
        """
        asyncore.dispatcher_with_send.__init__(self, src_sock)
        self.plugin_mgr = None
        self.other_side = other_side
        if other_side == None:
            self.side = 'client'
            self.msg_spec = messages.protocol[0][0]
        else:
            self.side = 'server'
            self.msg_spec = messages.protocol[0][1]
            self.other_side.other_side = self
        self.stream = Stream()
        self.last_report = 0
        self.msg_queue = []
        self.out_of_sync = False

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

        if self.out_of_sync:
            data = self.stream.read(len(self.stream))
            self.stream.packet_finished()
            if self.other_side:
                self.other_side.send(data)
            return

        try:
            packet = parse_packet(self.stream, self.msg_spec, self.side)
            while packet != None:
                if packet['msgtype'] == 0x01 and self.side == 'client':
                    # Determine which protocol message definitions to use.
                    proto_version = packet['proto_version']
                    logger.info('Client requests protocol version %d' % proto_version)
                    if not proto_version in messages.protocol:
                        logger.error("Unsupported protocol version %d" % proto_version)
                        self.handle_close()
                        return
                    self.msg_spec, self.other_side.msg_spec = messages.protocol[proto_version]
                forward = True
                if self.plugin_mgr:
                    forwarding = self.plugin_mgr.filter(packet, self.side)
                    if forwarding and packet.modified:
                        packet['raw_bytes'] = self.msg_spec[packet['msgtype']](packet)
                if forwarding and self.other_side:
                    self.other_side.send(packet['raw_bytes'])
                # Since we know we're at a message boundary, we can inject
                # any messages in the queue
                if len(self.msg_queue) > 0 and self.other_side:
                    for msgbytes in self.msg_queue:
                        self.other_side.send(msgbytes)
                    self.msg_queue = []
                packet = parse_packet(self.stream,self.msg_spec, self.side)
        except PartialPacketException:
            pass # Not all data for the current packet is available.
        except Exception:
            logger.error("MinecraftProxy for %s caught exception, out of sync" % self.side)
            logger.error(traceback.format_exc())
            logger.debug("Current stream buffer: %s" % repr(self.stream.buf))
            self.out_of_sync = True
            self.stream.reset()

    def handle_close(self):
        """Call shutdown handler."""
        logger.info("%s socket closed.", self.side)
        self.close()
        if self.other_side is not None:
            logger.info("shutting down other side")
            self.other_side.other_side = None
            self.other_side.close()
            self.other_side = None
            logger.info("shutting down plugin manager")
            self.plugin_mgr.destroy()

    def inject_msg(self, bytes):
        self.msg_queue.append(bytes)


class Message(dict):
    def __init__(self, d):
        super(Message, self).__init__(d)
        self.modified = False

    def __setitem__(self, key, val):
        if key in self and self[key] != val:
            self.modified = True
        return super(Message, self).__setitem__(key, val)

def parse_packet(stream, msg_spec, side):
    """Parse a single packet out of stream, and return it."""
    # read Packet ID
    msgtype = parse_unsigned_byte(stream)
    if not msg_spec[msgtype]:
        raise UnsupportedPacketException(msgtype)
    logger.debug("%s trying to parse message type %x" % (side, msgtype))
    msg_parser = msg_spec[msgtype]
    msg = msg_parser(stream)
    msg['raw_bytes'] = stream.packet_finished()
    return Message(msg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
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
        if opts.perf_data:
            logger.warn("Profiling enabled, saving data to %s" % opts.perf_data)
            import cProfile
            cProfile.run('asyncore.loop()', opts.perf_data)
        else:
            asyncore.loop()

