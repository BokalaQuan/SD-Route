import logging

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)


class RequestInfo(object):
    def __init__(self, request_type=None, network_layer_type=None, transport_layer_type=None,
                 src_datapath=None, src_dpid=None, src_mac=None, src_ip=None, src_port_no=None,
                 dst_datapath=None, dst_dpid=None, dst_mac=None, dst_ip=None, dst_port_no=None,
                 switches=None):
        self.request_type = request_type
        self.network_layer_type = network_layer_type
        self.transport_layer_type = transport_layer_type
        self.src_datapath = src_datapath
        self.src_dpid = src_dpid
        self.src_mac = src_mac
        self.src_ip = src_ip
        self.src_port_no = src_port_no
        self.dst_datapath = dst_datapath
        self.dst_dpid = dst_dpid
        self.dst_mac = dst_mac
        self.dst_ip = dst_ip
        self.dst_port_no = dst_port_no
        self.switches = switches


class RouteInfoMaintainer(object):
    # singleton class, used to maintain the route information
    _instances = 0

    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'request_info_dic'):
            # explanation of self.request_info_dic: {link:(request,path)}
            self.request_info_dic = {}
            self.request_info_dic_port = {}
            
            self.link_path_old = []
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(RouteInfoMaintainer, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def update(self, route_manage, fault_recovery, task_entry, link_list):
        """update request route/port info in RouteInfoMaintainer

        :param route_manage: RouteManage instance
        :param fault_recovery: fault_recovery_main instance
        :param task_entry: request task entry
        :param link_list: route path result
        :return:
        """
        request_info = RequestInfo(request_type=None, network_layer_type=None, transport_layer_type=None,
                                   src_datapath=None, src_dpid=task_entry.src_dpid, src_mac=None,
                                   src_ip=task_entry.src_ip, src_port_no=task_entry.src_port_no,
                                   dst_datapath=None, dst_dpid=task_entry.dst_dpid,
                                   dst_mac=None, dst_ip=task_entry.dst_ip, dst_port_no=task_entry.dst_port_no,
                                   switches=route_manage.switches)
        route_info = {'path': link_list,
                      'request': request_info,
                      'task_entry': task_entry}

        # self.update_request_info_for_link(fault_recovery, route_info)
        # self.update_request_info_for_ports(route_manage, route_info)

    def update_request_info_for_link(self, fault_recovery, route_info):
        if fault_recovery.DATA_STORE_METHOD == fault_recovery.IMPROVED_STORE_METHOD:
            self._update_route_info(route_info)
        elif fault_recovery.DATA_STORE_METHOD == fault_recovery.OLD_STORE_METHOD:
            self._update_route_info_old(route_info)

        logger.debug('instance of route_info_maintainer in RouteManage is: ', self)

    def update_request_info_for_ports(self, route_manage, route_info):
        switches = route_manage.switches

        fault_classifier = route_manage.fault_classifier

        link_list = route_info['path']
        task_entry = route_info['task_entry']

        if len(link_list) == 1:
            dpid = switches.get_switch(link_list[0]).dp.id
            dst_port_index = (dpid, task_entry.dst_port_no)
            if dst_port_index in fault_classifier.edge_switch_to_server_ports:
                self._update_route_info_port(dst_port_index, route_info)
        elif len(link_list) > 1:
            sw1 = switches.get_switch(link_list[0])
            sw2 = switches.get_switch(link_list[len(link_list) - 1])
            src_dpid = sw1.dp.id
            dst_dpid = sw2.dp.id
            dst_port_index = (dst_dpid, task_entry.dst_port_no)
            src_port_index = (src_dpid, task_entry.src_port_no)
            if dst_port_index in fault_classifier.edge_switch_to_server_ports:
                self._update_route_info_port(dst_port_index, route_info)
            elif src_port_index in fault_classifier.edge_switch_to_server_ports:
                self._update_route_info_port(src_port_index, route_info)
        else:
            logger.debug("None port modified!!")

    def get_route_info(self):
        logger.debug('get route info, request_info_dic is: %s', self.request_info_dic)
        return self.request_info_dic

    def get_route_info_by_port(self):
        logger.debug('get route info, request_info_dic_port is: %s', self.request_info_dic_port)
        return self.request_info_dic_port

    def get_route_info_old(self):
        return self.link_path_old

    def _update_route_info(self, route_info):
        route_request_info = route_info['request']
        route_path = route_info['path']
        task_entry = route_info['task_entry']
        route_path_length = len(route_path)

        for current_switch_index in range(route_path_length-1)[::-1]:
            current_switch = route_path[current_switch_index]
            next_switch = route_path[current_switch_index+1]
            link_path_dic_index = (current_switch, next_switch)
            if self.request_info_dic in link_path_dic_index:
                self.request_info_dic[link_path_dic_index].append((route_request_info, route_path, task_entry))
            else:
                self.request_info_dic[link_path_dic_index] = [(route_request_info, route_path, task_entry)]

        logger.debug('update route info, request_info_dic is: %s', self.request_info_dic)

    def _update_route_info_old(self, route_info):
        route_path = route_info['path']
        self.link_path_old.append(route_path)

    def _update_route_info_port(self, port_index, route_info):
        route_request_info_list = route_info['request']
        route_path = route_info['path']
        task_entry = route_info['task_entry']

        if port_index in self.request_info_dic_port:
            old_request_info_list = self.request_info_dic_port[port_index]
            old_request_info_list.append((route_request_info_list, route_path, task_entry))
            new_request_info_list = old_request_info_list
            self.request_info_dic_port[port_index] = new_request_info_list
        else:
            self.request_info_dic_port[port_index] = [(route_request_info_list, route_path, task_entry)]

        logger.debug('update route info, request_info_dic_port is: %s', self.request_info_dic_port)
