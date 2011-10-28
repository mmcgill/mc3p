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

import sys, unittest, shutil, tempfile, os, os.path, logging, imp

from mc3p.plugins import PluginConfig, PluginManager, MC3Plugin, msghdlr

MOCK_PLUGIN_CODE = """
from mc3p.plugins import MC3Plugin, msghdlr

print 'Initializing mockplugin.py'
instances = []
fail_on_init = False
fail_on_destroy = False

class MockPlugin(MC3Plugin):
    def __init__(self, *args, **kargs):
        super(MockPlugin, self).__init__(*args, **kargs)
        global instances
        instances.append(self)
        self.initialized = False
        self.destroyed = False
        self.drop_next_msg = False
        self.last_msg = None

    def init(self, args):
        self.initialized = True
        self.destroyed = False
        if fail_on_init:
            raise Exception('Failure!')

    def destroy(self):
        self.destroyed = True
        if fail_on_destroy:
            raise Exception('Failure!')

    @msghdlr(0x03)
    def handle_chat(self, msg, dest):
        self.last_msg = msg
        if self.drop_next_msg:
            self.drop_next_msg = False
            return False
        else:
            return True
"""
    
class MockMinecraftProxy(object):
    pass

def load_source(name, path):
    """Replacement for __import__/imp.load_source().

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
    mod = __import__(name)
    for p in name.split('.')[1:]:
        mod = getattr(mod, p)
    return reload(mod)

class TestPluginManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pdir = tempfile.mkdtemp()
        cls.pkgdir = tempfile.mkdtemp(dir=cls.pdir)
        with open(os.path.join(cls.pkgdir, '__init__.py'), 'w') as f:
            f.write('')
        sys.path.append(cls.pdir)

    @classmethod
    def tearDownClass(cls):
        sys.path.pop()
        shutil.rmtree(cls.pdir)

    def _write_and_load(self, name, content):
        pfile = os.path.join(*name.split('.'))
        pfile = os.path.join(self.pdir, pfile+'.py')
        print 'loading %s as %s' % (pfile, name)
        with open(pfile, 'w') as f:
            f.write(content)
        mod = load_source(name, pfile)
        return mod

    def setUp(self):
        self.pdir = self.__class__.pdir
        self.cli_proxy, self.srv_proxy = MockMinecraftProxy(), MockMinecraftProxy()

    def tearDown(self):
        if hasattr(self,'pmgr') and self.pmgr != None:
            try: self.pmgr.destroy()
            except Exception as e:
                import traceback
                traceback.print_exc()

    def testInstantiation(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig().add('mockplugin', 'p1').add('mockplugin', 'p2')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(2, len(mockplugin.instances))
        self.assertTrue(mockplugin.instances[0].initialized)
        self.assertTrue(mockplugin.instances[1].initialized)

    def testDefaultPluginIds(self):
        pcfg = PluginConfig().add('mockplugin')
        self.assertEqual('mockplugin', pcfg.ids[0])

        pcfg.add('mockplugin')
        pcfg.add('mockplugin')
        self.assertEqual('mockplugin1', pcfg.ids[1])
        self.assertEqual('mockplugin2', pcfg.ids[2])

    def testEmptyPluginConfig(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig()
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(0, len(mockplugin.instances))
        
    def testMissingPluginClass(self):
        self._write_and_load('empty', 'from mc3p.plugins import MC3Plugin\n')
        pcfg = PluginConfig().add('empty', 'p')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        # Should log an error, but not raise an exception.
        self.pmgr._instantiate_all()

    def testMultiplePluginClasses(self):
        code = MOCK_PLUGIN_CODE + "class AnotherPlugin(MC3Plugin): pass"
        mockplugin = self._write_and_load('mockplugin', code)
        pcfg = PluginConfig().add('mockplugin', 'p')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(0, len(mockplugin.instances))

    handshake_msg1 = {'msgtype':0x01, 'proto_version': 21, 'username': 'foo',
                      'nu1': 0, 'nu2': 0, 'nu3': 0, 'nu4': 0, 'nu5': 0, 'nu6': 0}
    handshake_msg2 = {'msgtype':0x01, 'eid': 1, 'reserved': '',
                      'map_seed': 42, 'server_mode': 0, 'dimension': 0,
                      'difficulty': 2, 'world_height': 128, 'max_players': 16}

    def testLoadingPluginInPackage(self):
        pkgname = os.path.basename(self.__class__.pkgdir)
        mockplugin = self._write_and_load(pkgname+'.mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig().add('%s.mockplugin' % pkgname, 'p1')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(1, len(mockplugin.instances))
        self.assertTrue(mockplugin.instances[0].initialized)

    def testInstantiationAfterSuccessfulHandshake(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig().add('mockplugin', 'p1').add('mockplugin', 'p2')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.assertEqual(0, len(mockplugin.instances))

        self.pmgr.filter(self.__class__.handshake_msg1, 'client')
        self.pmgr.filter(self.__class__.handshake_msg2, 'server')
        self.assertEqual(2, len(mockplugin.instances))

    def testMessageHandlerRegistration(self):
        class A(MC3Plugin):
            @msghdlr(0x01, 0x02, 0x03)
            def hdlr1(self, msg, dir): pass
            @msghdlr(0x04)
            def hdlr2(self, msg, dir): pass
        a = A(21, None, None)
        hdlrs = getattr(a, '_MC3Plugin__hdlrs')
        for msgtype in (0x01, 0x02, 0x03, 0x04):
            self.assertTrue(msgtype in hdlrs)
        self.assertEquals('hdlr1', hdlrs[0x01].__name__)
        self.assertEquals('hdlr2', hdlrs[0x04].__name__)

    def testMessageHandlerFiltering(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig().add('mockplugin', 'p1').add('mockplugin', 'p2')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr.filter(self.__class__.handshake_msg1, 'client')
        self.pmgr.filter(self.__class__.handshake_msg2, 'server')
        p1 = mockplugin.instances[0]
        p2 = mockplugin.instances[1]
        msg = {'msgtype': 0x03, 'chat_msg': 'foo!'}

        self.assertTrue(self.pmgr.filter(msg, 'client'))
        self.assertEquals(msg, p1.last_msg)
        self.assertEquals(msg, p2.last_msg)

        p1.drop_next_msg = True
        self.assertFalse(self.pmgr.filter({'msgtype': 0x03, 'chat_msg': 'bar!'}, 'server'))
        self.assertEquals(msg, p2.last_msg)

        p1.drop_next_msg = True
        self.assertTrue(self.pmgr.filter({'msgtype': 0x04, 'time': 42}, 'client'))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()

