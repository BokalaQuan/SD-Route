from ryu.controller import event
from ryu.lib.dpid import dpid_to_str


class EventSwitchAdd(event.EventBase):
    def __init__(self, switch):
        super(EventSwitchAdd, self).__init__()
        self.switch = switch


class EventSwitchDel(event.EventBase):
    def __init__(self, dpid):
        super(EventSwitchDel, self).__init__()
        self.dpid = dpid


class EventLinkAdd(event.EventBase):
    def __init__(self, link):
        super(EventLinkAdd, self).__init__()
        self.link = link


class EventLinkDel(event.EventBase):
    def __init__(self, src, dst):
        super(EventLinkDel, self).__init__()
        self.src = src
        self.dst = dst


class EventLinkDelUpdateTopo(event.EventBase):
    def __init__(self, switches, links, src_port, dst_port, timestamp):
        super(EventLinkDelUpdateTopo, self).__init__()
        self.switches = switches
        self.links = links
        self.src_port = src_port
        self.dst_port = dst_port
        self.timestamp = timestamp


class EventPortDownUpdateTopo(event.EventBase):
    def __init__(self, port, timestamp):
        super(EventPortDownUpdateTopo, self).__init__()
        self.port = port
        self.timestamp = timestamp


class EventSwitchRequest(event.EventRequestBase):
    # If dpid is None, reply all switches
    def __init__(self, dpid=None):
        super(EventSwitchRequest, self).__init__()
        self.dst = 'TopologyManage'
        self.dpid = dpid

    def __str__(self):
        if self.dpid:
            return 'EventSwitchRequest<dpid=%s>', self.dpid
        return 'EventSwitchRequest<all switches>'


class EventSwitchReply(event.EventReplyBase):
    def __init__(self, dst, switches):
        super(EventSwitchReply, self).__init__(dst)
        self.switches = switches

    def __str__(self):
        return 'EventSwitchReply< >'


class EventLinkRequest(event.EventRequestBase):
    # If src, dst is None, reply all links
    def __init__(self, src_dpid=None, dst_dpid=None):
        super(EventLinkRequest, self).__init__()
        self.dst = 'TopologyManage'
        self.src_dpid = src_dpid
        self.dst_dpid = dst_dpid

    def __str__(self):
        if self.src_dpid and self.dst_dpid:
            return 'EventLinkRequest<src=%s, dst=%s>', \
                   (self.src_dpid, self.dst_dpid)
        return 'EventLinkRequest<all links>'


class EventLinkReply(event.EventReplyBase):
    def __init__(self, dst, links):
        super(EventLinkReply, self).__init__(dst)
        self.links = links

    def __str__(self):
        return 'EventLinkReply< >'


class EventTopoInitializeEnd(event.EventBase):
    def __init__(self, link_table):
        super(EventTopoInitializeEnd, self).__init__()
        self.link_table = link_table

