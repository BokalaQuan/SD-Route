import logging
LOG = logging.getLogger(__name__)


class EventBase(object):
    # Nothing yet
    pass


class EventFaultRecoveryBase(EventBase):
    def __init__(self):
        super(EventFaultRecoveryBase, self).__init__()


class EventFaultRecoveryUpdateServer(EventBase):
    def __init__(self, servers):
        self.servers = servers
        pass
    pass


class EventFaultRecoveryLinkDelete(EventBase):
    def __init__(self, src_port, dst_port, timestamp):
        self.src_port = src_port
        self.dst_port = dst_port
        self.timestamp = timestamp
        pass
    pass


class EventFaultRecoveryPortDown(EventBase):
    def __init__(self, port, timestamp):
        self.port = port
        self.timestamp = timestamp
