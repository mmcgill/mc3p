
import logging

logger = logging.getLogger('plugin.chatty')

def init(sock1, sock2, args):
    """Initialize the plugin."""
    logger.info("chatty plugin initialized.")

def msg03(msg, dir):
    """Intercept and print chat messages."""
    if "server" == dir:
        print msg['chat_msg']
        return False
    return True

