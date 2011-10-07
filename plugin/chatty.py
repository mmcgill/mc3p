
from plugins import MC3Plugin, msghdlr
import logging

logger = logging.getLogger('plugin.chatty')

class ChattyPlugin(MC3Plugin):
    def init(self, args):
        """Initialize the plugin."""
        print 'chatty: %s' % args
        logger.info("chatty plugin initialized: %s" % args)

    @msghdlr(0x03)
    def handle_chat(self, msg, dir):
        """Intercept and print chat messages."""
        if "server" == dir:
            print msg['chat_msg']
            return False
        return True

