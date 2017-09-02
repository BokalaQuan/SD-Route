import logging

from ryu.lib.dpid import dpid_to_str, str_to_dpid
from device import Device
from topology_manage.object.port import PortTable
from lib.project_lib import enum


logger = logging.getLogger(__name__)

FLOW_IDLE_TIMEOUT = 60
FLOW_HARD_TIMEOUT = 600


class Switch(Device):
    AttributeEnum = enum(core="core", access="access", edge="edge",
                         aggregation="aggregation")

    def __init__(self, dp, s):
        super(Switch, self).__init__(dp)

        self.name = None

        # switch attribute: [core, access, edge]
        self.attribute = self.AttributeEnum.edge

        # switches[dpid] = Switch
        self.switches = s

        # neigbors[Switch] = [port_no]
        self.neighbors = {}

        # ports[port_no] = Port
        self.ports = PortTable()

    def __eq__(self, s):
        try:
            if self.dp.id == s.dp.id:
                return True
        except:
            return False
        return False

    def __str__(self):
        return '<Switch: %s>' % self.name

    def to_dict(self):
        return {'dpid': self.dp.id,
                'name': self.name,
                'attribute': self.attribute,
                'neighbors': [{'neighbor_dpid': dpid, 'port': port} for (dpid, port) in self.neighbors.items()],
                'ports': [port.to_dict() for (port_no, port) in self.ports.items()]}

    def to_conf_format(self):
        return {'dpid': dpid_to_str(self.dp.id),
                'name': self.name,
                'attribute': self.attribute}


class SwitchTable(dict):
    def __init__(self):
        super(SwitchTable, self).__init__()

    def add_switch(self, dpid, dp, s):
        try:
            sw = self[dpid]
            sw.dp = dp
            sw.switches = s
            return {dpid: sw}
        except KeyError:
            sw = Switch(dp, s)
            self[dpid] = sw
            return {dpid: sw}

    def del_switch(self, dpid):
        try:
            del self[dpid]
        except KeyError:
            pass

    def get_switch(self, dpid):
        if dpid in self:
            return self[dpid]
        return None

    def set_attribute(self, dpid, attr):
        sw = self[dpid]

        if attr in sw.AttributeEnum:
            sw.attribute = attr
        else:
            return AttributeError

    def get_neighbor(self, dpid, neighbor_dpid):
        try:
            return self[dpid].neighbors[neighbor_dpid]
        except KeyError:
            return None

    def set_neighbor(self, dpid, neighbor_dpid, port_no):
        if neighbor_dpid not in self[dpid].neighbors:
            self[dpid].neighbors[neighbor_dpid] = [port_no]
        elif port_no not in self[dpid].neighbors[neighbor_dpid]:
            self[dpid].neighbors[neighbor_dpid].append(port_no)

    def del_neighbor(self, dpid, neighbor_dpid, port_no):
        try:
            self[dpid].neighbors[neighbor_dpid].remove(port_no)
        except ValueError:
            pass
        if len(self[dpid].neighbors[neighbor_dpid]) == 0:
            del self[dpid].neighbors[neighbor_dpid]

    def to_dict(self):
        r = [{"dpid": dpid, "switch": switch.to_dict()} for (dpid, switch) in self.items()]
        return r

    def to_conf_format(self):
        r = [{"dpid": dpid,
              "switch": switch.to_conf_format()} for (dpid, switch) in self.items()]
        return r
