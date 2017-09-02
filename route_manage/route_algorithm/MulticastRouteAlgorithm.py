import logging
import random

from lib.project_lib import Megabits
from topology_manage.object.link import LinkTableApi

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

COST_INDEX = 500.0
ENDLESS_FLOAT = 99999999999.9


class MGAlgorithm(object):
    def __init__(self, max_chromosome_quantity=60, max_generation=15, candidate_quantity=3,
                 crossover_probability=0.6, variation_probability=0.1):
        if not hasattr(self, 'crossover_probability'):
            super(MGAlgorithm, self).__init__()

            # map of switch dpid and serial number:
            # num = self.switch_queue.index(dpid)
            # dpid = self.switch_queue[num]
            self.switch_queue = []

            # map of edge (src_dpid, dst_dpid) and serial number:
            # num = self.edge_queue.index((src_dpid, dst_dpid))
            # (src_dpid, dst_dpid) = self.edge_queue = [num]
            self.edge_queue = []

            self.sou_vertex = None
            self.des_vertexes = None  # this variable is a list reference, (int), record destination vertexes ids.
            self.des_vertexes_quantity = None
            self.vertexes_quantity = None
            self.edges_quantity = None
            self.min_available_bandwidth = None

            self.population = []  # (class Chromosome), it is the operation object of genetic algorithm,
            # function population_init() will fill it.

            self.chromosome_quantity = 0  # function population_init() will fill this variable,
            # of course, chromosome_quantity == population.__len__() forever, they can be exchanged with each other.

            self.vertexes = []
            self.edges = []

            # GA parameter
            self.max_chromosome_quantity = max_chromosome_quantity
            self.max_generation = max_generation
            self.candidate_quantity = candidate_quantity
            self.crossover_probability = crossover_probability
            self.variation_probability = variation_probability

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(MGAlgorithm, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def get_link(self):
        index = self.evaluate_population()
        paths_unit = self.delete_circuit(self.population[index])
        rval = []
        for path_num, path in enumerate(paths_unit):
            rval.append([])
            for vertex in path:
                rval[path_num].append(self.switch_queue[vertex])
        return rval

    def init_algorithm(self, switches, links):
        self.fill_vertexes_and_edges(switches, links)

    def update_link_status(self, links):
        assert isinstance(links, LinkTableApi)

        # print "========================================"
        #
        # print links.items()
        #
        # for dpids, edge in links.items():
        #     ev = edge.values()[0]
        #     print dpids, " >>>> ", ev
        #
        # print "========================================"

        self.edges = []
        for i in range(len(links)):
            self.edges.append(Edge())
        self.edges_quantity = self.edges.__len__()
        for dpids, edge in links.items():
            num = self.edge_queue.index((dpids[0], dpids[1]))
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]

            self.edges[num].id = num
            self.edges[num].vertex_id0 = src_num
            self.edges[num].vertex_id1 = dst_num
            self.edges[num].delay = float(ev.delay)
            self.edges[num].cost = float(ev.cost)/COST_INDEX
            self.edges[num].available_width = ENDLESS_FLOAT  # float(ev.available_band)
            self.edges[num].width = float(ev.total_band)

            logger.debug("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
                         dpids[0], dpids[1],
                         float(ev.available_band)/Megabits,
                         float(ev.total_band)/Megabits,
                         1.0 - float(ev.available_band) / float(ev.total_band))

    def run(self, src_dpid, dst_dpid, min_available_bandwidth):
        # map dpid to vertex
        sou_vertex = self.switch_queue.index(src_dpid)
        des_vertexes = []
        for dpid in dst_dpid:
            des_vertexes.append(self.switch_queue.index(dpid))
        logger.debug("src_vertex:%s, dst_vertexes:%s, min_available_bandwidth:%s",
                     sou_vertex, des_vertexes, float(min_available_bandwidth))

        # run algorithm
        self._update_request(sou_vertex, des_vertexes, float(min_available_bandwidth))

        logger.debug("population_init")
        self.population_init(self.max_chromosome_quantity)

        logger.debug("genetic_algorithm")
        self.genetic_algorithm()

    def _update_request(self, sou_vertex, des_vertexes, min_available_bandwidth):
        self.sou_vertex = sou_vertex
        self.des_vertexes = des_vertexes
        self.des_vertexes_quantity = des_vertexes.__len__()
        self.min_available_bandwidth = min_available_bandwidth

    def find_edge(self, vertex1, vertex2):  # return the edge that connect vertex1 and vertex2
        for i in range(self.vertexes[vertex2].degree):
            if vertex1 == self.vertexes[vertex2].connect_vertex[i]:
                return self.vertexes[vertex2].connect_edge[i]
        logger.error("WARNING: find_edge() error!!")
        return -1

    def fill_vertexes_and_edges(self, switches, links):
        """
            initial topology information for algorithm.
        """
        # update switch/edge queue
        self.switch_queue = switches.keys()
        self.edge_queue = links.keys()

        # init self.vertexes and self.edges
        for i in range(len(switches)):
            self.vertexes.append(Vertex())
        for i in range(len(links)):
            self.edges.append(Edge())

        # update self.vertexes
        for dpid, sw in switches.items():
            num = self.switch_queue.index(dpid)
            neighbors_in_dpid = sw.neighbors.keys()
            neighbors_in_num = []
            for n in neighbors_in_dpid:
                neighbors_in_num.append(self.switch_queue.index(n))

            self.vertexes[num].id = num
            self.vertexes[num].connect_vertex = neighbors_in_num
            self.vertexes[num].degree = len(neighbors_in_num)

        # update self.edges
        for dpids, edge in links.items():
            num = self.edge_queue.index((dpids[0], dpids[1]))
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]

            self.edges[num].id = num
            self.edges[num].vertex_id0 = src_num
            self.edges[num].vertex_id1 = dst_num
            self.edges[num].delay = float(ev.delay)
            self.edges[num].cost = float(ev.cost)/COST_INDEX
            self.edges[num].width = float(ev.total_band)

        # update self.vertexes[].connect_edge
        for vertex in self.vertexes:
            for neighbor in vertex.connect_vertex:
                for edge in self.edges:
                    if (edge.vertex_id0, edge.vertex_id1) == (vertex.id, neighbor) or \
                       (edge.vertex_id0, edge.vertex_id1) == (neighbor, vertex.id):
                        self.vertexes[vertex.id].connect_edge.append(edge.id)

        # update self.vertexes_quantity and self.edges_quantity
        self.vertexes_quantity = self.vertexes.__len__()
        self.edges_quantity = self.edges.__len__()

    def population_init(self, max_chromosome_quantity, edge_be_selected_probability=0.7):
        chromosome_quantity = max_chromosome_quantity
        if chromosome_quantity % 2 == 1:
            chromosome_quantity += 1
        for i in range(chromosome_quantity):
            temp_chromosome = Chromosome(self.edges_quantity)
            for j in range(self.edges_quantity):
                temp_random = random.random()
                if temp_random < edge_be_selected_probability:
                    temp_chromosome.genes[j] = True
                else:
                    temp_chromosome.genes[j] = False
            self.population.append(temp_chromosome)
        self.chromosome_quantity = chromosome_quantity

    def evaluate_population(self):
        best_fitness = ENDLESS_FLOAT
        temp_total_fitness = 0.0
        outstanding = 0
        for i in range(self.chromosome_quantity):
            temp_fitness = self.population[i].fitness
            temp_total_fitness += temp_fitness
            if best_fitness > temp_fitness:
                best_fitness = temp_fitness
                outstanding = i
        return outstanding

    def crossover_multi_point__remain_outstanding(self, crossover_probability, outstanding):
        follow_outstanding = None
        position = [0, 0, 0, 0, 0, 0]
        selected = []
        random_sequence = [i for i in range(self.chromosome_quantity)]
        for i in range(self.chromosome_quantity):
            index = int(random.random() * i)
            temp = random_sequence[i]
            random_sequence[i] = random_sequence[index]
            random_sequence[index] = temp
        for i in range(0, self.chromosome_quantity, 2):
            if random_sequence[i] != outstanding and random_sequence[i+1] != outstanding:
                random_probability = random.random()
                if random_probability < crossover_probability:
                    for j in range(1, 6):
                        position[j] = int(random.random() * self.edges_quantity)
                    for j in range(5, 1, -1):
                        for k in range(1, j):
                            if position[k] > position[k+1]:
                                temp_position = position[k]
                                position[k] = position[k+1]
                                position[k+1] = temp_position
                    for j in range(3):
                        temp_number = int(random.random() * 6)
                        if temp_number not in selected:
                            selected.append(temp_number)
                    for j in range(selected.__len__()):
                        if selected[j] == 5:
                            for k in range(position[selected[j]], self.edges_quantity):
                                temp_boolean = self.population[random_sequence[i]].genes[k]
                                self.population[random_sequence[i]].genes[k] = \
                                    self.population[random_sequence[i+1]].genes[k]
                                self.population[random_sequence[i+1]].genes[k] = temp_boolean
                        else:
                            for k in range(position[selected[j]], position[selected[j] + 1]):
                                temp_boolean = self.population[random_sequence[i]].genes[k]
                                self.population[random_sequence[i]].genes[k] = \
                                    self.population[random_sequence[i+1]].genes[k]
                                self.population[random_sequence[i+1]].genes[k] = temp_boolean
            elif random_sequence[i] == outstanding:
                for j in range(self.edges_quantity):
                    self.population[random_sequence[i+1]].genes[j] = self.population[random_sequence[i]].genes[j]
                self.population[random_sequence[i+1]].fitness = self.population[random_sequence[i]].fitness
                follow_outstanding = random_sequence[i+1]
            else:
                for j in range(self.edges_quantity):
                    self.population[random_sequence[i]].genes[j] = self.population[random_sequence[i+1]].genes[j]
                self.population[random_sequence[i]].fitness = self.population[random_sequence[i+1]].fitness
                follow_outstanding = random_sequence[i]
        return follow_outstanding

    def variation__remain_outstanding(self, variation_probability, outstanding, follow_outstanding):
        for i in range(self.chromosome_quantity):
            if i != outstanding and i != follow_outstanding:
                for j in range(self.edges_quantity):
                    random_probability = random.random()
                    if random_probability < variation_probability:
                        self.population[i].genes[j] = False if self.population[i].genes[j] else True

    def fitness_evaluate(self, chromosome_reference):
        temp_vertexes = [None for i in range(self.vertexes_quantity)]
        previous_vertex = [-1 for i in range(self.vertexes_quantity)]
        paths_length = [ENDLESS_FLOAT for i in range(self.vertexes_quantity)]
        tag = [False for i in range(self.vertexes_quantity)]
        be_selected_edges = []
        tree_vertexes_quantity = 0
        min_length = ENDLESS_FLOAT
        record = 0
        temp_fitness = 0.0

        # construct new topology.
        for i in range(self.edges_quantity):
            if chromosome_reference.genes[i] is True:
                index0, index1 = self.edges[i].vertex_id0, self.edges[i].vertex_id1
                if temp_vertexes[index0] is None:
                    temp_vertexes[index0] = Vertex()
                    tree_vertexes_quantity += 1
                temp_vertexes[index0].connect_vertex.append(index1)
                temp_vertexes[index0].connect_edge.append(i)
                temp_vertexes[index0].degree += 1
                if temp_vertexes[index1] is None:
                    temp_vertexes[index1] = Vertex()
                    tree_vertexes_quantity += 1
                temp_vertexes[index1].connect_vertex.append(index0)
                temp_vertexes[index1].connect_edge.append(i)
                temp_vertexes[index1].degree += 1

        # to handle exception
        if temp_vertexes[self.sou_vertex] is None:
            chromosome_reference.fitness = ENDLESS_FLOAT
            return

        # evaluate path.
        vertex_selected = self.sou_vertex
        tag[self.sou_vertex] = True
        paths_length[self.sou_vertex] = 0.0
        for i in range(tree_vertexes_quantity - 1):
            for j in range(self.vertexes_quantity):
                if temp_vertexes[j] is not None and tag[j] is False:
                    min_length = paths_length[j]
                    record = j
                    break
            for j in range(temp_vertexes[vertex_selected].degree):
                if tag[temp_vertexes[vertex_selected].connect_vertex[j]] is False:
                    temp_edge = temp_vertexes[vertex_selected].connect_edge[j]
                    if self.edges[temp_edge].available_width < self.min_available_bandwidth:
                        temp_edge_cost = ENDLESS_FLOAT
                    else:
                        temp_edge_cost = self.edges[temp_edge].cost
                    if paths_length[temp_vertexes[vertex_selected].connect_vertex[j]] > \
                       paths_length[vertex_selected] + temp_edge_cost:
                        paths_length[temp_vertexes[vertex_selected].connect_vertex[j]] = \
                            paths_length[vertex_selected] + temp_edge_cost
                        previous_vertex[temp_vertexes[vertex_selected].connect_vertex[j]] = vertex_selected
            for j in range(self.vertexes_quantity):
                if temp_vertexes[j] is not None and tag[j] is False and paths_length[j] < min_length:
                    min_length = paths_length[j]
                    record = j
            vertex_selected = record
            tag[vertex_selected] = True

        for i in range(self.des_vertexes_quantity):
            j = self.des_vertexes[i]
            if previous_vertex[j] == -1:
                chromosome_reference.fitness = ENDLESS_FLOAT
                return
            while previous_vertex[j] != -1:
                temp_edge = self.find_edge(j, previous_vertex[j])
                if temp_edge not in be_selected_edges:
                    temp_fitness += self.edges[temp_edge].cost
                    be_selected_edges.append(temp_edge)
                j = previous_vertex[j]
        chromosome_reference.fitness = temp_fitness

    def selection_championships(self, candidate_quantity):
        temp_population = []
        for i in range(self.chromosome_quantity):
            c = Chromosome(self.edges_quantity)
            be_selected_chromosome = int(random.random() * self.chromosome_quantity)
            for j in range(candidate_quantity - 1):
                random_chromosome = int(random.random() * self.chromosome_quantity)
                if self.population[be_selected_chromosome].fitness > self.population[random_chromosome].fitness:
                    be_selected_chromosome = random_chromosome
            for j in range(self.edges_quantity):
                c.genes[j] = self.population[be_selected_chromosome].genes[j]
            c.fitness = self.population[be_selected_chromosome].fitness
            temp_population.append(c)
        self.population = temp_population

    def delete_circuit(self, chromosome_reference):
        temp_vertexes = [None for i in range(self.vertexes_quantity)]
        previous_vertex = [-1 for i in range(self.vertexes_quantity)]
        paths_length = [ENDLESS_FLOAT for i in range(self.vertexes_quantity)]
        tag = [False for i in range(self.vertexes_quantity)]
        tree_vertexes_quantity = 0
        min_length = ENDLESS_FLOAT
        record = 0
        paths_unit = []
        empty_list = []

        # construct new topology.
        for i in range(self.edges_quantity):
            if chromosome_reference.genes[i] is True:
                index0, index1 = self.edges[i].vertex_id0, self.edges[i].vertex_id1
                if temp_vertexes[index0] is None:
                    temp_vertexes[index0] = Vertex()
                    tree_vertexes_quantity += 1
                temp_vertexes[index0].connect_vertex.append(index1)
                temp_vertexes[index0].connect_edge.append(i)
                temp_vertexes[index0].degree += 1
                if temp_vertexes[index1] is None:
                    temp_vertexes[index1] = Vertex()
                    tree_vertexes_quantity += 1
                temp_vertexes[index1].connect_vertex.append(index0)
                temp_vertexes[index1].connect_edge.append(i)
                temp_vertexes[index1].degree += 1

        # to handle exception
        if temp_vertexes[self.sou_vertex] is None:
            logger.error("!!!multi cast tree not found, no exist link to dst or too low available bandwidth!!!")
            return empty_list

        # evaluate path.
        vertex_selected = self.sou_vertex
        tag[self.sou_vertex] = True
        paths_length[self.sou_vertex] = 0.0
        for i in range(tree_vertexes_quantity - 1):
            for j in range(self.vertexes_quantity):
                if temp_vertexes[j] is not None and tag[j] is False:
                    min_length = paths_length[j]
                    record = j
                    break
            for j in range(temp_vertexes[vertex_selected].degree):
                if tag[temp_vertexes[vertex_selected].connect_vertex[j]] is False:
                    temp_edge = temp_vertexes[vertex_selected].connect_edge[j]
                    if self.edges[temp_edge].available_width < self.min_available_bandwidth:
                        temp_edge_cost = ENDLESS_FLOAT
                    else:
                        temp_edge_cost = self.edges[temp_edge].cost
                    if paths_length[temp_vertexes[vertex_selected].connect_vertex[j]] > \
                       paths_length[vertex_selected] + temp_edge_cost:
                        paths_length[temp_vertexes[vertex_selected].connect_vertex[j]] = \
                            paths_length[vertex_selected] + temp_edge_cost
                        previous_vertex[temp_vertexes[vertex_selected].connect_vertex[j]] = vertex_selected
            for j in range(self.vertexes_quantity):
                if temp_vertexes[j] is not None and tag[j] is False and paths_length[j] < min_length:
                    min_length = paths_length[j]
                    record = j
            vertex_selected = record
            tag[vertex_selected] = True

        for i in range(self.des_vertexes_quantity):
            temp_path = []
            j = self.des_vertexes[i]
            if previous_vertex[j] == -1:
                logger.error("!!!multi cast tree not found, no exist link to dst or too low available bandwidth!!!")
                return empty_list
            temp_path.append(j)
            while previous_vertex[j] != -1:
                temp_path.insert(0, previous_vertex[j])
                j = previous_vertex[j]
            paths_unit.append(temp_path)
        return paths_unit

    def genetic_algorithm(self):
        outstanding = None
        for i in range(self.max_generation):
            follow_outstanding = self.crossover_multi_point__remain_outstanding(self.crossover_probability, outstanding)
            self.variation__remain_outstanding(self.variation_probability, outstanding, follow_outstanding)
            for j in range(self.chromosome_quantity):
                self.fitness_evaluate(self.population[j])
            self.selection_championships(self.candidate_quantity)
            outstanding = self.evaluate_population()


class Link(object):
    def __init__(self):
        self.des_vertex_id = 0
        self.link = []  # (int), it show a link by store a sequence of vertex id, for example: [45, 15, 82, 67, 20],
        # then the sou_vertex is 45, the des_vertex_id is 20.


class Chromosome(object):
    def __init__(self, edges_quantity):
        self.genes = [False for i in range(edges_quantity)]
        self.fitness = ENDLESS_FLOAT


class Vertex(object):
    def __init__(self):
        self.id = 0
        self.degree = 0  # this variable value == self.connect_vertex.__len__() == self.connect_edge__len__()  forever.
        self.connect_vertex = []  # (int), store all self.id vertex's neighbor vertexes' ids
        self.connect_edge = []  # (int), store edges' ids, these edges connect self.id vertex to neighbor vertexes.
    # for example:
    # a class Vertex instance: v,
    #             v.id == 12,
    # v.connect_vertex == [33, 7, 144, 26, 95],
    #   v.connect_edge == [4, 72, 63, 15, 101],
    #
    # then it means: v.degree == 5,
    #                v connect to No.33  vertex, by virtue of No.4   edge
    #                v connect to No.7   vertex, by virtue of No.72  edge
    #                v connect to No.144 vertex, by virtue of No.63  edge
    #                v connect to No.26  vertex, by virtue of No.15  edge
    #                v connect to No.95  vertex, by virtue of No.101 edge


class Edge(object):
    def __init__(self):
        self.id = 0
        self.vertex_id0 = 0  # store one of the two vertexes that are connected by this edge.
        self.vertex_id1 = 0  # store another one of the two vertexes that are connected by this edge.
        self.width = 0.0
        self.available_width = 0.0
        self.packet_loss = 0.0
        self.delay = 0.0
        self.delay_jitter = 0.0
        self.cost = 0.0
    # if self.id == 45, self.vertex_id0 == 7, self.vertex_id1 == 94,
    # then we can be sure that No.7 vertex connect to No.94 vertex by virtue of No.45 edge.
