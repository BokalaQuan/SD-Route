import logging
import json

from ryu.base import app_manager
from ryu.controller import event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether
from ryu.lib import mac
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp, ipv4

import topology_manage.api as topo_api
from lib.project_lib import find_packet
from HostTrack import DEFAULT_ARP_PING_SRC_MAC


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

proxy_arp_instance_name = 'proxy_arp_app'
rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})


class EventHostMissing(event.EventBase):
    def __init__(self, msg, flag):
        super(EventHostMissing, self).__init__()
        self.msg = msg
        self.flag = flag


class HostDiscovery(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _EVENTS = []

    def __init__(self, *args, **kwargs):
        super(HostDiscovery, self).__init__(*args, **kwargs)
        self.switches = None

    @set_ev_cls(EventHostMissing, MAIN_DISPATCHER)
    def host_missing_handler(self, ev):
        msg = ev.msg
        if ev.flag == 'host':
            req_ip = msg
        elif ev.flag == 'src':
            pkt = packet.Packet(msg.data)
            ip_layer = find_packet(pkt, 'ipv4')
            req_ip = ip_layer.src
        elif ev.flag == 'dst':
            pkt = packet.Packet(msg.data)
            ip_layer = find_packet(pkt, 'ipv4')
            req_ip = ip_layer.dst
        else:
            assert ValueError
            return

        self.switches = topo_api.get_all_switch(self)

        for dpid in self.switches:
            sw = self.switches.get_switch(dpid)
            if sw.attribute == sw.AttributeEnum.edge:
                self._send_arp_request(sw.dp, req_ip)
                pass

    @staticmethod
    def _send_arp_request(datapath, req_ip):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        out_port = ofproto.OFPP_FLOOD

        p = packet.Packet()
        p.add_protocol(ethernet.ethernet(ethertype=ether.ETH_TYPE_ARP,
                                         dst=mac.BROADCAST_STR,
                                         src=DEFAULT_ARP_PING_SRC_MAC))
        p.add_protocol(arp.arp(opcode=arp.ARP_REQUEST,
                               src_mac=DEFAULT_ARP_PING_SRC_MAC,
                               dst_mac=mac.DONTCARE_STR,
                               dst_ip=req_ip))
        p.serialize()

        actions = [parser.OFPActionOutput(out_port)]
        datapath.send_packet_out(in_port=ofproto_v1_3.OFPP_ANY,
                                 actions=actions, data=p.data)
