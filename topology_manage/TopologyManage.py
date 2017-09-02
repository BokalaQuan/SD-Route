import logging
import json
import os
import time

from webob import Response

import ryu.utils
from ryu import topology
from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import (HANDSHAKE_DISPATCHER, MAIN_DISPATCHER, CONFIG_DISPATCHER)
from ryu.controller import ofp_event
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.dpid import dpid_to_str, str_to_dpid
from ryu.lib.port_no import port_no_to_str
from ryu.app.wsgi import ControllerBase, WSGIApplication, route

from object.switch import SwitchTable
from object.port import Port
from object.link import Link, LinkTable, LinkTableApi
from topology_manage.object import topo_event
from lib.project_lib import Megabits
from link_monitor.link_monitor_main import LinkMonitor


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

route_manage_instance_name = 'route_manage_app'
rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})

TOPO_INIT_FINISH_TIME = 8

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
# LINK_CONF_FILE_PATH = FILE_PATH + '/conf/link_info.conf'
# SWITCH_CONF_FILE_PATH = FILE_PATH + '/conf/switch_info.conf'
# LINK_CONF_FILE_PATH = FILE_PATH + '/conf/link_info.json'
# SWITCH_CONF_FILE_PATH = FILE_PATH + '/conf/switch_info.json'

LINK_CONF_FILE_PATH = '/home/bokala/PycharmProjects/SD-Route/example/topo_custom/topo_file/link_info.json'
SWITCH_CONF_FILE_PATH = '/home/bokala/PycharmProjects/SD-Route/example/topo_custom/topo_file/switch_info.json'


class TopologyManage(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _EVENTS = [topo_event.EventSwitchAdd, topo_event.EventSwitchDel,
               topo_event.EventLinkAdd, topo_event.EventLinkDel,
               topo_event.EventSwitchReply, topo_event.EventLinkReply,
               topo_event.EventLinkDelUpdateTopo, topo_event.EventPortDownUpdateTopo,
               topo_event.EventTopoInitializeEnd]

    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(TopologyManage, self).__init__(*args, **kwargs)

        # switches[dpid] = Switch
        self.switches = SwitchTable()

        # links[(src_dpid, dst_dpid)] = Link
        self.links = LinkTable()

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(TopologyManageRestController, {route_manage_instance_name: self})

        self.send_topo_initialize_end_thread = None
        self.start_link_monitor_thread = None

    @set_ev_cls(topology.event.EventSwitchEnter)
    def switch_enter_handler(self, event):
        """
            event handler triggered when switch enter.
        """
        dpid = event.switch.dp.id
        self.switches.add_switch(dpid, event.switch.dp, self.switches)
        logger.debug('switch enter (dpid=%s)', dpid_to_str(dpid))

    @set_ev_cls(topology.event.EventSwitchLeave)
    def switch_leave_handler(self, event):
        """
            event handler triggered when switch leave.
            delete the Switch object directly.
            where sending EventSwitchDel event.
        """
        dpid = event.switch.dp.id

        switch = self.switches.get_switch(dpid)
        for neighbor_dpid, port_no_list in switch.neighbors.items():
            # clean invalid neighbor switch.neighbors
            del self.switches.get_switch(neighbor_dpid).neighbors[dpid]
            # clean invalid virtual link
            self.links.del_all_virtual_link(neighbor_dpid, dpid)

        self.switches.del_switch(dpid)

        self.send_event_to_observers(topo_event.EventSwitchDel(dpid))
        logger.debug('switch leave (dpid=%s)', dpid_to_str(dpid))

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER])
    def switch_state_change_handler(self, event):
        """
            event handler when switch state change from 'config mode'
            to 'main mode', update switch information.
            where sending EventSwitchAdd event.
        """
        dpid = event.datapath.id

        self.switches.add_switch(dpid, event.datapath, self.switches)
        switch = self.switches.get_switch(dpid)

        switch.attribute = switch.AttributeEnum.edge

        for port_no, port in event.datapath.ports.iteritems():
            if port_no not in switch.ports:
                switch.ports.add_port(port_no, port, event.datapath)

            if port_no == ofproto_v1_3.OFPP_LOCAL:
                switch.name = port.name.rstrip('\x00')
            else:
                switch.name = str(event.datapath.address[0])

        self.send_event_to_observers(topo_event.EventSwitchAdd(switch))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def clean_flow_table(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        inst = []
        mod = parser.OFPFlowMod(datapath=datapath, table_id=ofproto.OFPTT_ALL,
                                command=ofproto.OFPFC_DELETE,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPP_ANY,
                                match=match,
                                instructions=inst)
        datapath.send_msg(mod)

        logger.debug("Clearing flow table on %s ",
                     dpid_to_str(datapath.id))

    @set_ev_cls(topology.event.EventPortAdd)
    def port_add_handler(self, event):
        """
            event handler triggered when port added.
            get Switch instance and create a Port object.
        """
        port = Port(event.port)
        try:
            switch = self.switches.get_switch(port.dpid)
            switch.ports.add_port(port.port_no, port)
        except KeyError:
            pass

        logger.debug('port added, port_no=%s (dpid=%s)',
                     port_no_to_str(port.port_no),
                     dpid_to_str(port.dpid))

    @set_ev_cls(topology.event.EventPortModify)
    def port_modify_handler(self, event):
        """
            event handler triggered when port modified (switch still
            own modified port, such as fiber inserted or pulled out).

            WARNING: ryu v3.24
            when port state is DOWN and then port state changes to
            LIVE, system would send a DOWN event before LIVE event.
        """
        new_port = Port(event.port)
        try:
            switch = self.switches.get_switch(new_port.dpid)
        except KeyError:
            return

        record_port = switch.ports.get_port(new_port.port_no)
        record_port_state = record_port.get_port_state()
        new_port_state = new_port.get_port_state()

        if record_port_state == new_port_state:
            # port state not changed
            logger.debug("port state not changed, sw %s port %s state: %s",
                         new_port.dpid, new_port.port_no, new_port_state)
            return

        timestamp = time.time()

        # when port state changed
        if record_port_state == ofproto_v1_3.OFPPR_DELETE and \
                new_port_state == ofproto_v1_3.OFPPR_ADD:
            # port state changed from DOWN to LIVE
            logger.debug("port state changed from DOWN to LIVE.")
            record_port.set_port_state(new_port_state)
            self.send_event_to_observers(
                topo_event.EventPortDownUpdateTopo(event.port, timestamp))
            pass
        elif record_port_state == ofproto_v1_3.OFPPR_ADD and \
                new_port_state == ofproto_v1_3.OFPPR_DELETE:
            # port state changed from LIVE to DOWN
            logger.debug("port state changed from LIVE to DOWN.")
            record_port.set_port_state(new_port_state)
            self.send_event_to_observers(
                topo_event.EventPortDownUpdateTopo(event.port, timestamp))
            pass
        else:
            logger.warning("other state changing at sw %s port %s, "
                           "origin state:%s, new state:%s",
                           new_port.dpid, new_port.port_no,
                           record_port_state, new_port_state)
            pass

    @set_ev_cls(topology.event.EventPortDelete)
    def port_delete_handler(self, event):
        """
            event handler triggered when port deleted(ovs-vsctl del-port).
            get Switch instance and delete specific Port object.
        """
        port = Port(event.port)
        try:
            switch = self.switches.get_switch(port.dpid)
            switch.ports.del_port(port.port_no)
        except KeyError:
            pass

        logger.debug('port deleted, port_no=%s (dpid=%s)',
                     port_no_to_str(port.port_no),
                     dpid_to_str(port.dpid))

    @set_ev_cls(topology.event.EventLinkAdd)
    def link_add_handler(self, event):
        """
            populate link information from event argument,
            then update switch neighbor information.
            where sending EventLinkAdd event.
        """
        if self.send_topo_initialize_end_thread is not None:
            hub.kill(self.send_topo_initialize_end_thread)

        # change by Bokala
        #
        if self.start_link_monitor_thread is not None:
            hub.kill(self.start_link_monitor_thread)

        src_dpid = event.link.src.dpid
        src_switch = self.switches.get_switch(src_dpid)
        src_datapath = src_switch.dp
        src_port = Port(port=event.link.src, datapath=src_datapath)

        dst_dpid = event.link.dst.dpid
        dst_switch = self.switches.get_switch(dst_dpid)
        dst_datapath = dst_switch.dp
        dst_port = Port(port=event.link.dst, datapath=dst_datapath)


        add_link = Link(src_port, dst_port)
        # update link
        link = self.links.add_link(add_link)

        # update switch neighbor info
        switch = self.switches.get_switch(src_port.dpid)
        try:
            switch.ports.get_port(src_port.port_no)
        except KeyError:
            switch.ports.add_port(src_port.port_no, src_port)

        self.switches.set_neighbor(src_port.dpid, dst_port.dpid, src_port.port_no)

        if link:
            self.send_event_to_observers(topo_event.EventLinkAdd(link))
            logger.debug('link connected: %s->%s', dpid_to_str(switch.dp.id),
                         dpid_to_str(dst_port.dpid))

        api_links = LinkTableApi()
        api_links.init(self.links)

        self.send_topo_initialize_end_thread = hub.spawn_after(TOPO_INIT_FINISH_TIME,
                                                               self.send_event_to_observers,
                                                               ev=topo_event.EventTopoInitializeEnd(api_links))

        self.start_link_monitor_thread = hub.spawn_after(TOPO_INIT_FINISH_TIME,
                                                          self.start_link_monitor,
                                                          ev=topo_event.EventTopoInitializeEnd(api_links))

    @set_ev_cls(topology.event.EventLinkDelete)
    def link_delete_handler(self, event):
        """
            event handler triggered when link deleted.
            delete corresponding Port object then
            clear switch neighbor information.
            where sending EventLinkDel event.
        """
        timestamp = time.time()

        src_port = event.link.src
        dst_port = event.link.dst

        src_dpid, dst_dpid = self.links.del_link(event.link)

        try:
            self.switches.del_neighbor(src_port.dpid, dst_port.dpid, src_port.port_no)
            self.switches.del_neighbor(dst_port.dpid, src_port.dpid, dst_port.port_no)
        except:
            pass

        api_links = LinkTableApi()
        api_links.init(self.links)
        if src_dpid and dst_dpid:
            self.send_event_to_observers(topo_event.EventLinkDel(src_dpid, dst_dpid))
            self.send_event_to_observers(topo_event.EventLinkDelUpdateTopo(self.switches, api_links,
                                                                           src_port, dst_port, timestamp))
            logger.debug('link disconnected: %s->%s', dpid_to_str(src_port.dpid),
                         dpid_to_str(dst_port.dpid))

    @set_ev_cls(topo_event.EventSwitchRequest)
    def switch_request_handler(self, req):
        """
            triggered when receive EventSwitchRequest.
            check dpid in request, then return all switch info
            or single one by dpid.
        """
        if req.dpid:
            switch = self.switches.get_switch(req.dpid)
            rep = topo_event.EventSwitchReply(req.src, switch)
        else:
            rep = topo_event.EventSwitchReply(req.src, self.switches)

        self.reply_to_request(req, rep)

    @set_ev_cls(topo_event.EventLinkRequest)
    def link_request_handler(self, req):
        """
            triggered when receive EventLinkRequest.
            check src/dst dpid in request, then return all link info
            or single one by dpid.
        """
        if req.src_dpid and req.dst_dpid:
            link = self.links.get_link_by_dpid(req.src_dpid, req.dst_dpid)
            rep = topo_event.EventLinkReply(req.src, link)
        else:
            api_links = LinkTableApi()
            api_links.init(self.links)
            rep = topo_event.EventLinkReply(req.src, api_links)

        self.reply_to_request(req, rep)

    @set_ev_cls(ofp_event.EventOFPGetAsyncReply, MAIN_DISPATCHER)
    def get_async_reply_handler(self, event):
        """
            [DEBUG] parse async reply info from switch.
        """
        msg = event.msg

        self.logger.debug('OFPGetAsyncReply received: '
                          'packet_in_mask=0x%08x:0x%08x '
                          'port_status_mask=0x%08x:0x%08x '
                          'flow_removed_mask=0x%08x:0x%08x',
                          msg.packet_in_mask[0],
                          msg.packet_in_mask[1],
                          msg.port_status_mask[0],
                          msg.port_status_mask[1],
                          msg.flow_removed_mask[0],
                          msg.flow_removed_mask[1])

    @set_ev_cls(ofp_event.EventOFPRoleReply, MAIN_DISPATCHER)
    def role_reply_handler(self, event):
        """
            [DEBUG] parse reply about switch role info.
        """
        msg = event.msg
        ofp = msg.datapath.ofproto

        if msg.role == ofp.OFPCR_ROLE_NOCHANGE:
            role = 'NOCHANGE'
        elif msg.role == ofp.OFPCR_ROLE_EQUAL:
            role = 'EQUAL'
        elif msg.role == ofp.OFPCR_ROLE_MASTER:
            role = 'MASTER'
        elif msg.role == ofp.OFPCR_ROLE_SLAVE:
            role = 'SLAVE'
        else:
            role = 'unknown'

        self.logger.debug('OFPRoleReply received: '
                          'role=%s generation_id=%d',
                          role, msg.generation_id)

    @set_ev_cls(ofp_event.EventOFPErrorMsg,
                [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, event):
        """
            [DEBUG] parse OFP error message.
        """
        msg = event.msg

        self.logger.debug('OFPErrorMsg received: type=0x%02x code=0x%02x '
                          'message=%s',
                          msg.type, msg.code, ryu.utils.hex_array(msg.data))

    def start_link_monitor(self, ev):
        # self.init_switch_configuration()
        # self.init_link_configuration()
        self.read_switch_configuration()
        self.read_link_configuration()
        link_monitor_object = LinkMonitor()
        link_monitor_object.topo_initialize_end_handler(ev)

    def init_switch_configuration(self):
        f = open(SWITCH_CONF_FILE_PATH, 'w+')
        conf = self.switches.to_conf_format()
        fp = json.dumps(conf)
        f.write(fp)
        f.close()

    # def read_switch_configuration(self):
    #     try:
    #         f = open(SWITCH_CONF_FILE_PATH, 'r')
    #     except:
    #         logger.error("read switch configuration file failed.")
    #         return
    #     fp = f.read()
    #     conf = json.loads(fp)
    #     for item in conf:
    #         dpid = item["dpid"]
    #         sw = self.switches.get_switch(dpid)
    #         if sw:
    #             sw.attribute = str(item["switch"]["attribute"])
    #     f.close()

    def init_link_configuration(self):
        f = open(LINK_CONF_FILE_PATH, 'w+')
        conf = self.links.to_conf_format()
        fp = json.dumps(conf)
        f.write(fp)
        f.close()

    # def read_link_configuration(self):
    #     try:
    #         f = open(LINK_CONF_FILE_PATH, 'r')
    #     except:
    #         logger.info("read link configuration file failed.")
    #         return
    #     fp = f.read()
    #     conf = json.loads(fp)
    #     for item in conf:
    #         src_dpid = item["src"]
    #         dst_dpid = item["dst"]
    #         if src_dpid > dst_dpid:
    #             src_dpid, dst_dpid = dst_dpid, src_dpid
    #         links = self.links.get_link_by_dpid(src_dpid, dst_dpid)
    #         if links:
    #             links[0].delay = item["link"][0]["delay"]
    #             links[0].cost = item["link"][0]["cost"]
    #             links[0].total_band = item["link"][0]["total_band"] * Megabits
    #     f.close()

    def read_switch_configuration(self):
        try:
            f = open(SWITCH_CONF_FILE_PATH, 'r')
        except:
            logger.error("read switch configuration file failed.")
            return
        fp = f.read()
        conf = json.loads(fp)
        for item in conf:
            dpid = item["dpid"]
            sw = self.switches.get_switch(dpid)
            if sw:
                sw.attribute = str(item["attribute"])
        f.close()

    def read_link_configuration(self):
        try:
            f = open(LINK_CONF_FILE_PATH, 'r')
        except:
            logger.info("read link configuration file failed.")
            return
        fp = f.read()
        conf = json.loads(fp)
        for item in conf:
            src_dpid = item["src"]
            dst_dpid = item["dst"]
            if src_dpid > dst_dpid:
                src_dpid, dst_dpid = dst_dpid, src_dpid
            links = self.links.get_link_by_dpid(src_dpid, dst_dpid)
            if links:
                links[0].delay = item["delay"]
                links[0].pkt_loss = item["loss"]
                links[0].total_band = item["bandwidth"] * Megabits
        f.close()


class TopologyManageRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(TopologyManageRestController, self).__init__(req, link, data, **config)
        self.topo_instance = data[route_manage_instance_name]

    @route('topologymanage', '/topologymanage/switch', methods=['GET'])
    def get_all_switch(self, req, **kwargs):
        body = json.dumps(self.topo_instance.switches.to_dict())
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/switch/{dpid}', methods=['GET'])
    def get_switch_with_dpid(self, req, **kwargs):
        dpid = str_to_dpid(kwargs['dpid'])
        switch = self.topo_instance.switches.get_switch(dpid)
        if switch:
            body = json.dumps(switch.to_dict())
        else:
            body = json.dumps(rest_body_none)
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/switch/{dpid}/neighbors', methods=['GET'])
    def get_neighbor_with_dpid(self, req, **kwargs):
        dpid = str_to_dpid(kwargs['dpid'])
        switch = self.topo_instance.switches.get_switch(dpid)
        if switch:
            body = json.dumps([{'neighbor_dpid': dpid, 'port': port}
                               for (dpid, port) in switch.neighbors.items()])
        else:
            body = json.dumps(rest_body_none)
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/link', methods=['GET'])
    def get_all_link(self, req, **kwargs):
        body = json.dumps(self.topo_instance.links.to_dict())
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/link/src/{src_dpid}/dst/{dst_dpid}',
           methods=['GET'])
    def get_link_by_dpid(self, req, **kwargs):
        link = self.topo_instance.links.get_link_by_dpid(str_to_dpid(kwargs['src_dpid']),
                                                         str_to_dpid(kwargs['dst_dpid']))
        if link:
            body = json.dumps([l.to_dict() for l in link])
        else:
            body = json.dumps(rest_body_none)
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/link/src/{src_dpid}/dst/{dst_dpid}',
           methods=['POST'])
    def update_virtual_link_by_dpid(self, req, **kwargs):
        payload = json.loads(req.body)
        src_dpid = str_to_dpid(kwargs['src_dpid'])
        dst_dpid = str_to_dpid(kwargs['dst_dpid'])
        src_port_no = int(payload['src_port_no'])
        dst_port_no = int(payload['dst_port_no'])

        try:
            src_sw = self.topo_instance.switches.get_switch(src_dpid)
            src_port = src_sw.ports.get_port(src_port_no)
            dst_sw = self.topo_instance.switches.get_switch(dst_dpid)
            dst_port = dst_sw.ports.get_port(dst_port_no)
        except:
            return Response(content_type='application/json',
                            body=json.dumps(rest_body_none))

        if self.topo_instance.links.add_virtual_link(
                src_dpid, src_port, dst_dpid, dst_port) is True:
            self.topo_instance.switches.set_neighbor(int(src_dpid), int(dst_dpid), src_port_no)
            self.topo_instance.switches.set_neighbor(int(dst_dpid), int(src_dpid), dst_port_no)
            body = json.dumps(rest_body_ok)
        else:
            body = json.dumps(rest_body_none)
        return Response(content_type='application/json', body=body)

    @route('topologymanage', '/topologymanage/link/src/{src_dpid}/dst/{dst_dpid}',
           methods=['DELETE'])
    def del_virtual_link_by_dpid(self, req, **kwargs):
        payload = json.loads(req.body)
        src_dpid = str_to_dpid(kwargs['src_dpid'])
        dst_dpid = str_to_dpid(kwargs['dst_dpid'])
        src_port_no = int(payload['src_port_no'])
        dst_port_no = int(payload['dst_port_no'])

        try:
            src_sw = self.topo_instance.switches.get_switch(src_dpid)
            src_port = src_sw.ports.get_port(src_port_no)
            dst_sw = self.topo_instance.switches.get_switch(dst_dpid)
            dst_port = dst_sw.ports.get_port(dst_port_no)
        except:
            return Response(content_type='application/json',
                            body=json.dumps(rest_body_none))

        if self.topo_instance.links.del_virtual_link(
                src_dpid, src_port, dst_dpid, dst_port) is True:
            self.topo_instance.switches.del_neighbor(int(src_dpid), int(dst_dpid), src_port_no)
            self.topo_instance.switches.del_neighbor(int(dst_dpid), int(src_dpid), dst_port_no)
            body = json.dumps(rest_body_ok)
        else:
            body = json.dumps(rest_body_none)
        return Response(content_type='application/json', body=body)
