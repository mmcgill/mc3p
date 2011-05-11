import re, asyncore, os, socket

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
            logging.info("Loaded %s"%os.path.abspath(mod.__file__))
        except:
            logging.error("ERROR: Failed to load plugin '%s' (from plugin.conf:%d)."%(pname,lnum))
            logging.error(traceback.format_exc())
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

def init_plugins():
    """Call plugin init() methods.

    Assumes that a PluginListener has already been created."""
    # Call plugin init methods.
    for p in plugins.values():
        if not p.__dict__.has_key('init') or not inspect.isfunction(p.init):
            continue
        c = PluginClient("client",p.__name__)
        s = PluginClient("server",p.__name__)
        try:
            p.init(c, s)
        except:
            logging.error("Plugin '%s' failed to initialize." % p.__name__)
            logging.error(traceback.format_exc())
            c.close()
            s.close()

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

PLUGIN_SOCKET_PATH = "/tmp/mc3psock"

class PluginListener(asyncore.dispatcher):
    """Listen for UNIX socket connections from plugins."""

    def __init__(self, stream, suffix):
        self.stream = stream
        asyncore.dispatcher.__init__(self)
        sockname = PLUGIN_SOCKET_PATH+"-"+suffix
        # Clean up the old socket, if it was there.
        if os.path.exists(sockname):
            os.unlink(sockname)
        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(sockname)
        self.listen(5)

    def handle_accept(self):
        pair = self.accept()
        if not pair:
            return
        sock, _ = pair
        PluginHandler(sock, self.stream)

class PluginHandler(asyncore.dispatcher):
    """Feed messages from plugins into a connection stream.

    Since writes through the UNIX socket aren't guaranteed to be atomic,
    we need a simple protocol to ensure we don't send a partial message
    to a Minecraft client or server. Here's the protocol:

        plugin_name: MC_string8, (len: MC_short, data: MC_byte * len)+

    A plugin starts by sending an MC_string8 to identify itself.
    It then sends a sequence of messages, each prefixed by its length."""

    def __init__(self, sock, stream):
        asyncore.dispatcher.__init__(self,sock)
        self.stream = stream
        self.plugin = None
        self.buf = stream()

    def handle_read(self):
        data = self.recv(4096)
        buf.append(data)
        try:
            if not plugin:
                plugin = MC_string8(buf)
                logging.debug("Got client connection from plugin '%s'" % plugin)
            size = MC_short(buf)
            while size <= len(buf):
                msgbytes = buf.read(size)
                logging.debug("Sending %d bytes from plugin %s" % (size, plugin))
                self.stream.send(msgbytes)
                buf.packet_finished()
        except PartialPacketException:
            pass # Not enough data in the buffer

class PluginClient(asyncore.dispatcher):
    """Send plugin messages to MC3P."""

    def __init__(self, suffix, plugin):
        """Connect to PluginListener.

        suffix is 'client' or 'server', and plugin is the plugin's name."""
        if 'client' == suffix:
            self.msg_spec = cli_msgs
        else:
            self.msg_spec = srv_msgs
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connect(PLUGIN_SOCKET_NAME+"-"+suffix)
        self.sendall(MC_string8(plugin))

    def inject_msg(msg):
        """Inject a message into the stream."""
        if not msg.has_key('msgtype'):
            logging.error("Plugin %s tried to send message without msgtype."%self.plugin)
            logging.debug("  msg: %s" % repr(msg))
            return
        msgtype = msg['msgtype']
        if not msg_spec[msgtype]:
            logging.error("Plugin %s tried to send message with unrecognized type %d" % (self.plugin, msgtype))
            logging.debug("  msg: %s" % repr(msg))
            return
        try:
            msgbytes = msg_spec[msgtype](msg)
        except:
            logging.error("Plugin %s sent invalid message of type %d" % (self.plugin, msgtype))
            logging.debug("  msg: %s" % repr(msg))

        #TODO: make use of asyncore interface to send this in non-blocking fashion.
        self.sendall(MC_short(len(msgbytes)))
        self.sendall(msgbytes)


