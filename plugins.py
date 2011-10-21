import re, asyncore, os, socket, logging, traceback, imp, inspect
import mcproto
from util import Stream, PartialPacketException
from parsing import *

### Globals ###

logger = logging.getLogger(__name__)

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

### Exceptions ###
class ConfigError(Exception):
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

        # Stores handshake messages before handshake has completed,
        # so they can be fed to plugins after initialization.
        self.__msgbuf = []

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
        to_srv = PluginClient('client', id)
        to_cli = PluginClient('server', id)
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
        if self.__session_active:
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
            if self.__msgbuf:
                for (_msg, _dst) in self.__msgbuf:
                    self._call_plugins(_msg, _dst)
                self.__msgbuf = None
            return self._call_plugins(msg, dst)
        else:
            if 'client' == dst and 0x01 == msg['msgtype']:
                logger.info('Handshake completed, loading plugins')
                self.__session_active = True
                self._load_plugins()
                self._instantiate_all()
            self.__msgbuf.append( (msg, dst) )
            return True

    def _call_plugins(self, msg, dst):
        msgtype = msg['msgtype']
        for id in self.__config.ordering(msgtype):
            inst = self.__instances.get(id, None)
            if inst and not inst.filter(msg, dst):
                return False
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
        try:
            if not self.default_handler(msg, dir):
                return False
        except:
            logger.error('Error in default handler of plugin %s:\n%s' % \
                         (self.__class__.__name__, traceback.format_exc()))
            return True

        try:
            if msgtype in self.__hdlrs:
                return self.__hdlrs[msgtype](self, msg, dir)
            else:
                return True
        except:
            hdlr = self.__hdlrs[msgtype]
            logger.error('Error in handler %s of plugin %s: %s' % \
                         (hdlr.__name__, self.__class__.__name__, traceback.format_exc()))
            return True


