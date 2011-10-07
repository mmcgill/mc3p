import unittest, shutil, tempfile, os, os.path, logging

from plugins import PluginConfig, PluginManager, load_source, MC3Plugin, msghdlr

MOCK_PLUGIN_CODE = """
from plugins import MC3Plugin, msghdlr

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

class TestPluginManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pdir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pdir)

    def _write_and_load(self, name, content):
        pfile = os.path.join(self.pdir, name+'.py')
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
        pcfg = PluginConfig(self.pdir).add('p1', 'mockplugin').add('p2', 'mockplugin')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(2, len(mockplugin.instances))
        self.assertFalse(mockplugin.instances[0].initialized)
        self.assertFalse(mockplugin.instances[1].initialized)

    def testEmptyPluginConfig(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig(self.pdir)
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(0, len(mockplugin.instances))
        
    def testMissingPluginClass(self):
        self._write_and_load('empty', 'from plugins import MC3Plugin\n')
        pcfg = PluginConfig(self.pdir).add('p', 'empty')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        # Should log an error, but not raise an exception.
        self.pmgr._instantiate_all()

    def testMultiplePluginClasses(self):
        code = MOCK_PLUGIN_CODE + "class AnotherPlugin(MC3Plugin): pass"
        mockplugin = self._write_and_load('mockplugin', code)
        pcfg = PluginConfig(self.pdir).add('p', 'mockplugin')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr._load_plugins()
        self.pmgr._instantiate_all()
        self.assertEqual(0, len(mockplugin.instances))

    handshake_msg = {'msgtype':0x01, 'eid': 1, 'reserved': '',
                     'map_seed': 42, 'server_mode': 0, 'dimension': 0,
                     'difficulty': 2, 'world_height': 128, 'max_players': 16}

    def testInstantiationAfterSuccessfulHandshake(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig(self.pdir).add('p1', 'mockplugin').add('p2', 'mockplugin')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.assertEqual(0, len(mockplugin.instances))

        self.pmgr.filter(self.__class__.handshake_msg, 'client')
        self.assertEqual(2, len(mockplugin.instances))

    def testMessageHandlerRegistration(self):
        class A(MC3Plugin):
            @msghdlr(0x01, 0x02, 0x03)
            def hdlr1(self, msg, dir): pass
            @msghdlr(0x04)
            def hdlr2(self, msg, dir): pass
        a = A(None, None)
        hdlrs = getattr(a, '_MC3Plugin__hdlrs')
        for msgtype in (0x01, 0x02, 0x03, 0x04):
            self.assertTrue(msgtype in hdlrs)
        self.assertEquals('hdlr1', hdlrs[0x01].__name__)
        self.assertEquals('hdlr2', hdlrs[0x04].__name__)

    def testMessageHandlerFiltering(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig(self.pdir).add('p1', 'mockplugin').add('p2', 'mockplugin')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.pmgr.filter(self.__class__.handshake_msg, 'client')
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

