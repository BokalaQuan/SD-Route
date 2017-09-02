#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections
import logging
import os

# logging.basicConfig(filename='./fattree.log', level=logging.INFO)
logger = logging.getLogger(__name__)

# BW of agg switch to core switch
# unit Mbits
bw_a2c = {
    'bw_2001-1001': 100,
    'bw_2001-1002': 20,
    'bw_2002-1003': 100,
    'bw_2002-1004': 20,
    'bw_2003-1001': 20,
    'bw_2003-1002': 20,
    'bw_2004-1003': 20,
    'bw_2004-1004': 20,
    'bw_2005-1001': 100,
    'bw_2005-1002': 20,
    'bw_2006-1003': 20,
    'bw_2006-1004': 20,
    'bw_2007-1001': 100,
    'bw_2007-1002': 20,
    'bw_2008-1003': 100,
    'bw_2008-1004': 20,
}

# BW of agg switch to edge switch
bw_a2e = {
    'bw_2001-3001': 20,
    'bw_2001-3002': 20,
    'bw_2002-3001': 20,
    'bw_2002-3002': 20,
    'bw_2003-3003': 20,
    'bw_2003-3004': 20,
    'bw_2004-3003': 10,
    'bw_2004-3004': 10,
    'bw_2005-3005': 10,
    'bw_2005-3006': 4,
    'bw_2006-3005': 4,
    'bw_2006-3006': 4,
    'bw_2007-3007': 20,
    'bw_2007-3008': 20,
    'bw_2008-3007': 20,
    'bw_2008-3008': 20,
}

# BW of host to edge
bw_h2e = 1000

# BW of access switch to core switch
bw_acc2core = {
    'bw_4001-1001': 100,
    'bw_4001-1002': 100,
    'bw_4001-1003': 100,
    'bw_4001-1004': 100,
    'bw_4002-1001': 100,
    'bw_4002-1002': 100,
    'bw_4002-1003': 100,
    'bw_4002-1004': 100,
}

# BW of user to access switch
bw_u2acc = 1000


class Fattree(Topo):
    logger.debug("Class Fattree")
    CoreSwitchList = []
    AggSwitchList = []
    EdgeSwitchList = []
    AccessSwitchList = []
    HostList = []
    UserList = []

    def __init__(self, k, density, access_switch_num, user_density):
        logger.debug("Class Fattree init")
        self.pod = k
        self.iCoreLayerSwitch = (k / 2) ** 2
        self.iAggLayerSwitch = k * k / 2
        self.iEdgeLayerSwitch = k * k / 2
        self.density = density
        self.iHost = self.iEdgeLayerSwitch * density
        self.iAccessLayerSwitch = access_switch_num
        self.iUser = user_density * self.iAccessLayerSwitch
        self.user_density = user_density

        # Init Topo
        Topo.__init__(self)

    def create_topo(self):
        self.create_core_switch(self.iCoreLayerSwitch)
        self.create_agg_switch(self.iAggLayerSwitch)
        self.create_edge_switch(self.iEdgeLayerSwitch)
        self.create_access_switch(self.iAccessLayerSwitch)
        self.create_host(self.iHost)
        self.create_user(self.iUser)

    def _add_switch(self, number, level, switch_list):
        swparam = {'protocols': 'OpenFlow13'}

        for x in xrange(1, number + 1):
            prefix = str(level) + "00"
            if x >= int(10):
                prefix = str(level) + "0"
            switch_list.append(self.addSwitch('s' + prefix + str(x), **swparam))

    def create_core_switch(self, number):
        logger.debug("Create Core Layer")
        self._add_switch(number, 1, self.CoreSwitchList)

    def create_agg_switch(self, number):
        logger.debug("Create Agg Layer")
        self._add_switch(number, 2, self.AggSwitchList)

    def create_edge_switch(self, number):
        logger.debug("Create Edge Layer")
        self._add_switch(number, 3, self.EdgeSwitchList)
        
    def create_access_switch(self, number):
        self._add_switch(number, 4, self.AccessSwitchList)
        
    def create_host(self, number):
        logger.debug("Create Host")
        for x in xrange(1, number + 1):
            prefix = "h00"
            if x >= int(10):
                prefix = "h0"
            elif x >= int(100):
                prefix = "h"
            self.HostList.append(self.addHost(prefix + str(x)))
            
    def create_user(self, number):
        for x in xrange(1, number + 1):
            prefix = "u00"
            if x >= int(10):
                prefix = "u0"
            elif x >= int(100):
                prefix = "u"
            self.UserList.append(self.addHost(prefix + str(x)))

    def create_core_agg_link(self, end):
        logger.debug("Add link Core to Agg.")
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    a = x + i
                    c = i * end + j
                    m = "bw_200" + str(a + 1) + "-100" + str(c + 1)
                    self.addLink(self.CoreSwitchList[i * end + j], self.AggSwitchList[x + i], bw=bw_a2c[m])

    def create_agg_edge_link(self, end):
        logger.debug("Add link Agg to Edge.")
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    e = x + j
                    a = x + i
                    m = "bw_200" + str(a + 1) + "-300" + str(e + 1)
                    self.addLink(self.AggSwitchList[x + i], self.EdgeSwitchList[x + j], bw=bw_a2e[m])

    def create_edge_host_link(self, bw_h2e):
        logger.debug("Add link Edge to Host.")
        for x in xrange(0, self.iEdgeLayerSwitch):
            for i in xrange(0, self.density):
                self.addLink(self.EdgeSwitchList[x], self.HostList[self.density * x + i], bw=bw_h2e)
                
    def create_access_core_link(self):
        for a in xrange(0, self.iAccessLayerSwitch):
            for c in xrange(0, self.iCoreLayerSwitch):
                m = "bw_400" + str(a + 1) + "-100" + str(c + 1)
                self.addLink(self.AccessSwitchList[a], self.CoreSwitchList[c], bw=bw_acc2core[m])
        pass
    
    def create_user_access_link(self, bw_u2acc):
        for x in xrange(0, self.iAccessLayerSwitch):
            for i in xrange(0, self.user_density):
                self.addLink(self.AccessSwitchList[x], self.UserList[self.user_density * x + i], bw=bw_u2acc)

    def create_link(self, bw_h2e=0.2):
        end = self.pod / 2
        self.create_core_agg_link(end)
        self.create_agg_edge_link(end)
        self.create_edge_host_link(bw_h2e)
        self.create_access_core_link()
        self.create_user_access_link(bw_u2acc)

    def set_ovs_protocol_13(self, ):
        self._set_ovs_protocol_13(self.CoreSwitchList)
        self._set_ovs_protocol_13(self.AggSwitchList)
        self._set_ovs_protocol_13(self.EdgeSwitchList)

    @staticmethod
    def _set_ovs_protocol_13(sw_list):
        for sw in sw_list:
            cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
            os.system(cmd)


def iperf_test(net, topo):
    logger.debug("Start iperfTEST")
    h1000, h1015, h1016 = net.get(
        topo.HostList[0], topo.HostList[14], topo.HostList[15])

    # iperf Server
    h1000.popen(
        'iperf -s -u -i 1 > iperf_server_differentPod_result', shell=True)

    # iperf Server
    h1015.popen(
        'iperf -s -u -i 1 > iperf_server_samePod_result', shell=True)

    # iperf Client
    h1016.cmdPrint('iperf -c ' + h1000.IP() + ' -u -t 10 -i 1 -b 100m')
    h1016.cmdPrint('iperf -c ' + h1015.IP() + ' -u -t 10 -i 1 -b 100m')


def ping_test(net):
    logger.debug("Start Test all network")
    net.pingAll()


def open_service(net, topo):
    logger.debug("start iperf server&SimpleHttpServer.")
    for i in range(len(topo.HostList)-4):
        host = net.get(topo.HostList[i])
#         host.popen(
#             'iperf -s -p 8080 -u > log/server_' + str(host.IP()) + '_iperf_result', shell=True)
        if i in xrange(0, 4) or i in xrange(8, 12):
            host.popen(
                'python -m SimpleHTTPServer 80', shell=True)
        if i in xrange(4, 8):
            host.popen(
                'python -m pyftpdlib -p 21', shell=True)


def set_igmp_version(net):
    h001 = net.get("h001")
    h002 = net.get("h002")
    h003 = net.get("h003")
    h004 = net.get("h004")
    h005 = net.get("h005")
    h006 = net.get("h006")
    h007 = net.get("h007")
    h008 = net.get("h008")
    h009 = net.get("h009")
    h010 = net.get("h010")
    h011 = net.get("h011")
    h012 = net.get("h012")
    h013 = net.get("h013")
    h014 = net.get("h014")
    h015 = net.get("h015")
    h016 = net.get("h016")
    h001.cmd('ip route add default via 10.0.0.1')
    h002.cmd('ip route add default via 10.0.0.1')
    h003.cmd('ip route add default via 10.0.0.1')
    h004.cmd('ip route add default via 10.0.0.1')
    h005.cmd('ip route add default via 10.0.0.1')
    h006.cmd('ip route add default via 10.0.0.1')
    h007.cmd('ip route add default via 10.0.0.1')
    h008.cmd('ip route add default via 10.0.0.1')
    h009.cmd('ip route add default via 10.0.0.1')
    h010.cmd('ip route add default via 10.0.0.1')
    h011.cmd('ip route add default via 10.0.0.1')
    h012.cmd('ip route add default via 10.0.0.1')
    h013.cmd('ip route add default via 10.0.0.1')
    h014.cmd('ip route add default via 10.0.0.1')
    h015.cmd('ip route add default via 10.0.0.1')
    h016.cmd('ip route add default via 10.0.0.1')
    h001.cmd('echo 2 > /proc/sys/net/ipv4/conf/h001-eth0/force_igmp_version')
    h002.cmd('echo 2 > /proc/sys/net/ipv4/conf/h002-eth0/force_igmp_version')
    h003.cmd('echo 2 > /proc/sys/net/ipv4/conf/h003-eth0/force_igmp_version')
    h004.cmd('echo 2 > /proc/sys/net/ipv4/conf/h004-eth0/force_igmp_version')
    h005.cmd('echo 2 > /proc/sys/net/ipv4/conf/h005-eth0/force_igmp_version')
    h006.cmd('echo 2 > /proc/sys/net/ipv4/conf/h006-eth0/force_igmp_version')
    h007.cmd('echo 2 > /proc/sys/net/ipv4/conf/h007-eth0/force_igmp_version')
    h008.cmd('echo 2 > /proc/sys/net/ipv4/conf/h008-eth0/force_igmp_version')
    h009.cmd('echo 2 > /proc/sys/net/ipv4/conf/h009-eth0/force_igmp_version')
    h010.cmd('echo 2 > /proc/sys/net/ipv4/conf/h010-eth0/force_igmp_version')
    h011.cmd('echo 2 > /proc/sys/net/ipv4/conf/h011-eth0/force_igmp_version')
    h012.cmd('echo 2 > /proc/sys/net/ipv4/conf/h012-eth0/force_igmp_version')
    h013.cmd('echo 2 > /proc/sys/net/ipv4/conf/h013-eth0/force_igmp_version')
    h014.cmd('echo 2 > /proc/sys/net/ipv4/conf/h014-eth0/force_igmp_version')
    h015.cmd('echo 2 > /proc/sys/net/ipv4/conf/h015-eth0/force_igmp_version')
    h016.cmd('echo 2 > /proc/sys/net/ipv4/conf/h016-eth0/force_igmp_version')


def create_topo():
    logging.debug("LV1 Create Fattree")
    # 3 layer; 4 core switch; host density is 2.
    topo = Fattree(4, 2, 2, 10)
    topo.create_topo()
    # bandwidth unit Mbits
    topo.create_link(bw_h2e)

    logging.debug("LV1 Start Mininet")
    controller_ip = "127.0.0.1"
    controller_port = 6633
    net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
    net.addController('controller', controller=RemoteController,
                      ip=controller_ip, port=controller_port)
    net.start()

    # use if `swparam = {'protocols': 'OpenFlow13'}` failed.
    topo.set_ovs_protocol_13()

    # set IGMP version to IGMPv2
    set_igmp_version(net)

    open_service(net, topo)
    # logger.debug("LV1 dumpNode")
    # dumpNodeConnections(net.hosts)
    # pingTest(net)
    # iperfTest(net, topo)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    if os.getuid() != 0:
        logger.debug("You are NOT root")
    elif os.getuid() == 0:
        create_topo()
