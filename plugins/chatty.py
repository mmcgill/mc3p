
import logging

def init(sock1, sock2):
    """Initialize the plugin."""
    global cli_sock, srv_sock
    cli_sock = sock1
    srv_sock = sock2
    logging.info("chatty plugin initialized.")

def msg03(msg, dir):
    """Intercept and print chat messages."""
    if "server" == dir:
        return True
    msgtxt = msg['chat_msg']
    logging.info("Intercepted chat message from %s: %s" % (dir, repr(msg['raw_bytes'])))
    cli_sock.inject_msg({'msgtype': 0x03, 'chat_msg': msgtxt+"!"})
    return False

