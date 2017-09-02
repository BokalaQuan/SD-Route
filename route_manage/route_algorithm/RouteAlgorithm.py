import logging
import random
import json
import copy
import networkx as nx

from lib.project_lib import Megabits
from topology_manage.object.link import LinkTableApi


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


class Algorithm(object):
    def __init__(self):
        if not hasattr(self, 'switch_queue'):
            super(Algorithm, self).__init__()

            # map of switch dpid and serial number:
            # num = self.switch_queue.index(dpid)
            # dpid = self.switch_queue[num]
            self.switch_queue = []

            # map of edge (src_dpid, dst_dpid) and serial number:
            # num = self.edge_queue.index((src_dpid, dst_dpid))
            # (src_dpid, dst_dpid) = self.edge_queue = [num]
            self.edge_queue = []

            # switch neighbors collection: {num: neighbor_list}
            self.switch_neighbors = {}

            # edge collection: {(src_num, dst_num): link}
            self.edge_collection = {}

            # for adaptation
            self.vertexs = []
            self.edges = []

            # population:
            # already remove invalid link by bandwidth threshold
            self.links = []
            self.fitness = []

            # link cache by GA: {(src_num, dst_num):[]}
            self.link_cache = {}

    def get_link(self, src, dst, link_type=None):
        pass

    def init_algorithm(self, switches, links):
        pass

    def update_link_status(self, links):
        pass

    def run(self, src_dpid, dst_dpid, min_bandwidth):
        pass

    def param_to_dict(self):
        pass

    def update_param(self, data):
        pass

    def _check_link_logic(self, link_list):
        for i in list(range(len(link_list)-1)):
            neighbors = self.vertexs[link_list[i]][1]
            if link_list[i+1] not in neighbors:
                logger.error("link logic check failed, error at %s in link:%s",
                             i+1, link_list)
                raise AssertionError
        return link_list


class GAPopulation(Algorithm):
    def __init__(self, delay_coefficient=5000, cost_coefficient=0.02, bw_load_coefficient=50,
                 generation_max=20, max_hop=6, crossover_probability=0.7, mutation_probability=0.1):
        if not hasattr(self, 'cost_coeffieient'):
            super(GAPopulation, self).__init__()

            self.age = 0

            self.delay_coefficient = float(delay_coefficient)
            self.cost_coefficient = float(cost_coefficient)
            self.bw_load_coefficient = float(bw_load_coefficient)
            self.generation_max = int(generation_max)
            self.max_hop = int(max_hop)
            self.crossover_probability = float(crossover_probability)
            self.mutation_probability = float(mutation_probability)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(GAPopulation, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def get_link(self, src, dst, link_type=None):
        fitness_max = 0
        num = 0

        for i, f in enumerate(self.fitness):
            if f > fitness_max:
                fitness_max = f
                num = i
        links_in_dpid = []
        links_in_num = self.links[num]
        self.link_cache[links_in_num[0], links_in_num[1]] = links_in_num
        for l in links_in_num:
            links_in_dpid.append(self.switch_queue[l])

        link_cost = 0
        for i in range(0, len(links_in_num)-1):
            for e in self.edges:
                if links_in_num[i] == e[1] and links_in_num[i+1] == e[2] or \
                   links_in_num[i] == e[2] and links_in_num[i+1] == e[1]:
                    link_cost += e[4]
                    break

        return links_in_dpid, link_cost

    def init_algorithm(self, switches, links):
        """
            called when topo changed.
            both switch enter/leave or link add/delete.
        """
        # initialize the arguments
        self.switch_queue = []
        self.edge_queue = []
        self.switch_neighbors = {}
        self.edge_collection = {}
        self.vertexs = []
        self.edges = []
        self.links = []
        self.fitness = []
        self.link_cache = {}

        # update switch/edge queue
        self.switch_queue = switches.keys()
        self.edge_queue = links.keys()

        # update switch neighbors
        for dpid, sw in switches.items():
            num = self.switch_queue.index(dpid)
            neighbors_in_dpid = sw.neighbors.keys()
            neighbors_in_num = []
            for n in neighbors_in_dpid:
                neighbors_in_num.append(self.switch_queue.index(n))
            self.switch_neighbors[num] = neighbors_in_num

        # init edge collection, ev.available_band = None
        for dpids, edge in links.items():
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]
            self.edge_collection[(src_num, dst_num)] = ev
            self.edges.append([0, src_num, dst_num,
                               float(ev.delay), float(ev.cost),
                               ev.available_band, float(ev.total_band)])

        # update self.vertexs
        for src_num, neighbors in self.switch_neighbors.items():
            self.vertexs.append([len(neighbors), neighbors, []])
            for dst_num in neighbors:
                for num, edge in enumerate(self.edges):
                    if (edge[1], edge[2]) == (src_num, dst_num) or \
                       (edge[1], edge[2]) == (dst_num, src_num):
                        self.vertexs[src_num][2].append(num)

    def update_link_status(self, links):
        self.age = 0

        assert isinstance(links, LinkTableApi)

        self.edges = []
        for dpids, edge in links.items():
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]
            self.edge_collection[(src_num, dst_num)] = ev
            self.edges.append([0, src_num, dst_num,
                               float(ev.delay), float(ev.cost),
                               float(ev.available_band), float(ev.total_band)])
            logger.debug("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
                         dpids[0], dpids[1],
                         float(ev.available_band)/Megabits,
                         float(ev.total_band)/Megabits,
                         1.0 - float(ev.available_band) / float(ev.total_band))

    def run(self, src_dpid, dst_dpid, min_bandwidth):
        self.evolve(src_dpid, dst_dpid, min_bandwidth)

    def fitness_evaluate(self, paths, min_bandwidth, vertexs, edges):
        edge_paths = []
        fitness = []
        for i in range(paths.__len__()):
            edge_paths.append([])
            for j in range(paths[i].__len__() - 1):
                edge_paths[i].append(find_edge(paths[i][j], paths[i][j + 1], vertexs))
        for i in range(edge_paths.__len__()):
            fitness.append(0)
            delay = 0
            cost = 0
            bw_load_rate = 0
            for j in range(edge_paths[i].__len__()):
                if edges[edge_paths[i][j]][5] < min_bandwidth:
                    fitness[i] = -1000
                    break
                delay += edges[edge_paths[i][j]][3]
                cost += edges[edge_paths[i][j]][4]
                bw_load_rate += (1 - edges[edge_paths[i][j]][5] / edges[edge_paths[i][j]][6])
            if fitness[i] == 0:
                assert (delay, cost, bw_load_rate) != (0, 0, 0)
                fitness[i] = 10.0 / (self.delay_coefficient * delay +
                                     self.cost_coefficient * cost +
                                     self.bw_load_coefficient * bw_load_rate)
        return fitness

    def init(self, src, dst, max_hop):
        return find_path_dfs(src, dst, max_hop, self.vertexs)

    @staticmethod
    def select(paths, fitness):
        default_path = 0
        for i in range(len(fitness)):
            if fitness[i] > 0:
                default_path = i
                break

        path_selected = default_path
        new_paths = []
        select_num_coefficient = 3
        if fitness.__len__() < select_num_coefficient:
            return paths
        for i in range(paths.__len__()):
            max_fitness = -1000
            for j in range(fitness.__len__() / select_num_coefficient):
                index = int(random.random() * fitness.__len__())
                if fitness[index] > max_fitness:
                    max_fitness = fitness[index]
                    path_selected = index

            # when select failed, choose the first adapt one.
            new_paths.append(paths[path_selected][:])
        return new_paths

    def cross(self):
        """
            randomly select two links to cross
        """
        random.shuffle(self.links)

        for num in range(len(self.links) / 2):
            if random.random() > self.crossover_probability:
                continue
            indv1 = self.links[2*num]
            indv2 = self.links[2*num + 1]
            self._list_cross(indv1, indv2)

    @staticmethod
    def _list_cross(list1, list2):
        """
            cross list1 and list2 at section with same [head: end],
            ignore the repeat point in this section.

            cross maybe 'failed' in:
            list1 = [1, 2, 3, 4, 5, 6, 7]
            list2 = [1, 2, 3, 8, 9 ,7]
            when try to cross section likes:
            [1, 2] or [1, 2, 3]
            but we think it's a normal condition and return None
            although cross action is invalid.

            :return True, False, None
        """
        if list1 == list2:
            return None

        list1_origin = list(list1)
        list2_origin = list(list2)
        logger.debug("list1_origin:%s, list2_origin:%s",
                     list1_origin, list2_origin)

        pre_cmp_list = []

        # find all same items
        for i in list1:
            if i in list2:
                pre_cmp_list.append(i)

        if len(pre_cmp_list) == 2:
            # no same item between src and dst
            return False
        elif len(pre_cmp_list) == 3:
            # one same item, randomly cross the front or behind section
            item = pre_cmp_list.pop()
            l1_num = list1.index(item)
            l2_num = list2.index(item)

            if (l1_num == 1 and l2_num == 1) or \
                    (l1_num == len(list1) - 2 and l2_num == len(list2) - 2):
                # no need to cross
                return False

            if random.randint(0, 1):
                # cross front section
                logger.debug("cross front section, lists1:%s, l1_num:%s, list2:%s, l2_num:%s",
                             list1, l1_num, list2, l2_num)
                list1[:l1_num], list2[:l2_num] = \
                    list2[:l2_num], list1[:l1_num]
            else:
                # cross behind section
                logger.debug("cross behind section, lists1:%s, l1_num:%s, list2:%s, l2_num:%s",
                             list1, l1_num, list2, l2_num)
                list1[l1_num + 1:], list2[l2_num + 1:] = \
                    list2[l2_num + 1:], list1[l1_num + 1:]
            return True
        else:
            # get head rnd, should not select the last one(dst)
            rnd_head = random.randint(0, len(pre_cmp_list) - 2)
            item_head = pre_cmp_list[rnd_head]
            pre_cmp_list = pre_cmp_list[rnd_head + 1:len(pre_cmp_list)]

            rnd_end = random.randint(0, len(pre_cmp_list) - 1)
            item_end = pre_cmp_list[rnd_end]

            l1_head_num = list1.index(item_head)
            l1_end_num = list1.index(item_end)
            if l1_head_num > l1_end_num:
                # cause pre_cmp_list depend on list1,
                # l1_head_num will never > l1_end_num
                assert 0
                l1_head_num, l1_end_num = l1_end_num, l1_head_num
                item_head, item_end = item_end, item_head

            l2_head_num = list2.index(item_head)
            l2_end_num = list2.index(item_end)
            if l2_head_num > l2_end_num:
                l1_exchange = list1[l1_head_num-1:l1_end_num]
                l2_exchange = list2[l2_end_num+1:l2_head_num]
                l2_exchange.reverse()
                list1 = list1_origin[:l1_head_num+1] + l2_exchange + list1_origin[l1_end_num:]
                list2 = list2_origin[:l2_end_num+1] + l1_exchange + list2_origin[l2_head_num:]
                pass
            else:
                list1[l1_head_num:l1_end_num], list2[l2_head_num:l2_end_num] = \
                    list2[l2_head_num:l2_end_num], list1[l1_head_num:l1_end_num]

            logger.debug("rnd cross, lists1:%s, l1{head:%s, end:%s}, list2:%s, l2{head:%s, end:%s}",
                         list1, l1_head_num, l1_end_num,
                         list2, l2_head_num, l2_end_num)

            if list1 == list1_origin and list2 == list2_origin:
                # list1 list2 exchange
                return None
            return True

    def remove_redundant_link(self):
        """
            remove redundant link in all links after cross.
        """
        threshold = 8

        for i in range(len(self.links)):
            new_link = self._remove_redundancy(self.links[i])
            counter = 0
            while new_link is False:
                new_link = self._remove_redundancy(self.links[i])
                counter += 1

                if counter > threshold:
                    logger.error("remove redundant link failed, find new one by DFS.")
                    link = self.links[i]
                    new_link = find_path_dfs(link[0], link[len(link)-1],
                                             self.max_hop, self.vertexs)[0]
                    break

            self.links[i] = new_link

    @staticmethod
    def _remove_redundancy(lists):
        """
            remove redundancy in list.
            select a new lists from redundant path.

            :return: lists, False
        """
        # get redundant collection.
        red_dict = {}
        red_dict_temp = {}
        for num, item in enumerate(lists):
            if item not in red_dict_temp:
                red_dict_temp[item] = [num]
                continue
            red_dict_temp[item].append(num)
        for i in red_dict_temp.keys():
            l = red_dict_temp[i]
            assert len(l) < 3
            if len(l) == 2:
                red_dict[i] = l

        if not red_dict:
            # no redundancy.
            return lists

        # find head and end redundant item.
        num_min = len(lists)
        num_max = 0
        head_item, end_item = None, None
        for key in red_dict.keys():
            head_num = red_dict[key][0]
            end_num = red_dict[key][1]
            if head_num < num_min:
                num_min = head_num
                head_item = key
            if end_num > num_max:
                num_max = end_num
                end_item = key

        # redundancy caused by cross, so lists are directed.
        if head_item == end_item:
            rval = lists[:num_min]+lists[num_max:len(lists)]
            return rval

        # select all redundant number
        red_list_num = []
        for num in range(num_min, num_max+1):
            if lists[num] in red_dict:
                red_list_num.append(num)

        # select path section: [[0,3], [7,9], [4,5], [11,12]]
        sel_path_section = []
        sel_item_list = []

        # point for red_list_num
        num_point = 0
        i = 0  # for while breaking.
        while True:
            red_num = red_list_num[num_point]
            red_item = lists[red_num]
            sel_nums = red_dict[red_item]
            if red_item not in sel_item_list:
                # if not sel_num_list:
                if not sel_path_section:
                    # add first section
                    sel_item_list.append(red_item)
                    origin_num = sel_nums[random.randint(0, 1)]

                    # sel_num_list.append(origin_num)
                    sel_path_section.append([0, sel_nums[0]])
                    sel_path_section.append([origin_num])

                    num = red_list_num.index(origin_num)
                    num_point = num+1
                    pass
                else:
                    # number of last item in sel_num_list
                    # last_num = sel_num_list[len(sel_num_list)-1]
                    last_num = sel_path_section[len(sel_path_section)-1][0]
                    if last_num > max(sel_nums):
                        # all redundant item's number < last one in sel_num_list.
                        # point just move forward.
                        logger.debug("last_num > max(sel_nums)")

                        num_point += 1
                        continue
                    elif last_num < min(sel_nums):
                        # all redundant item's number > last one in sel_num_list.
                        # select sel_nums[0] as the end of current section
                        # select one randomly as the head of next section
                        logger.debug("last_num < min(sel_nums)")

                        sel_item_list.append(red_item)
                        origin_num = sel_nums[random.randint(0, 1)]

                        # sel_num_list.append(origin_num)
                        t = sel_path_section.pop()
                        t.append(sel_nums[0])
                        sel_path_section.append(t)

                        sel_path_section.append([origin_num])

                        num = red_list_num.index(origin_num)
                        num_point = num+1
                        pass
                    else:
                        # sel_nums[0] < last_num < sel_nums[1]
                        # select sel_nums[1] as the end of current section
                        # select one randomly as the head of next section
                        logger.debug("sel_nums[0] < last_num < sel_nums[1]")

                        sel_item_list.append(red_item)
                        origin_num = sel_nums[random.randint(0, 1)]

                        # sel_num_list.append(sel_nums[1])
                        t = sel_path_section.pop()
                        t.append(sel_nums[1])
                        sel_path_section.append(t)

                        sel_path_section.append([origin_num])

                        num = red_list_num.index(origin_num)
                        num_point = num+1
                        pass
            else:
                return False

            i += 1
            if lists[red_num] == end_item:
                sel_path_section.pop()
                t = [sel_nums[1], len(lists)-1]
                sel_path_section.append(t)
                break

            if i > len(red_list_num):
                logger.info("_remove_redundancy break while get threshold.")
                return False

        # generate return value.
        rval = []
        for num_item in sel_path_section:
            for n in range(num_item[0], num_item[1]):
                rval.append(lists[n])
        rval.append(lists[len(lists)-1])
        return rval

    def mutate(self):
        """
            point mutation
        """
        for n, link in enumerate(self.links):
            if random.random() > self.mutation_probability:
                continue
            logger.debug("origin link:%s", link)

            if len(self.links[n]) == 2:
                continue

            # choose one vertex and mutate.
            mutate_new_vertex, mutate_sel_num = self._mutate_vertex_select(self.links[n])
            mutate_link = self.links[n][:]
            mutate_link[mutate_sel_num] = mutate_new_vertex
            logger.debug("mutate_link:%s, mutate_sel_num:%s", mutate_link, mutate_sel_num)

            # try to mutate boost.
            new_link = self._mutate_boost(mutate_link, mutate_sel_num)
            if new_link is not False:
                logger.debug("mutate boot, link:%s", new_link)
                self.links[n] = new_link
                continue

            # when mutate boost failed, find new one by DFS.
            new_link = self._mutate_find_new_path(mutate_link, mutate_sel_num)
            if new_link is not False:
                logger.debug("find new one by DFS:%s", new_link)
                self.links[n] = new_link
                continue
            else:
                logger.error("find new link failed, revert link change in mutate.")
                self.links[n] = link
                pass

    def _mutate_vertex_select(self, link):
        """
            select a vertex for mutation randomly.
        """
        rnd = random.randint(1, len(link)-2)
        mutated_vertex_num = link[rnd]
        former_vertex_neighbor = copy.copy(self.vertexs[link[rnd-1]][1])

        index = former_vertex_neighbor.index(mutated_vertex_num)
        former_vertex_neighbor.pop(index)

        mutate_dst_num = former_vertex_neighbor[random.randint(0, len(former_vertex_neighbor)-1)]

        return mutate_dst_num, rnd

    def _mutate_boost(self, link, mutate_num):
        """
            try to find neighbor of new vertex(mutated) in remaining link.
        """
        mutate_item = link[mutate_num]
        if mutate_item == link[len(link)-1]:
            return link[:mutate_num+1]
        return False

    def _mutate_find_new_path(self, link, mutate_num_in_link):
        dfs_paths = find_path_dfs(link[mutate_num_in_link], link[len(link)-1],
                                  self.max_hop, self.vertexs)
        assert len(dfs_paths) != 0
        counter_list = [0] * len(dfs_paths)

        for n, path in enumerate(dfs_paths):
            for vertex in link:
                if vertex in path:
                    break
                else:
                    counter_list[n] += 1
            if counter_list[n] == len(link):
                return link[:mutate_num_in_link] + path

        # find by dfs failed, choose the most similar one and remove redundancy.
        similar_path = dfs_paths[counter_list.index(max(counter_list))]
        similar_link = link[:mutate_num_in_link] + similar_path

        # remove redundancy
        threshold = 8

        new_link = self._remove_redundancy(similar_link)
        counter = 0
        while new_link is False:
            new_link = self._remove_redundancy(similar_link)
            counter += 1
            if counter > threshold:
                return False
        return new_link

    def evolve(self, src_dpid, dst_dpid, min_bandwidth):
        src_num = self.switch_queue.index(src_dpid)
        dst_num = self.switch_queue.index(dst_dpid)
        logger.debug("population init")
        self.links = self.init(src_num, dst_num, self.max_hop)
        logger.debug("population age: %s, init links:%s", self.age, self.links)

        while True:
            self.fitness = self.fitness_evaluate(self.links, min_bandwidth, self.vertexs, self.edges)

            self.links = self.select(self.links, self.fitness)
            logger.debug("population select, links=%s", self.links)
            self.fitness = self.fitness_evaluate(self.links, min_bandwidth, self.vertexs, self.edges)

            item = self.links[0]
            if self.links.count(item) == len(self.links):
                logger.debug("evolve end when all links are same.")
                break

            if self.age > self.generation_max:
                logger.debug("evolve end when get max generation.")
                break

            self.cross()
            logger.debug("population cross, links=%s", self.links)
            self.remove_redundant_link()
            logger.debug("remove redundant, links=%s", self.links)

            self.mutate()
            logger.debug("population mutate, links=%s", self.links)
            self.remove_redundant_link()
            logger.debug("remove redundant, links=%s", self.links)

            # fitness calculated for logger
            # self.fitness = self.fitness_evaluate(self.links, min_bandwidth, self.vertexs, self.edges)
            # logger.debug("fitness:%s", self.fitness)

            self.age += 1
            logger.debug("population age: %s, links:%s", self.age, self.links)

    def param_to_dict(self):
        body = json.dumps({"delay_coefficient": self.delay_coefficient,
                           "cost_coefficient": self.cost_coefficient,
                           "bw_load_coefficient": self.bw_load_coefficient,
                           "generation_max": self.generation_max,
                           "max_hop": self.max_hop,
                           "crossover_probability": self.crossover_probability,
                           "mutation_probability": self.mutation_probability})
        return body

    def update_param(self, data):
        if data["algorithm_type"] != "GA":
            return False

        def update(s, k, p):
            if k in p: return float(p[k])
            else: return s

        self.delay_coefficient = update(self.delay_coefficient, "delay_coefficient", data)
        self.cost_coefficient = update(self.cost_coefficient, "cost_coefficient", data)
        self.bw_load_coefficient = update(self.bw_load_coefficient, "bw_load_coefficient", data)
        self.generation_max = update(self.generation_max, "generation_max", data)
        self.max_hop = update(self.max_hop, "max_hop", data)
        self.crossover_probability = update(self.crossover_probability, "crossover_probability", data)
        self.mutation_probability = update(self.mutation_probability, "mutation_probability", data)
        return True


class GAIndividual(object):
    def __init__(self, link, total_band, available_band, delay, cost):
        super(GAIndividual, self).__init__()

        self.link = link

        self.total_band = total_band
        self.available_band = available_band
        self.delay = delay
        self.cost = cost


class Dijkstra(Algorithm):
    def __init__(self, delay_coefficient=5000, cost_coefficient=0.02, bw_load_coefficient=50):
        if not hasattr(self, 'cost_coeffieient'):
            super(Dijkstra, self).__init__()

            self.delay_coefficient = delay_coefficient
            self.cost_coefficient = cost_coefficient
            self.bw_load_coefficient = bw_load_coefficient

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(Dijkstra, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def get_link(self, src, dst, link_type=None):
        dst_num = self.switch_queue.index(dst)

        links_in_num = None
        for num, link in enumerate(self.links):
            if dst_num == link[len(link)-1]:
                links_in_num = self.links[num]
                break

        # handle algorithm failure mode
        if links_in_num is None:
            logger.error("links_in_num is None")
            return None, None
        elif len(links_in_num) < 2:
            # such as when no path from switch A(number:1) to switch B(number:2)
            # the result will be [2]
            logger.error("destination switch unreachable in graph.")
            return None, None

        self.link_cache[links_in_num[0], links_in_num[1]] = links_in_num
        links_in_dpid = []
        for l in links_in_num:
            links_in_dpid.append(self.switch_queue[l])

        link_cost = 0
        for i in range(0, len(links_in_num)-1):
            for e in self.edges:
                if links_in_num[i] == e[1] and links_in_num[i+1] == e[2] or \
                   links_in_num[i] == e[2] and links_in_num[i+1] == e[1]:
                    link_cost += e[4]
                    break

        return links_in_dpid, link_cost

    def init_algorithm(self, switches, links):
        """
            called when topo changed.
            both switch enter/leave or link add/delete.
        """
        logger.info("topology's data input Dijktra")
        print "switch's number = ", len(switches)
        print "link's number = ", len(links)

        self.switch_queue = []
        self.edge_queue = []
        self.switch_neighbors = {}
        self.edge_collection = {}
        self.vertexs = []
        self.edges = []
        self.links = []
        self.fitness = []
        self.link_cache = {}

        # update switch/edge queue
        self.switch_queue = switches.keys()
        self.edge_queue = links.keys()

        # update switch neighbors
        for dpid, sw in switches.items():
            num = self.switch_queue.index(dpid)
            neighbors_in_dpid = sw.neighbors.keys()
            neighbors_in_num = []
            for n in neighbors_in_dpid:
                neighbors_in_num.append(self.switch_queue.index(n))
            self.switch_neighbors[num] = neighbors_in_num

        # update edge collection
        # for dpids, edge in links.items():
        #     src_num = self.switch_queue.index(dpids[0])
        #     dst_num = self.switch_queue.index(dpids[1])
        #     ev = edge.values()[0]
        #     self.edge_collection[(src_num, dst_num)] = ev
        #     self.edges.append([0, src_num, dst_num,
        #                        float(ev.delay), float(ev.cost),
        #                        ev.available_band, float(ev.total_band)])

        '''
        Change cost to loss
        '''
        for dpids, edge in links.items():
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]
            self.edge_collection[(src_num, dst_num)] = ev
            self.edges.append([0, src_num, dst_num,
                               float(ev.delay), float(ev.cost),
                               ev.available_band, float(ev.total_band),
                               ev.pkt_loss])


        # update self.vertexs
        for src_num, neighbors in self.switch_neighbors.items():
            self.vertexs.append([len(neighbors), neighbors, []])
            for dst_num in neighbors:
                for num, edge in enumerate(self.edges):
                    if (edge[1], edge[2]) == (src_num, dst_num) or \
                       (edge[1], edge[2]) == (dst_num, src_num):
                        self.vertexs[src_num][2].append(num)

    def update_link_status(self, links):
        assert isinstance(links, LinkTableApi)

        self.edges = []
        # for dpids, edge in links.items():
        #     src_num = self.switch_queue.index(dpids[0])
        #     dst_num = self.switch_queue.index(dpids[1])
        #     ev = edge.values()[0]
        #     self.edge_collection[(src_num, dst_num)] = ev
        #     self.edges.append([0, src_num, dst_num,
        #                        float(ev.delay), float(ev.cost),
        #                        float(ev.available_band), float(ev.total_band)])
        #     logger.debug("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
        #                  dpids[0], dpids[1],
        #                  float(ev.available_band)/Megabits,
        #                  float(ev.total_band)/Megabits,
        #                  1.0 - float(ev.available_band) / float(ev.total_band))

        '''
        Change cost to loss
        '''
        for dpids, edge in links.items():
            src_num = self.switch_queue.index(dpids[0])
            dst_num = self.switch_queue.index(dpids[1])
            ev = edge.values()[0]
            self.edge_collection[(src_num, dst_num)] = ev
            self.edges.append([0, src_num, dst_num,
                               float(ev.delay), float(ev.cost),
                               float(ev.available_band), float(ev.total_band),
                               ev.pkt_loss])
            logger.debug("src_dpid:%s, dst_dpid:%s, available band:%s Mbits, total band:%s Mbits, usage:%s",
                         dpids[0], dpids[1],
                         float(ev.available_band)/Megabits,
                         float(ev.total_band)/Megabits,
                         1.0 - float(ev.available_band) / float(ev.total_band))



    def run(self, src_dpid, dst_dpid, min_bandwidth):
        src_num = self.switch_queue.index(src_dpid)
        self.links = self.calculate(src_num, self.vertexs, self.edges)

    def calculate(self, sou_vertex, vertexs, edges):
        """
            return paths list from source vertex to all the other destination
            vertex, such as:
            when source vertex number = 5
            paths = [[5, 6, 7, ..., 1], [5, ..., 4], [5, 8], ..., [5]]
        """
        tag = [0 for i in range(vertexs.__len__())]
        previous_vertex = [-1 for i in range(vertexs.__len__())]
        paths_length = [10000 for i in range(vertexs.__len__())]
        paths = []

        vertex_selected = sou_vertex
        tag[sou_vertex] = 1
        paths_length[sou_vertex] = 0

        for i in range(vertexs.__len__() - 1):
            for j in range(vertexs.__len__()):
                if tag[j] == 0:
                    min_length = paths_length[j]
                    record = j
                    break
            for j in vertexs[vertex_selected][1]:
                if tag[j] == 0:
                    temp = self.use_available_bandwidth_mark_weight(vertex_selected, j, edges)
                    if paths_length[vertex_selected] + temp < paths_length[j]:
                        paths_length[j] = paths_length[vertex_selected] + temp
                        previous_vertex[j] = vertex_selected
            for j in range(vertexs.__len__()):
                if tag[j] == 0:
                    if paths_length[j] < min_length:
                        min_length = paths_length[j]
                        record = j
            vertex_selected = record
            tag[vertex_selected] = 1
        for i in range(vertexs.__len__()):
            paths.append([i])
            j = i
            while not previous_vertex[j] == -1:
                j = previous_vertex[j]
                paths[i].insert(0, j)
        return paths

    def use_available_bandwidth_mark_weight(self, vertex1, vertex2, edges):
        for i in range(edges.__len__()):
            if vertex1 == edges[i][1]:
                if vertex2 == edges[i][2]:
                    rval = (self.delay_coefficient * edges[i][3] +
                            self.cost_coefficient * edges[i][4] +
                            self.bw_load_coefficient * (1-edges[i][5]/edges[i][6]))
                    return rval
            if vertex2 == edges[i][1]:
                if vertex1 == edges[i][2]:
                    rval = (self.delay_coefficient * edges[i][3] +
                            self.cost_coefficient * edges[i][4] +
                            self.bw_load_coefficient * (1-edges[i][5]/edges[i][6]))
                    return rval
        return 2 * (self.delay_coefficient * 1 +
                    self.cost_coefficient * 100 +
                    self.bw_load_coefficient * 1)

    def param_to_dict(self):
        body = json.dumps({"delay_coefficient": self.delay_coefficient,
                           "cost_coefficient": self.cost_coefficient,
                           "bw_load_coefficient": self.bw_load_coefficient})
        return body

    def update_param(self, data):
        if data["algorithm_type"] != "Dij":
            return False

        def update(s, k, p):
            if k in p: return float(p[k])
            else: return s

        self.delay_coefficient = update(self.delay_coefficient, "delay_coefficient", data)
        self.cost_coefficient = update(self.cost_coefficient, "cost_coefficient", data)
        self.bw_load_coefficient = update(self.bw_load_coefficient, "bw_load_coefficient", data)
        return True


def find_path_dfs(sou_vertex, des_vertexs, max_hop, vertexs):
    """
        DFS and init
    """
    path_record = []
    pop_vertex = 0
    path = []
    search_space = []
    path.append(sou_vertex)
    search_space.append(vertexs[sou_vertex][1][:])
    while True:
        if search_space[search_space.__len__() - 1].__len__() > 0:
            pop_vertex = search_space[search_space.__len__() - 1].pop()
            path.append(pop_vertex)
        else:
            while search_space[search_space.__len__() - 1].__len__() == 0:
                path.pop()
                search_space.pop()
                if search_space.__len__() == 0:
                    return path_record
            continue
        if pop_vertex == des_vertexs:
            path_record.append(path[:])
            path.pop()
        else:
            if path.__len__() < max_hop:
                search_space.append([i for i in vertexs[pop_vertex][1] if i not in path][:])
            else:
                path.pop()


def find_edge(vertex1, vertex2, vertexs):
    if vertexs[vertex1][0] < vertexs[vertex2][0]:
        for i in range(vertexs[vertex1][0]):
            if vertexs[vertex1][1][i] == vertex2:
                return vertexs[vertex1][2][i]
        return -1
    else:
        for i in range(vertexs[vertex2][0]):
            if vertexs[vertex2][1][i] == vertex1:
                return vertexs[vertex2][2][i]
        return -1

'''
    By Bokala
'''

class RouteAlgorithm(object):

    def __init__(self):
        self.switch_queue = []
        self.link_queue = []

        self.nodes = []
        self.edges = []

        self.num_nodes = 0
        self.num_edges = 0

        self.src_node = None
        self.dst_node = None
        self.min_available_bandwidth = 0.0

        self.loss = 0
        self.delay = 0
        self.band = 0

        self.path = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(RouteAlgorithm, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance


    def init_algorithm(self, switches, links):

        logger.info("topology's data input RouteAlgorithm")
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


        self.src_node = src_dpid
        self.dst_node = dst_dpid
        self.min_available_bandwidth = min_available_bandwidth

        logger.debug("src_vertex:%s, dst_vertexes:%s, min_available_bandwidth:%s",
                     src_dpid, dst_dpid, float(min_available_bandwidth))

        self.main()
        logger.debug("Start Route Algorithm")




    def get_link(self, src, dst):
        return self.path, self.delay

    def main(self):
        graph = nx.Graph()

        for edge in self.edges:
            graph.add_edge(edge.src, edge.dst, delay=edge.delay, band=edge.band, loss=edge.loss)

        if random.random() < 0.5:
            path = nx.dijkstra_path(graph, self.src_node, self.dst_node, weight='delay')
        else:
            path = nx.dijkstra_path(graph, self.src_node, self.dst_node, weight='loss')

        self.path = path

        delay = 0.0
        loss = 1.0
        bandwidth = 9999999999999999.9
        for index in range(len(path) - 1):
            delay += graph.edge[path[index]][path[index + 1]]['delay']
            loss *= 1 - graph.edge[path[index]][path[index + 1]]['loss']
            if bandwidth > graph.edge[path[index]][path[index + 1]]['band']:
                bandwidth = graph.edge[path[index]][path[index + 1]]['band']

        self.delay = delay
        self.loss = 1-loss
        self.band = bandwidth

        print self.path, "delay=", self.delay, "ms pkt_loss=", int(self.loss * 100), "% bandwidth=", self.band



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