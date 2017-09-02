import time
import logging

from ryu.controller.handler import set_ev_cls
from ryu.app.wsgi import WSGIApplication
from ryu.ofproto import ofproto_v1_3
from ryu.base import app_manager
from base.parameters import SERVER_STATE_DOWN
from fault_recovery import fault_recovery_event
from fault_recovery.fault_classifier import FaultClassifier, FaultRecoveryDataMaintainer
from fault_recovery.fault_classifier import ServerToEdgeSwitchFault
from route_manage.route_info_maintainer import RequestInfo, RouteInfoMaintainer

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

servers = {}
fault_recovery_instance_name = 'fault_recovery_main_instance'

# 'improved' for improved structure while 'old' for old structure
IMPROVED_STORE_METHOD = 'improved'
OLD_STORE_METHOD = 'old'
DATA_STORE_METHOD = IMPROVED_STORE_METHOD


class FaultRecoveryMain(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(FaultRecoveryMain, self).__init__(*args, **kwargs)
        self.fault_classifier = FaultClassifier()

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(FaultRecoveryDataMaintainer, {fault_recovery_instance_name: self})

    @set_ev_cls(fault_recovery_event.EventFaultRecoveryLinkDelete)
    def link_delete_handler(self, ev):
        """
            try to recovery when link is down.
        """
        src_port = ev.src_port
        src_switch_dpid = src_port.dpid
        dst_port = ev.dst_port
        dst_switch_dpid = dst_port.dpid

        # get fault type by src & dst switch port.
        link_fault = self.fault_classifier.classify_link_fault_type(src_port, dst_port)

        failure_link_index = (src_switch_dpid, dst_switch_dpid)
        reverse_failure_link_index = (dst_switch_dpid, src_switch_dpid)

        if DATA_STORE_METHOD == IMPROVED_STORE_METHOD:
            affected_route_requests = self._find_affected_route_requests(failure_link_index,
                                                                         reverse_failure_link_index)
        elif DATA_STORE_METHOD == OLD_STORE_METHOD:
            affected_route_requests = self._find_affected_route_requests_old(failure_link_index,
                                                                             reverse_failure_link_index)
        else:
            logger.exception("unsupported method:%s", DATA_STORE_METHOD)
            return

        # try to recovery all affected route requests.
        if affected_route_requests:
            logger.info('affected route %s requests', len(affected_route_requests))
            for (route_request, route_path, task_entry) in affected_route_requests:
                if isinstance(route_request, RequestInfo):
                    link_fault.recovery_path(route_request, servers, route_path, task_entry)
                else:
                    raise TypeError('The type of request is not RequestInfo!')
                pass
            pass

        # calculate recovery time cost.
        recovery_spend_time = time.time() - ev.timestamp
        logger.info('recover fault link success, time cost: %s', recovery_spend_time)

    @set_ev_cls(fault_recovery_event.EventFaultRecoveryPortDown)
    def port_modify_handler(self, ev):
        """
            try to recovery when port is down.
            ONLY handle the port which is connect to host.
        """
        port = ev.port
        port_switch = port.dpid
        port_no = port.port_no
        port_index = (port_switch, port_no)

        port_fault = ServerToEdgeSwitchFault()

        logger.info('Receive port down event! The delete switch is: %s, port_no is: %s',
                    port_switch, port_no)
        if self.fault_classifier.servers_state_based_on_port[port_index] == SERVER_STATE_DOWN:
            logger.info('This port down event has already been handled, so ignore this event!')
            return

        if port_index in self.fault_classifier.edge_switch_to_server_ports:
            self.fault_classifier.servers_state_based_on_port[port_index] = SERVER_STATE_DOWN
            affected_route_request = self._find_affected_route_path_by_port(port_index)
            if affected_route_request is not None:
                for (route_request, route_path, task_entry) in affected_route_request:
                    port_fault.recovery_path(route_request, servers, route_path, task_entry)
                    pass
            pass
        else:
            return
        pass

    @staticmethod
    def _find_affected_route_requests(failure_link_index, reverse_failure_link_index):
        find_affected_request_start_time = time.time()

        route_info_maintainer = RouteInfoMaintainer()
        request_info_dic = route_info_maintainer.get_route_info()

        if not request_info_dic:
            return None
        else:
            if failure_link_index in request_info_dic:
                affected_route_requests_and_path = request_info_dic[failure_link_index]
            elif reverse_failure_link_index in request_info_dic:
                affected_route_requests_and_path = request_info_dic[reverse_failure_link_index]
            else:
                return None

        find_affected_request_end_time = time.time()
        find_affected_request_spend_time = find_affected_request_end_time - find_affected_request_start_time
        logger.info('use improved methods, find affected request spent %s seconds!',
                    find_affected_request_spend_time)

        return affected_route_requests_and_path

    @staticmethod
    def _find_affected_route_path_by_port(port_index):
        route_info_maintainer = RouteInfoMaintainer()
        request_info_dic_by_port = route_info_maintainer.get_route_info_by_port()

        if not request_info_dic_by_port:
            return None
        else:
            if port_index in request_info_dic_by_port:
                affected_route_requests_and_path = request_info_dic_by_port[port_index]
            else:
                return None

        return affected_route_requests_and_path

    @staticmethod
    def _find_affected_route_requests_old(failure_link_index, reverse_failure_link_index):
        find_affected_request_start_time = time.time()

        route_info_maintainer = RouteInfoMaintainer()
        link_path_old = route_info_maintainer.get_route_info_old()
        affected_route_path = []

        for route_path in link_path_old:
            route_path_length = len(route_path)
            for current_switch_index in range(route_path_length - 1):
                next_switch_index = current_switch_index + 1
                if (route_path[current_switch_index], route_path[next_switch_index]) == failure_link_index:
                    affected_route_path.append(failure_link_index)
                elif (route_path[current_switch_index], route_path[next_switch_index]) == reverse_failure_link_index:
                    affected_route_path.append(reverse_failure_link_index)

        find_affected_request_end_time = time.time()
        find_affected_request_spend_time = find_affected_request_end_time - find_affected_request_start_time
        logger.info('use old method, find affected request spent %s seconds!',
                    find_affected_request_spend_time)

        return affected_route_path
