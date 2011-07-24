"""Record and play back server messages.

When run as an mc3p plugin, dvr saves messages from a client or server to a file.
When run as a stand-alone plugin, dvr replays those saved messages.

Format of a message file:
    <file> := <msg>*
    <msg> := <size> <delay> BYTE+
    <delay> := FLOAT
    <size> := INT

When dvr is run stand-alone, it acts as both the minecraft client and server.
It listens on a port as the server, and then connects as a client to mc3p.
It then replays all recorded messages, from both the client and server.

Command-line arguments:
[-X SPEED_FACTOR]
[-s SRV_PORT]
MC3P_PORT
FILE
"""

import socket, asyncore, logging, logging.config, os.path, sys, optparse, time, struct

if __name__ == "__main__":
    mc3p_dir = os.path.dirname(os.path.abspath(os.path.join(__file__,'..')))
    sys.path.append(mc3p_dir)

from plugins import PluginError, MC3Plugin, msghdlr

logger = logging.getLogger('plugin.dvr')

### Recording ##################

class DVROptParser(optparse.OptionParser):
    def error(self, msg):
        raise PluginError(msg)

class DVRPlugin(MC3Plugin):

    def init(self, args):
        self.cli_msgs = set()
        self.all_cli_msgs = False
        self.cli_msgfile = None
        self.srv_msgs = set()
        self.all_srv_msgs = False
        self.srv_msgfile = None
        self.parse_plugin_args(args)
        logger.info('initialized')
        logger.debug('cli_msgs=%s, srv_msgs=%s' % \
                     (repr(cli_msgs), repr(srv_msgs)))
        self.t0 = time.time()

    def parse_plugin_args(self, argstr):
        parser = DVROptParser()
        parser.add_option('--cli-file', dest='cli_file', default=None,
                          metavar='PATH', help='client capture file')
        parser.add_option('--srv-file', dest='srv_file', default=None,
                          metavar='PATH', help='server capture file')
        parser.add_option('-c', '--from-client', dest='cli_msgs',
                          default='', metavar='MSGS',
                          help='comma-delimited list of client message IDs')
        parser.add_option('-s', '--from-server', dest='srv_msgs',
                          default='', metavar='MSGS',
                          help='comma-delimited list of server message IDs')
        # TODO: Add append/overwrite options.

        (opts, args) = parser.parse_args(argstr.split(' '))
        if len(args) > 0:
            raise PluginError("Unexpected arguments '%s'" % args)

        if opts.cli_msgs == '' and opts.srv_msgs == '':
            raise PluginError("Must supply either --cli-msgs or --srv-msgs")

        if opts.cli_msgs == '*':
            self.all_cli_msgs = True
        elif opts.cli_msgs != '':
            self.cli_msgs = set([msg_id(s) for s in opts.cli_msgs.split(',')])

        if opts.srv_msgs == '*':
            self.all_srv_msgs = True
        elif opts.srv_msgs != '':
            self.srv_msgs = set([msg_id(s) for s in opts.srv_msgs.split(',')])
        # Always capture the disconnect messages.
        self.cli_msgs.add(0xff)
        self.srv_msgs.add(0xff)

        self.cli_msgfile = open(opts.cli_file, 'w')
        try:
            self.srv_msgfile = open(opts.srv_file, 'w')
        except:
            self.cli_msgfile.close()

    def msg_id(self, s):
        base = 16 if s.startswith('0x') else 10
        try: return int(s, base)
        except: raise PluginError("Invalid message ID '%s'" % s)

    def default_handler(self, msg, dir):
        pid = msg['msgtype']
        if 'client' == dir and (self.all_cli_msgs or pid in self.cli_msgs):
            self.record_msg(msg, self.cli_msgfile)
        if 'server' == dir and self.all_srv_msgs or pid in self.srv_msgs):
            self.record_msg(msg, self.srv_msgfile)

    def record_msg(self, msg, file):
        t = time.time() - self.t0
        bytes = msg['raw_bytes']
        hdr = struct.pack("<If", len(bytes), t)
        file.write(hdr)
        file.write(bytes)
        logger.debug('at t=%f, wrote msg of type %d (%d bytes)' % \
                     (t, msg['msgtype'], len(bytes)))

### Playback ###################

cli_done = False
srv_done = False

class MockListener(asyncore.dispatcher_with_send):
    """Listen for client connection, and spawn MockServer."""
    def __init__(self,host,port,msgfile):
        self.msgfile = msgfile
        asyncore.dispatcher_with_send.__init__(self)
        # Listen, and wait for connection.
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind( (host, port) )
        self.listen(1)
        logger.debug("listening on %s:%d" % (host, port))

    def handle_accept(self):
        pair = self.accept()
        if pair == None:
            logger.error('Failed to accept connection')
            self.close()
        else:
            (sock, addr) = pair
            logger.debug("received client connection from %s" % repr(addr))
            MockServer(sock, self.msgfile, 'server')
            self.close()

class MockServer(asyncore.dispatcher_with_send):
    def __init__(self, sock, msgfile, name, close_on_ff=True):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.msgfile = msgfile
        self.name = name
        self.close_on_ff = close_on_ff
        self.t0 = time.time() # start time
        self.nextmsg = None
        self.tnext = None
        self.closing = False

    def handle_read(self):
        """Read and throw away incomming bytes."""
        data = self.recv(4096)
        logger.debug("%s read %d bytes" % (self.name, len(data)))

    def readmsg(self):
        """Set self.nextmsg, self.tnext, or self.closing if no more messages."""
        nstr = self.msgfile.read(8)
        if len(nstr) == 0:
            self.closing = True
            logger.debug('%s reached end of file' % self.name)
        else:
            n, self.tnext = struct.unpack("<If", nstr)
            self.nextmsg = self.msgfile.read(n)
            logger.debug('%s read %d bytes from file with t=%f' % (self.name, n, self.tnext))

    def readable(self):
        return not self.closing and asyncore.dispatcher_with_send.readable(self)

    def writable(self):
        if self.closing:
            logger.debug('%s closing connection' % self.name)
            self.close()
        elif not self.nextmsg:
            self.readmsg()
        if self.nextmsg:
            t = time.time() - self.t0
            if t >= self.tnext:
                msgtype = struct.unpack('>B', self.nextmsg[0])[0]
                logger.info('%s sending msgtype %x (%d bytes) at t=%f', self.name, msgtype, len(self.nextmsg), t)
                self.send(self.nextmsg)
                msgtype = struct.unpack('>B', self.nextmsg[0])[0]
                self.nextmsg = None
                if msgtype == 255 and self.close_on_ff:
                    self.closing = True
        return not self.closing and asyncore.dispatcher_with_send.writable(self)


class MockClient(MockServer):
    def __init__(self,host, port, msgfile):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.debug("connecting to %s:%d" % (host,port))
        sock.connect( (host, port) )
        MockServer.__init__(self, sock, msgfile, "client", False)

def playback():
    # Parse arguments.
    opts = parse_args()

    # Override plugin.dvr log level with command-line option
    if opts.loglvl:
        logger.setLevel(getattr(logging, opts.loglvl.upper()))

    # Open server message file.
    try:
        srv_msgfile = open(opts.srv_msgfile, 'r')
    except Exception as e:
        print "Could not open %s: %s" % (opts.srv_msgfile, str(e))
        sys.exit(1)

    # Start listener, which will associate MockServer with socket on client connect.
    (srv_host, srv_port) = parse_addr(opts.srv_addr)
    MockListener(srv_host, srv_port, srv_msgfile)
    print "Started server."

    # Open client message file.
    try:
        cli_msgfile = open(opts.cli_msgfile, 'r')
    except Exception as e:
        print "Could not open %s: %s" % (opts.cli_msgfile, str(e))
        sys.exit(1)
    # Start client.
    (cli_host, cli_port) = parse_addr(opts.mc3p_addr)
    client = MockClient(cli_host, cli_port, cli_msgfile)
    print "Started client."

    # Loop until we're done.
    asyncore.loop(0.1)

    print "Done."

def parse_args():
    parser = make_arg_parser()
    (opts, args) = parser.parse_args()
    if len(args) != 0:
        parser.error("Unexpected arguments %s" % args)

    check_path(parser, opts.srv_msgfile, "--srv required")
    check_path(parser, opts.cli_msgfile, "--cli required")

    return opts

def check_path(parser, path, msg):
    if not path:
        parser.error(msg)
    if not os.path.exists(path):
        print "No such file '%s'" % path
        sys.exit(1)
    if not os.path.isfile(path):
        print "'%s' is not a file" % path
        sys.exit(1)

def parse_addr(addr):
    host = 'localhost'
    parts = addr.split(':',1)
    if len(parts) == 2:
        host = parts[0]
        parts[0] = parts[1]
    try:
        port = int(parts[0])
    except:
        print "Invalid port '%s'" % parts[0]
        sys.exit(1)
    return (host,port)

def make_arg_parser():
    parser = optparse.OptionParser(
        usage="usage: %prog [--to [HOST:]PORT] [--via [HOST:]PORT] [-x FACTOR] --srv SRV_FILE --cli CLI_FILE")
    parser.add_option('--via', dest='mc3p_addr',
        type='string', metavar='[HOST:]PORT', help='mc3p address', default='localhost:34343')
    parser.add_option('--to', dest='srv_addr',
        type='string', metavar='[HOST:]PORT', help='server address', default='localhost:25565')
    parser.add_option('-x', '--delay', dest='delay', type='float',
        metavar='FACTOR', help='multiply delay between messages by FACTOR', default=1.0)
    parser.add_option('--srv', dest='srv_msgfile', type='string', metavar='SRV_FILE',
        help='path to server message file', default=None)
    parser.add_option('--cli', dest='cli_msgfile', type='string', metavar='CLI_FILE',
        help='path to client message file', default=None)
    parser.add_option("-l", "--log-level", dest="loglvl", metavar="LEVEL",
                      choices=["debug","info","warn","error"], default=None,
                      help="Override logging.conf root log level")
    return parser

if __name__ == "__main__":
    logcfg = os.path.join(mc3p_dir,'logging.conf')
    if os.path.exists(logcfg) and os.path.isfile(logcfg):
        logging.config.fileConfig(logcfg)
    else:
        logging.basicConfig(level=logging.WARN)

    playback()

