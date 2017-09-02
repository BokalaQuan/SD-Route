"""
This module is designed to tracking hosts.
The event EventHostState raised by this module
can be used as API.
"""
import time
import logging
import json

from collections import defaultdict
from webob import Response

from ryu.base import app_manager
from ryu.controller import event
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.ofproto import ether
from ryu.topology import api
from ryu.lib import hub
from ryu.lib.packet import (arp, ipv4, tcp, icmp, lldp)
from ryu.lib.dpid import dpid_to_str
from ryu.app.wsgi import ControllerBase, WSGIApplication, route


ETHERNET = ethernet.ethernet.__name__
ARP = arp.arp.__name__
IP = ipv4.ipv4.__name__
TCP = tcp.tcp.__name__
ICMP = icmp.icmp.__name__
LLDP = lldp.lldp.__name__

LOG = logging.getLogger(__name__)

host_track_instance_name = 'host_track_app'
rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})

# Times (in seconds) to use for different timeouts:
timeoutSec = dict(
    arpAware=10 * 2,  # Quiet ARP-responding entries are pinged after this
    arpSilent=10 * 20,  # This is for quiet entries not known to answer ARP
    arpReply=4,  # Time to wait for an ARP reply before retrial
    timerInterval=5,  # Seconds between timer routine activations
    entryMove=60  # Minimum expected time to move a physical entry
)

# Address to send ARP pings from.
# The particular one here is just an arbitrary locally administered address.
DEFAULT_ARP_PING_SRC_MAC = '02:00:00:00:be:ef'

ARP_PING_FLOW_PRIORITY = 300
GATEWAY_IP_LIST = ['10.0.0.201', '10.0.0.202', '10.0.0.203']
GATEWAY_MAC_DICT = {'10.0.0.201': 'c9:c9:c9:c9:c9:c9',
                    '10.0.0.202': 'ca:ca:ca:ca:ca:ca',
                    '10.0.0.203': 'cb:cb:cb:cb:cb:cb'}


class EventHostState(event.EventBase):
    def __init__(self, mac_to_port, entry, new_dpid=None, new_port=None,
                 join=False, leave=False, move=False):
        super(EventHostState, self).__init__()
        self.mac_to_port = mac_to_port
        self.entry = entry
        self.move = move
        self.leave = leave
        self.join = join
        assert sum(1 for x in [join, leave, move] if x) == 1

        # You can alter these and they'll change where we think it goes...
        self._new_dpid = new_dpid
        self._new_port = new_port

        # TODO: Allow us to cancel add/removes

    @property
    def new_dpid(self):
        """
        New DPID for move events"
        """
        assert self.move
        return self._new_dpid

    @property
    def new_port(self):
        """
        New port for move events"
        """
        assert self.move
        return self._new_port


class Alive(object):
    """
    Holds liveliness information for MAC and IP entries
    """

    def __init__(self, liveliness_interval=timeoutSec['arpSilent']):
        self.lastTimeSeen = time.time()
        self.interval = liveliness_interval

    def expired(self):
        return time.time() > self.lastTimeSeen + self.interval

    def refresh(self):
        self.lastTimeSeen = time.time()


class PingCtrl(Alive):
    """
    Holds information for handling ARP pings for hosts
    """
    # Number of ARP ping attempts before deciding it failed
    pingLim = 3

    def __init__(self):
        super(PingCtrl, self).__init__(timeoutSec['arpReply'])
        self.pending = 0

    def sent(self):
        self.refresh()
        self.pending += 1

    def failed(self):
        return self.pending > PingCtrl.pingLim

    def received(self):
        # Clear any pending timeouts related to ARP pings
        self.pending = 0


class IpEntry(Alive):
    """
    This entry keeps track of IP addresses seen from each MAC entry and will
    be kept in the macEntry object's ipaddrs dictionary. At least for now,
    there is no need to refer to the original macEntry as the code is organized.
    """

    def __init__(self, has_arp):
        if has_arp:
            super(IpEntry, self).__init__(timeoutSec['arpAware'])
        else:
            super(IpEntry, self).__init__(timeoutSec['arpSilent'])
        self.has_arp = has_arp
        self.pings = PingCtrl()

    def set_has_arp(self):
        if not self.has_arp:
            self.has_arp = True
            self.interval = timeoutSec['arpAware']


class MacEntry(Alive):
    """
    Not strictly an ARP entry.
    When it gets moved to Topology, may include other host info, like
    services, and it may replace dpid by a general switch object reference
    We use the port to determine which port to forward traffic out of.
    """

    def __init__(self, dpid, port, macaddr):
        super(MacEntry, self).__init__()
        self.dpid = dpid
        self.port = port
        self.macaddr = macaddr
        self.ipaddrs = {}

    def __str__(self):
        return ' '.join([dpid_to_str(self.dpid), str(self.port), str(self.macaddr)])

    def __eq__(self, other):
        if other is None:
            return False
        elif type(other) == tuple:
            return (self.dpid, self.port, self.macaddr) == other

        if self.dpid != other.dpid: return False
        if self.port != other.port: return False
        if self.macaddr != other.macaddr: return False
        if self.dpid != other.dpid: return False
        # What about ipaddrs??
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_dict(self):
        return {'dpid': self.dpid,
                'port': self.port,
                'mac addr': self.macaddr,
                'ip addr': self.ipaddrs.keys()}


class HostTrack(app_manager.RyuApp):
    _EVENTS = [EventHostState]
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, ping_src_mac=None, install_flow=True,
                 eat_packets=True, *args, **kwargs):
        super(HostTrack, self).__init__(*args, **kwargs)
        self.name = 'host_tracker'
        self.mac_to_port = defaultdict(lambda: defaultdict(lambda: None))  # {dpid:{mac:port}}
        self.datapaths = {}
        if ping_src_mac is None:
            ping_src_mac = DEFAULT_ARP_PING_SRC_MAC

        self.ping_src_mac = ping_src_mac
        self.install_flow = install_flow
        self.eat_packets = eat_packets

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(HostTrackRestController, {host_track_instance_name: self})

        # send the gateway found event to RouteManage
        # self.update_gateway_entry()

        # The following tables should go to Topology later
        self.entry_by_mac = {}
        self.timer_thread = hub.spawn(self._timer)

    # def update_gateway_entry(self):
    #     for gateway_ip,gateway_mac in GATEWAY_MAC_DICT.items():
    #         mac_entry = MacEntry(dpid=None, port=None, mac_addr=gateway_mac)
    #         mac_entry.ipaddrs[gateway_ip] = 0
    #         self.send_event_to_observers(EventHostState(mac_to_port=None, entry=mac_entry, join=True),
    #                                      MAIN_DISPATCHER)
    #     pass

    def _timer(self):
        while True:
            self._check_timeouts()
            hub.sleep(timeoutSec['timerInterval'])

    def get_mac_entry(self, macaddr):
        try:
            result = self.entry_by_mac[macaddr]
        except KeyError as e:
            result = None
        return result

    def send_ping(self, mac_entry, ipaddr):
        """
        Builds an ETH/IP any-to-any ARP packet (an "ARP ping")
        """
        r = packet.Packet()
        r.add_protocol(ethernet.ethernet(ethertype=ether.ETH_TYPE_ARP,
                                         dst=mac_entry.macaddr,
                                         src=self.ping_src_mac))
        r.add_protocol(arp.arp(opcode=arp.ARP_REQUEST,
                               src_mac=self.ping_src_mac,
                               dst_mac=mac_entry.macaddr,
                               dst_ip=ipaddr))
        r.serialize()

        self.logger.debug("%i %i sending ARP REQ to %s %s",
                          mac_entry.dpid, mac_entry.port, mac_entry.macaddr, ipaddr)
        data = r.data
        datapath = self.datapaths[mac_entry.dpid]
        if datapath is None:
            self.logger.debug("%i %i ERROR sending ARP REQ to %s %s",
                              mac_entry.dpid, mac_entry.port, mac_entry.macaddr, ipaddr)
            del mac_entry.ipaddrs[ipaddr]
        else:
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            actions = [parser.OFPActionOutput(mac_entry.port)]
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=ofproto.OFPP_CONTROLLER,
                                      actions=actions,
                                      data=data)
            datapath.send_msg(out)
        return

    def get_src_ip_and_arp(self, header_list):
        """
        Gets source IPv4 address for packets that have one (IPv4 and ARP)
        
        Returns (ip_address, has_arp).  If no IP, returns (None, False).
        """
        if IP in header_list:
            src_ip = header_list[IP].src
            dst_ip = header_list[IP].dst
            self.logger.debug("IP %s => %s", src_ip, dst_ip)
            return src_ip, False
        elif ARP in header_list:
            src_ip = header_list[ARP].src_ip
            dst_ip = header_list[ARP].dst_ip
            self.logger.debug("ARP %s => %s",
                              src_ip, dst_ip)
            return src_ip, True
        return None, False

    def update_ip_info(self, pkt_ip_src, mac_entry, has_arp):
        """
        Update given MacEntry
        
        If there is IP info in the incoming packet, update the macEntry
        accordingly. In the past we assumed a 1:1 mapping between MAC and IP
        addresses, but removed that restriction later to accommodate cases
        like virtual interfaces (1:n) and distributed packet rewriting (n:1)
        """
        if pkt_ip_src in mac_entry.ipaddrs:
            # that entry already has that IP
            ip_entry = mac_entry.ipaddrs[pkt_ip_src]
            ip_entry.refresh()
            self.logger.debug("%s already has IP %s, refreshing",
                              str(mac_entry), str(pkt_ip_src))
        else:
            # new mapping
            ip_entry = IpEntry(has_arp)
            mac_entry.ipaddrs[pkt_ip_src] = ip_entry
            self.logger.debug("Learned %s got IP %s", str(mac_entry), str(pkt_ip_src))
        if has_arp:
            ip_entry.pings.received()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def arp_response_flow_entry(self, ev):
        if not self.install_flow: return
        self.logger.debug("Installing flow for ARP ping responses")
        datapath = ev.msg.datapath
        dpid = datapath.id
        self.datapaths[dpid] = datapath
        self.mac_to_port.setdefault(dpid, {})
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_type=ether.ETH_TYPE_ARP,
                                eth_dst=self.ping_src_mac)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=0,
                                priority=ARP_PING_FLOW_PRIORITY,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        Populate MAC and IP tables based on incoming packets.
        
        Handles only packets from ports identified as not switch-only.
        If a MAC was not seen before, insert it in the MAC table;
        otherwise, update table and entry.
        If packet has a source IP, update that info for the macEntry (may require
        removing the info from another entry previously with that IP address).
        It does not forward any packets, just extract info from them.
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        if in_port > ofproto.OFPP_MAX:
            # ignore reserve port
            return
        dpid = datapath.id
        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst_mac = eth.dst
        src_mac = eth.src

        header_list = dict(
            (p.protocol_name, p) for p in pkt.protocols if type(p) != str)

        # if the in_port is the port between switches:return
        link_list = api.get_all_link(self)
        for index, link in enumerate(link_list):
            if dpid == link.src.dpid:
                if in_port == link.src.port_no:
                    return
            elif dpid == link.dst.dpid:
                if in_port == link.dst.port_no:
                    return
        # if the packet is LLDP:return         
        if LLDP in header_list:
            return

        self.logger.debug("PacketIn: %i %i ETH %s => %s",
                          dpid, in_port, src_mac, dst_mac)

        # Learn or update dpid/port/MAC info
        mac_entry = self.get_mac_entry(src_mac)

        if mac_entry is None:
            # there is no known host by that MAC
            # should we raise a NewHostFound event (at the end)?
            mac_entry = MacEntry(dpid, in_port, src_mac)
            self.mac_to_port[dpid][src_mac] = in_port
            self.entry_by_mac[src_mac] = mac_entry
            self.logger.info("Learned %s", str(mac_entry))
            self.send_event_to_observers(EventHostState(self.mac_to_port, mac_entry, join=True), MAIN_DISPATCHER)
        elif mac_entry != (dpid, in_port, src_mac):
            # there is already an entry of host with that MAC, but host has moved
            # should we raise a HostMoved event (at the end)?
            self.logger.info("Learned %s moved to %i %i", str(mac_entry), dpid, in_port)
            # if there has not been long since heard from it...
            if time.time() - mac_entry.lastTimeSeen < timeoutSec['entryMove']:
                self.logger.warning("Possible duplicate: %s at time %i, now (%i %i), time %i",
                                    str(mac_entry), mac_entry.lastTimeSeen,
                                    dpid, in_port, time.time())
            # should we create a whole new entry, or keep the previous host info?
            # for now, we keep it: IP info, answers pings, etc.
            del self.mac_to_port[mac_entry.dpid][src_mac]
            self.mac_to_port[dpid][src_mac] = in_port
            e = EventHostState(self.mac_to_port, mac_entry, move=True, new_dpid=dpid, new_port=in_port)
            self.send_event_to_observers(e)
            mac_entry.dpid = e._new_dpid
            mac_entry.inport = e._new_port
        mac_entry.refresh()

        pkt_ip_src, has_arp = self.get_src_ip_and_arp(header_list)
        if pkt_ip_src is not None:
            self.update_ip_info(pkt_ip_src, mac_entry, has_arp)

        if self.eat_packets and dst_mac == self.ping_src_mac:
            pass  # RYU do not support Event Halt

    def _check_timeouts(self):
        """
        Checks for timed out entries
        """
        for mac_entry in self.entry_by_mac.values():
            entry_pinged = False
            for ip_addr, ip_entry in mac_entry.ipaddrs.items():
                if ip_entry.expired():
                    if ip_entry.pings.failed():
                        del mac_entry.ipaddrs[ip_addr]
                        self.logger.info("Entry %s: IP address %s expired",
                                         str(mac_entry), str(ip_addr))
                    else:
                        self.send_ping(mac_entry, ip_addr)
                        ip_entry.pings.sent()
                        entry_pinged = True
            if mac_entry.expired() and not entry_pinged:
                self.logger.info("Entry %s expired", str(mac_entry))
                # sanity check: there should be no IP addresses left
                if len(mac_entry.ipaddrs) > 0:
                    for ip in mac_entry.ipaddrs.keys():
                        self.logger.warning("Entry %s expired but still had IP address %s",
                                            str(mac_entry), str(ip_addr))
                        del mac_entry.ipaddrs[ip_addr]
                del self.mac_to_port[mac_entry.dpid][mac_entry.macaddr]
                self.send_event_to_observers(EventHostState(self.mac_to_port, mac_entry, leave=True))
                del self.entry_by_mac[mac_entry.macaddr]


class HostTrackRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(HostTrackRestController, self).__init__(req, link, data, **config)
        self.host_track_instance = data[host_track_instance_name]

    @route('hosttrack', '/hosttrack/hostentry', methods=['GET'])
    def get_host_entry(self, req, **kwargs):
        entry_by_mac = self.host_track_instance.entry_by_mac
        if not len(entry_by_mac) == 0:
            entry_json = [{mac: entry.to_dict()}
                          for (mac, entry) in entry_by_mac.items()]
            body = json.dumps(entry_json)
        else:
            body = rest_body_none
        return Response(content_type='application/json', body=body)
