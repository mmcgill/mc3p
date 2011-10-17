
## What is mc3p?

mc3p (short for Minecraft Protocol-Parsing Proxy) is a Minecraft proxy
server with a Python plugin API for reading/modifying/injecting Minecraft
client-server messages.

## Using mc3p to forward Minecraft connections.

With no plugins configured, mc3p acts as a simple proxy. Suppose your network
administrator only allows outbound connections on port 80, but you want to
play Minecarft on your favorite server, herobrine.net:25565. If you have access
to a computer with python and a public IP address, you can use mc3p to forward
your connection at the expense of some extra latency.

On your server, run mc3p at the command line like so (you may need
root/Administrator privileges, depending on your OS):

    $ python mc3p.py -p 80 herobrine.net
    INFO|17:53:41|mc3p - mitm_listener bound to 80

In your Minecraft client, add <yourserver>:80 to the server list and
refresh it. You should see the herobrine.net server message, and be able
to connect to herobrine.net through mc3p.

## Using mc3p plugins.

If all you need is port forwarding, there are easier ways. The value of mc3p
is its plugin API. An mc3p plugin has complete control over all the
messages that pass between the Minecraft client and server. A plugin can
register to intercept messages of any type, and can drop, modify, or inject
any message at will. Best of all, mc3p does all the work of parsing the
Minecraft protocol and handling network I/O, freeing plugin developers to
focus on functionality.

The 'mute' plugin is provided as a simple example of mc3p's flexibility,
This plugin allows a player to mute chat messages from selected players on a
server. This functionality requires no modification to either the Minecraft
client or server.

We can load the plugin by starting mc3p with the --plugin command line option:

    $ python mc3p.py --plugin mute:mute herobrine.net

mc3p initializes the mute plugin when the Minecraft client connects to a server
through the proxy. We can now mute a player by entering '/mute NAME' in chat,
unmute with '/unmute NAME', and display muted players with '/muted'. The plugin
works by intercepting (and sometimes discarding) Minecraft chat messages.

## Writing mc3p plugins.

    from plugins import MC3Plugin, msghdlr

    class MutePlugin(MC3Plugin):
        """Lets the client mute players, hiding their chat messages.
        
        The client controls the plugin with chat commands:
            /mute NAME      Hide all messages from player NAME.
            /unmute NAME    Allow messages from player NAME.
            /muted          Show the list of currently muted players.
        """
        def init(self, args):
            self.muted_set = set() # Set of muted player names.

        def send_chat(self, chat_msg):
            """Send a chat message to the client."""
            self.to_client({'msgtype': 0x03, 'chat_msg': chat_msg})

        def mute(self, player_name):
            self.muted_set.add(player_name)
            self.send_chat('Muted %s' % player_name)

        def unmute(self, player_name):
            if player_name in self.muted_set:
                self.muted_set.remove(player_name)
                self.send_chat('Unmuted %s' % player_name)
            else:
                self.send_chat('%s is not muted' % player_name)

        def muted(self):
            self.send_chat('Currently muted: %s' % ', '.join(self.muted_set))

        @msghdlr(0x03)
        def handle_chat(self, msg, source):
            txt = msg['chat_msg']
            if source == 'client':
                # Handle mute commands
                if txt.startswith('/mute '):     self.mute(txt[len('/mute '):])
                elif txt.startswith('/unmute '): self.unmute(txt[len('/unmute '):])
                elif txt == '/muted':            self.muted()
                else: return True # Forward all other chat messages.

                return False # Drop mute plugin commands.
            else:
                # Drop messages containing the string <NAME>, where NAME is a muted player name.
                return not any(txt.startswith('<%s>' % name) for name in self.muted_set)
    

## Installation.

mc3p should run on any system with a working installation of Python 2.7.
So far, mc3p has been tested on OS X and Linux.

To install and use mc3p, ...

