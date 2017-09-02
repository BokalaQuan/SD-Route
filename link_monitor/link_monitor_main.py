import time
import logging

from operator import attrgetter
from collections import defaultdict
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import (packet, ethernet, icmp, ipv4)
from ryu.ofproto import ether
from ryu.lib import hub

from monitor_scheduler import PollingScheduler
from stats_parser import StateParser
from switch_port_selector import SwitchPortSelector
from topology_manage.object.link import Link, LinkTable, LinkTableApi
from web_service import ws_event
from lib.project_lib import Bytes


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

OFP_FLOW_STATS_REQUEST = 1
OFP_PORT_STATS_REQUEST = 2
OFP_QUEUE_STATS_REQUEST = 3
OFP_GROUP_STATS_REQUEST = 4
OFP_METER_STATS_REQUEST = 5

SPECIAL_SRC_MAC = 'dd:dd:dd:dd:dd:dd'
SPECIAL_DST_MAC = 'ee:ee:ee:ee:ee:ee'
SPECIAL_COOKIE = 123654
SPECIAL_DPID_PORT_NO = '00_00'
MIN_DELAY = 0.000100
POLL_INTERVAL = 2 # seconds, should be larger than 1 second

global_link_table = LinkTableApi()
global_number = False


class LinkMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # _EVENTS = [topo_event.EventLinkAdd, topo_event.EventTopoInitializeEnd,
    #            ofp_event.EventOFPPortStatsReply]

    def __init__(self, *args, **kwargs):
        super(LinkMonitor, self).__init__(*args, **kwargs)
        self.name = 'LinkMonitor'
        self.port_state = defaultdict(lambda: defaultdict(lambda: {}))
        self.link_state = defaultdict(lambda: defaultdict(lambda: {}))
        self.datapaths = {}
        self.controller_to_switch_delay = {}
        self.controller_to_switch_send_time = {}
        self.poll_interval = POLL_INTERVAL
        self.stats_parser = StateParser()
        hub.spawn_after(60,self.change_number)
        # hub.spawn_after(8, self.test_handle_topo_initialize_end)
        pass

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    # This method is using!
    # @set_ev_cls(topo_event.EventTopoInitializeEnd, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER,MAIN_DISPATCHER])
    def topo_initialize_end_handler(self, ev):
        # print 'receive topo initialize end event!!!!!!!! link_table is: ', ev.link_table

        global global_link_table
        link_table = ev.link_table
        global_link_table = link_table
        self.link_table = link_table
        self.stats_request_type = self.select_request_type()

        self.switch_port_selctor = SwitchPortSelector(link_table)
        self.need_monitor_ports = self.switch_port_selctor.select_need_monitor_ports()

        self.monitor_scheduler_obj = PollingScheduler(self.poll_interval, self.need_monitor_ports)
        self.monitor_scheduler_obj.start_monitor_band(self.stats_request_type)
        hub.spawn_after(30,self.change_number)
        pass

    def change_number(self):
        global global_number
        global_number = True

    def send_controller_to_switch_packet_out(self, port):
        datapath = port.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        print 'actions: ', actions

        special_src_mac = 'dd:dd:dd:dd:dd:dd'
        special_dst_mac = 'ee:ee:ee:ee:ee:ee'
        src_mac_addr = special_src_mac
        dst_mac_addr = special_dst_mac
        p = packet.Packet()

        e = ethernet.ethernet(dst=dst_mac_addr,
                              src=src_mac_addr, ethertype=ether.ETH_TYPE_IP)
        p.add_protocol(e)

        i = ipv4.ipv4(src='0.0.0.0', dst='0.0.0.1')
        p.add_protocol(i)

        src_port_index = str(port.dpid) + '_' + str(port.port_no)
        dst_port_index = SPECIAL_DPID_PORT_NO
        send_time = str("%.6f" % time.time())
        add_data = ',' + src_port_index + ',' + dst_port_index + ',' + send_time + ','
        icmp_data = icmp.TimeExceeded(data_len=len(add_data),
                                      data=add_data)
        ic = icmp.icmp(data=icmp_data)
        p.add_protocol(ic)

        p.serialize()
        datapath.send_packet_out(in_port=ofproto.OFPP_CONTROLLER,
                                 actions=actions, data=p.data)
        self.controller_to_switch_send_time[datapath.id] = float(time.time())
        print ('send packet out!!!!!!!!!!!!!!!!!!!!!!!!! Now the time is: ',
               self.controller_to_switch_send_time[datapath.id])
        pass

    def send_switch_to_switch_packet_out(self, port, link):
        datapath = port.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        # actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        actions = [ofp_parser.OFPActionOutput(1)]
        print 'actions: ', actions

        special_src_mac = 'dd:dd:dd:dd:dd:dd'
        special_dst_mac = 'ee:ee:ee:ee:ee:ee'
        src_mac_addr = special_src_mac
        dst_mac_addr = special_dst_mac
        p = packet.Packet()

        e = ethernet.ethernet(dst=dst_mac_addr,
                              src=src_mac_addr, ethertype=ether.ETH_TYPE_IP)
        p.add_protocol(e)

        i = ipv4.ipv4(src='0.0.0.0', dst='0.0.0.2')
        p.add_protocol(i)

        src_port_index = str(link.src.dpid) + '_' + str(link.src.port_no)
        dst_port_index = str(link.dst.dpid) + '_' + str(link.dst.port_no)
        send_time = str("%.6f" % time.time())
        add_data = ',' + src_port_index + ',' + dst_port_index + ',' + send_time + ','
        icmp_data = icmp.TimeExceeded(data_len=len(add_data),
                                      data=add_data)
        ic = icmp.icmp(data=icmp_data)
        p.add_protocol(ic)

        p.serialize()
        datapath.send_packet_out(in_port=ofproto.OFPP_CONTROLLER,
                                 actions=actions, data=p.data)
        print ('send packet out!!!!!!!!!!!!!!!!!!!!!!!!! Now the time is: ', time.time())
        pass

    def add_switch_to_controller_flow(self, port):
        special_src_mac = 'dd:dd:dd:dd:dd:dd'
        special_dst_mac = 'ee:ee:ee:ee:ee:ee'
        datapath = port.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]

        # install a flow to avoid packet_in next time
        match = ofp_parser.OFPMatch(eth_dst=special_dst_mac, eth_src=special_src_mac)
        self.add_flow(datapath, 1, match, actions)
        pass

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(cookie=1, datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    def select_request_type(self):
        # print ('select request type!!')
        logger.info('start link monitor!')
        stats_request_type = [OFP_FLOW_STATS_REQUEST, OFP_PORT_STATS_REQUEST]
        return stats_request_type

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, [CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _port_stats_reply_handler(self, ev):
#         print('handle port_stats_reply!')
#         global global_link_table
        self.parse_port_stats_reply(ev)
        pass

    def parse_port_stats_reply(self, ev):
        global global_number
        current_time = time.time()
#         print 'current_time', current_time
        global global_link_table
        body = ev.msg.body
        dpid = ev.msg.datapath.id

        for stats in sorted(body, key=attrgetter('port_no')):
            port = stats.port_no
            contain_keys = self.port_state[dpid].keys()
            if dpid not in self.port_state or ((dpid in self.port_state) and (port not in contain_keys)):
                self.port_state[dpid][port] = {
                    'rx_packets': 0, 'tx_packets': 0,
                    'rx_bytes': 0, 'tx_bytes': 0,
                    'rx_dropped': 0, 'tx_dropped': 0,
                    'rx_errors': 0, 'tx_errors': 0,
                    'rx_frame_err': 0, 'rx_over_err': 0,
                    'rx_crc_err': 0, 'collisions': 0,
                    'duration_sec': 0, 'duration_nsec': 0,
                    'time': 0}

        for stats in sorted(body, key=attrgetter('port_no')):
            port_no = stats.port_no

            error_packet = (stats.tx_errors + stats.rx_errors) - (
                self.port_state[dpid][port_no]['tx_errors'] + self.port_state[dpid][port_no]['rx_errors'])
            totle_packet = (stats.tx_packets + stats.rx_packets) - (
                self.port_state[dpid][port_no]['rx_packets'] + self.port_state[dpid][port_no]['tx_packets'])

            if error_packet != 0:
                self.link_state[dpid][port_no]["Error packet rate"] = (error_packet / totle_packet) * 100
            else:
                self.link_state[dpid][port_no]["Error packet rate"] = 0
                pass

            receive_bytes = (stats.tx_bytes + stats.rx_bytes) - (
                self.port_state[dpid][port_no]['tx_bytes'] + self.port_state[dpid][port_no]['rx_bytes'])
#             print 'current_time', current_time
            last_time = self.port_state[dpid][port_no]['time']
#             print 'last_time', last_time
            time_interval = current_time - last_time
            if receive_bytes != 0 and time_interval != 0:
                used_band = receive_bytes / time_interval * Bytes
            else:
                used_band = 0
                pass
            self.link_state[dpid][port_no]['Speed'] = used_band

            global global_number
            for dpid_index in global_link_table.iterkeys():
                if dpid in dpid_index:
                    select_dpid_index = dpid_index
                    for port_no_index in global_link_table[select_dpid_index]:
                        if port_no in port_no_index:
                            if global_number:
                                if int(dpid)==int(128983237624):
#                                     print 'receive_bytes:', receive_bytes, 'time_interval', time_interval, ', used_band:', used_band
#                                     print 'dpid: ', dpid,', port_no: ', port_no, ', stats.tx_bytes: ', stats.tx_bytes, ', stats.rx_bytes', stats.rx_bytes
#                                     print 'dpid: ', dpid, ', tx_bytes in store data: ', self.port_state[dpid][port_no]['tx_bytes'], ', rx_bytes in store data: ', self.port_state[dpid][port_no]['rx_bytes']
                                    pass
                            select_port_index = port_no_index
                            # TODO: set link info before link monitor start
                            total_band = global_link_table[select_dpid_index][select_port_index].total_band
                            # total_band = 1024000
                            available_band = total_band - used_band
                            global_link_table[select_dpid_index][select_port_index].available_band = available_band
#                             print 'available_band', available_band, ' select_dpid_index ', select_dpid_index
                            
                            # send ws update band event
                            (current_dpid,next_dpid) = select_dpid_index
                            (current_port_no,next_port_no) = select_port_index
                            link_band = [current_dpid, current_port_no, next_dpid, next_port_no, available_band]
                            self.send_event_to_observers(ws_event.EventWebLinkBandChange(link_band))

            self.port_state[dpid][port] = {
                'rx_packets': stats.rx_packets,
                'tx_packets': stats.tx_packets,
                'rx_bytes': stats.rx_bytes,
                'tx_bytes': stats.tx_bytes,
                'rx_dropped': stats.rx_dropped,
                'tx_dropped': stats.tx_dropped,
                'rx_errors': stats.rx_errors,
                'tx_errors': stats.tx_errors,
                'rx_frame_err': stats.rx_frame_err,
                'rx_over_err': stats.rx_over_err,
                'rx_crc_err': stats.rx_crc_err,
                'collisions': stats.collisions,
                'duration_sec': stats.duration_sec,
                'duration_nsec': stats.duration_nsec,
                'time': current_time}
        return self.port_state, self.link_state


class Port(object):
    def __init__(self, datapath, dpid, port_no):
        self.datapath = datapath
        self.dpid = dpid
        self.port_no = port_no