from .threads import LocalFuture
from .charm import charm
import time


class Channel(object):

    def __new__(cls, chare, remote, local=None):
        if not hasattr(chare, '__channels__'):
            chare.__initchannelattrs__()
        ch = chare.__findPendingChannel__(remote, False)
        if ch is None:
            local_port = len(chare.__channels__)
            ch = _Channel(local_port, remote, True)
            chare.__channels__.append(ch)
            chare.__pendingChannels__.append(ch)
        else:
            ch.setEstablished()
        if local is None:
            # if local is None, we assume local endpoint is the individual chare
            if hasattr(chare, 'thisIndex'):
                local = chare.thisProxy[chare.thisIndex]
            else:
                local = chare.thisProxy
        remote._channelConnect__(local, ch.port)
        return ch


CHAN_BUF_SIZE = 40000

class _Channel(object):

    def __init__(self, port, remote, locally_initiated):
        self.port = port
        self.remote = remote
        self.remote_port = -1
        self.send_seqno = 0
        self.recv_seqno = 0
        self.data = {}
        self.recv_fut = None  # this future is used to block on self.recv()
        self.wait_ready = None  # this future is used to block on ready (by charm.iwait())
        self.established = False
        self.established_fut = None
        self.locally_initiated = locally_initiated

    def setEstablished(self):
        self.established = True
        del self.established_fut
        del self.locally_initiated

    def ready(self):
        return self.recv_seqno in self.data

    def waitReady(self, f):
        self.wait_ready = f

    def send(self, *msg, **kwargs):
        if not self.established:
            self.established_fut = LocalFuture()
            self.established_fut.get()
            self.setEstablished()
        self.remote._channelRecv__(self.remote_port, self.send_seqno, *msg, **kwargs)
        self.send_seqno = (self.send_seqno + 1) % CHAN_BUF_SIZE

    def recv(self, *post_buffers, post_buf_addresses = None, post_buf_sizes = None, stream_ptrs = None):
        if self.recv_seqno in self.data:
            ret = self.data.pop(self.recv_seqno)
        else:
            self.recv_fut = LocalFuture()
            ret = self.recv_fut.get()
            self.recv_fut = None
        self.recv_seqno = (self.recv_seqno + 1) % CHAN_BUF_SIZE

        if post_buffers:
            gpu_recv_bufs = ret[-1]
            # ret = ret[:-1:1]
            assert len(post_buffers) == len(gpu_recv_bufs)
            recv_future = charm.getGPUDirectData(post_buffers, gpu_recv_bufs, stream_ptrs)
            recv_future.get()
        elif post_buf_addresses != None:
            gpu_recv_bufs = ret
            # ret = ret[:-1:1]
            assert len(post_buffers) == len(gpu_recv_bufs)
            assert post_buf_sizes
            recv_future = charm.getGPUDirectDataFromAddresses(post_buf_addresses, post_buf_sizes, gpu_recv_bufs, stream_ptrs)
            recv_future.get()


        return ret






