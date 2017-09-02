import logging
import random
import copy
import json
import os
import networkx as nx

from lib.project_lib import Megabits
from topology_manage.object.link import LinkTableApi

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

INF = 99999999999.9

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
PS_PATH = FILE_PATH + '/ps/topo_ran.json'


class Individual(object):
    """

    """

    def __init__(self):
        self.src_node = None
        self.dst_node = []

        self.edge_list = []
        self.edge_all_list = []

        self.chromosome = []
        self.paths = []

        self.delay = 0.0
        self.loss = 0.0
        self.bandwidth = float('Infinity')

        self.fitness = 0.0

        self.graph = nx.Graph()

        self.dominated = False
        self.pareto_rank = 0
        self.crowding_distance = 0
        self.num_dominated = 0
        self.location = 0
        self.dominating_list = []

    def initialize(self, len_chrom, edge_all_list, src, dst):
        #
        for i in range(len_chrom):
            if random.random() < 0.5:
                self.chromosome.append(True)
            else:
                self.chromosome.append(False)

        self.edge_all_list = edge_all_list
        self.src_node = src
        self.dst_node = dst

        # evaluate this individual and computing it's fitness or property
        self.fitness_evaluate()


    def fitness_evaluate(self):
        self._init_subgraph_by_chromosome()

    def _init_subgraph_by_chromosome(self):
        edge_select = []

        state = True

        for x in range(self.chromosome.__len__()):
            if self.chromosome[x]:
                edge_select.append(self.edge_all_list[x])

        for edge in edge_select:
            self.graph.add_edge(edge.src, edge.dst, delay=edge.delay, band=edge.band, loss=edge.loss)


        if state:
            if self.src_node not in self.graph.node:
                state = False

            else:
                for dst in self.dst_node:
                    if dst not in self.graph.node:
                        state = False
                        break

        if state:
            if nx.is_connected(self.graph):
                state = True
            else:
                state = False

        if state:
            self._init_tree_by_subgraph()
        else:
            self.delay = INF
            self.loss = INF

    def _init_tree_by_subgraph(self):
        self.paths = []

        for dst in self.dst_node:
            if random.random() < 0.5:
                path = nx.dijkstra_path(self.graph, self.src_node, dst, weight='delay')
            else:
                path = nx.dijkstra_path(self.graph, self.src_node, dst, weight='loss')

            self.paths.append(path)

        self._cal_fitness()


    def _cal_fitness(self):

        max_delay = 0.0
        max_loss = 0.0

        for path in self.paths:
            delay = 0.0
            loss = 1.0
            for index in range(len(path) - 1):
                delay += self.graph.edge[path[index]][path[index + 1]]['delay']
                loss *= 1 - self.graph.edge[path[index]][path[index + 1]]['loss']
                if self.bandwidth > self.graph.edge[path[index]][path[index + 1]]['band']:
                    self.bandwidth = self.graph.edge[path[index]][path[index + 1]]['band']

            # if max_delay < delay:
            #     max_delay = delay
            #
            # if max_loss < 1 - loss:
            #     max_loss = 1 - loss

            max_delay += delay
            max_loss += 1 - loss


        self.delay = float(max_delay / len(self.dst_node))
        self.loss = float(max_loss) / len(self.dst_node)


    def is_better_than(self, ind):
        if self.loss <= ind.loss and self.delay < ind.delay:
            return True
        elif self.loss < ind.loss and self.delay <= ind.delay:
            return True
        else:
            return False

    def is_same_to(self, ind):
        if self.delay == ind.delay and self.loss == ind.loss:
            return True
        return False

    def single_point_crossover(self, ind):
        length = self.chromosome.__len__()
        pos = random.randint(0, length)

        chrom_copy = copy.copy(self.chromosome)

        for i in range(length):
            if i > pos:
                self.chromosome[i] = ind.chromosome[i]
                ind.chromosome[i] = chrom_copy[i]

            if random.random() < 0.08:
                if self.chromosome[i]:
                    self.chromosome[i] = False
                else:
                    self.chromosome[i] = True

                if ind.chromosome[i]:
                    ind.chromosome[i] = False
                else:
                    ind.chromosome[i] = True

        self.fitness_evaluate()
        ind.fitness_evaluate()

    def uniform_crossover(self, ind):
        length = self.chromosome.__len__()

        chrom_copy = copy.copy(self.chromosome)

        for i in range(length):
            if random.random() < 0.5:
                self.chromosome[i] = ind.chromosome[i]
                ind.chromosome[i] = chrom_copy[i]
            if random.random() < 0.08:
                if self.chromosome[i]:
                    self.chromosome[i] = False
                else:
                    self.chromosome[i] = True

                if ind.chromosome[i]:
                    ind.chromosome[i] = False
                else:
                    ind.chromosome[i] = True

        self.fitness_evaluate()
        ind.fitness_evaluate()


    def clear_property(self):
        self.dominated = False
        self.pareto_rank = 0
        self.crowding_distance = 0
        self.num_dominated = 0
        self.location = 0
        self.dominating_list = []

    def to_format(self):
        r = {"paths": self.paths,
             "delay": self.delay,
             "loss": self.loss,
             "bandwidth": self.bandwidth}
        return r

    @staticmethod
    def set_to_format(sets):
        # for item in sets:
        #     r.append(item.to_format())
        #     r["individual"] = item.to_format()
        # return r

        r = [{"Individual": item,
              "attribute": sets[item].to_format()} for item in range(len(sets))]
        # for item in range(len(sets)):
        return r



class MOEA(object):
    def __init__(self, popsize, maxgen, pc, pm):
        self.state = 0

        self.switch_queue = []
        self.link_queue = []

        self.nodes = []
        self.edges = []

        self.num_nodes = 0
        self.num_edges = 0

        self.src_node = None
        self.dst_node = None
        self.min_available_bandwidth = 0.0

        self.current_population = []
        self.external_population = []

        self.population_size = popsize
        self.max_num_func_evals = maxgen
        self.pc = pc
        self.pm = pm

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(MOEA, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def init_algorithm(self, switches, links):

        logger.info("topology's data input MOEA")
        print "switch's number = ", len(switches)
        print "link's number = ", len(links)


        self.switch_queue = switches.keys()
        self.link_queue = links.keys()

        for dpid, sw in switches.items():
            index = self.switch_queue.index(dpid)
            neighbors_dpid = sw.neighbors.keys()
            neighbors_index = []
            for i in neighbors_dpid:
                neighbors_index.append(self.switch_queue.index(i))

            node = Node(index, len(neighbors_index), neighbors_index)
            self.nodes.append(node)

        for dpids, link in links.items():
            index = self.link_queue.index((dpids[0], dpids[1]))
            value = link.values()[0]
            src = dpids[0]
            dst = dpids[1]

            loss = float(value.pkt_loss) / 100.0

            edge = Edge(index, src, dst, float(value.delay), float(value.total_band), loss)
            self.edges.append(edge)

        self.num_nodes = self.nodes.__len__()
        self.num_edges = self.edges.__len__()


    def update_link_status(self, links):
        assert isinstance(links, LinkTableApi)

        self.edges = []

        for dpids, link in links.items():
            index = self.link_queue.index((dpids[0], dpids[1]))
            src = dpids[0]
            dst = dpids[1]

            value = link.values()[0]

            loss = float(value.pkt_loss) / 100.0

            edge = Edge(index, src, dst, float(value.delay), float(value.total_band), loss)
            self.edges.append(edge)

            logger.debug("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
                         dpids[0], dpids[1],
                         float(value.available_band) / Megabits,
                         float(value.total_band) / Megabits,
                         1.0 - float(value.available_band) / float(value.total_band))

        self.num_edges = self.edges.__len__()


    def run(self, src_dpid, dst_dpid, min_available_bandwidth):

        self.dst_node = []
        self.src_node = src_dpid
        self.dst_node = dst_dpid
        self.min_available_bandwidth = min_available_bandwidth

        logger.debug("src_vertex:%s, dst_vertexes:%s, min_available_bandwidth:%s",
                     src_dpid, dst_dpid, float(min_available_bandwidth))

        # run MOEA
        if not self.state:
            self.main()
            self.write_ps_to_file()
            logger.debug("Main LOOP")
            self.state += 1
        else:
            self.state += 1
            return

    def write_ps_to_file(self):

        ps = Individual.set_to_format(self.external_population)

        with open(PS_PATH, 'w') as json_file:
            pfp = json.dumps(ps, indent=4, sort_keys=True)
            json_file.write(pfp)


    def main(self):
        pass

    def get_link(self):
        pass

    def init_population(self):
        pass

    def init_external(self):
        pass

    def evolution(self):
        pass

class Node(object):
    """
    means "switch"
    """
    def __init__(self, id, degree, nodes):
        self.id = id
        self.degree = degree
        self.connect_node = nodes

class Edge(object):
    """
    means link
    """
    def __init__(self, id, src, dst, delay, band, loss):
        self.id = id
        self.src = src
        self.dst = dst
        self.delay = delay
        self.band = band
        self.loss = loss