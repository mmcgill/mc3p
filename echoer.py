import socket
import asyncore
import sys
import signal

class echoer(asyncore.dispatcher):

    def __init__(self,sock):
        asyncore.dispatcher.__init__(self,sock)

    def handle_read(self):
        data=self.recv(4092)
        if (len(data) > 0):
            print "echoing %d bytes" % len(data)
            self.send(data)

    def handle_close(self):
        print "%s disconnected" % repr(self.getpeername())
        self.close()

class echo_server(asyncore.dispatcher):

    def __init__(self,port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("",port))
        self.listen(5)
        print "echo_server bound to %d" % port

    def handle_accept(self):
        sock,addr = self.accept()
        print "%s connected" % repr(addr)
        echoer(sock)

def sigint_handler(signum,stack):
    print "Shutting down"
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    echo_server(25565)
    asyncore.loop()
