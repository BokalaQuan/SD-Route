
ADD_PORT = 0
DELETE_PORT = 1
class SwitchPortSelector(object):

    def __init__(self, link_table):
        self.link_table = link_table
        self.need_monitor_ports = []
        pass
    
    def select_need_monitor_ports(self):
        # print ('select need monitor ports!')
        for src_dpid,dst_dpid in self.link_table.iterkeys():
            links = self.link_table[(src_dpid,dst_dpid)]
            for link in links.values():
                src_port_no = link.src.port_no
                src_port_dpid = link.src.dpid
                src_port_datapath = link.src.datapath
                need_monitor_src_port = (src_port_dpid,src_port_no,src_port_datapath)
                self.need_monitor_ports.append(need_monitor_src_port)
                
                dst_port_no = link.dst.port_no
                dst_port_dpid = link.dst.dpid
                dst_port_datapath = link.dst.datapath
                need_monitor_dst_port = (dst_port_dpid,dst_port_no,dst_port_datapath)
                self.need_monitor_ports.append(need_monitor_dst_port)
                pass
            pass
        return self.need_monitor_ports
    
    def set_link_table(self, link_table):
        self.link_table = link_table
        pass
        
    def get_need_monitor_ports(self):
        return self.need_monitor_ports
    
    def update_need_monitor_ports(self, update_type, src_port, dst_port):
        src_port_dpid = src_port.dpid
        src_port_datapath = src_port.datapath
        src_port_no = src_port.port_no
        need_monitor_src_port = (src_port_dpid,src_port_no,src_port_datapath)
        
        dst_port_dpid = dst_port.dpid
        dst_port_datapath = dst_port.datapath
        dst_port_no = dst_port.port_no
        need_monitor_dst_port = (dst_port_dpid,dst_port_no,dst_port_datapath)
        
        if update_type == ADD_PORT:
            self.need_monitor_ports.append(need_monitor_src_port)
            self.need_monitor_ports.append(need_monitor_dst_port)
        else:
            self.need_monitor_ports.remove(need_monitor_src_port)
            self.need_monitor_ports.remove(need_monitor_dst_port)
        return self.need_monitor_ports
    
    pass
        