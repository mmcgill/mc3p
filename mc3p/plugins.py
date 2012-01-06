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

import re
import asyncore
import os
import socket
import logging
import traceback
import imp
import inspect
import multiprocessing
import Queue
import messages
from util import Stream, PartialPacketException
from parsing import *

### Globals ###

logger = logging.getLogger(__name__)


### Exceptions ###
class ConfigError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg


class PluginError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class PluginConfig(object):
    """Store plugin configuration"""
    def __init__(self):
        self.__ids = []
        self.__plugin_names = {}  # { id -> plugin_name }
        self.__argstrs = {}       # { id -> argstr }
        self.__orderings = {}     # { msgtype -> [id1, id2, ...] }

    def __default_id(self, plugin_name):
        id = plugin_name
        i = 1
        while id in self.__ids:
            id = plugin_name + str(i)
            i += 1
        return id

    def add(self, plugin_name, id=None, argstr=''):
        if id is None:
            id = self.__default_id(plugin_name)
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

        # Holds the protocol version number after successful handshake.
        self.__proto_version = 0

        # Stores handshake messages before handshake has completed,
        # so they can be fed to plugins after initialization.
        self.__msgbuf = []

        # For asynchronously injecting messages from the client or server.
        self.__from_client_q = multiprocessing.Queue()
        self.__from_server_q = multiprocessing.Queue()

        # Plugin configuration.
        self.__config = config

    def next_injected_msg_from(self, source):
        """Return the Queue containing source's messages to be injected."""
        if source == 'client':
            q = self.__from_client_q
        elif source == 'server':
            q = self.__from_server_q
        else:
            raise Exception('Unrecognized source ' + source)
        try:
            return q.get(block=False)
        except Queue.Empty:
            return None

    def _load_plugins(self):
        """Load or reload all plugins."""
        logger.info('%s loading plugins' % repr(self))
        for pname in self.__config.plugins:
            self._load_plugin(pname)

    def _load_plugin(self, pname):
        """Load or reload plugin pname."""
        try:
            logger.debug('  Loading %s' % pname)
            mod = __import__(pname)
            for p in pname.split('.')[1:]:
                mod = getattr(mod, p)
            self.__plugins[pname] = reload(mod)
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
                self._instantiate_one(id, pname)

    def _find_plugin_class(self, pname):
        """Return the subclass of MC3Plugin in pmod."""
        pmod = self.__plugins[pname]
        class_check = lambda c: \
            c != MC3Plugin and isinstance(c, type) and issubclass(c, MC3Plugin)
        classes = filter(class_check, pmod.__dict__.values())
        if len(classes) == 0:
            logger.error("Plugin '%s' does not contain " % pname + \
                         "a subclass of MC3Plugin")
            return None
        elif len(classes) > 1:
            logger.error(("Plugin '%s' contains multiple subclasses " + \
                          "of MC3Plugin: %s") % \
                         (pname, ', '.join([c.__name__ for c in classes])))
        else:
            return classes[0]

    def _instantiate_one(self, id, pname):
        """Instantiate plugin pmod with id."""
        clazz = self._find_plugin_class(pname)
        if None == clazz:
            return
        try:
            logger.debug("  Instantiating plugin '%s' as '%s'" % (pname, id))
            inst = clazz(self.__proto_version,
                         self.__from_client_q,
                         self.__from_server_q)
            inst.init(self.__config.argstr[id])
            self.__instances[id] = inst
        except Exception as e:
            logger.error("Failed to instantiate '%s': %s" % (id, str(e)))

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
                    logger.error(("Error cleaning up instance " + \
                                  "'%s' of plugin '%s'") % \
                                 (iname, self.__config.plugin[iname]))
                    logger.error(traceback.format_exc())
            self.__instances = {}

    def filter(self, msg, source):
        """Filter msg through the configured plugins.

        Returns True if msg should be forwarded, False otherwise.
        """
        if self.__session_active:
            if self.__msgbuf:
                # Re-play handshake messages to the plugins,
                # ignoring return values since the messages have
                # already been sent and so cannot be filtered.
                for (_msg, _source) in self.__msgbuf:
                    self._call_plugins(_msg, _source)
                self.__msgbuf = None
            return self._call_plugins(msg, source)
        else:
            if 0x01 == msg['msgtype']:
                if 'client' == source:
                    self.__proto_version = msg['proto_version']
                    logger.debug('PluginManager detected proto version %d' %
                                 self.__proto_version)
                else:
                    logger.info('Handshake completed, loading plugins')
                    self.__session_active = True
                    self._load_plugins()
                    self._instantiate_all()
            self.__msgbuf.append((msg, source))
            return True

    def _call_plugins(self, msg, source):
        msgtype = msg['msgtype']
        for id in self.__config.ordering(msgtype):
            inst = self.__instances.get(id, None)
            if inst and not inst.filter(msg, source):
                return False
        return True

    def __repr__(self):
        return '<PluginManager>'


class MsgHandlerWrapper(object):
    def __init__(self, msgtypes, method):
        for msgtype in msgtypes:
            if None == messages.cli_msgs[msgtype] and \
               None == messages.srv_msgs[msgtype]:
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

    def __init__(self, proto_version, from_client, from_server):
        self.__proto_version = proto_version
        self.__to_client = from_server
        self.__to_server = from_client
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
                logger.debug('  registered handler %s for %x' \
                             % (name, msgtype))

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

    def __encode_msg(self, source, msg):
        cli_msgs, srv_msgs = messages.protocol[self.__proto_version]
        msg_spec = cli_msgs if source == 'client' else srv_msgs

        if 'msgtype' not in msg:
            logger.error("Plugin %s tried to send message without msgtype." %\
                         self.__class__.__name__)
            logger.debug("  msg: %s" % repr(msg))
            return None
        msgtype = msg['msgtype']
        if not msg_spec[msgtype]:
            logger.error(("Plugin %s tried to send message with " +\
                          "unrecognized type %d") %\
                         (self.__class__.__name__, msgtype))
            logger.debug("  msg: %s" % repr(msg))
            return None
        try:
            msgbytes = msg_spec[msgtype](msg)
        except:
            #Todo: Make this output stacktrace
            logger.error("Plugin %s sent invalid message of type %d" % \
                         (self.__class__.__name__, msgtype))
            logger.debug("  msg: %s" % repr(msg))
        return msgbytes

    def to_server(self, msg):
        """Send msg to the server asynchronously."""
        msgbytes = self.__encode_msg('client', msg)
        if msgbytes:
            self.__to_server.put(msgbytes)

    def to_client(self, msg):
        """Send msg to the client asynchronously."""
        msgbytes = self.__encode_msg('server', msg)
        if msgbytes:
            self.__to_client.put(msgbytes)

    def default_handler(self, msg, source):
        """Default message handler for all message types.

        Override in subclass to filter all message types."""
        return True

    def filter(self, msg, source):
        """Filter msg via the appropriate message handler(s).

        Returns True to forward msg on, False to drop it.
        Modifications to msg are passed on to the recipient.
        """
        msgtype = msg['msgtype']
        try:
            if not self.default_handler(msg, source):
                return False
        except:
            logger.error('Error in default handler of plugin %s:\n%s' % \
                         (self.__class__.__name__, traceback.format_exc()))
            return True

        try:
            if msgtype in self.__hdlrs:
                return self.__hdlrs[msgtype](self, msg, source)
            else:
                return True
        except:
            hdlr = self.__hdlrs[msgtype]
            logger.error('Error in handler %s of plugin %s: %s' % \
                         (hdlr.__name__, self.__class__.__name__,
                          traceback.format_exc()))
            return True
