import logging

from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication

from cluster_manage import ClusterManage, ClusterManageRestController
from host_manage.HostTrack import EventHostState, MacEntry
from fault_recovery.fault_classifier import FaultClassifier
from base.parameters import SERVER_STATE_DOWN, SERVER_STATE_UP

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

cluster_manage_instance_name = 'cluster_manage_app'


class HostManageMain(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(HostManageMain, self).__init__(*args, **kwargs)

        # server business type: {ip: BusinessType[]}
        self.servers = {}

        # mac_to_port
        self.mac_to_port = None
        self.entry = {}
        self.cluster_manage = ClusterManage()
        self.fault_classifier = FaultClassifier()

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(ClusterManageRestController, {cluster_manage_instance_name: self})

    @set_ev_cls(EventHostState, MAIN_DISPATCHER)
    def host_state_handler(self, ev):
        """
            handle host state event from module HostTrack,
            update host tracing information.
        """
        self.mac_to_port = ev.mac_to_port
        if ev.join:
            # logger.info("[host join]entry updated:%s", ev.entry)
            # self.entry[ev.entry.macaddr] = ev.entry
            for server_ip in ev.entry.ipaddrs.keys():
                self.cluster_manage.update_server_status(server_ip, SERVER_STATE_UP)
                self.fault_classifier.update_server_position(server_ip,
                                                             (ev.entry.dpid, ev.entry.port))
                self.fault_classifier.update_server_status(server_ip, SERVER_STATE_UP)
            pass
        elif ev.move:
            # logger.info("[host move]entry updated:%s origin:%s",
            #             ev.entry, self.entry[ev.entry.macaddr])
            # self.entry[ev.entry.macaddr] = ev.entry
            pass
        elif ev.leave:
            # logger.info("[host leave]entry updated:%s", ev.entry)
            # del self.entry[ev.entry.macaddr]
            for server_ip in ev.entry.ipaddrs.keys():
                self.cluster_manage.update_server_status(server_ip, SERVER_STATE_DOWN)
                # TODO: update server status in fault_classifier may cause recovery failure
                # when server status is set to DOWN before recovery triggered.
                self.fault_classifier.update_server_status(server_ip, SERVER_STATE_DOWN)
            pass
