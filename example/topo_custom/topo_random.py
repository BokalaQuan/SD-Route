#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.topo import Topo

import logging
import os
import json

logger = logging.getLogger(__name__)

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
LINK_PATH = FILE_PATH + '/topo_file/link_info.json'
SWITCH_PATH = FILE_PATH + '/topo_file/switch_info.json'

class RandomTopo(Topo):

    logger.debug("Class RandomTopo")
    SwitchList = []
    HostList = []

    def __init__(self, num_node, num_edge):
        logger.debug("Class RandomTopo Initialize")
        self.num_node = num_node
        self.num_edge = num_edge

        Topo.__init__(self)

    def create_switch(self):
        logger.debug("Create Switch")
        swparam = {'protocols': 'OpenFlow13'}

        try:
            f = open(SWITCH_PATH, 'r')
        except:
            logger.error("read switch configuration file failed.")
            return
        fp = f.read()
        conf = json.loads(fp)

        for item in conf:
            self.SwitchList.append(self.addSwitch(item["name"], **swparam))

    def create_host(self):
        logger.debug("Create Host")

        for x in xrange(1, self.num_node + 1):
            prefix = "h00"
            if x >= int(10):
                prefix = "h0"
            elif x >= int(100):
                prefix = "h"
            self.HostList.append(self.addHost(prefix + str(x)))

    def create_s2s_link(self):
        logger.debug("Add link between switches")

        try:
            f = open(LINK_PATH, 'r')
        except:
            logger.info("read link configuration file failed.")
            return
        fp = f.read()
        conf = json.loads(fp)

        for item in conf:
            src = self.SwitchList[item["src"]-1]
            dst = self.SwitchList[item["dst"]-1]

            bandwidth = int(item["bandwidth"])
            delay = str(item["delay"]) + 'ms'
            loss = int(item["loss"])

            linkopts = dict(bw=bandwidth, delay=delay, loss=loss)
            self.addLink(src, dst, **linkopts)

    def create_s2h_link(self):

        for i in range(self.num_node):
            self.addLink(self.SwitchList[i], self.HostList[i], bw=5)

    def set_ovs_protocol_13(self):
        self._set_ovs_protocol_13(self.SwitchList)

    @staticmethod
    def _set_ovs_protocol_13(sw_list):
        for sw in sw_list:
            cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
            os.system(cmd)

    def create_topo(self):
        self.create_switch()
        self.create_host()
        self.create_s2s_link()
        self.create_s2h_link()

def set_igmp_version(net, hs_list):
    for host in hs_list:
        h = net.get(str(host))
        h.cmd('ip route add default via 10.0.0.1')
        h.cmd("echo 2 > /proc/sys/net/ipv4/conf/%s-eth0/force_igmp_version" % h)



def create_topo():
    logger.debug("Create Random Topology")

    topo = RandomTopo(50, 134)
    topo.create_topo()

    logger.debug("Start Mininet")
    controller_ip = "127.0.0.1"
    controller_port = 6633
    net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
    net.addController('controller', controller=RemoteController,
                      ip=controller_ip, port=controller_port)
    net.start()

    topo.set_ovs_protocol_13()
    set_igmp_version(net, topo.HostList)

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    if os.getuid() != 0:
        logger.debug("You are NOT root")
    elif os.getuid() == 0:
        create_topo()
