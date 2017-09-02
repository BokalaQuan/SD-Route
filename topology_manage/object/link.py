import logging
import time

from ryu.topology import switches

from lib.project_lib import enum


logger = logging.getLogger(__name__)


class Link(switches.Link):
    AttributeEnum = enum(
        direct='direct',
        virtual='virtual')

    def __init__(self, src_port, dst_port, attr=None, pkt_loss=None,
                 total_band=None, available_band=None, delay=None, cost=None):
        self.src = src_port
        self.dst = dst_port

        self.attribute = attr
        self.pkt_loss = pkt_loss
        self.total_band = total_band
        self.available_band = available_band
        self.delay = delay
        self.cost = cost

        self.timestamp = time.time()

    def __eq__(self, other):
        if self.src == other.src and \
                self.dst == other.dst:
            return True
        return False

    def to_dict(self):
        return {'src_port': self.src.to_dict(),
                'dst_port': self.dst.to_dict(),
                'attribute': self.attribute,
                'pkt_loss': self.pkt_loss,
                'delay': self.delay,
                'cost': self.cost,
                'available_band': self.available_band,
                'total_band': self.total_band}

    def to_conf_format(self):
        return {'src_port': self.src.port_no,
                'dst_port': self.dst.port_no,
                'delay': self.delay,
                'cost': self.cost,
                'total_band': self.total_band}


class LinkTable(dict):
    def __init__(self, *args, **kwargs):
        super(LinkTable, self).__init__(*args, **kwargs)

    def add_link(self, link):
        src_port = link.src
        dst_port = link.dst

        src_dp = src_port.datapath

        src_port, dst_port = serialize(src_port, dst_port)

        src_dpid = src_port.dpid
        dst_dpid = dst_port.dpid
        src_dp = src_port.datapath

        new_link = Link(src_port, dst_port, attr=Link.AttributeEnum.direct)

        if (src_dpid, dst_dpid) not in self:
            self[(src_dpid, dst_dpid)] = [new_link]
            # self[(src_dpid, dst_dpid)].append(new_link)
            return {(src_dpid, dst_dpid): new_link}
        elif new_link not in self[(src_dpid, dst_dpid)]:
            self[(src_dpid, dst_dpid)].append(new_link)
            return {(src_dpid, dst_dpid): new_link}
        else:
            return None

    def del_link(self, link):
        src_port = link.src
        dst_port = link.dst

        src_port, dst_port = serialize(src_port, dst_port)
        if (src_port.dpid, dst_port.dpid) not in self:
            return None, None
        try:
            self[(src_port.dpid, dst_port.dpid)].remove(Link(src_port, dst_port))
            if len(self[(src_port.dpid, dst_port.dpid)]) == 0:
                del self[(src_port.dpid, dst_port.dpid)]
            return src_port.dpid, dst_port.dpid
        except:
            return None, None

    def get_link(self, link):
        src_port = link.src
        dst_port = link.dst

        src_port, dst_port = serialize(src_port, dst_port)
        try:
            return self[(src_port.dpid, dst_port.dpid)]
        except KeyError:
            return None

    def get_link_by_dpid(self, src_dpid, dst_dpid):
        if src_dpid > dst_dpid:
            src_dpid, dst_dpid = dst_dpid, src_dpid

        try:
            return self[(src_dpid, dst_dpid)]
        except KeyError:
            return None

    def add_virtual_link(self, src_dpid, src_port, dst_dpid, dst_port):
        if src_dpid > dst_dpid:
            src_dpid, dst_dpid = dst_dpid, src_dpid
            src_port, dst_port = dst_port, src_port

        new_virtual_link = Link(src_port, dst_port, attr=Link.AttributeEnum.virtual)

        if (src_dpid, dst_dpid) not in self:
            self[(src_dpid, dst_dpid)] = [new_virtual_link]
            return True

        try:
            i = self[(src_dpid, dst_dpid)].index(new_virtual_link)
        except:
            self[(src_dpid, dst_dpid)].append(new_virtual_link)
            return True

        # already have link with attr is not virtual
        if self[(src_dpid, dst_dpid)][i].attribute != Link.AttributeEnum.virtual:
            return False

    def del_virtual_link(self, src_dpid, src_port, dst_dpid, dst_port):
        if src_dpid > dst_dpid:
            src_dpid, dst_dpid = dst_dpid, src_dpid
            src_port, dst_port = dst_port, src_port

        if (src_dpid, dst_dpid) not in self:
            return None

        del_virtual_link = Link(src_port, dst_port)
        ls = self[(src_dpid, dst_dpid)]

        try:
            l = ls[ls.index(del_virtual_link)]
            if l.attribute == Link.AttributeEnum.virtual:
                self[(src_dpid, dst_dpid)].remove(del_virtual_link)
                if len(self[(src_dpid, dst_dpid)]) == 0:
                    del self[(src_dpid, dst_dpid)]
                return True
        except ValueError:
            return None

    def del_all_virtual_link(self, src_dpid, dst_dpid):
        if src_dpid > dst_dpid:
            src_dpid, dst_dpid = dst_dpid, src_dpid

        if (src_dpid, dst_dpid) not in self:
            return None

        for i, link in enumerate(self[(src_dpid, dst_dpid)]):
            if link.attribute == Link.AttributeEnum.virtual:
                del self[(src_dpid, dst_dpid)][i]

        if len(self[(src_dpid, dst_dpid)]) == 0:
            del self[(src_dpid, dst_dpid)]

    def to_dict(self):
        r = [{"src": src, "dst": dst, "link": [l.to_dict() for l in link]}
             for ((src, dst), link) in self.items()]
        return r

    def to_conf_format(self):
        r = [{"src": src, "dst": dst, "link": [l.to_conf_format() for l in link]}
             for ((src, dst), link) in self.items()]
        return r


class LinkTableApi(dict):
    def __init__(self, *args, **kwargs):
        super(LinkTableApi, self).__init__(*args, **kwargs)

    def init(self, link_table):
        assert isinstance(link_table, LinkTable)

        for src_dpid, dst_dpid in link_table.keys():
            links = link_table[(src_dpid, dst_dpid)]
            for link in links:
                src_port_no = link.src.port_no
                dst_port_no = link.dst.port_no
                if (src_dpid, dst_dpid) not in self:
                    self[(src_dpid, dst_dpid)] = {}
                self[(src_dpid, dst_dpid)][(src_port_no, dst_port_no)] = link


def serialize(src, dst):
    # if not isinstance(src, Port_base): raise TypeError
    # if not isinstance(dst, Port_base): raise TypeError
    #
    # src = Port(src)
    # dst = Port(dst)

    if src.dpid > dst.dpid:
        return dst, src
    return src, dst