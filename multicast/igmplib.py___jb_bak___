# Copyright (C) 2013 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import struct

from ryu.base import app_manager
from ryu.controller import event
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import (MAIN_DISPATCHER, DEAD_DISPATCHER)
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.ofproto import (ofproto_v1_0, ofproto_v1_2, ofproto_v1_3)
from ryu.lib import addrconv
from ryu.lib import hub
from ryu.lib.dpid import dpid_to_str
from ryu.lib.packet import (packet, ethernet, ipv4, igmp)
from lib.project_lib import find_packet
from topology_manage.object.switch import SwitchTable


MG_GROUP_ADDED = 1
MG_MEMBER_CHANGED = 2
MG_GROUP_REMOVED = 3


class EventMulticastGroupChanged(event.EventBase):
    """a event class that notifies the changes of the statuses of the
    multicast groups."""

    def __init__(self, reason, address, dst, group):
        """
        ========= =====================================================
        Attribute Description
        ========= =====================================================
        reason    why the event occurs. use one of MG_*.
        address   a multicast group address.
        dst       a list of o numbers in which the members exist.
        ========= =====================================================
        """
        super(EventMulticastGroupChanged, self).__init__()
        self.reason = reason
        self.address = address
        self.dst = dst
        self.group = group


class IgmpLib(app_manager.RyuApp):
    """IGMP support library."""

    # -------------------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------------------
    def __init__(self):
        """initialization."""
        super(IgmpLib, self).__init__()
        self.name = 'igmplib'
        self._querier = IgmpVirtualQuerier(self.send_event_to_observers)

    def set_querier_mode(self, switches):
        """set a datapath id and server port number to the instance
        of IgmpQuerier.

        ============ ==================================================
        Attribute    Description
        ============ ==================================================
        switches     set all edge switch operate as querier.
        ============ ==================================================
        """
        assert isinstance(switches, SwitchTable)
        self._querier.set_querier_mode(switches)

    # -------------------------------------------------------------------
    # PUBLIC METHODS ( EVENT HANDLERS )
    # -------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """PacketIn event handler. when the received packet was IGMP,
        proceed it. otherwise, ignore event."""
        msg = ev.msg

        req_pkt = packet.Packet(msg.data)
        req_igmp = req_pkt.get_protocol(igmp.igmp)
        if req_igmp:
            self._querier.packet_in_handler(req_pkt, req_igmp, msg)

    def start_igmp_querier(self):
        self._querier.start_loop()
        # TODO: send general query with STARTUP_QUERY_INTERVAL

    def stop_igmp_querier(self):
        self._querier.stop_loop()


class IgmpBase(object):
    """IGMP abstract class library."""

    # -------------------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------------------
    def __init__(self):
        self._set_flow_func = {
            ofproto_v1_0.OFP_VERSION: self._set_flow_entry_v1_0,
            ofproto_v1_2.OFP_VERSION: self._set_flow_entry_v1_2,
            ofproto_v1_3.OFP_VERSION: self._set_flow_entry_v1_2,
        }
        self._del_flow_func = {
            ofproto_v1_0.OFP_VERSION: self._del_flow_entry_v1_0,
            ofproto_v1_2.OFP_VERSION: self._del_flow_entry_v1_2,
            ofproto_v1_3.OFP_VERSION: self._del_flow_entry_v1_2,
        }

    # -------------------------------------------------------------------
    # PROTECTED METHODS ( RELATED TO OPEN FLOW PROTOCOL )
    # -------------------------------------------------------------------
    def _set_flow_entry_v1_0(self, datapath, actions, in_port, dst,
                             src=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            dl_type=ether.ETH_TYPE_IP, in_port=in_port,
            nw_src=self._ipv4_text_to_int(src),
            nw_dst=self._ipv4_text_to_int(dst))
        mod = parser.OFPFlowMod(
            datapath=datapath, match=match, cookie=0,
            command=ofproto.OFPFC_ADD, actions=actions)
        datapath.send_msg(mod)

    def _set_flow_entry_v1_2(self, datapath, actions, in_port, dst,
                             src=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            eth_type=ether.ETH_TYPE_IP, in_port=in_port, ipv4_dst=dst)
        if src is not None:
            match.append_field(ofproto.OXM_OF_IPV4_SRC, src)
        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, command=ofproto.OFPFC_ADD,
            priority=65535, match=match, instructions=inst)
        datapath.send_msg(mod)

    def _set_flow_entry(self, datapath, actions, in_port, dst, src=None):
        """set a flow entry."""
        set_flow = self._set_flow_func.get(datapath.ofproto.OFP_VERSION)
        assert set_flow
        set_flow(datapath, actions, in_port, dst, src)

    def _del_flow_entry_v1_0(self, datapath, in_port, dst, src=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            dl_type=ether.ETH_TYPE_IP, in_port=in_port,
            nw_src=self._ipv4_text_to_int(src),
            nw_dst=self._ipv4_text_to_int(dst))
        mod = parser.OFPFlowMod(
            datapath=datapath, match=match, cookie=0,
            command=ofproto.OFPFC_DELETE)
        datapath.send_msg(mod)

    def _del_flow_entry_v1_2(self, datapath, in_port, dst, src=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            eth_type=ether.ETH_TYPE_IP, in_port=in_port, ipv4_dst=dst)
        if src is not None:
            match.append_field(ofproto.OXM_OF_IPV4_SRC, src)
        mod = parser.OFPFlowMod(
            datapath=datapath, command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
            match=match)
        datapath.send_msg(mod)

    def _del_flow_entry(self, datapath, in_port, dst, src=None):
        """remove a flow entry."""
        del_flow = self._del_flow_func.get(datapath.ofproto.OFP_VERSION)
        assert del_flow
        del_flow(datapath, in_port, dst, src)

    def _do_packet_out(self, datapath, data, in_port, actions):
        """send a packet."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
            data=data, in_port=in_port, actions=actions)
        datapath.send_msg(out)

    # -------------------------------------------------------------------
    # PROTECTED METHODS ( OTHERS )
    # -------------------------------------------------------------------
    def _ipv4_text_to_int(self, ip_text):
        """convert ip v4 string to integer."""
        if ip_text is None:
            return None
        assert isinstance(ip_text, str)
        return struct.unpack('!I', addrconv.ipv4.text_to_bin(ip_text))[0]


class IgmpVirtualQuerier(IgmpBase):
    """IGMP virtual querier emulation class library. All SDN edge switch
    in this OF domain works as Router while sharing single group table,
    IGMP query message is sent by all edge switch.

    this querier is a simplified implementation, and is not based on RFC,
    for example as following points:
    - routers(SDN switch) share single group table
    - do not send general query with STARTUP_QUERY_INTERVAL
    - do not send specific query with LAST_MEMBER_QUERY_INTERVAL
    - and so on

    IGMPv3 not supported now.
    """

    # -------------------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------------------
    def __init__(self, send_event):
        """initialization."""
        super(IgmpVirtualQuerier, self).__init__()
        self.name = "IgmpVirtualQuerier"
        self.logger = logging.getLogger(self.name)
        self._send_event = send_event

        self._querier_thread = None

        # the structure of self._queriers
        #
        # +------+-------------+-------+------------------+
        # | dpid | 'groups'    | group | 'reserved': None |
        # |      |             +       +------------------+
        # |      |             +       | ...              +
        # |      |             +-------+------------------+
        # |      |             | ...                      |
        # |      +-------------+--------------------------+
        # |      | 'datapath'  |                          |
        # |      +-------------+--------------------------+
        # |      | 'query_pkt' |                          |
        # +------+----------------------------------------+
        # | ...                                           |
        # +-----------------------------------------------+
        #
        # dpid        datapath id.
        # group       multicast address.
        # datapath    datapath.
        # query_pkt   general IGMP query packet.
        # reserved    for further usage.
        self._queriers = {}

        # the structure of self._groups
        #
        # +-------+------+--------+------------------------+
        # | group | dpid | portno | 'replied': True/False  |
        # |       |      |        +------------------------+
        # |       |      |        | 'leave': True/False    |
        # |       |      |        +------------------------+
        # |       |      |        | 'member': member count |
        # |       |      |        +------------------------+
        # |       |      |        | 'out': out             |
        # |       |      |        +------------------------+
        # |       |      |        | 'in': in               |
        # |       |      +--------+------------------------+
        # |       |      | ...                             |
        # |       +------+--------+------------------------+
        # |       | ...                                    |
        # +------------------------------------------------+
        # | ...                                            |
        # +------------------------------------------------+
        #
        # group       multicast address.
        # dpid        datapath id of switch which group member attached to.
        # portno      a port number which port group member attached to.
        # replied     the value indicates whether a REPORT message was replied.
        # leave       the value indicates whether a LEAVE message was received.
        # member      the value indicates the number of member added to this group.
        # out         the value indicates whether a flow entry for the
        #             packet outputted from group src to the port was registered.
        # in          the value indicates whether a flow entry for the
        #             packet inputted from the port to controller was registered.
        self._groups = {}

        self._set_logger()

    def set_querier_mode(self, switches):
        """setup all edge switch as querier, while system booting."""
        for sw in switches.values():
            if sw.attribute == sw.AttributeEnum.edge:
                ofp_port = sw.dp.ports[sw.dp.ofproto.OFPP_LOCAL]
                general_query_pkt = self._igmp_general_query(ofp_port.hw_addr)

                self._queriers.setdefault(
                    sw.dp.id,
                    {'groups': {}, 'datapath': sw.dp,
                     'query_pkt': general_query_pkt})

        if self._querier_thread:
            hub.kill(self._querier_thread)
            self._querier_thread = None

    def packet_in_handler(self, req_pkt, req_igmp, msg):
        """the process when the querier received IGMP."""
        dpid = msg.datapath.id
        if dpid not in self._queriers:
            # non-querier mode switch do not handle igmp packet.
            return

        in_port = msg.match['in_port']

        log = "SW=%s PORT=%d IGMP received. " % (
            dpid_to_str(dpid), in_port)
        self.logger.debug(str(req_igmp))

        if igmp.IGMP_TYPE_QUERY == req_igmp.msgtype:
            self.logger.debug(log + "[QUERY]")
            # unless use out scope querier, should never handle igmp query,
            # as edge switch works in querier mode.
        elif (igmp.IGMP_TYPE_REPORT_V1 == req_igmp.msgtype or
              igmp.IGMP_TYPE_REPORT_V2 == req_igmp.msgtype):
            self.logger.debug(log + "[REPORT]")
            self._do_report(req_igmp, in_port, msg)
        elif igmp.IGMP_TYPE_LEAVE == req_igmp.msgtype:
            self.logger.debug(log + "[LEAVE]")
            self._do_leave(req_igmp, in_port, msg)
        elif igmp.IGMP_TYPE_REPORT_V3 == req_igmp.msgtype:
            self.logger.debug(log + "V3 is not supported yet.")
        else:
            self.logger.warning(log + "[unknown type:%d]",
                                req_igmp.msgtype)

    def start_loop(self):
        """start QUERY thread."""
        self._querier_thread = hub.spawn(self._send_general_query)
        self.logger.info("started a querier.")

    def stop_loop(self):
        """stop QUERY thread."""
        hub.kill(self._querier_thread)
        self._querier_thread = None
        self.logger.info("stopped a querier.")

    # -------------------------------------------------------------------
    # PRIVATE METHODS ( RELATED TO IGMP )
    # -------------------------------------------------------------------
    def _do_query(self, query, iph, eth, in_port, msg):
        """
            the process when the received a QUERY message
            from out scope network. So this function only
            works when no Virtual Query setup.
        """
        pass

    def _send_general_query(self):
        """
            send general QUERY message in all query switch periodically.
        """
        while True:
            # reset host reply status.
            for switches in self._groups.values():
                for ports in switches.values():
                    for port_state in ports.values():
                        port_state['replied'] = False

            # send general query on all switches with query model.
            for querier in self._queriers.values():
                datapath = querier['datapath']
                res_pkt = querier['query_pkt']

                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                send_port = ofproto.OFPP_ANY
                flood = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

                self._do_packet_out(datapath, res_pkt.data, send_port, flood)

            hub.sleep(igmp.QUERY_RESPONSE_INTERVAL)

            # QUERY timeout expired.
            del_groups = []
            for group, switches in self._groups.iteritems():
                del_switches = []
                for dpid, ports in switches.iteritems():
                    del_ports = []
                    for portno, port_state in ports.iteritems():
                        if not port_state['replied']:
                            del_ports.append(portno)
                    for del_port in del_ports:
                        del self._groups[group][dpid][del_port]
                    if not ports:
                        del_switches.append(dpid)
                for del_switch in del_switches:
                    del self._groups[group][del_switch]
                if not switches:
                    del_groups.append([group, del_switches])
            for del_group in del_groups:
                del self._groups[del_group[0]]
                for dpid in del_group[1]:
                    del self._queriers[dpid]['groups'][del_group[0]]
                self._send_event(EventMulticastGroupChanged(
                    MG_GROUP_REMOVED, del_group[0], None, self._groups))

            rest_time = igmp.QUERY_INTERVAL - igmp.QUERY_RESPONSE_INTERVAL
            hub.sleep(rest_time)

    def _send_group_specific_query(self):
        """
            send group specific QUERY message in all query switch periodically.
        """
        pass

    def _do_report(self, report, in_port, msg):
        """
            the process when one querier received a REPORT message.
        """
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        if ofproto.OFP_VERSION == ofproto_v1_0.OFP_VERSION:
            size = 65535
        else:
            size = ofproto.OFPCML_MAX

        # add new group to self._groups and self._queriers
        # send a event when the multicast group address is new.
        if not self._queriers[dpid]['groups'].get(report.address):
            self._queriers[dpid]['groups'].setdefault(
                report.address, {'reserved': None})
            self._queriers[dpid]['groups'][report.address]['datapath'] = datapath
        if not self._groups.get(report.address):
            self._groups.setdefault(report.address, {})
            self._send_event(EventMulticastGroupChanged(
                MG_GROUP_ADDED, report.address, None, self._groups))

        # add new dpid to self._groups
        if not self._groups[report.address].get(dpid):
            self._groups[report.address].setdefault(dpid, {})

        # add new port to group when a host sent a REPORT message and
        # set a flow entry for this host to the controller.
        if not self._groups[report.address][dpid].get(in_port):
            self._groups[report.address][dpid].setdefault(
                in_port,
                {'replied': True, 'leave': False, 'member': 1,
                 'out': False, 'in': False})

            pkt = packet.Packet(msg.data)
            ip_layer = find_packet(pkt, 'ipv4')
            self._send_event(EventMulticastGroupChanged(
                MG_MEMBER_CHANGED, report.address, ip_layer.src, self._groups))

            self._set_flow_entry(
                datapath,
                [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, size)],
                in_port, report.address)

        # update port IGMP query replied
        if not self._groups[report.address][dpid][in_port]['replied']:
            self._groups[report.address][dpid][in_port]['replied'] = True

        # update port IGMP query leave
        if not self._groups[report.address][dpid][in_port]['leave']:
            self._groups[report.address][dpid][in_port]['leave'] = False

    def _do_leave(self, leave, in_port, msg):
        """
            the process when the querier received a LEAVE message.
        """
        datapath = msg.datapath
        dpid = datapath.id

        try:
            self._groups[leave.address][dpid][in_port]['leave'] = True
        except:
            # ignore not managed group's LEAVE message.
            self.logger.warning("receive not managed group's LEAVE message.")
            return

        # format and send specific query
        # TODO: send specific query with LAST_MEMBER_QUERY_INTERVAL
        datapath = self._queriers[dpid]['datapath']
        res_pkt = self._igmp_specific_query(datapath.ports[in_port].hw_addr,
                                            leave.address)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        send_port = ofproto.OFPP_ANY
        outport = [parser.OFPActionOutput(in_port)]

        self._do_packet_out(datapath, res_pkt.data, send_port, outport)

        # wait for REPORT messages.
        timeout = igmp.LAST_MEMBER_QUERY_INTERVAL
        hub.spawn(self._do_timeout_for_leave, timeout, datapath,
                  leave.address, in_port)

    def _do_timeout_for_query(self, timeout, datapath):
        pass

    def _do_timeout_for_leave(self, timeout, datapath, group, in_port):
        dpid = datapath.id
        hub.sleep(timeout)

        if self._groups[group][dpid][in_port]['leave']:
            self._del_flow_entry(datapath, in_port, group)
            self._send_event(EventMulticastGroupChanged(
                MG_MEMBER_CHANGED, group, 'leave', self._groups))

            del self._groups[group][dpid][in_port]
            if not self._groups[group][dpid]:
                del self._groups[group][dpid]
            if not self._groups[group]:
                del self._groups[group]
                del self._queriers[dpid]['groups'][group]
                self._send_event(EventMulticastGroupChanged(
                    MG_GROUP_REMOVED, group, None, self._groups))

    @staticmethod
    def _igmp_general_query(eth_src):
        """create general query igmp packet.

        :param eth_src: querier mac address
        :return res_pkt: serialized general query packet
        """
        res_igmp = igmp.igmp(
            msgtype=igmp.IGMP_TYPE_QUERY,
            maxresp=igmp.QUERY_RESPONSE_INTERVAL * 10,
            csum=0,
            address='0.0.0.0')
        res_ipv4 = ipv4.ipv4(
            total_length=len(ipv4.ipv4()) + len(res_igmp),
            proto=inet.IPPROTO_IGMP, ttl=1,
            src='0.0.0.0',
            dst=igmp.MULTICAST_IP_ALL_HOST)
        res_ether = ethernet.ethernet(
            dst=igmp.MULTICAST_MAC_ALL_HOST,
            src=eth_src,
            ethertype=ether.ETH_TYPE_IP)
        res_pkt = packet.Packet()
        res_pkt.add_protocol(res_ether)
        res_pkt.add_protocol(res_ipv4)
        res_pkt.add_protocol(res_igmp)
        res_pkt.serialize()

        return res_pkt

    @staticmethod
    def _igmp_specific_query(eth_src, group_ip):
        """create specific query igmp packet.

        :param eth_src: querier mac address
        :param group_ip: group ip address
        :return res_pkt: serialized specific query packet
        """
        res_igmp = igmp.igmp(
            msgtype=igmp.IGMP_TYPE_QUERY,
            maxresp=igmp.LAST_MEMBER_QUERY_INTERVAL * 10,
            csum=0,
            address=group_ip)
        res_ipv4 = ipv4.ipv4(
            total_length=len(ipv4.ipv4()) + len(res_igmp),
            proto=inet.IPPROTO_IGMP, ttl=1,
            src='0.0.0.0',
            dst=igmp.MULTICAST_IP_ALL_HOST)
        res_ether = ethernet.ethernet(
            dst=igmp.MULTICAST_MAC_ALL_HOST,
            src=eth_src,
            ethertype=ether.ETH_TYPE_IP)
        res_pkt = packet.Packet()
        res_pkt.add_protocol(res_ether)
        res_pkt.add_protocol(res_ipv4)
        res_pkt.add_protocol(res_igmp)
        res_pkt.serialize()

        return res_pkt

    # -------------------------------------------------------------------
    # PRIVATE METHODS ( OTHERS )
    # -------------------------------------------------------------------
    def _set_logger(self):
        """change log format."""
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        hdl = logging.StreamHandler()
        fmt_str = '[querier][%(levelname)s] %(message)s'
        hdl.setFormatter(logging.Formatter(fmt_str))
        self.logger.addHandler(hdl)
