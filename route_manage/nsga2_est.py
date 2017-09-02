import logging
import json
import os
import time

import networkx as nx
import pylab

from route_algorithm.MOEARouteAlgorithm import Node, Edge
from route_algorithm.NSGA2 import NSGA2

LINK_CONF_FILE_PATH = '/home/bokala/PycharmProjects/SD-Route/example/topo_custom/topo_file/link_info.json'

class Topology(object):
    def __init__(self):
        self.links = []
        self.num_link = 0
        self.graph = nx.Graph()


    def read_link_configuration(self):
        try:
            f = open(LINK_CONF_FILE_PATH, 'r')
        except:
            return
        fp = f.read()
        conf = json.loads(fp)
        num = 0
        for item in conf:
            src_dpid = item["src"]
            dst_dpid = item["dst"]
            if src_dpid > dst_dpid:
                src_dpid, dst_dpid = dst_dpid, src_dpid

            delay = float(item["link"][0]["delay"])
            cost = float(item["link"][0]["cost"])
            total_band = float(item["link"][0]["total_band"])
            edge = Edge(num,src_dpid,dst_dpid,delay,cost,total_band)
            self.links.append(edge)
            num += 1

        self.num_link = len(self.links)
        f.close()

    def init_graph(self):
        try:
            f = open(LINK_CONF_FILE_PATH, 'r')
        except:
            return
        fp = f.read()
        conf = json.loads(fp)

        for item in conf:
            src_dpid = item["src"]
            dst_dpid = item["dst"]
            delay = item["delay"]
            pkt_loss = item["loss"]
            total_band = item["bandwidth"]
            self.graph.add_edge(src_dpid, dst_dpid, delay=delay, loss=pkt_loss, band=total_band)

        f.close()
        # pos = nx.shell_layout(self.graph)
        nx.draw(self.graph)
        pylab.title('Self_Define Net', fontsize=15)
        pylab.show()


if __name__ == '__main__':
    topo = Topology()

    topo.init_graph()