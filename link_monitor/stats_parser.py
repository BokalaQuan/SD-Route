from operator import attrgetter
from collections import defaultdict

class StateParser(object):

    def __init__(self):
        self.port_state = defaultdict(lambda:defaultdict(lambda:{}))
        self.link_state = defaultdict(lambda:defaultdict(lambda:{}))
        pass
    
    
    def parse_port_stats_reply(self, ev):
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
                                         'duration_sec': 0, 'duration_nsec':0}
                        
        for stats in sorted(body, key=attrgetter('port_no')):
            port = stats.port_no
            
            error_packet = (stats.tx_errors + stats.rx_errors) - (self.port_state[dpid][port]['tx_errors'] + self.port_state[dpid][port]['rx_errors'])
            totle_packet = (stats.tx_packets + stats.rx_packets) - (self.port_state[dpid][port]['rx_packets'] + self.port_state[dpid][port]['tx_packets'])
            
            if error_packet != 0:
                self.link_state[dpid][port]["Error packet rate"] = (error_packet / totle_packet) * 100  
            else:
                self.link_state[dpid][port]["Error packet rate"] = 0
                pass
            
            Bytes = (stats.tx_bytes + stats.rx_bytes) - (self.port_state[dpid][port]['tx_bytes'] + self.port_state[dpid][port]['rx_bytes'])
            Time = stats.duration_sec - self.port_state[dpid][port]['duration_sec']
            if Bytes != 0 and Time != 0:
                Speed = Bytes / Time
            else:
                Speed = 0
                pass
            self.link_state[dpid][port]['Speed'] = Speed
            
            print 'dpid: ', dpid,  ' port_no: ',port, ' used band is: ', Speed

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
            pass
        return self.port_state, self.link_state
