import logging
import json
import time
import netaddr

from datetime import datetime
from threading import Thread
from webob import Response

from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller import ofp_event
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether
from ryu.lib import hub
from ryu.lib import mac
from ryu.lib.packet import packet
from ryu.lib.packet import ipv4, ipv6, ethernet, igmp
from ryu.app.wsgi import ControllerBase, WSGIApplication, route

from base.parameters import DefaultBusinessType, BusinessType
from base.parameters import GATEWAY_IP_LIST, GATEWAY_MAC_DICT, ROUTE_TASK_HANDLE_INTERVAL
from base.parameters import LINK_STATUS_PRINTER, LINK_STATUS_PRINTER_INTERVAL
from lib.project_lib import Megabits, find_packet
# from SystemLogger import SystemPerformanceLogger
from web_service import ws_event
from multicast import igmplib
from topology_manage.object import topo_event as topo_event
from topology_manage.object.link import LinkTableApi
from host_manage.HostTrack import EventHostState, MacEntry
from host_manage.HostDiscovery import EventHostMissing
from topology_manage.ProxyArp import ARPTable
from route_manage.route_algorithm.RouteAlgorithm import GAPopulation, Dijkstra, RouteAlgorithm
from route_manage.route_algorithm.MulticastRouteAlgorithm import MGAlgorithm
from route_manage.route_algorithm.NSGA2 import NSGA2
from route_manage.route_task import RouteTaskEntry, NATRouteTaskEntry, MulticastTaskEntry, RouteTaskHandler
from route_info_maintainer import RouteInfoMaintainer
from link_monitor import link_monitor_main
from fault_recovery import fault_recovery_event, fault_recovery_main
from fault_recovery.fault_classifier import FaultClassifier
from load_balance.load_balancer import LoadBalancer
from host_manage.cluster_manage import ClusterManage

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

route_manage_instance_name = 'route_manage_app'
rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})
rest_body_deprecated = json.dumps({'msg': 'this api is deprecated'})

TABLE_MISS_FLOW_PRIORITY = 100

REQUEST_CACHE_TIMEOUT = 50 * ROUTE_TASK_HANDLE_INTERVAL

# system_performance_logger = SystemPerformanceLogger()

ROUTE_TYPE_USER_TO_SERVER = 1
ROUTE_TYPE_SERVER_TO_USER = 2
ROUTE_TYPE_INTRA_TOPO = 3


class RouteManage(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _EVENTS = [ws_event.EventWebRouteSet, ws_event.EventWebLinkBandChange,
               ws_event.EventWebRouteSetDij, EventHostMissing,
               fault_recovery_event.EventFaultRecoveryLinkDelete,
               fault_recovery_event.EventFaultRecoveryPortDown]

    _CONTEXTS = {
        'wsgi': WSGIApplication,
        'igmplib': igmplib.IgmpLib
    }

    def __init__(self, install_flow=True, *args, **kwargs):
        if not hasattr(self, 'servers'):
            super(RouteManage, self).__init__(*args, **kwargs)

            # server business type: {ip: BusinessType[]}
            self.servers = {}

            # mac_to_port
            self.mac_to_port = None
            self.entry = {}

            # multicast group info
            self.multicast_group = {}

            # switch list
            self.switches = None

            # link list
            self.links = None

            # request cache: {(src_ip, dst_ip): timestamp}
            self.request_cache = {}

            # Algorithm object
            self.algorithm_state = False
            self.algorithm_type = "Dij"
            # self.algorithm = Dijkstra()
            self.algorithm = RouteAlgorithm()


            # multicast Algorithm object
            self.multicast_algorithm_state = False
            self.multicast_algorithm_type = "GA"
            # self.multicast_algorithm = MGAlgorithm()
            self.multicast_algorithm = NSGA2()

            # route task handler
            self.queue = hub.Queue()
            self.route_task_handler = RouteTaskHandler(self)

            # install flow for fail match ip packet
            self.install_flow = install_flow

            # link state printer
            self.link_state_printer = LINK_STATUS_PRINTER

            # cluster management
            # self.cluster_manage = ClusterManage()

            # Used for fault recovery. Get an instance of RouteInfoMaintainer(This is a singleton class)
            self.route_info_maintainer = RouteInfoMaintainer()
            # self.fault_classifier = FaultClassifier()

            # Used for server load balancing.
            # load balancer
            # self.load_balancer = LoadBalancer()

            # TODO: Refactor to GatewayManager module
            # send the gateway found event to RouteManage
            self.update_gateway_entry()

            # Use arp_table to find mac address
            self.arp_table = ARPTable()

            # TODO: @deprecated
            # system initialization status
            self.init_status = False

            # Register a igmp handler
            self._igmp_handler = kwargs['igmplib']

            # Register a restful controller for this module
            wsgi = kwargs['wsgi']
            wsgi.register(RouteManageRestController, {route_manage_instance_name: self})

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(RouteManage, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance    

    def update_gateway_entry(self):
        for gateway_ip, gateway_mac in GATEWAY_MAC_DICT.items():
            self.update_entry(dpid=None, port=None, macaddr=gateway_mac, ip_addr=gateway_ip)
        pass

    def update_entry(self, dpid, port, macaddr, ip_addr):
        mac_entry = MacEntry(dpid, port, macaddr)
        mac_entry.ipaddrs[ip_addr] = 0
        self.entry[macaddr] = mac_entry

    def get_mac(self, ip_addr):
        for mac_addr, host_info_entry in self.entry.items():
            if host_info_entry.ipaddrs.keys()[0] == ip_addr:
                return mac_addr
            pass
        return None

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def table_miss_flow_entry(self, ev):
        if not self.install_flow: return
        logger.debug("Installing table miss flow for IP packet")
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=0,
                                priority=TABLE_MISS_FLOW_PRIORITY,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(topo_event.EventTopoInitializeEnd)
    def topo_init_handler(self, ev):
        """
            topology init, get all switches.
        """

        # change By Bokala.
        if self.init_status:
            return

        # init topology information for RouteManage.
        self.links = ev.link_table
        rep = self.send_request(topo_event.EventSwitchRequest())
        self.switches = rep.switches

        # init cluster information.
        # self.cluster_manage.read_cluster_configuration()
        # self.cluster_manage.read_server_configuration()
        # self.cluster_manage.cluster_init()

        # init fault recovery
        # self.fault_classifier.update_port_type(self.switches)
        # self.fault_classifier.init_server_in_cluster(self.cluster_manage.servers)

        # init load balancer
        # self.load_balancer.init(self.cluster_manage.clusters,
        #                         self.fault_classifier.servers_based_on_type)
        # self.load_balancer.update()

        # init igmplib.
        self._igmp_handler.set_querier_mode(self.switches)
        self._igmp_handler.start_igmp_querier()

        # init unicast algorithm.
        self.algorithm.init_algorithm(self.switches, self.links)
        self.algorithm_state = True

        # init multicast algorithm.
        self.multicast_algorithm.init_algorithm(self.switches, self.links)
        self.multicast_algorithm_state = True

        # init link state printer.
        if self.link_state_printer:
            self._start_link_status_printer()

        logger.info("system initialization finished.")
        self.init_status = True

    @set_ev_cls(topo_event.EventLinkDelUpdateTopo)
    def link_delete_handler(self, ev):
        """
            receive link deleted event, update topology info in algorithm and
            active fault_recovery module by EventFaultRecoveryLinkDelete.
        """
        self.algorithm.init_algorithm(ev.switches, ev.links)
        self.send_event_to_observers(fault_recovery_event.EventFaultRecoveryLinkDelete(
            ev.src_port, ev.dst_port, ev.timestamp))

    @set_ev_cls(topo_event.EventPortDownUpdateTopo)
    def port_down_handler(self, ev):
        """
            receive port down event, only handle edge switch port with host attached to,
            and active fault_recovery module by EventFaultRecoveryPortDown.
        """
        port = ev.port
        is_port_down = port.is_down()
        if not is_port_down:
            # ignore port add event
            return

        switch_port = self.mac_to_port[port.dpid]
        if port.port_no not in switch_port.values():
            # ignore no host attached port
            return

        self.send_event_to_observers(
            fault_recovery_event.EventFaultRecoveryPortDown(ev.port, ev.timestamp))

    def change_algorithm_type(self, algorithm_type):
        """change algorithm type by rest api."""
        if algorithm_type == "GA":
            new_algorithm = GAPopulation()
        elif algorithm_type == "Dij":
            new_algorithm = Dijkstra()
        else:
            logger.info("algorithm not support, now is [%s].",
                        self.algorithm_type)
            return

        new_algorithm.switch_queue = self.algorithm.switch_queue
        new_algorithm.edge_queue = self.algorithm.edge_queue
        new_algorithm.switch_neighbors = self.algorithm.switch_neighbors
        new_algorithm.edge_collection = self.algorithm.edge_collection
        new_algorithm.vertexs = self.algorithm.vertexs
        new_algorithm.edges = self.algorithm.edges

        logger.info("change algorithm from %s to %s",
                    self.algorithm_type, algorithm_type)

        self.algorithm = new_algorithm
        self.algorithm_type = algorithm_type

    @set_ev_cls(EventHostState, MAIN_DISPATCHER)
    def host_state_handler(self, ev):
        """
            handle host state event from module HostTrack,
            update host tracing information.
        """
        self.mac_to_port = ev.mac_to_port
        if ev.join:
            logger.info("[host join]entry updated:%s", ev.entry)
            self.entry[ev.entry.macaddr] = ev.entry
        elif ev.move:
            logger.info("[host move]entry updated:%s origin:%s",
                        ev.entry, self.entry[ev.entry.macaddr])
            self.entry[ev.entry.macaddr] = ev.entry
        elif ev.leave:
            logger.info("[host leave]entry updated:%s", ev.entry)
            del self.entry[ev.entry.macaddr]

    @set_ev_cls(igmplib.EventMulticastGroupChanged, MAIN_DISPATCHER)
    def multicast_group_handler(self, ev):
        """
            handle multicast group event from module IgmpLib,
            updating group information.
        """
        msg = {
            igmplib.MG_GROUP_ADDED: 'Multicast Group Added',
            igmplib.MG_MEMBER_CHANGED: 'Multicast Group Member Changed',
            igmplib.MG_GROUP_REMOVED: 'Multicast Group Removed',
        }
        logger.info("[%s] group:%s info:%s",
                    msg.get(ev.reason), ev.address, ev.dst)

        if ev.reason == igmplib.MG_GROUP_ADDED:
            self.multicast_group = ev.group
            pass
        elif ev.reason == igmplib.MG_GROUP_REMOVED:
            self.multicast_group = ev.group
            pass
        elif ev.reason == igmplib.MG_MEMBER_CHANGED:
            self.multicast_group = ev.group
            pass

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        pkt = packet.Packet(msg.data)

        header_list = dict(
            (p.protocol_name, p) for p in pkt.protocols if type(p) != str)

        # ignore igmp packet
        if igmp.igmp.__name__ in header_list:
            return

        # handle packet
        if ipv4.ipv4.__name__ in header_list:
            self._handle_ip(msg, pkt, header_list[ipv4.ipv4.__name__])
            pass
        elif ipv6.ipv6.__name__ in header_list:
            pass

    def _handle_ip(self, msg, pkt, ip_layer):
        ether_layer = find_packet(pkt, ethernet.ethernet.__name__)

        src_mac = ether_layer.src
        dst_mac = ether_layer.dst
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst

        # ignore broadcast packet.
        if dst_mac == mac.BROADCAST_STR or \
           dst_ip == '255.255.255.0':
            return

        # handle multicast packet.
        dst_ip_fmt = netaddr.IPAddress(dst_ip)
        if dst_ip_fmt.is_multicast():
            self._handle_multicast_udp(msg, pkt, ip_layer)
            return

        # lookup entry for source host.
        if src_mac in self.entry:
            src_dpid = self.entry[src_mac].dpid
            src_port_no = self.entry[src_mac].port
            if not self.entry[src_mac].ipaddrs.get(src_ip):
                logger.debug("entry[%s] miss ipaddrs[%s]",
                             src_mac, src_ip)
                self.send_event_to_observers(EventHostMissing(msg, 'src'))
                pass
        else:
            logger.debug("src entry[%s] missing", src_mac)
            self.send_event_to_observers(EventHostMissing(msg, 'src'))
            return

        # lookup entry for destination host.
        if dst_mac in self.entry:
            dst_dpid = self.entry[dst_mac].dpid
            dst_port_no = self.entry[dst_mac].port
            if not self.entry[dst_mac].ipaddrs.get(dst_ip):
                logger.debug("entry[%s] miss ipaddrs[%s]",
                             dst_mac, dst_ip)
                self.send_event_to_observers(EventHostMissing(msg, 'dst'))
                pass
        else:
            logger.debug("dst entry[%s] missing", dst_mac)
            self.send_event_to_observers(EventHostMissing(msg, 'dst'))
            return

        # check destination host business type.
        if (dst_ip not in self.servers) and (dst_ip not in GATEWAY_IP_LIST):
            logger.error("server %s type unset, route will be calculated with DEFAULT: %s",
                         dst_ip, DefaultBusinessType)
            pass

        # check algorithm initialization.
        if self.algorithm_state is not True:
            logger.debug("algorithm uninitialized.")
            return

        # ignore same (src_ip, dst_ip) packet-in in queue
        # while task in queue and call algorithm.evolve
        if (src_ip, dst_ip) in self.request_cache:
            if time.time() - self.request_cache[(src_ip, dst_ip)][0] < \
                    REQUEST_CACHE_TIMEOUT:
                return
            else:
                self.request_cache[(src_ip, dst_ip)][0] = time.time()
        else:
            self.request_cache[(src_ip, dst_ip)] = [time.time(), 0]

        # set logger and push task to queue.
        # system_performance_logger.new_request()
        # system_performance_logger.handle_req_start(time.time())

        src_port_index = (src_dpid, src_port_no)
        dst_port_index = (dst_dpid, dst_port_no)

        '''
        if (dst_ip in GATEWAY_IP_LIST) and \
                (src_port_index in self.fault_classifier.access_switch_to_user_ports):
            # This request is send from user to server,
            # so calculate the dst server and execute the NAT strategy on the access switch.
            # Note: now, in this case, we make the two-way flow entries,
            # which are those for user to server and for server to user.
            dst_server_ip = self.load_balancer.get_server(dst_ip)
            logger.info("dst_server:%s, dst_gw:%s", dst_server_ip, dst_ip)
            dst_server_mac = self.get_mac(dst_server_ip)
            if dst_server_mac is None:
                logger.info("host_missing, dst_server_ip:%s", dst_server_ip)
                self.send_event_to_observers(EventHostMissing(dst_server_ip, 'host'))
                return
            dst_server_info = self.cluster_manage.servers[dst_server_ip]
            dst_server_switch_dpid = dst_server_info.location[0]
            dst_server_switch_port_no = dst_server_info.location[1]
            task_entry = NATRouteTaskEntry(route_type=ROUTE_TYPE_USER_TO_SERVER,
                                           src_dpid=src_dpid, src_ip=src_ip, src_port_no=src_port_no,
                                           dst_dpid=dst_server_switch_dpid, dst_ip=dst_server_ip,
                                           dst_port_no=dst_server_switch_port_no,
                                           gateway_ip=dst_ip, gateway_mac=dst_mac,
                                           server_mac=dst_server_mac, user_mac=src_mac,
                                           route_manage=self)
        elif dst_port_index in self.fault_classifier.access_switch_to_user_ports:
            # Note: I'm not sure about the follow.
            # This means that this request is send by the server, which maybe impossible in this system.
            # Now, we don't handle this case.
            return
        else:
            task_entry = RouteTaskEntry(route_type=ROUTE_TYPE_INTRA_TOPO,
                                        src_dpid=src_dpid, src_ip=src_ip, src_port_no=src_port_no,
                                        dst_dpid=dst_dpid, dst_ip=dst_ip, dst_port_no=dst_port_no,
                                        route_manage=self)

        '''

        task_entry = RouteTaskEntry(route_type=ROUTE_TYPE_INTRA_TOPO,
                                    src_dpid=src_dpid, src_ip=src_ip, src_port_no=src_port_no,
                                    dst_dpid=dst_dpid, dst_ip=dst_ip, dst_port_no=dst_port_no,
                                    route_manage=self)


        self.add_to_queue(task_entry)
        self.trigger_update()

    def _handle_multicast_udp(self, msg, pkt, ip_layer):
        ether_layer = find_packet(pkt, ethernet.ethernet.__name__)

        src_mac = ether_layer.src
        dst_mac = ether_layer.dst
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst

        # lookup entry for group source host.
        if src_mac in self.entry:
            src_dpid = self.entry[src_mac].dpid
            src_port_no = self.entry[src_mac].port
            if not self.entry[src_mac].ipaddrs.get(src_ip):
                logger.debug("entry[%s] miss ipaddrs[%s]",
                             src_mac, src_ip)
                self.send_event_to_observers(EventHostMissing(msg, 'src'))
                pass
        else:
            logger.debug("src entry[%s] missing", src_mac)
            self.send_event_to_observers(EventHostMissing(msg, 'src'))
            return

        if ip_layer.dst not in self.multicast_group:
            logger.info("No member in group, set drop flow table.")
            # TODO: set drop flow for no member group in multicast src.
            return

        # check algorithm initialization.
        if self.multicast_algorithm_state is not True:
            logger.debug("multicast algorithm uninitialized.")
            return

        # ignore same (src_ip, dst_ip) packet-in in queue
        # while task in queue and call algorithm.evolve
        if (src_ip, dst_ip) in self.request_cache:
            if time.time() - self.request_cache[(src_ip, dst_ip)][0] < \
                    REQUEST_CACHE_TIMEOUT:
                return
            else:
                self.request_cache[(src_ip, dst_ip)][0] = time.time()
        else:
            self.request_cache[(src_ip, dst_ip)] = [time.time(), 0]

        task_entry = MulticastTaskEntry(route_type=ROUTE_TYPE_INTRA_TOPO,
                                        src_dpid=src_dpid, src_ip=src_ip, src_port_no=src_port_no,
                                        dst_dpid_set=self.multicast_group[dst_ip].keys(), group_ip=dst_ip,
                                        route_manage=self)
        self.add_to_queue(task_entry)
        self.trigger_update()

        pass

    def process_queued_msg(self):
        """add all the queued routing information to route task handler."""
        try:
            while not self.queue.empty():
                task_entry = self.queue.get()
                self.route_task_handler.update_entry(task_entry)
        except:
            pass

    def add_to_queue(self, msg):
        """an interface to add a object into queue."""
        if not self.queue.full():
            self.queue.put(msg)

    def trigger_update(self):
        """create a thread to update route task queue."""
        update_thread = Thread(target=self.process_queued_msg)
        update_thread.setDaemon(True)
        update_thread.start()

    def _start_link_status_printer(self):
        """create link status print thread."""
        ls_printer = Thread(target=self._link_state_printer)
        ls_printer.setDaemon(True)
        ls_printer.start()

    @staticmethod
    def _link_state_printer():
        """link state printer."""
        time.sleep(2)

        while True:
            links = link_monitor_main.global_link_table
            assert isinstance(links, LinkTableApi)

            current_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            logger.info("*************************** link status @%s ***************************", current_time)

            for dpids, edge in links.items():
                ev = edge.values()[0]
                logger.info("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
                            dpids[0], dpids[1],
                            float(ev.available_band)/Megabits,
                            float(ev.total_band)/Megabits,
                            1 - float(ev.available_band) / ev.total_band)

            logger.info("*************************** link status end ***************************")
            time.sleep(LINK_STATUS_PRINTER_INTERVAL)


class RouteManageRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(RouteManageRestController, self).__init__(req, link, data, **config)
        self.route_manage_instance = data[route_manage_instance_name]

    @route('routemanage', '/routemanage/server', methods=['GET'])
    def get_server_bussiness_type(self, req, **kwargs):
        body = json.dumps(self.route_manage_instance.servers)
        return Response(content_type='application/json', body=body)

    @route('routemanage', '/routemanage/server', methods=['POST'])
    def update_server_bussiness_type(self, req, **kwargs):
        logger.warning("[RouteManageRestController.update_server_bussiness_type]"
                       "this method is deprecated")
        server_message = json.loads(req.body)
        for server_ip_unicode, server_info in server_message.items():
            server_ip = str(server_ip_unicode)
            server_info_str_list = str(server_info).split(',')
            server_type, server_switch, switch_port, server_mac = server_info_str_list
            self.route_manage_instance.servers[server_ip] = str(server_type)
            server_switch_int = int(server_switch)
            switch_port_int = int(switch_port)
            server_mac_str = str(server_mac)
            self.route_manage_instance.update_entry(dpid=server_switch_int, port=switch_port_int,
                                                    macaddr=server_mac_str, ip_addr=server_ip)
            pass
        fault_recovery_main.servers = self.route_manage_instance.servers
        return Response(content_type='application/json', body=rest_body_deprecated)

    @route('routemanage', '/routemanage/algorithm', methods=['GET'])
    def get_algorithm_param(self, req, **kwargs):
        al = self.route_manage_instance.algorithm
        body = al.param_to_dict()
        return Response(content_type='application/json', body=body)

    @route('routemanage', '/routemanage/algorithm', methods=['POST'])
    def update_algorithm_param(self, req, **kwargs):
        body = rest_body_ok
        payload = json.loads(req.body)
        al = self.route_manage_instance.algorithm

        if al.update_param(payload) is not True:
            body = rest_body_none

        return Response(content_type='application/json', body=body)

    @route('routemanage', '/routemanage/algorithm/type', methods=['POST'])
    def update_algorithm_type(self, req, **kwargs):
        payload = json.loads(req.body)
        self.route_manage_instance.change_algorithm_type(str(payload["algorithm_type"]))
