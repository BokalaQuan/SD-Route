import time
import netaddr
import logging

from threading import Thread
from web_service import ws_event
from ryu.lib import ofctl_v1_3
from ryu.lib.dpid import dpid_to_str
from ryu.ofproto import ether

from base.parameters import BusinessType, DefaultBusinessType
from base.parameters import server_tcp_port, ROUTE_TASK_HANDLE_INTERVAL
from base.parameters import FLOW_IDLE_TIMEOUT, FLOW_HARD_TIMEOUT, ROUTE_FLOW_PRIORITY
from base.parameters import MULTICAST_FLOW_IDLE_TIMEOUT, MULTICAST_FLOW_HARD_TIMEOUT
from link_monitor import link_monitor_main
from fault_recovery import fault_recovery_main
# from route_manage.RouteManage import system_performance_logger

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


class RouteTaskHandler(list):
    """
        handle route task in queue with window ROUTE_TASK_HANDLE_INTERVAL.
        merge requests for performance improvement.
    """
    def __init__(self, route_manage):
        super(RouteTaskHandler, self).__init__()

        self.route_manage = route_manage
        self.rt_interval = ROUTE_TASK_HANDLE_INTERVAL

        self._init_thread()

    def _init_thread(self):
        """init RouteTaskHandler thread."""
        logger.info('route task handler thread start with interval %fs', self.rt_interval)
        gc_thread = Thread(target=self._handle_task)
        gc_thread.setDaemon(True)
        gc_thread.start()

    def _handle_task(self):
        """
            handle the whole task queue, calculate route and deploy flow table.
        """
        while True:
            now_time = time.time()
            for i in list(range(len(self))):
                # get next undo task.
                entry = self[0]

                if entry.timestamp < now_time:
                    if isinstance(entry, RouteTaskEntry) or \
                       isinstance(entry, NATRouteTaskEntry):
                        # handle unicast request task.
                        link_list, link_cost = entry.route_calc()
                        if link_list is None:
                            logger.error("route path calculate failed/ no path exist.")
                            break

                        entry.deploy_flow_table(link_list, link_cost)
                        # system_performance_logger.handle_req_finish(time.time())
                        '''
                        Fault recovery
                        '''

                        # Update the request information and its route path information for fault_recovery
                        # self.route_manage.route_info_maintainer.update(self.route_manage, fault_recovery_main,
                        #                                                entry, link_list)
                    elif isinstance(entry, MulticastTaskEntry):
                        # handle multicast request task.
                        link_list, link_cost = entry.route_calc()
                        if link_list is None:
                            break

                        entry.deploy_flow_table(link_list, link_cost)

                    # pop task when is done.
                    self.pop(0)
                else:
                    # when all task timeout done.
                    break

            time.sleep(self.rt_interval)

    def update_entry(self, task_entry):
        """update route task entry."""
        self.append(task_entry)


class TaskEntryBase(object):
    """
        task entry base class, all task entry inherited from here.
    """
    def __init__(self, route_type, src_dpid, src_ip, src_port_no,
                 dst_dpid, dst_ip, dst_port_no, route_manage):
        # value in checker should not be None
        checker = [route_type, src_dpid, src_ip, dst_dpid, dst_ip]
        assert sum(1 for i in checker if i is None) == 0

        self.route_type = route_type
        self.src_dpid = src_dpid
        self.src_ip = src_ip
        self.src_port_no = src_port_no
        self.dst_dpid = dst_dpid
        self.dst_ip = dst_ip
        self.dst_port_no = dst_port_no
        self.timestamp = time.time()
        self.route_manage = route_manage
        pass

    def __str__(self):
        logger.exception("task entry string unset.")
        return None

    # @system_performance_logger.timer
    def route_calc(self):
        """calculate route for unicast request.

        :return:
        """
        if self.src_dpid == self.dst_dpid:
            link_list = [self.src_dpid]
            link_cost = 0
            # self.request_cache[(src_ip, dst_ip)][1] = link_list
            logger.info("src:%s, dst:%s, both connect to dpid:%s",
                        self.src_ip, self.dst_ip, self.src_dpid)
        else:
            self.route_manage.algorithm.update_link_status(link_monitor_main.global_link_table)
            try:
                business_type = BusinessType[self.route_manage.servers[self.dst_ip]]
            except KeyError:
                business_type = BusinessType[DefaultBusinessType]
            self.route_manage.algorithm.run(self.src_dpid, self.dst_dpid, business_type)
            link_list, link_cost = self.route_manage.algorithm.get_link(self.src_dpid,
                                                                        self.dst_dpid)
            # self.request_cache[(src_ip, dst_ip)][1] = link_list
            logger.info("src:%s, dst:%s, deploy link:%s, link cost:%s",
                        self.src_ip, self.dst_ip, link_list, link_cost)
        return link_list, link_cost

    def deploy_flow_table(self, link_list, link_cost):
        """Deploy flow tables of switches in both way, from the end of link_list to the start

        :param link_list: path list from source to destination
        :param link_cost: path cost
        :return:
        """
        pass

    @staticmethod
    def flow_mod(datapath, src_ip, dst_ip, inport, outport):
        """deploy flow table

        :param datapath: switch datapath
        :param src_ip: source ip address for matching
        :param dst_ip: destination ip address for matching
        :param inport: data in port number for matching
        :param outport: data out port number
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP, in_port=inport,
                                ipv4_src=str(src_ip), ipv4_dst=str(dst_ip))

        actions = [parser.OFPActionOutput(outport)]

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=ROUTE_FLOW_PRIORITY,
                                idle_timeout=FLOW_IDLE_TIMEOUT,
                                hard_timeout=FLOW_HARD_TIMEOUT,
                                command=ofproto.OFPFC_ADD,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    def to_dict(self):
        pass


class RouteTaskEntry(TaskEntryBase):
    """data center inside route task entry

    :param route_type: ROUTE_TYPE_INTRA_TOPO
    :param src_dpid: source switch datapath id
    :param src_ip: source host ip address
    :param src_port_no: source switch port number
    :param dst_dpid: destination switch datapath id
    :param dst_ip: destination host ip address
    :param dst_port_no: destination switch port number
    """
    def __init__(self, route_type, src_dpid, src_ip, src_port_no,
                 dst_dpid, dst_ip, dst_port_no, route_manage):
        super(RouteTaskEntry, self).__init__(route_type, src_dpid, src_ip, src_port_no,
                                             dst_dpid, dst_ip, dst_port_no,
                                             route_manage)
        pass

    def __str__(self):
        return "RouteTaskEntry"

    def deploy_flow_table(self, link_list, link_cost):
        if len(link_list) == 1:
            dp = self.route_manage.switches.get_switch(link_list[0]).dp
            self.flow_mod(dp, self.dst_ip, self.src_ip, self.dst_port_no, self.src_port_no)
            self.flow_mod(dp, self.src_ip, self.dst_ip, self.src_port_no, self.dst_port_no)
            return True
        elif len(link_list) > 1:
            sw1 = self.route_manage.switches.get_switch(link_list[0])
            sw2 = self.route_manage.switches.get_switch(link_list[len(link_list) - 1])
            if len(link_list) == 2:
                self.flow_mod(sw2.dp, self.dst_ip, self.src_ip, self.dst_port_no, sw2.neighbors[sw1.dp.id][0])
                self.flow_mod(sw2.dp, self.src_ip, self.dst_ip, sw2.neighbors[sw1.dp.id][0], self.dst_port_no)
                self.flow_mod(sw1.dp, self.dst_ip, self.src_ip, sw1.neighbors[sw2.dp.id][0], self.src_port_no)
                self.flow_mod(sw1.dp, self.src_ip, self.dst_ip, self.src_port_no, sw1.neighbors[sw2.dp.id][0])
                return True
            else:
                links = []
                for num, dpid in enumerate(link_list):
                    sw = self.route_manage.switches.get_switch(dpid)
                    if num == 0:
                        self.flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                      self.src_port_no, sw.neighbors[link_list[num+1]][0])

                        second_dpid = link_list[num+1]
                        first_port_no = sw.neighbors[second_dpid][0]
                        second_sw = self.route_manage.switches.get_switch(second_dpid)
                        second_port_no = second_sw.neighbors[dpid][0]
                        first_link = [dpid_to_str(sw.dp.id), first_port_no,
                                      dpid_to_str(second_sw.dp.id), second_port_no]
                        links.append(first_link)
                        continue
                    if num == len(link_list) - 1:
                        self.flow_mod(sw.dp, self.dst_ip, self.src_ip,
                                      self.dst_port_no, sw.neighbors[link_list[num-1]][0])
                        continue
                    self.flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                  sw.neighbors[link_list[num-1]][0], sw.neighbors[link_list[num+1]][0])
                    self.flow_mod(sw.dp, self.dst_ip, self.src_ip,
                                  sw.neighbors[link_list[num+1]][0], sw.neighbors[link_list[num-1]][0])
                    # add ws_update event msg: middle links
                    current_dpid = dpid
                    next_dpid = link_list[num+1]
                    next_sw = self.route_manage.switches.get_switch(next_dpid)
                    current_port_no = sw.neighbors[next_dpid][0]
                    next_port_no = next_sw.neighbors[current_dpid][0]
                    current_link = [dpid_to_str(sw.dp.id), current_port_no,
                                    dpid_to_str(next_sw.dp.id), next_port_no]
                    links.append(current_link)

                # send GUI event
                if self.route_manage.algorithm_type == "GA":
                    self.route_manage.send_event_to_observers(ws_event.EventWebRouteSet(links))
                elif self.route_manage.algorithm_type == "Dij":
                    self.route_manage.send_event_to_observers(ws_event.EventWebRouteSetDij(links))
            self.flow_mod(sw2.dp, self.src_ip, self.dst_ip,
                          sw2.neighbors[link_list[len(link_list)-2]][0], self.dst_port_no)
            self.flow_mod(sw1.dp, self.dst_ip, self.src_ip,
                          sw1.neighbors[link_list[1]][0], self.src_port_no)
            return True
        else:
            logger.info("find path failed!")
            return False

    def to_dict(self):
        r = {'route_type': self.route_type,
             'src_dpid': self.src_dpid,
             'src_ip': self.src_ip,
             'src_port_no': self.src_port_no,
             'dst_dpid': self.dst_dpid,
             'dst_ip': self.dst_ip,
             'dst_port_no': self.dst_port_no}
        return r


class NATRouteTaskEntry(TaskEntryBase):
    def __init__(self, route_type, src_dpid, src_ip, src_port_no, dst_dpid, dst_ip, dst_port_no,
                 route_manage, gateway_ip, gateway_mac, server_mac, user_mac):
        super(NATRouteTaskEntry, self).__init__(route_type, src_dpid, src_ip, src_port_no,
                                                dst_dpid, dst_ip, dst_port_no,
                                                route_manage)
        self.gateway_ip = gateway_ip
        self.gateway_mac = gateway_mac
        self.server_mac = server_mac
        self.user_mac = user_mac
        pass

    def __str__(self):
        return "NATRouteTaskEntry"

    def update_attribute(self, dst_ip=None, dst_port_no=None, server_mac=None):
        if dst_ip:
            self.dst_ip = dst_ip
        if dst_port_no:
            self.dst_port_no = dst_port_no
        if server_mac:
            self.server_mac = server_mac
        pass

    def deploy_flow_table(self, link_list, link_cost):
        if len(link_list) > 1:
            sw1_dpid = link_list[0]
            sw2_dpid = link_list[len(link_list)-1]
            sw1 = self.route_manage.switches.get_switch(sw1_dpid)
            sw2 = self.route_manage.switches.get_switch(sw2_dpid)
            if len(link_list) == 2:
                self.flow_mod(sw2.dp, self.dst_ip, self.src_ip, self.dst_port_no, sw2.neighbors[sw1.dp.id][0])
                self.flow_mod(sw2.dp, self.src_ip, self.dst_ip, sw2.neighbors[sw1.dp.id][0], self.dst_port_no)
                self.flow_mod(sw1.dp, self.dst_ip, self.src_ip, sw1.neighbors[sw2.dp.id][0], self.src_port_no)
                self.flow_mod(sw1.dp, self.src_ip, self.dst_ip, self.src_port_no, sw1.neighbors[sw2.dp.id][0])
                return True
            else:
                links = []
                reverse_link_list = link_list[::-1]
                for num, dpid in enumerate(reverse_link_list):
                    sw = self.route_manage.switches.get_switch(dpid)
                    if num == 0:
                        if (sw.attribute == sw.AttributeEnum.access) and ((dpid, self.src_port_no) in
                                self.route_manage.fault_classifier.access_switch_to_user_ports):
                            self._user_to_server_flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                                          sw.neighbors[reverse_link_list[num+1]][0],
                                                          self.gateway_ip, self.gateway_mac,
                                                          self.server_mac, self.user_mac)
                            self._server_to_user_flow_mod(sw.dp, self.src_ip, self.dst_ip, self.dst_port_no,
                                                          self.gateway_ip, self.gateway_mac,
                                                          self.server_mac, self.user_mac)
                        else:
                            self.flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                          sw.neighbors[reverse_link_list[num+1]][0],
                                          self.dst_port_no)
                            self.flow_mod(sw.dp, self.dst_ip, self.src_ip,
                                          self.dst_port_no, sw.neighbors[reverse_link_list[num+1]][0])

                        second_dpid = reverse_link_list[num+1]
                        first_port_no = sw.neighbors[second_dpid][0]
                        second_sw = self.route_manage.switches.get_switch(second_dpid)
                        second_port_no = second_sw.neighbors[dpid][0]
                        first_link = [dpid_to_str(sw.dp.id), first_port_no,
                                      dpid_to_str(second_sw.dp.id), second_port_no]
                        links.append(first_link)
                        continue
                    if num == len(reverse_link_list) - 1:
                        if (sw.attribute == sw.AttributeEnum.access) and \
                                ((dpid, self.src_port_no) in
                                 self.route_manage.fault_classifier.access_switch_to_user_ports):
                            self._user_to_server_flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                                          sw.neighbors[reverse_link_list[num-1]][0],
                                                          self.gateway_ip, self.gateway_mac,
                                                          self.server_mac, self.user_mac)
                            self._server_to_user_flow_mod(sw.dp, self.src_ip, self.dst_ip, self.src_port_no,
                                                          self.gateway_ip, self.gateway_mac,
                                                          self.server_mac, self.user_mac)
                        else:
                            self.flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                          self.src_port_no, sw.neighbors[reverse_link_list[num-1]][0])
                            self.flow_mod(sw.dp, self.dst_ip, self.src_ip,
                                          sw.neighbors[reverse_link_list[num-1]][0], self.src_port_no)
                        continue
                    self.flow_mod(sw.dp, self.src_ip, self.dst_ip,
                                  sw.neighbors[reverse_link_list[num+1]][0],
                                  sw.neighbors[reverse_link_list[num-1]][0])
                    self.flow_mod(sw.dp, self.dst_ip, self.src_ip,
                                  sw.neighbors[reverse_link_list[num-1]][0],
                                  sw.neighbors[reverse_link_list[num+1]][0])
                    # add ws_update event msg: middle links
                    current_dpid = dpid
                    next_dpid = reverse_link_list[num+1]
                    next_sw = self.route_manage.switches.get_switch(next_dpid)
                    current_port_no = sw.neighbors[next_dpid][0]
                    next_port_no = next_sw.neighbors[current_dpid][0]
                    current_link = [dpid_to_str(sw.dp.id), current_port_no,
                                    dpid_to_str(next_sw.dp.id), next_port_no]
                    links.append(current_link)

                # send GUI event
                if self.route_manage.algorithm_type == "GA":
                    self.route_manage.send_event_to_observers(ws_event.EventWebRouteSet(links))
                elif self.route_manage.algorithm_type == "Dij":
                    self.route_manage.send_event_to_observers(ws_event.EventWebRouteSetDij(links))
            return True
        else:
            logger.info("find path failed!")
            return False

    @staticmethod
    def _user_to_server_flow_mod(datapath, user_ip, server_ip, outport,
                                 gateway_ip, gateway_mac, server_mac, user_mac):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # match by IP address of users and gateways
        format_match = {'dl_type': str(0x0800),
                        'nw_proto': 6,
                        'ipv4_src': str(user_ip),
                        'ipv4_dst': str(gateway_ip)}
        match = ofctl_v1_3.to_match(datapath, format_match)

        actions = [parser.OFPActionDecNwTtl(),
                   parser.OFPActionSetField(tcp_dst=int(server_tcp_port)),
                   parser.OFPActionSetField(ipv4_dst=netaddr.IPAddress(server_ip)),
                   parser.OFPActionSetField(eth_dst=netaddr.EUI(server_mac)),
                   parser.OFPActionOutput(outport)]

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath, flags=1,
                                priority=ROUTE_FLOW_PRIORITY, cookie=0,
                                buffer_id=ofproto.OFP_NO_BUFFER,
                                idle_timeout=FLOW_IDLE_TIMEOUT,
                                hard_timeout=FLOW_HARD_TIMEOUT,
                                command=ofproto.OFPFC_ADD,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @staticmethod
    def _server_to_user_flow_mod(datapath, user_ip, server_ip, outport,
                                 gateway_ip, gateway_mac, server_mac, user_mac):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # match by IP address of server and user
        format_match = {'dl_type': str(0x0800),
                        'nw_proto': 6,
                        'ipv4_src': str(server_ip),
                        'ipv4_dst': str(user_ip)}

        actions = [parser.OFPActionDecNwTtl(),
                   parser.OFPActionSetField(tcp_src=int(80)),
                   parser.OFPActionSetField(ipv4_src=netaddr.IPAddress(gateway_ip)),
                   parser.OFPActionSetField(eth_src=netaddr.EUI(gateway_mac)),
                   parser.OFPActionSetField(eth_dst=netaddr.EUI(user_mac)),
                   parser.OFPActionOutput(outport)]

        match = ofctl_v1_3.to_match(datapath, format_match)
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath, flags=1,
                                priority=ROUTE_FLOW_PRIORITY, cookie=0,
                                buffer_id=ofproto.OFP_NO_BUFFER,
                                idle_timeout=FLOW_IDLE_TIMEOUT,
                                hard_timeout=FLOW_HARD_TIMEOUT,
                                command=ofproto.OFPFC_ADD,
                                match=match, instructions=inst)
        datapath.send_msg(mod)
        pass

    def to_dict(self):
        r = {'server_mac': self.server_mac,
             'gateway_ip': self.gateway_ip,
             'gateway_mac': self.gateway_mac,
             'route_type': self.route_type,
             'src_dpid': self.src_dpid,
             'src_ip': self.src_ip,
             'src_port_no': self.src_port_no,
             'dst_dpid': self.dst_dpid,
             'dst_ip': self.dst_ip,
             'dst_port_no': self.dst_port_no}
        return r


class MulticastTaskEntry(TaskEntryBase):
    """multicast route task entry

    :param route_type: ROUTE_TYPE_INTRA_TOPO
    :param src_dpid: group source switch datapath id
    :param src_ip: group source host ip address
    :param src_port_no: source switch port number
    :param dst_dpid_set: group destination switch datapath id
    :param group_ip: group ip address
    """
    def __init__(self, route_type, src_dpid, src_ip, src_port_no,
                 dst_dpid_set, group_ip, route_manage):
        super(MulticastTaskEntry, self).__init__(route_type, src_dpid, src_ip, src_port_no,
                                                 dst_dpid=dst_dpid_set, dst_ip=group_ip, dst_port_no=None,
                                                 route_manage=route_manage)
        pass

    def __str__(self):
        return "MulticastTaskEntry"

    # @system_performance_logger.timer
    def route_calc(self):
        """calculate route for multicast request."""
        self.route_manage.multicast_algorithm.update_link_status(link_monitor_main.global_link_table)
        self.route_manage.multicast_algorithm.run(self.src_dpid, self.dst_dpid, BusinessType["VIDEO"])
        link_list = self.route_manage.multicast_algorithm.get_link()

        logger.info("src:%s, dst:%s, deploy multicast link:%s",
                    self.src_ip, self.dst_ip, link_list)
        link_cost = None
        return link_list, link_cost

    def deploy_flow_table(self, link_list, link_cost):
        # get formatted link list and reverse for deployment.
        format_link_list = self._format_link_list(link_list)
        format_link_list.reverse()

        # get group information.
        group_info = self.route_manage.multicast_group[self.dst_ip]

        for link in format_link_list:
            dpid = link.keys()[0]
            info = link.values()[0]
            switch = self.route_manage.switches[dpid]

            # get inport
            if info['root'] is False:
                in_port = switch.neighbors[info['former']][0]
            else:
                in_port = self.src_port_no

            # get outports
            outports = []
            if info['end']:
                # add destination outport.
                group_outports = group_info[dpid].keys()
                for port in group_outports:
                    outports.append(port)
                    pass
            if len(info['next']) != 0:
                # add outport to next switch.
                for dpid in info['next']:
                    outports.append(switch.neighbors[dpid][0])
                    pass

            # deploy flow table
            self.flow_mod(switch.dp, self.src_ip, self.dst_ip,
                          in_port, outports)
        pass

    @staticmethod
    def flow_mod(datapath, src_ip, dst_ip, inport, outport):
        """for multicast support

        :param outport: data out ports number list
        """
        assert isinstance(outport, list)

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP, in_port=inport,
                                ipv4_src=str(src_ip), ipv4_dst=str(dst_ip))

        actions = []
        for port in outport:
            actions.append(parser.OFPActionOutput(port))

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=ROUTE_FLOW_PRIORITY,
                                idle_timeout=MULTICAST_FLOW_IDLE_TIMEOUT,
                                hard_timeout=MULTICAST_FLOW_HARD_TIMEOUT,
                                command=ofproto.OFPFC_ADD,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @staticmethod
    def _format_link_list(link_list):
        """format multicast link list for flow table deployment.

        :param link_list: set of every unicast link list
        :return format_link_list: set of switch for flow table deployment

        such as:
        link_list = [[1, 2, 3, 4], [1, 2, 5, 6], [1, 2, 5, 7]]
        format_link_list = [{1: {'shared': True, 'end': False, 'root': True, 'former': None, 'next': [2]}},
                            {2: {'shared': True, 'end': False, 'root': False, 'former': 1, 'next': [3, 5]}},
                            {3: {'shared': False, 'end': False, 'root': False, 'former': 2, 'next': [4]}},
                            {5: {'shared': True, 'end': False, 'root': False, 'former': 2, 'next': [6, 7]}},
                            {4: {'shared': False, 'end': True, 'root': False, 'former': 3, 'next': []}},
                            {6: {'shared': False, 'end': True, 'root': False, 'former': 5, 'next': []}},
                            {7: {'shared': False, 'end': True, 'root': False, 'former': 5, 'next': []}}]
        """
        branch_len = []
        for branch in link_list:
            branch_len.append(len(branch))

        max_depth = max(branch_len)

        format_link_list = []
        format_link_list_dpid = []
        for depth in range(max_depth):
            for branch_num in range(len(link_list)):
                if depth > (len(link_list[branch_num]) - 1):
                    continue

                dpid = link_list[branch_num][depth]
                if dpid not in format_link_list_dpid:
                    format_link_list_dpid.append(dpid)
                    format_link_list.append(
                        {dpid: {'former': None,     # former dpid
                                'next': [],         # next dpids
                                'root': False,      # is root of tree or not
                                'shared': False,    # is shared branch or not
                                'end': False}})     # is end of branch or not
                else:
                    index = format_link_list_dpid.index(dpid)
                    format_link_list[index][dpid]['shared'] = True

                index = format_link_list_dpid.index(dpid)
                if depth > 0:
                    former_dpid = link_list[branch_num][depth-1]
                    format_link_list[index][dpid]['former'] = former_dpid
                    if depth < (len(link_list[branch_num])-1):
                        next_dpid = link_list[branch_num][depth+1]
                        if next_dpid not in format_link_list[index][dpid]['next']:
                            format_link_list[index][dpid]['next'].append(next_dpid)
                    else:
                        format_link_list[index][dpid]['end'] = True
                else:
                    format_link_list[index][dpid]['root'] = True
                    next_dpid = link_list[branch_num][depth+1]
                    if next_dpid not in format_link_list[index][dpid]['next']:
                        format_link_list[index][dpid]['next'].append(next_dpid)

        return format_link_list

    def to_dict(self):
        r = {'route_type': self.route_type,
             'src_dpid': self.src_dpid,
             'src_ip': self.src_ip,
             'src_port_no': self.src_port_no,
             'dst_dpid': self.dst_dpid,
             'dst_ip': self.dst_ip,
             'dst_port_no': self.dst_port_no}
        return r
