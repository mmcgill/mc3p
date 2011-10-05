import unittest, shutil, tempfile, os, os.path, logging

from plugins import PluginConfig, PluginManager, load_source

MOCK_PLUGIN_CODE = """
from plugins import MC3Plugin

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

    def init(self, args):
        self.initialized = True
        self.destroyed = False
        if fail_on_init:
            raise Exception('Failure!')

    def destroy(self):
        self.destroyed = True
        if fail_on_destroy:
            raise Exception('Failure!')

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

    def testInstantiationAfterSuccessfulHandshake(self):
        mockplugin = self._write_and_load('mockplugin', MOCK_PLUGIN_CODE)
        pcfg = PluginConfig(self.pdir).add('p1', 'mockplugin').add('p2', 'mockplugin')
        self.pmgr = PluginManager(pcfg, self.cli_proxy, self.srv_proxy)
        self.assertEqual(0, len(mockplugin.instances))

        self.pmgr.filter({'msgtype':0x01, 'eid': 1, 'reserved': '',
                          'map_seed': 42, 'server_mode': 0, 'dimension': 0,
                          'difficulty': 2, 'world_height': 128, 'max_players': 16},
                         'client')
        self.assertEqual(2, len(mockplugin.instances))
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()

