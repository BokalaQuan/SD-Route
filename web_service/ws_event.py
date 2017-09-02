import logging

LOG = logging.getLogger(__name__)


class EventBase(object):
    # Nothing yet
    pass


class EventFaultRecoveryBase(EventBase):
    def __init__(self):
        super(EventFaultRecoveryBase, self).__init__()


class EventWebRouteSet(EventBase):
    def __init__(self, links):
        self.links = links
        pass


class EventWebRouteSetDij(EventBase):
    def __init__(self, links):
        self.links = links
        pass


class EventDDoSTracebackSuccess():
    def __init__(self):
        pass

    pass


class EventWebLinkBandChange():
    def __init__(self, link_band):
        self.link_band = link_band
        pass

    pass


class EventDDoSTracebackSuccess_Link():
    def __init__(self, link):
        self.link = link
        pass

    pass
