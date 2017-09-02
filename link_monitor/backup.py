

"""

"""
from operator import attrgetter
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from collections import defaultdict
from ryu.lib.dpid import dpid_to_str
import copy

global port_rest
port_rest = defaultdict(lambda:defaultdict(lambda:[])) 

class LinkMonitor(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(LinkMonitor, self).__init__(*args, **kwargs)
        self.name = 'LinkMonitor' 
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.port_state = defaultdict(lambda:defaultdict(lambda:{}))
        self.link_state = defaultdict(lambda:defaultdict(lambda:{}))
        
        
    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        print ('state of switch:  ',datapath.address, ' change!')
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
                
    def _monitor(self):
        print('start monitor!')
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10000)
            
    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)
        
#     @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
#     def _flow_stats_reply_handler(self, ev):
#         body = ev.msg.body
#         dpid = ev.msg.datapath.id 
#         if dpid not in self.flow_new:
#             self.flow_new[dpid] = [0,0]
#             self.flow_old[dpid] = [0,0]
# 
#         self.logger.info('---------------- -------- ------------------------- -------- --------')
#         self.logger.info( "datapath: %s ",dpid_to_str(ev.msg.datapath.id))
#         for stats in body:
#             if 'ipv4_dst' in stats.match  :
#                 if stats.match['ipv4_dst']== '192.168.1.101' :
#                     self.flow_new[dpid][0] = stats.duration_sec
#                     self.flow_new[dpid][1] = stats.byte_count
#                     speed = ((self.flow_new[dpid][1]-self.flow_old[dpid][1])/(self.flow_new[dpid][0]-self.flow_old[dpid][0]))/1000
#                     self.flow_old[dpid][0] = stats.duration_sec
#                     self.flow_old[dpid][1] = stats.byte_count      
            
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id 
        if dpid not in self.port_state :
            for stats in sorted(body, key=attrgetter('port_no')):
                port = stats.port_no
                self.port_state[dpid][port] = {
                                         'rx_packets': 0,'tx_packets': 0,
                                         'rx_bytes': 0,'tx_bytes': 0,
                                         'rx_dropped': 0,'tx_dropped': 0,
                                         'rx_errors': 0,'tx_errors': 0,
                                         'rx_frame_err': 0,'rx_over_err': 0,
                                         'rx_crc_err': 0,'collisions': 0,
                                         'duration_sec': 0,'duration_nsec':0}
                        
        for stats in sorted(body, key=attrgetter('port_no')):
            port = stats.port_no
            
            Error_packet = (stats.tx_errors+stats.rx_errors)-(self.port_state[dpid][port]['tx_errors']+self.port_state[dpid][port]['rx_errors'])
            Totle_packet = (stats.tx_packets+stats.rx_packets)-(self.port_state[dpid][port]['rx_packets']+self.port_state[dpid][port]['tx_packets'])
            
            if Error_packet != 0:
                self.link_state[dpid][port]["Error packet rate"] = (Error_packet/Totle_packet)*100  
            else:
                self.link_state[dpid][port]["Error packet rate"] = 0
            
            Bytes = (stats.tx_bytes+stats.rx_bytes)-(self.port_state[dpid][port]['tx_bytes']+self.port_state[dpid][port]['rx_bytes'])
            Time = stats.duration_sec - self.port_state[dpid][port]['duration_sec']
            if Bytes != 0 and Time != 0:
                Speed = Bytes/Time
            else:
                Speed = 0
            self.link_state[dpid][port]['Speed'] = Speed

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
                                         'duration_nsec': stats.duration_nsec}
            
    
    def get_state(self):
        global link
        link = copy.deepcopy(self.link_state)
        return link

            