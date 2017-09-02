import logging
import json
import time
import datetime

from threading import Thread
from webob import Response

from ryu.base import app_manager
from ryu.controller import event
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.lib import hub
from ryu.lib import mac
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import arp, ipv4

from lib.project_lib import enum
from host_manage.HostTrack import DEFAULT_ARP_PING_SRC_MAC


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

proxy_arp_instance_name = 'proxy_arp_app'
rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})

ARP_FLOW_PRIORITY = 200

ARP_TABLE_GC_INTERVAL = 60
ARP_ENTRY_TIMEOUT = 1200
# ARP_ENTRY_DELETE = 30

ARP_FLOOD_TIMES_CONTROL = 5
ARP_FLOOD_CONTROL_TIMEOUT = 10

GATEWAY_IP_LIST = ['10.0.0.201', '10.0.0.202', '10.0.0.203']
GATEWAY_MAC_DICT = {'10.0.0.201': 'c9:c9:c9:c9:c9:c9',
                    '10.0.0.202': 'ca:ca:ca:ca:ca:ca',
                    '10.0.0.203': 'cb:cb:cb:cb:cb:cb'}


class EventProxyArpTableUpdate(event.EventBase):
    def __init__(self, msg):
        super(EventProxyArpTableUpdate, self).__init__()
        self.msg = msg


class ProxyArp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _EVENTS = [EventProxyArpTableUpdate]

    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, install_flow=True, *args, **kwargs):
        super(ProxyArp, self).__init__(*args, **kwargs)
        self.name = 'proxy_arp'

        # host mac addr to port
        # {dpid: {mac: port}}
        self.mac_to_port = {}

        # port block list
        # {(dpid, eth_src, dst_ip): [in_port, flood_times, timestamp]}
        self.port_block_list = {}

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(ProxyArpRestController, {proxy_arp_instance_name: self})

        # arp table
        # {ip: mac}
        self.queue = hub.Queue()
        self.arp_table = ARPTable()

        # install flow for arp packet
        self.install_flow = install_flow

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def arp_table_miss_flow_entry(self, ev):
        if not self.install_flow: return
        self.logger.debug("Installing flow for ARP packet")
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_type=ether.ETH_TYPE_ARP)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=0,
                                priority=ARP_FLOW_PRIORITY,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        pkt = packet.Packet(msg.data)

        for p in pkt.protocols:
            if isinstance(p, arp.arp):
                self.handle_arp(msg, pkt, p)
            # elif isinstance(p, ndp):
            #     self.handle_ndp
            elif isinstance(p, ipv4.ipv4):
                self.handle_ip(msg, pkt, p)
            else:
                pass

    def handle_arp(self, msg, pkt, arp_pkt):
        dpid = msg.datapath.id
        eth_layer = self.parse_packet(pkt, 'ethernet')
        eth_src = eth_layer.src
        eth_dst = eth_layer.dst
        mac_learning = arp_pkt.src_mac
        ip_learning = arp_pkt.src_ip
        in_port = msg.match['in_port']

        # ignore arp ping from module HostTrack
        if eth_src == DEFAULT_ARP_PING_SRC_MAC:
            return
        elif eth_dst == DEFAULT_ARP_PING_SRC_MAC:
            self.add_to_queue((ip_learning, mac_learning))
            self.trigger_update()
            return

        # update arp table by src host info
        self.add_to_queue((ip_learning, mac_learning))
        self.trigger_update()

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth_src] = in_port

        if arp_pkt.opcode == arp.ARP_REQUEST:
            logger.debug("[request]packet in dpid=%s %s %s in_port=%s",
                         dpid, eth_src, eth_dst, in_port)
            self.handle_arp_request(msg, pkt, arp_pkt, eth_layer)
        elif arp_pkt.opcode == arp.ARP_REPLY:
            logger.debug("[reply]packet in dpid=%s %s %s in_port=%s",
                         dpid, eth_src, eth_dst, in_port)
            self.handle_arp_reply(msg, pkt, arp_pkt, eth_layer)
        else:
            return

    def handle_arp_request(self, msg, pkt, arp_pkt, eth_pkt):
        dp = msg.datapath
        dpid = dp.id

        eth_src = eth_pkt.src
        eth_dst = eth_pkt.dst
        ip_src = arp_pkt.src_ip
        ip_dst = arp_pkt.dst_ip

        in_port = msg.match['in_port']

        # TODO: external host arp request

        # handle unicast arp request
        if eth_dst != mac.BROADCAST_STR:
            if eth_src in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][eth_src]
                self.proxy_arp_reply(datapath=dp, eth_src=eth_dst, eth_dst=eth_src,
                                     ip_src=ip_dst, ip_dst=ip_src, out_port=out_port)
                logger.debug("[unicast request]arp reply: %s to %s", ip_dst, ip_src)
                return
            else:
                logger.debug("[unicast request]could not find out_port")
                pass

        # handle broadcast arp request
        if ip_dst in GATEWAY_IP_LIST:
            eth_dst_lookup = GATEWAY_MAC_DICT[ip_dst]
        else:
            # look up arp_table for host mac.
            eth_dst_lookup = self.arp_table.get_mac(ip_dst)

        if eth_dst_lookup:
            if eth_src in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][eth_src]
                self.proxy_arp_reply(datapath=dp, eth_src=eth_dst_lookup, eth_dst=eth_src,
                                     ip_src=ip_dst, ip_dst=ip_src, out_port=out_port)
                logger.debug("[broadcast request]arp reply: %s to %s", ip_dst, ip_src)
                return
            else:
                logger.debug("[broadcast request]could not find out_port")
                pass

        # when request couldn't be resolved.
        self.flooding_strategy(msg, eth_src, ip_dst, in_port)

    def flooding_strategy(self, msg, eth_src, ip_dst, in_port):
        """
            use All-Path bridging, choose one port as the only arp request in_port.
        """
        dp = msg.datapath
        dpid = dp.id

        if (dpid, eth_src, ip_dst) in self.port_block_list:
            port, flood_times, timestamp = self.port_block_list[(dpid, eth_src, ip_dst)]
            if time.time()-timestamp > ARP_FLOOD_CONTROL_TIMEOUT:
                # TODO: expired by timer
                del self.port_block_list[(dpid, eth_src, ip_dst)]
                logger.debug("[All-Path bridging]port_block_list entry expired")
                return
            if port != in_port:
                # drop duplicated arp request.
                self._drop(dp, in_port)
                logger.debug("[All-Path bridging]drop arp request from dpid:%s port:%s", dpid, in_port)
            else:
                # flood times control, avoid too much flood.
                if flood_times < ARP_FLOOD_TIMES_CONTROL:
                    self._flood(dp, msg, in_port)
                    self.port_block_list[(dpid, eth_src, ip_dst)][1] += 1
                    logger.debug("[All-Path bridging]controlled flood")
                else:
                    logger.debug("[All-Path bridging]too much request, ignored")
                    pass
        else:
            # create port block list entry and flood the pkt.
            self.port_block_list[(dpid, eth_src, ip_dst)] = [in_port, 1, time.time()]
            self._flood(dp, msg, in_port)
            logger.debug("[All-Path bridging]controlled flood")

    def handle_arp_reply(self, msg, pkt, arp_pkt, eth_pkt):
        pass

    def handle_ip(self, msg, pkt, ip_pkt):
        pass

    @staticmethod
    def proxy_arp_reply(datapath, eth_src, eth_dst, ip_src, ip_dst, out_port):
        parser = datapath.ofproto_parser

        arp_reply = packet.Packet()
        arp_reply.add_protocol(ethernet.ethernet(
            dst=eth_dst, src=eth_src,
            ethertype=ether.ETH_TYPE_ARP))

        arp_reply.add_protocol(arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac=eth_src, src_ip=ip_src,
            dst_mac=eth_dst, dst_ip=ip_dst))

        arp_reply.serialize()

        actions = [parser.OFPActionOutput(out_port)]

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=datapath.ofproto.OFPP_CONTROLLER,
            actions=actions, data=arp_reply.data)

        datapath.send_msg(out)

    @staticmethod
    def _add_flow(datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=5, hard_timeout=15,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @staticmethod
    def _flood(datapath, msg, in_port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @staticmethod
    def _drop(datapath, in_port):
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=[], data=None)

        datapath.send_msg(out)

    @staticmethod
    def parse_packet(pkt, target):
        """
            try to extract the packet and find for specific protocol.
        """
        for pkt in pkt.protocols:
            try:
                if pkt.protocol_name == target:
                    return pkt
            except AttributeError:
                pass
        return None

    def process_queued_msg(self):
        """
            try to process all the queued routing information.
        """
        try:
            while not self.queue.empty():
                arp_src_ip, eth_src = self.queue.get()
                self.arp_table.update_entry(arp_src_ip, eth_src)
        except:
            pass

    def add_to_queue(self, msg):
        """
            a interface to add a object into queue.
        """
        if not self.queue.full():
            self.queue.put(msg)

    def trigger_update(self):
        """
            create a thread to update the routing table.
        """
        update_thread = Thread(target=self.process_queued_msg)
        update_thread.setDaemon(True)
        update_thread.start()


class ProxyArpRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(ProxyArpRestController, self).__init__(req, link, data, **config)
        self.proxy_arp_instance = data[proxy_arp_instance_name]

    @route('proxyarp', '/proxyarp/arptable', methods=['GET'])
    def get_arp_table(self, req, **kwargs):
        body = json.dumps(self.proxy_arp_instance.arp_table.to_dict())
        return Response(content_type='application/json', body=body)


class ARPTable(dict):
    def __init__(self):
        if not hasattr(self, 'expire_time'):
            super(ARPTable, self).__init__()

            self.gc_interval = ARP_TABLE_GC_INTERVAL
            self.expire_time = ARP_ENTRY_TIMEOUT

            self._init_thread()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(ARPTable, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def _init_thread(self):
        """
            create a thread to check arp entry validation.
        """
        logger.info('garbage collector thread start with interval %ds', self.gc_interval)
        gc_thread = Thread(target=self._garbage_collect)
        gc_thread.setDaemon(True)
        gc_thread.start()

    def _garbage_collect(self):
        """
            iterate the whole arp table.
            deprecate TIMEOUT entries and delete DEL entries.
        """
        while True:
            now_time = time.time()
            valid_time = now_time - self.expire_time
            logger.debug('[ARP Table]garbage collecting.')

            for ip, entry in self.items():
                if entry.state == entry.StateEnum.LIVE:
                    if entry.timestamp < valid_time:
                        entry.state = entry.StateEnum.TIMEOUT
                elif entry.state == entry.StateEnum.TIMEOUT:
                    if entry.timestamp < now_time:
                        # entry.state = entry.StateEnum.DEL
                        del self[ip]

            time.sleep(self.gc_interval)

    def update_entry(self, ip, mac):
        """
            update arp table entry.
        """
        try:
            entry = self[ip]
            entry.mac = mac
            entry.timestamp = time.time()
            entry.state = entry.StateEnum.LIVE
        except KeyError:
            self[ip] = ARPEntry(mac)

    def get_mac(self, ip):
        """
            get mac from arp table by ip
        """
        if ip in self:
            rval = self[ip]
            if rval.state == rval.StateEnum.LIVE:
                return rval.mac
        return None

    def to_dict(self):
        r = [{'ip': ip, "arp_entry": arp_entry.to_dict()} for (ip, arp_entry) in self.items()]
        return r


class ARPEntry(object):
    StateEnum = enum(LIVE='live', TIMEOUT='timeout', DEL='delete')

    def __init__(self, mac):
        self.mac = mac
        self.timestamp = time.time()
        self.state = self.StateEnum.LIVE

    def to_dict(self):
        r = {'mac': self.mac,
             'update_time': datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
             'state': self.state}

        return r
