import netaddr
import logging

from ryu.topology import switches
from ryu.topology.switches import Port as Port_type
from ryu.lib.dpid import dpid_to_str
from ryu.lib.port_no import port_no_to_str
from ryu.ofproto.ofproto_v1_3_parser import OFPPort

logger = logging.getLogger(__name__)


class Port(switches.Port):
    def __init__(self, port, datapath=None):
        if isinstance(port, Port_type):     # port to neighbor switch
            self.datapath = datapath
            self.dpid = port.dpid
            self._ofproto = port._ofproto
            self._config = port._config
            self._state = port._state

            self.port_no = port.port_no
            self.hw_addr = netaddr.EUI(port.hw_addr)
            self.name = port.name

        elif isinstance(port, OFPPort):     # ofp_phy_port
            self.dpid = datapath.id
            self._ofproto = datapath.ofproto
            self._config = port.config
            self._state = port.state

            self.port_no = port.port_no
            self.hw_addr = netaddr.EUI(port.hw_addr)
            self.name = port.name
        else:
            raise AttributeError

    def get_port_state(self):
        return self._state

    def set_port_state(self, state):
        self._state = state

    def to_dict(self):
        d = {'port_no': self.port_no,
             'hw_addr': str(self.hw_addr),
             'name': self.name.rstrip('\0')}

        return d


class PortTable(dict):
    def __init__(self):
        super(PortTable, self).__init__()

    def add_port(self, port_no, port, datapath=None):
        try:
            port = Port(port, datapath)
        except TypeError:
            pass

        try:
            self[port_no] = Port(port, datapath)
        except KeyError:
            pass

    def del_port(self, port_no):
        try:
            del self[port_no]
        except KeyError:
            pass

    def get_port(self, port_no):
        try:
            return self[port_no]
        except KeyError:
            return None
