#!/usr/bin/env python

import logging

from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch

logger = logging.getLogger(__name__)


def start_net():
    info("****creating network****\n")
    net = Mininet(switch=OVSKernelSwitch, controller=RemoteController, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    # swparam = {'protocols': 'OpenFlow13'}
    swparam = {}

    s1 = net.addSwitch('s1', **swparam)
    s2 = net.addSwitch('s2', **swparam)
    s3 = net.addSwitch('s3', **swparam)
    s4 = net.addSwitch('s4', **swparam)

    h1s1 = net.addHost("h1s1")
    h2s1 = net.addHost("h2s1")
    h3s1 = net.addHost("h3s1")
    h1s2 = net.addHost("h1s2")
    h2s2 = net.addHost("h2s2")
    h3s2 = net.addHost("h3s2")
    h1s3 = net.addHost("h1s3")
    h2s3 = net.addHost("h2s3")
    h3s3 = net.addHost("h3s3")
    h1s4 = net.addHost("h1s4")
    h2s4 = net.addHost("h2s4")
    h3s4 = net.addHost("h3s4")

    # add link between sw and host
    net.addLink(s1, h1s1, 1, 0)
    net.addLink(s1, h2s1, 2, 0)
    net.addLink(s1, h3s1, 3, 0)
    net.addLink(s2, h1s2, 1, 0)
    net.addLink(s2, h2s2, 2, 0)
    net.addLink(s2, h3s2, 3, 0)
    net.addLink(s3, h1s3, 1, 0)
    net.addLink(s3, h2s3, 2, 0)
    net.addLink(s3, h3s3, 3, 0)
    net.addLink(s4, h1s4, 1, 0)
    net.addLink(s4, h2s4, 2, 0)
    net.addLink(s4, h3s4, 3, 0)

    # add link between sw
    net.addLink(s1, s2, 4, 4)
    net.addLink(s2, s3, 5, 4)
    net.addLink(s2, s4, 6, 4)

    # start net
    net.start()

    ###########################################################################

    # force host IGMP version to IGMPv2
    h1s1.cmd('echo 2 > /proc/sys/net/ipv4/conf/h1s1-eth0/force_igmp_version')
    h2s1.cmd('echo 2 > /proc/sys/net/ipv4/conf/h2s1-eth0/force_igmp_version')
    h3s1.cmd('echo 2 > /proc/sys/net/ipv4/conf/h3s1-eth0/force_igmp_version')
    h1s2.cmd('echo 2 > /proc/sys/net/ipv4/conf/h1s2-eth0/force_igmp_version')
    h2s2.cmd('echo 2 > /proc/sys/net/ipv4/conf/h2s2-eth0/force_igmp_version')
    h3s2.cmd('echo 2 > /proc/sys/net/ipv4/conf/h3s2-eth0/force_igmp_version')
    h1s3.cmd('echo 2 > /proc/sys/net/ipv4/conf/h1s3-eth0/force_igmp_version')
    h2s3.cmd('echo 2 > /proc/sys/net/ipv4/conf/h2s3-eth0/force_igmp_version')
    h3s3.cmd('echo 2 > /proc/sys/net/ipv4/conf/h3s3-eth0/force_igmp_version')
    h1s4.cmd('echo 2 > /proc/sys/net/ipv4/conf/h1s4-eth0/force_igmp_version')
    h2s4.cmd('echo 2 > /proc/sys/net/ipv4/conf/h2s4-eth0/force_igmp_version')
    h3s4.cmd('echo 2 > /proc/sys/net/ipv4/conf/h3s4-eth0/force_igmp_version')

    # set host ip
    h1s1.cmd('ip addr del 10.0.0.1/8 dev h1s1-eth0')
    h1s1.cmd('ip addr add 172.16.10.10/24 dev h1s1-eth0')
    h2s1.cmd('ip addr del 10.0.0.2/8 dev h2s1-eth0')
    h2s1.cmd('ip addr add 172.16.20.20/24 dev h2s1-eth0')
    h3s1.cmd('ip addr del 10.0.0.3/8 dev h3s1-eth0')
    h3s1.cmd('ip addr add 172.16.30.30/24 dev h3s1-eth0')

    h1s2.cmd('ip addr del 10.0.0.4/8 dev h1s2-eth0')
    h1s2.cmd('ip addr add 192.168.1.1/24 dev h1s2-eth0')
    h2s2.cmd('ip addr del 10.0.0.5/8 dev h2s2-eth0')
    h2s2.cmd('ip addr add 192.168.1.2/24 dev h2s2-eth0')
    h3s2.cmd('ip addr del 10.0.0.6/8 dev h3s2-eth0')
    h3s2.cmd('ip addr add 192.168.1.3/24 dev h3s2-eth0')

    h1s3.cmd('ip addr del 10.0.0.7/8 dev h1s3-eth0')
    h1s3.cmd('ip addr add 192.168.1.4/24 dev h1s3-eth0')
    h2s3.cmd('ip addr del 10.0.0.8/8 dev h2s3-eth0')
    h2s3.cmd('ip addr add 192.168.1.5/24 dev h2s3-eth0')
    h3s3.cmd('ip addr del 10.0.0.9/8 dev h3s3-eth0')
    h3s3.cmd('ip addr add 192.168.1.6/24 dev h3s3-eth0')

    h1s4.cmd('ip addr del 10.0.0.10/8 dev h1s4-eth0')
    h1s4.cmd('ip addr add 192.168.1.7/24 dev h1s4-eth0')
    h2s4.cmd('ip addr del 10.0.0.11/8 dev h2s4-eth0')
    h2s4.cmd('ip addr add 192.168.1.8/24 dev h2s4-eth0')
    h3s4.cmd('ip addr del 10.0.0.12/8 dev h3s4-eth0')
    h3s4.cmd('ip addr add 192.168.1.9/24 dev h3s4-eth0')

    # set host route table
    h1s1.cmd('ip route add default via 172.16.10.254')
    h2s1.cmd('ip route add default via 172.16.20.254')
    h3s1.cmd('ip route add default via 172.16.30.254')

    h1s2.cmd('ip route add default via 192.168.1.254')
    h2s2.cmd('ip route add default via 192.168.1.254')
    h3s2.cmd('ip route add default via 192.168.1.254')

    h1s3.cmd('ip route add default via 192.168.1.254')
    h2s3.cmd('ip route add default via 192.168.1.254')
    h3s3.cmd('ip route add default via 192.168.1.254')

    h1s4.cmd('ip route add default via 192.168.1.254')
    h2s4.cmd('ip route add default via 192.168.1.254')
    h3s4.cmd('ip route add default via 192.168.1.254')

    CLI(net)

    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    start_net()
