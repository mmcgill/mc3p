import re, asyncore, os, socket, logging, traceback, imp, inspect
import mcproto
from util import Stream, PartialPacketException
from parsing import *

### Globals ###

logger = logging.getLogger(__name__)

def _plugin_call(f, *args):
    """Call f, return (True, retval) or (False, ex)."""
    try:
        return True, f(*args)
    except PluginError as e:
        return False, e
    except Exception as e2:
        logger.error(traceback.format_exc())
        return False, e

def load_source(name, path):
    """Replacement for imp.load_source().

    When loading 'foo.py', imp.load_source() uses a pre-compiled
    file ('foo.pyc' or 'foo.pyo') if its timestamp is not older than
    that of 'foo.py'. Unfortunately, the timestamps have a resolution
    of seconds on most platforms, so updates made to 'foo.py' within
    a second of the imp.load_source() call may or may not be reflected
    in the loaded module -- the behavior is non-deterministic.

    This load_source() replacement deletes a pre-compiled
    file before calling imp.load_source() if the pre-compiled file's
    timestamp is less than or equal to the timestamp of path.
    """
    if os.path.exists(path):
        for ending in ('c', 'o'):
            compiled_path = path+ending
            if os.path.exists(compiled_path) and \
               os.path.getmtime(compiled_path) <= os.path.getmtime(path):
                os.unlink(compiled_path)
    return imp.load_source(name, path)

class MCPlugin(object):
    def __init__(self, name, path, argstr):
        self.name = name
        self.path = path
        self.argstr = argstr
        self.module = load_source(name, path)
        self.to_client = None
        self.to_server = None
        self.handlers = {}

        self._load_handlers()

    def _load_handlers(self):
        # Look for catch-all message handler 'msgXX'.
        logger.debug('loading handlers from %s' % self.module.__file__)

        self._default_handler = None
        hdlr = self.module.__dict__.get('msgXX', None)
        if hdlr != None and inspect.isfunction(hdlr):
            logger.debug('  found default handler')
            self._default_handler = hdlr

        # Find the remaining handler functions.
        for f in filter(inspect.isfunction, self.module.__dict__.values()):
            match = msg_re.match(f.__name__)
            if not match:
                continue
            logger.debug('  found %s' % f.__name__)
            msgtype = int(match.group(1),16)
            if msgtype in self.handlers:
                raise PluginError("Error in %s: found multiple" % \
                                  (self.module.__file__,msgtype))
            else:
                self.handlers[msgtype] = f

    def default_handler(self, msg, dir):
        if self._default_handler:
            return self._default_handler(msg, dir)
        else:
            return None

    def init(self):
        logger.info('initializing %s' % self.name)
        if not self.module.__dict__.has_key('init') or \
           not inspect.isfunction(self.module.init):
            return
        self.to_client = PluginClient("client",self.name)
        self.to_server = PluginClient("server",self.name)
        success, ret = _plugin_call(self.module.init,
                                    self.to_client,
                                    self.to_server,
                                    self.argstr)
        if not success:
            print "Plugin '%s' failed to initialize: %s" % (self.name, e.msg)
            self.to_client.close()
            self.to_server.close()

    def destroy(self):
        logger.info('destroying %s' % self.name)
        if 'destroy' in self.module.__dict__ and \
           inspect.isfunction(self.module.destroy):
            _plugin_call(self.module.destroy)
        self.to_client.close()
        self.to_server.close()

# List of MCPlugin instances.
plugins = []

# Map of msgtype (int) to list of handler functions.
handlers = {}

client_plugin_lstnr = None
server_plugin_lstnr = None

### Exceptions ###
class ConfigException(Exception):
    def __init__(self,msg):
        Exception.__init__(self)
        self.msg = msg
    def __str__(self):
        return self.msg

class PluginError(Exception):
    def __init__(self,msg):
        self.msg = msg

    def __str__(self):
        return self.msg

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
    pdir = os.path.join(pdir,"plugin")
    for (lnum,line) in active:
        parts = line.split(" ", 1)
        pname = parts[0]
        ppath = os.path.join(pdir,pname)+".py"
        argstr = ""
        if len(parts) > 1:
            pname = parts[0]
            argstr = parts[1]

        def _load():
            plugin = MCPlugin(pname, ppath, argstr)
            plugins.append(plugin)
            logger.info("Loaded %s"%os.path.abspath(plugin.module.__file__))

        success, ret = _plugin_call(_load)
        if not success:
            print "Error loading %s: %s" % (pname, str(e))

    # Load message handlers.
    for plugin in plugins:
        # Load message-specific handlers
        for msgtype, f in plugin.handlers.items():
            if not handlers.has_key(msgtype):
                handlers[msgtype] = []
            handlers[msgtype].append(f)
            logger.info("Registered %s.%s"%(plugin.name,f.__name__))

    # Process message handler sections, and re-order handlers.
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
    of (lnum,line) pairs. hdlrs maps message types (int) to
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

def init_plugins(cli_proxy, srv_proxy):
    """Call plugin init() methods."""
    global client_plugin_lstnr, server_plugin_lstnr
    client_plugin_lstnr = PluginListener(cli_proxy, "client")
    server_plugin_lstnr = PluginListener(srv_proxy, "server")

    # Call plugin init methods.
    for plugin in plugins:
        plugin.init()

def destroy_plugins():
    for plugin in plugins:
        plugin.destroy()

    logger.info('closing plugin listeners')
    global client_plugin_lstnr, server_plugin_lstnr
    client_plugin_lstnr.close()
    server_plugin_lstnr.close()

def call_handlers(packet,side):
    """Call handlers, return True if packet should be forwarded."""
    # Call all default handlers first.
    for plugin in plugins:
        if not call_handler(plugin, plugin.default_handler, packet, side):
            return False

    # Call all message-specific handlers next.
    msgtype = packet['msgtype']
    if not handlers.has_key(msgtype):
        return True
    for handler in handlers[msgtype]:
        if not call_handler(plugin, handler, packet, side):
            return False

    # All handlers allowed message
    return True

def call_handler(plugin, handler, packet, side):
    success, ret = _plugin_call(handler, packet, side)
    if not success:
        logger.info("current MC message: %s" % repr(packet))
        print "Error in plugin %s: %s" % (plugin.name, str(e))
    elif ret == False: # 'if not ret:' is incorrect, a None return value means 'allow'
        return False
    else:
        return True

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
        # See if the socket is valid.
        try:
            sock.getpeername()
            PluginHandler(sock, self.stream)
        except socket.error:
            logger.info("In PluginListener.handle_accept(), sock.getpeername() failed. Did a plugin fail to initialize?")

class PluginHandler(asyncore.dispatcher):
    """Feed messages from plugins into a connection stream.

    Since writes through the UNIX socket aren't guaranteed to be atomic,
    we need a simple protocol to ensure we don't send a partial message
    to a Minecraft client or server. Here's the protocol:

        plugin_name: MC_string8, (len: MC_short, data: MC_byte * len)+

    A plugin starts by sending an MC_string8 to identify itself.
    It then sends a sequence of messages, each prefixed by its length."""

    def __init__(self, sock, proxy):
        self.proxy = proxy
        self.plugin = None
        self.buf = Stream()
        asyncore.dispatcher.__init__(self,sock)

    def handle_read(self):
        data = self.recv(4096)
        self.buf.append(data)
        try:
            if not self.plugin:
                self.plugin = MC_string8(self.buf)
                self.buf.packet_finished()
                logger.debug("Got client connection from plugin '%s'" % self.plugin)
            size = MC_short(self.buf)
            while size <= len(self.buf):
                msgbytes = self.buf.read(size)
                self.buf.packet_finished()
                logger.debug("Sending %d bytes from plugin %s: %s" % (size, self.plugin, repr(msgbytes)))
                self.proxy.inject_msg(msgbytes)
                size = MC_short(self.buf)
        except PartialPacketException:
            pass # Not enough data in the buffer

class PluginClient(asyncore.dispatcher):
    """Send plugin messages to MC3P."""

    def __init__(self, suffix, plugin):
        """Connect to PluginListener.

        suffix is 'client' or 'server', and plugin is the plugin's name."""
        if 'client' == suffix:
            self.msg_spec = mcproto.cli_msgs
        else:
            self.msg_spec = mcproto.srv_msgs
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connect(PLUGIN_SOCKET_PATH+"-"+suffix)
        self.sendall(MC_string8(plugin))

    def inject_msg(self, msg):
        """Inject a message into the stream."""
        if not msg.has_key('msgtype'):
            logger.error("Plugin %s tried to send message without msgtype."%self.plugin)
            logger.debug("  msg: %s" % repr(msg))
            return
        msgtype = msg['msgtype']
        if not self.msg_spec[msgtype]:
            logger.error("Plugin %s tried to send message with unrecognized type %d" % (self.plugin, msgtype))
            logger.debug("  msg: %s" % repr(msg))
            return
        try:
            msgbytes = self.msg_spec[msgtype](msg)
        except:
            logger.error("Plugin %s sent invalid message of type %d" % (self.plugin, msgtype))
            logger.debug("  msg: %s" % repr(msg))

        #TODO: make use of asyncore interface to send this in non-blocking fashion.
        self.sendall(MC_short(len(msgbytes)))
        self.sendall(msgbytes)

class PluginConfig(object):
    """Store plugin configuration"""
    def __init__(self, dir):
        self.__dir = dir
        self.__ids = []
        self.__plugin_names = {} # { id -> plugin_name }
        self.__argstrs = {} # { id -> argstr }
        self.__orderings = {} # { msgtype -> [id1, id2, ...] }

    def add(self, id, plugin_name, argstr=''):
        if id in self.__ids:
            raise ConfigError("Duplicate id '%s'" % id)
        self.__ids.append(id)
        self.__plugin_names[id] = plugin_name
        self.__argstrs[id] = argstr
        return self

    def order(self, msgtype, id_list):
        if len(set(id_list)) != len(id_list):
            raise ConfigError("Duplicate ids in %s" % repr(id_list))
        unknown_ids = set(self.__ids) - set(id_list)
        if len(unknown_ids) > 0:
            raise ConfigError("No such ids: %s" % repr(unknown_ids))
        self.__orderings[msgtype] = id_list
        return self

    @property
    def plugin_dir(self):
        """Directory that contains plugin files."""
        return self.__dir

    @property
    def ids(self):
        """List of instance ids."""
        return list(self.__ids)

    @property
    def plugins(self):
        """Set of instantiated plugin names."""
        return set(self.__plugin_names.values())

    @property
    def plugin(self):
        """Map of ids to plugin names."""
        return dict(self.__plugin_names)

    @property
    def argstr(self):
        """Map of ids to argument strings."""
        return dict(self.__argstrs)

    def ordering(self, msgtype):
        """Return a total ordering of instance ids for this msgtype."""
        if not msgtype in self.__orderings:
            return self.ids
        else:
            o = list(self.__orderings[msgtype])
            for id in self.__ids:
                if not id in o:
                    o.append(id)
            return o

class PluginManager(object):
    """Manage plugins for an mc3p session."""
    def __init__(self, config, cli_proxy, srv_proxy):
        # Map of plugin name to module.
        self.__plugins = {}

        # Map of instance ID to MC3Plugin instance.
        self.__instances = {}

        # True when a successful client-server handshake has completed.
        self.__session_active = False

        # For asynchronously injecting messages to the client or server.
        self.__client_plugin_lstnr = PluginListener(cli_proxy, "client")
        self.__server_plugin_lstnr = PluginListener(srv_proxy, "server")

        # Plugin configuration.
        self.__config = config

    def _load_plugins(self):
        """Load or reload all plugins."""
        logger.info('%s loading plugins' % repr(self))
        for pname in self.__config.plugins:
            self._load_plugin(pname)

    def _load_plugin(self, pname):
        """Load or reload plugin pname."""
        ppath = os.path.join(self.__config.plugin_dir, pname+'.py')
        try:
            logger.debug('  Loading %s at %s' % (pname, ppath))
            self.__plugins[pname] = load_source(pname, ppath)
        except Exception as e:
            logger.error("Plugin %s failed to load: %s" % (pname, str(e)))
            return

    def _instantiate_all(self):
        """Instantiate plugins based on self.__config.

        Assumes plugins have already been loaded.
        """
        logger.info('%s instantiating plugins' % repr(self))
        for id in self.__config.ids:
            pname = self.__config.plugin[id]
            if not pname in self.__plugins:
                continue
            else:
                self._instantiate_one(id,pname)

    def _find_plugin_class(self, pname):
        """Return the subclass of MC3Plugin in pmod."""
        pmod = self.__plugins[pname]
        class_check = lambda c: \
            c != MC3Plugin and isinstance(c, type) and issubclass(c, MC3Plugin)
        classes = filter(class_check, pmod.__dict__.values())
        if len(classes) == 0:
            logger.error("Plugin '%s' does not contain a subclass of MC3Plugin" % pname)
            return None
        elif len(classes) > 1:
            logger.error("Plugin '%s' contains multiple subclasses of MC3Plugin: %s" % \
                         (pname, ', '.join([c.__name__ for c in classes])))
        else:
            return classes[0]

    def _instantiate_one(self, id, pname):
        """Instantiate plugin pmod with id."""
        clazz = self._find_plugin_class(pname)
        if None == clazz:
            return
        to_cli = PluginClient('client', id)
        to_srv = PluginClient('server', id)
        try:
            logger.debug("  Instantiating plugin '%s' as '%s'" % (pname, id))
            inst = clazz(to_cli, to_srv)
            inst.init(self.__config.argstr[id])
            self.__instances[id] = inst
        except Exception as e:
            logger.error("Failed to instantiate '%s': %s" % (id, str(e)))
            to_cli.close()
            to_srv.close()

    def destroy(self):
        """Destroy plugin instances."""
        self.__plugins = {}
        logger.info("%s destroying plugin instances" % repr(self))
        for iname in self.__instances:
            logger.debug("  Destroying '%s'" % iname)
            try:
                self.__instances[iname]._destroy()
            except:
                logger.error("Error cleaning up instance '%s' of plugin '%s'" % \
                             (iname, self.__config.plugin[iname]))
                logger.error(traceback.format_exc())
        self.__instances = {}
        self.__client_plugin_lstnr.close()
        self.__server_plugin_lstnr.close()

    def filter(self, msg, dst):
        """Filter msg through the configured plugins.

        Returns True if msg should be forwarded, False otherwise.
        """
        if self.__session_active:
            msgtype = msg['msgtype']
            for id in self.__config.ordering(msgtype):
                inst = self.__instances[id]
                if not inst.filter(msg, dst):
                    return False
            return True
        else:
            if 'client' == dst and 0x01 == msg['msgtype']:
                logger.info('Handshake completed, loading plugins')
                self.__session_active = True
                self._load_plugins()
                self._instantiate_all()
            return True

    def __repr__(self):
        return '<PluginManager>'

class MsgHandlerWrapper(object):
    def __init__(self, msgtypes, method):
        for msgtype in msgtypes:
            if None == mcproto.cli_msgs[msgtype] and \
               None == mcproto.srv_msgs[msgtype]:
                raise PluginError('Unrecognized message type %x' % msgtype)
        self.msgtypes = msgtypes
        self.method = method

    def __call__(*args, **kargs):
        self.method(*args, **kargs)

def msghdlr(*msgtypes):
    def wrapper(f):
        return MsgHandlerWrapper(msgtypes, f)
    return wrapper

class MC3Plugin(object):
    """Base class for mc3p plugins."""

    def __init__(self, to_client, to_server):
        self.__to_client = to_client
        self.__to_server = to_server
        self.__hdlrs = {}
        self._collect_msg_hdlrs()

    def _collect_msg_hdlrs(self):
        wrappers = filter(lambda x: isinstance(x, MsgHandlerWrapper),
                          self.__class__.__dict__.values())
        print repr(self.__class__.__dict__.values())
        for wrapper in wrappers:
            self._unwrap_hdlr(wrapper)

    def _unwrap_hdlr(self, wrapper):
        hdlr = wrapper.method
        name = hdlr.__name__
        for msgtype in wrapper.msgtypes:
            if msgtype in self.__hdlrs:
                othername = self.__hdlrs[msgtype].__name__
                raise PluginError('Multiple handlers for %x: %s, %s' % \
                                  (msgtype, othername, name))
            else:
                self.__hdlrs[msgtype] = hdlr
                logger.debug('  registered handler %s for %x' % (name, msgtype))


    def init(self, args):
        """Initialize plugin instance.

        Override to provide subclass-specific initialization."""

    def destroy(self):
        """Free plugin resources.

        Override in subclass."""

    def _destroy(self):
        """Internal cleanup, do not override."""
        self.__to_client.close()
        self.__to_server.close()
        self.destroy()

    def to_server(self, msg):
        """Send msg to the server asynchronously."""
        self.__to_server.inject_msg(msg)

    def to_client(self, msg):
        """Send msg to the client asynchronously."""
        self.__to_client.inject_msg(msg)

    def default_handler(self, msg, dir):
        """Default message handler for all message types.

        Override in subclass to filter all message types."""
        return True

    def filter(self, msg, dir):
        """Filter msg via the appropriate message handler(s).

        Returns True to forward msg on, False to drop it.
        Modifications to msg are passed on to the recipient.
        """
        msgtype = msg['msgtype']
        if not self.default_handler(msg, dir):
            return False
        elif msgtype in self.__hdlrs:
            return self.__hdlrs[msgtype](self, msg, dir)
        else:
            return True


