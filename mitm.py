import asyncore
import socket
import sys
import signal

class mitm_listener(asyncore.dispatcher):
    """Listens for incoming Minecraft client connections to create mitm_channels for.
    """

    def __init__(self, srcport, dsthost, dstport):
        """Create a server that forwards local srcport to dsthost:dstport.
        """
        asyncore.dispatcher.__init__(self)
        self.dsthost = dsthost
        self.dstport = dstport
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("",srcport))
        self.listen(5)
        print "mitm_listener bound to %d" % srcport

    def handle_accept(self):
        sock,addr = self.accept()
        print "mitm_listener accepted connection from %s" % repr(addr)
        chan = mitm_channel(sock,self.dsthost,self.dstport)
        

class mitm_channel:
    """Handles a Minecraft client-server connection.
    """

    def __init__(self, clientsock, dsthost, dstport):
        print "creating mitm_channel from client to %s:%d" % (dsthost,dstport)
        self.mitm_client = mitm_socket(clientsock, self.handle_client_data,
                                       self.client_closed)
        serversock = socket.create_connection((dsthost,dstport))
        self.mitm_server = mitm_socket(serversock, self.handle_server_data,
                                       self.server_closed)

    def handle_client_data(self,data):
        """Parse, manipulate, and forward client data.
        """
        if (self.mitm_server):
            print "sending %d bytes from client to server" % len(data)
            self.mitm_server.send(data)
        else:
            print "dropping %d bytes from client" % len(data)

    def handle_server_data(self,data):
        """Parse, manipulate, and forward server data.
        """
        if (self.mitm_client):
            print "sending %d bytes from server to client" % len(data)
            self.mitm_client.send(data)
        else:
            print "dropping %d bytes from server" % len(data)

    def client_closed(self):
        print "mitm_channel: client socket closed"
        self.mitm_client = None
        if (self.mitm_server):
            print "mitm_channel: closing server socket"
            self.mitm_server.close()
            self.mitm_server = None

    def server_closed(self):
        print "mitm_channel: server socket closed"
        self.mitm_server = None
        if (self.mitm_client):
            print "mitm_channel: closing client scoket"
            self.mitm_client.close()
            self.mitm_client = None

class mitm_socket(asyncore.dispatcher):
    """Asyncronously reads from/writes to a socket using asyncore.
    """

    def __init__(self, sock, data_hdlr, close_hdlr):
        asyncore.dispatcher.__init__(self,sock)
        self.data_hdlr = data_hdlr
        self.close_hdlr = close_hdlr

    def handle_read(self):
        data = self.recv(4092)
        if (len(data) > 0):
            self.data_hdlr(data)

    def handle_close(self):
        print "mitm_socket closed"
        self.close()
        self.close_hdlr()

def sigint_handler(signum, stack):
    print "Received SIGINT, shutting down"
    sys.exit(0) 

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    lstnr = mitm_listener(34343, "localhost", 25565)
    asyncore.loop()

