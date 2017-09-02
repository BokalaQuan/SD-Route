import json
import logging
import random

from ryu.app.wsgi import ControllerBase, route
from route_manage.route_algorithm.RouteAlgorithm import Dijkstra
from base.parameters import BusinessType
from host_manage.object.server import ClusterServer

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

PortType_EdgeSwitchToServer = 1
PortType_EdgeSwitchToTopo = 2
PortType_IntraTopo = 3
PortType_AccessSwitchToTopo = 4
PortType_AccessSwitchToUser = 5

FaultType_LinkFault__EdgeSwitchToServer = 11
FaultType_LinkFault__EdgeSwitchToTopo = 12
FaultType_LinkFault__IntraTopo = 13
FaultType_LinkFault__AccessSwitchToTopo = 14
FaultType_LinkFault__AccessSwitchToUser = 15

FaultType_PortFault__EdgeSwitchToServer = 21
FaultType_PortFault__EdgeSwitchToTopo = 22
FaultType_PortFault__IntraTopo = 23
FaultType_PortFault__AccessSwitchToTopo = 24
FaultType_PortFault__AccessSwitchToUser = 25

ChooseSameSwitchServer = True

SERVER_STATE_DOWN = 'DOWN'
SERVER_STATE_UP = 'UP'


class FaultClassifier(object):
    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'edge_switch_to_server_ports'):
            # super(FaultClassifier, self).__init__(req, *args, **kwargs)
            self.edge_switch_to_server_ports = []
            self.edge_switch_to_topo_ports = []
            self.intra_topo_ports = []
            self.access_switch_to_topo_ports = []
            self.access_switch_to_user_ports = []

            # servers_based_on_type stores all the servers' information based on its type,
            # it is an dictionary which is made as:
            # {'server_type': [(server_ip, server_switch, switch_port)]}, for example, it can be:
            # {'VIDEO': [(10.0.0.1, 3001,3), (10.0.0.2, 3001,4)], 'FTP': [(10.0.0.5, 3002, 3), (10.0.0.6, 3002, 4)]}
            self.servers_based_on_type = {}

            # servers_based_on_ip stores all the servers' information based on its ip,
            # it is an dictionary which is made as:
            # {'server_ip': (server_type, server_switch, switch_port)}, for example, it can be:
            # {'10.0.0.1': (VIDEO, 3001, 3)}
            self.servers_based_on_ip = {}

            # servers_based_on_port stores all the servers' information based on its port,
            # it is an dictionary which is made as:
            # {(server_switch, switch_port): (server_ip, server_type)}, for example, it can be:
            # {(3001, 3): ('10.0.0.1',VIDEO)}
            self.servers_based_on_port = {}
            self.servers_state_based_on_port = {}

            #
            self.server_ip_mac_dict = {}
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(FaultClassifier, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def init_server_in_cluster(self, server_in_cluster):
        for server_ip, server_info in server_in_cluster.iteritems():
            if isinstance(server_info, ClusterServer):
                server_type = server_info.cluster.cluster_type
                server_switch, switch_port = server_info.location
                server_mac_addr = server_info.mac
                server_state = server_info.status

                if server_type in self.servers_based_on_type:
                    servers_in_type = self.servers_based_on_type[server_type]
                    servers_in_type.append((server_ip, server_switch, switch_port))
                    self.servers_based_on_type[server_type] = servers_in_type
                else:
                    self.servers_based_on_type[server_type] = \
                        [(server_ip, server_switch, switch_port)]

                self.servers_based_on_ip[server_ip] = (server_type, server_switch, switch_port)
                self.servers_based_on_port[(server_switch, switch_port)] = (server_ip, server_type)
                self.servers_state_based_on_port[(server_switch, switch_port)] = server_state
                self.server_ip_mac_dict[server_ip] = server_mac_addr
        pass

    def init_port_type(self, switch):
        # TODO: set switch port type
        # now rest api FaultRecoveryDataMaintainer.init_port_types()
        pass

    def update_server_status(self, server_ip, status):
        """update server status, UP or DOWN

        :param server_ip:
        :param status: SERVER_STATE_DOWN/SERVER_STATE_UP
        :return:
        """
        assert (status == SERVER_STATE_DOWN or status == SERVER_STATE_UP)
        if server_ip in self.servers_based_on_ip:
            server_type, server_switch, switch_port = self.servers_based_on_ip[server_ip]
            if self.servers_state_based_on_port[(server_switch, switch_port)] == status:
                logger.debug("server %s status unchanged %s", server_ip, status)
                return
            self.servers_state_based_on_port[(server_switch, switch_port)] = status
            logger.info("server %s status updated to %s", server_ip, status)
        pass

    def update_server_position(self, server_ip, new_position):
        """update server position

        :param server_ip:
        :param new_position: (switch_dpid, switch_port)
        :return:
        """
        new_switch = new_position[0]
        new_port = new_position[1]
        if server_ip in self.servers_based_on_ip:
            server_type, server_switch, switch_port = self.servers_based_on_ip[server_ip]
            if server_switch == new_switch and switch_port == new_port:
                # no necessary to update
                logger.debug("server position unchanged, %s:(%s, %s)",
                             server_ip, new_switch, new_port)
                return

            # update self.servers_based_on_port
            del self.servers_based_on_port[(server_switch, switch_port)]
            self.servers_based_on_port[new_position] = (server_ip, server_type)

            # update self.servers_based_on_ip
            self.servers_based_on_ip[server_ip] = (server_type, new_switch, new_port)

            # update self.servers_based_on_type
            servers = self.servers_based_on_type[server_type]
            index = servers.index((server_ip, server_switch, switch_port))
            servers.pop(index)
            servers.append((server_ip, new_switch, new_port))
            logger.info("server position updated, %s:(%s, %s)",
                        server_ip, new_switch, new_port)
        else:
            logger.debug("do not contain %s:(%s, %s)",
                         server_ip, new_switch, new_port)
        pass

    def update_port_type(self, switches):
        """update switch port type such as edge_switch_to_server_ports.

        :param switches: topology switch information, SwitchTable()
        :return:
        """
        for dpid in switches:
            sw = switches.get_switch(dpid)
            if sw.attribute == sw.AttributeEnum.core:
                # set core switch port to intra topology
                for port_no in sw.ports:
                    if sw.ports[port_no].is_reserved():
                            continue
                    port_index = (dpid, port_no)
                    self.intra_topo_ports.append(port_index)
                pass
            elif sw.attribute == sw.AttributeEnum.aggregation:
                # set aggregation switch port to intra topology
                for port_no in sw.ports:
                    if sw.ports[port_no].is_reserved():
                            continue
                    port_index = (dpid, port_no)
                    self.intra_topo_ports.append(port_index)
                pass
            elif sw.attribute == sw.AttributeEnum.edge:
                neighbor_ports_list = []
                # set edge switch port to intra topology(to core/aggregation switch)
                for neighbor_dpid in sw.neighbors:
                    port_no = sw.neighbors[neighbor_dpid][0]
                    neighbor_ports_list.append(port_no)
                    neighbor_sw = switches.get_switch(neighbor_dpid)
                    if neighbor_sw.attribute == neighbor_sw.AttributeEnum.core or \
                       neighbor_sw.attribute == neighbor_sw.AttributeEnum.aggregation:
                        if sw.ports[port_no].is_reserved():
                            continue
                        port_index = (dpid, port_no)
                        self.edge_switch_to_topo_ports.append(port_index)
                # set edge switch port to server(unset attribute port)
                for port_no in sw.ports:
                    if port_no not in neighbor_ports_list:
                        if sw.ports[port_no].is_reserved():
                            continue
                        port_index = (dpid, port_no)
                        self.edge_switch_to_server_ports.append(port_index)
                pass
            elif sw.attribute == sw.AttributeEnum.access:
                neighbor_ports_list = []
                # set access switch port to intra topology(to core switch)
                for neighbor_dpid in sw.neighbors:
                    port_no = sw.neighbors[neighbor_dpid][0]
                    neighbor_ports_list.append(port_no)
                    neighbor_sw = switches.get_switch(neighbor_dpid)
                    if neighbor_sw.attribute == neighbor_sw.AttributeEnum.core:
                        if sw.ports[port_no].is_reserved():
                            continue
                        port_index = (dpid, port_no)
                        self.access_switch_to_topo_ports.append(port_index)
                # set access switch port to user(unset attribute port)
                for port_no in sw.ports:
                    if port_no not in neighbor_ports_list:
                        if sw.ports[port_no].is_reserved():
                            continue
                        port_index = (dpid, port_no)
                        self.access_switch_to_user_ports.append(port_index)
                pass
            else:
                logger.warning("unset switch attribute: %s",
                               sw.attribute)
                continue
        pass

    def get_server_mac_by_ip(self, server_ip):
        if server_ip in self.server_ip_mac_dict:
            return self.server_ip_mac_dict[server_ip]
        else:
            return None

    def classify_link_fault_type(self, src_port, dst_port):
        """
            classify fault link type by src & dst switch dpid and port_no,
            return type in subclass of FaultTypeBase.
        """
        src_switch_dpid = src_port.dpid
        src_port_no = src_port.port_no
        src_port_index = (src_switch_dpid, src_port_no)

        dst_switch_dpid = dst_port.dpid
        dst_port_no = dst_port.port_no
        dst_port_index = (dst_switch_dpid, dst_port_no)

        if src_port_index in self.edge_switch_to_server_ports or \
                dst_port_index in self.edge_switch_to_server_ports:
            link_fault = ServerToEdgeSwitchFault()
        elif src_port_index in self.access_switch_to_user_ports or \
                dst_port_index in self.access_switch_to_user_ports:
            link_fault = UserToAccessSwitchFault()
        elif src_port_index in self.access_switch_to_topo_ports or \
                dst_port_index in self.access_switch_to_topo_ports:
            link_fault = AccessSwitchToTopoFault()
        else:
            link_fault = IntraTopoFault()

        return link_fault

    def classify_port_fault_type(self, fault_port):
        pass

    def update_port_types(self):
        pass

    def update_server_types(self):
        pass


class FaultTypeBase(object):
    def __init__(self, *args, **kwargs):
        pass

    def dispatch_flow_entry(self, link_list, route_request):
        pass

    def recovery_path(self, route_request, servers, former_route_path, task_entry):
        pass


class ServerToEdgeSwitchFault(FaultTypeBase):
    def __init__(self, *args, **kwargs):
        super(ServerToEdgeSwitchFault, self).__init__()

        self.fault_classifier = FaultClassifier()
        self.routing_algorithm = Dijkstra()

    def recovery_path(self, route_request, servers, former_route_path, task_entry):
        src_dpid = route_request.src_dpid
        src_port_no = route_request.src_port_no
        dst_dpid = route_request.dst_dpid
        dst_port_no = route_request.dst_port_no

        # find deleted server
        delete_server_ip, delete_server_type, delete_server_switch, switch_port = \
            self._find_delete_server(src_dpid, src_port_no, dst_dpid, dst_port_no)

        # find all redundancy servers
        all_redundancy_servers, same_switch_redundancy_servers = \
            self._find_all_redundancy_servers(delete_server_ip, delete_server_type, delete_server_switch, switch_port)

        # choose alternative server
        same_switch_server, chosen_alternative_server = \
            self._choose_alternative_server(all_redundancy_servers, same_switch_redundancy_servers)
        (chosen_server_ip, chosen_server_switch, chosen_switch_port) = chosen_alternative_server

        # calculate new route path
        link_list = self._calculate_route_path(same_switch_server, chosen_alternative_server, chosen_server_switch,
                                               former_route_path, route_request, servers)
        server_ip = chosen_alternative_server[0]
        to_server_port_no = chosen_alternative_server[2]
        server_mac = self.fault_classifier.get_server_mac_by_ip(server_ip)
        task_entry.update_attribute(dst_ip=server_ip, dst_port_no=to_server_port_no, server_mac=server_mac)

        # Here may be rewrite for improve: for the same switch server, we just need to change the flow entries 
        # in edge switch and access switch(NAT strategy) 
        task_entry.deploy_flow_table(link_list=link_list, link_cost=None)
        # if same_switch_server:
        #     self.dispatch_same_switch_flow_entry(chosen_server_switch, server_ip, to_server_port_no, route_request)
        # else:
        #     self.dispatch_flow_entry(link_list, route_request, server_ip, to_server_port_no)
        logger.info('request from %s to %s, new server ip:%s, route path:%s',
                    route_request.src_ip, route_request.dst_ip, server_ip, link_list)
        pass

    def _find_delete_server(self, src_switch_dpid, src_port_no, dst_switch_dpid, dst_port_no):
        src_port_index = (src_switch_dpid, src_port_no)
        dst_port_index = (dst_switch_dpid, dst_port_no)
        if dst_port_index in self.fault_classifier.servers_based_on_port:
            (server_ip, server_type) = self.fault_classifier.servers_based_on_port[dst_port_index]
            (server_switch, switch_port) = dst_port_index
        else: 
            logger.exception('The delete server is not in the servers maintained by fault_classifier!')
            return None, None, None, None
        return server_ip, server_type, server_switch, switch_port

    def _find_all_redundancy_servers(self, delete_server_ip, delete_server_type, delete_server_switch, switch_port):
        all_redundancy_servers = []
        same_switch_redundancy_servers = []

        if delete_server_type in self.fault_classifier.servers_based_on_type:
            all_redundancy_servers = self.fault_classifier.servers_based_on_type[delete_server_type]
        else:
            logger.exception('There is no redundancy server for %s', delete_server_type)

        while (delete_server_ip, delete_server_switch, switch_port) in all_redundancy_servers:
            all_redundancy_servers.remove((delete_server_ip, delete_server_switch, switch_port))
            pass

        for each_server in all_redundancy_servers:
            (each_server_ip, each_server_switch, each_switch_port) = each_server
            if self.fault_classifier.servers_state_based_on_port[(each_server_switch, each_switch_port)] == \
                    SERVER_STATE_DOWN:
                i = all_redundancy_servers.index((each_server_switch, each_switch_port))
                all_redundancy_servers.pop(i)
            if each_server_switch == delete_server_switch:
                same_switch_redundancy_servers.append(each_server)
                pass
            pass
        return all_redundancy_servers, same_switch_redundancy_servers

    @staticmethod
    def _choose_alternative_server(all_redundancy_servers, same_switch_redundancy_servers):
        same_switch_server = False
        if ChooseSameSwitchServer:
            if len(same_switch_redundancy_servers) != 0:
                random_index = random.randint(0, len(same_switch_redundancy_servers)-1)
                chosen_alternative_server = same_switch_redundancy_servers[random_index]
                same_switch_server = True
                return same_switch_server, chosen_alternative_server
            elif (len(same_switch_redundancy_servers) == 0) and (len(all_redundancy_servers) != 0):
                random_index = random.randint(0, len(all_redundancy_servers)-1)
                chosen_alternative_server = all_redundancy_servers[random_index]
                return same_switch_server, chosen_alternative_server
            else:
                logger.exception('There is no redundancy server!')
        else:
            if len(all_redundancy_servers) != 0:
                random_index = random.randint(0, len(all_redundancy_servers))
                chosen_alternative_server = all_redundancy_servers[random_index]
                return same_switch_server, chosen_alternative_server
            else:
                logger.exception('There is no redundancy server!')

    def _calculate_route_path(self, same_switch_server, chosen_alternative_server,
                              chosen_alternative_server_switch, former_route_path, route_request, servers):
        server_ip = chosen_alternative_server[0]
        if same_switch_server:
            link_list = former_route_path
            return link_list
        else:
            # Here may be an improve port. Can we use the former routing path?
            self.routing_algorithm.run(route_request.src_dpid, chosen_alternative_server_switch,
                                       BusinessType[servers[server_ip]])
            link_list, link_cost = self.routing_algorithm.get_link(route_request.src_dpid,
                                                                   chosen_alternative_server_switch)
            return link_list


class IntraTopoFault(FaultTypeBase):
    def __init__(self, *args, **kwargs):
        super(IntraTopoFault, self).__init__()
        self.routing_algorithm = Dijkstra()
        pass

    def recovery_path(self, route_request, servers, former_route_path, task_entry):
        self.routing_algorithm.run(route_request.src_dpid, route_request.dst_dpid,
                                   BusinessType[servers[route_request.dst_ip]])
        link_list, link_cost = self.routing_algorithm.get_link(route_request.src_dpid,
                                                               route_request.dst_dpid)

        if link_list is None:
            # TODO: try to use redundancy server
            logger.error("route path calculate failed/ no path exist, recovery failed.")
            return

        task_entry.deploy_flow_table(link_list=link_list, link_cost=None)
        logger.info('request from %s to %s, recalculated route path:%s',
                    route_request.src_ip, route_request.dst_ip, link_list)


class AccessSwitchToTopoFault(FaultTypeBase):
    def __init__(self, *args, **kwargs):
        super(AccessSwitchToTopoFault, self).__init__()
        pass
    
    def recovery_path(self, src_dpid, dst_dpid, min_bandwidth, task_entry):
        pass


class UserToAccessSwitchFault(FaultTypeBase):
    def __init__(self, *args, **kwargs):
        super(UserToAccessSwitchFault, self).__init__()
        pass
    
    def recovery_path(self, src_dpid, dst_dpid, min_bandwidth, task_entry):
        pass


class FaultRecoveryDataMaintainer(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(FaultRecoveryDataMaintainer, self).__init__(req, link, data, **config)
        self.fault_classifier = FaultClassifier()
        
    @route('fault_recover', '/fault_recovery/init_server', methods='POST')
    def init_server_types(self, req, **kwargs):
        # initialize the servers
        # server message in config file is a list, for example, it can be:
        # [{'10.0.0.1': 'VIDEO,3001,2'}]
        logger.warning("[FaultRecoveryDataMaintainer.init_server_types]"
                       "this method is abandoned")
        # logger.info('receive initialize server type message!')
        # server_message = json.loads(req.body)
        # for server_ip_unicode, server_info in server_message.items():
        #     server_ip = str(server_ip_unicode)
        #     server_info_str_list = str(server_info).split(',')
        #     server_type, server_switch, switch_port, server_state, server_mac_addr = server_info_str_list
        #     server_switch_int = int(server_switch)
        #     switch_port_int = int(switch_port)
        #     if server_type in self.fault_classifier.servers_based_on_type:
        #         servers_in_type = self.fault_classifier.servers_based_on_type[server_type]
        #         servers_in_type.append((server_ip, server_switch_int, switch_port_int))
        #         self.fault_classifier.servers_based_on_type[server_type] = servers_in_type
        #     else:
        #         self.fault_classifier.servers_based_on_type[server_type] = \
        #             [(server_ip, server_switch_int, switch_port_int)]
        #
        #     self.fault_classifier.servers_based_on_ip[server_ip] = (server_type, server_switch_int, switch_port_int)
        #     self.fault_classifier.servers_based_on_port[(server_switch_int, switch_port_int)] = (server_ip, server_type)
        #     self.fault_classifier.servers_state_based_on_port[(server_switch_int, switch_port_int)] = server_state
        #     self.fault_classifier.server_ip_mac_dict[server_ip] = server_mac_addr
        # pass
    
    @route('fault_recover', '/fault_recovery/init_port', methods='POST')
    def init_port_types(self, req, **kwargs):
        # TODO: init when topology manage init finshed
        # initialize the ports
        # port message is a dictionary, for example, it can be:
        # {'(3005, 3)': 1, '(3001, 3)': 1}
        logger.warning("[FaultRecoveryDataMaintainer.init_port_types]"
                       "this method is deprecated")
        logger.info('receive initialize port message!')
        msg = json.loads(req.body)
        for original_port_index, port_type in msg.items():
            port_type_int = int(port_type)
            port_index_str_list = str(original_port_index).split(',')
            port_index_switch = int(port_index_str_list[0])
            port_index_port_no = int(port_index_str_list[1])
            port_index = (port_index_switch, port_index_port_no)
            if port_type_int == PortType_EdgeSwitchToServer:
                self.fault_classifier.edge_switch_to_server_ports.append(port_index)
            elif port_type_int == PortType_AccessSwitchToUser:
                self.fault_classifier.access_switch_to_user_ports.append(port_index)
            elif port_type_int == PortType_AccessSwitchToTopo:
                self.fault_classifier.access_switch_to_topo_ports.append(port_index)
            elif port_type_int == PortType_EdgeSwitchToTopo:
                self.fault_classifier.edge_switch_to_topo_ports.append(port_index)
            elif port_type_int == PortType_IntraTopo:
                self.fault_classifier.intra_topo_ports.append(port_index)
        pass
