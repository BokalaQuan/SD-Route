from ryu.lib import hub

OFP_FLOW_STATS_REQUEST = 1
OFP_PORT_STATS_REQUEST = 2
OFP_QUEUE_STATS_REQUEST = 3
OFP_GROUP_STATS_REQUEST = 4
OFP_METER_STATS_REQUEST = 5

class MonitorScheduler(object):

    def __init__(self, need_monitor_ports):
        self.need_monitor_ports = need_monitor_ports
        pass
    
    def set_need_monitor_ports(self, need_monitor_ports):
        self.need_monitor_ports = need_monitor_ports
        pass
    
    
    def send_request(self, stats_request_type, need_monitor_ports):
        # print ('send request!')
        if OFP_PORT_STATS_REQUEST in stats_request_type:
            for each_port in need_monitor_ports:
                datapath = each_port[2]
                port_no = each_port[1]
                self.start_request_port(datapath, port_no)
                pass
            pass
        
        pass
        
    def start_request_port(self, datapath, port_no):
        parser = datapath.ofproto_parser
        port_request = parser.OFPPortStatsRequest(datapath, 0, port_no)
        datapath.send_msg(port_request)
        pass
    pass

    
class PollingScheduler(MonitorScheduler):
    def __init__(self,poll_interval, need_monitor_ports):
        super(PollingScheduler, self).__init__(need_monitor_ports)
#         MonitorScheduler.__init__(need_monitor_ports)
        self.poll_interval = poll_interval
        pass
        
    def start_monitor_band(self, stats_request_type):
        # print ('start monitor!')
        hub.spawn(self.start_poll_monitor(stats_request_type))
        pass
    
    
    def start_poll_monitor(self, stats_request_type):
        while True:
            self.send_request(stats_request_type, self.need_monitor_ports)
            hub.sleep(self.poll_interval)
        pass
        
    
