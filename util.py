

class PartialPacketException(Exception):
    """Thrown during parsing when not a complete packet is not available."""
    pass


class Stream(object):
    """Represent a stream of bytes."""

    def __init__(self):
        """Initialize the stream."""
        self.buf = ""
        self.i = 0
        self.tot_bytes = 0
        self.wasted_bytes = 0

    def append(self,str):
        """Append a string to the stream."""
        self.buf += str

    def read(self,n):
        """Read n bytes, returned as a string."""
        if self.i + n > len(self.buf):
            self.wasted_bytes += self.i
            self.i = 0
            raise PartialPacketException()
        str = self.buf[self.i:self.i+n]
        self.i += n
        return str

    def packet_finished(self):
        """Mark the completion of a packet, and return its bytes as a string."""
        # Discard all data that was read for the previous packet,
        # and reset i.
        data = ""
        if self.i > 0:
            data = self.buf[:self.i]
            self.buf = self.buf[self.i:]
            self.tot_bytes += self.i
            self.i = 0
        return data

    def __len__(self):
        return len(self.buf) - self.i



