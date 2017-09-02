import logging
import random
import time

from route_manage.route_algorithm.RouteAlgorithm import GAPopulation
from RouteManage import BusinessType

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

"""
    test data, fattree 48
"""
edge_queue = [(2002, 3001), (1001, 2007), (1003, 2004), (2001, 3002), (2008, 3008), (2004, 3003), (1001, 2003),
              (2003, 3004), (1002, 2001), (2002, 3002), (2005, 3006), (1002, 2005), (2001, 3001), (2006, 3005),
              (1003, 2008), (2008, 3007), (1004, 2004), (1001, 2005), (2003, 3003), (1003, 2006), (1004, 2008),
              (2004, 3004), (1001, 2001), (1003, 2002), (2006, 3006), (2007, 3007), (2005, 3005), (1002, 2003),
              (1004, 2002), (2007, 3008), (1002, 2007), (1004, 2006)]
edges = [[0, 6, 13, 0.01, 20.0, 119999989.0, 120000000.0], [0, 1, 11, 0.001, 1000.0, 99999989.0, 100000000.0],
         [0, 3, 8, 0.01, 20.0, 19999989.0, 20000000.0], [0, 5, 14, 0.01, 20.0, 119999989.0, 120000000.0],
         [0, 12, 0, 0.01, 20.0, 119999989.0, 120000000.0], [0, 8, 15, 0.01, 10.0, 9999989.0, 10000000.0],
         [0, 1, 7, 0.001, 1000.0, 99999989.0, 100000000.0], [0, 7, 16, 0.01, 20.0, 19999988.0, 20000000.0],
         [0, 2, 5, 0.01, 20.0, 19999989.0, 20000000.0], [0, 6, 14, 0.01, 20.0, 119999990.0, 120000000.0],
         [0, 9, 18, 0.02, 2.0, 3999989.0, 4000000.0], [0, 2, 9, 0.01, 20.0, 19999989.0, 20000000.0],
         [0, 5, 13, 0.01, 20.0, 119999989.0, 120000000.0], [0, 10, 17, 0.02, 2.0, 3999989.0, 4000000.0],
         [0, 3, 12, 0.001, 1000.0, 99999989.0, 100000000.0], [0, 12, 19, 0.01, 20.0, 119999989.0, 120000000.0],
         [0, 4, 8, 0.01, 20.0, 19999989.0, 20000000.0], [0, 1, 9, 0.001, 1000.0, 99999989.0, 100000000.0],
         [0, 7, 15, 0.01, 20.0, 19999988.0, 20000000.0], [0, 3, 10, 0.01, 20.0, 19999989.0, 20000000.0],
         [0, 4, 12, 0.01, 20.0, 19999989.0, 20000000.0], [0, 8, 16, 0.01, 10.0, 9999989.0, 10000000.0],
         [0, 1, 5, 0.001, 1000.0, 99999989.0, 100000000.0], [0, 3, 6, 0.001, 1000.0, 99999989.0, 100000000.0],
         [0, 10, 18, 0.02, 2.0, 3999990.0, 4000000.0], [0, 11, 19, 0.01, 20.0, 119999989.0, 120000000.0],
         [0, 9, 17, 0.01, 10.0, 9999989.0, 10000000.0], [0, 2, 7, 0.01, 20.0, 19999989.0, 20000000.0],
         [0, 4, 6, 0.01, 20.0, 19999989.0, 20000000.0], [0, 11, 0, 0.01, 20.0, 119999989.0, 120000000.0],
         [0, 2, 11, 0.01, 20.0, 19999990.0, 20000000.0], [0, 4, 10, 0.01, 20.0, 19999990.0, 20000000.0]]
switch_queue = [3008, 1001, 1002, 1003, 1004, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 3001, 3002, 3003, 3004,
                3005, 3006, 3007]
switch_neighbors = {0: [12, 11], 1: [5, 7, 9, 11], 2: [5, 7, 9, 11], 3: [12, 6, 8, 10], 4: [12, 6, 8, 10],
                    5: [13, 2, 14, 1], 6: [13, 14, 3, 4], 7: [1, 2, 15, 16], 8: [16, 3, 4, 15], 9: [1, 2, 17, 18],
                    10: [3, 4, 17, 18], 11: [0, 1, 2, 19], 12: [0, 3, 4, 19], 13: [5, 6], 14: [5, 6], 15: [7, 8],
                    16: [7, 8], 17: [9, 10], 18: [9, 10], 19: [12, 11]}
vertexs = [[2, [12, 11], [4, 29]], [4, [5, 7, 9, 11], [22, 6, 17, 1]], [4, [5, 7, 9, 11], [8, 27, 11, 30]],
           [4, [12, 6, 8, 10], [14, 23, 2, 19]], [4, [12, 6, 8, 10], [20, 28, 16, 31]],
           [4, [13, 2, 14, 1], [12, 8, 3, 22]], [4, [13, 14, 3, 4], [0, 9, 23, 28]],
           [4, [1, 2, 15, 16], [6, 27, 18, 7]], [4, [16, 3, 4, 15], [21, 2, 16, 5]],
           [4, [1, 2, 17, 18], [17, 11, 26, 10]], [4, [3, 4, 17, 18], [19, 31, 13, 24]],
           [4, [0, 1, 2, 19], [29, 1, 30, 25]], [4, [0, 3, 4, 19], [4, 14, 20, 15]], [2, [5, 6], [12, 0]],
           [2, [5, 6], [3, 9]], [2, [7, 8], [18, 5]], [2, [7, 8], [7, 21]], [2, [9, 10], [26, 13]],
           [2, [9, 10], [10, 24]], [2, [12, 11], [15, 25]]]


class TestGAPopulation(object):
    def __init__(self):
        super(TestGAPopulation, self).__init__()
        self.algorithm = GAPopulation(crossover_probability=1,
                                      mutation_probability=1)

        self.algorithm.switch_queue = switch_queue
        self.algorithm.edge_queue = edge_queue
        self.algorithm.switch_neighbors = switch_neighbors

        self.algorithm.vertexs = vertexs
        self.algorithm.edges = edges
        self.update_edge()

    def update_edge(self):
        for i, e in enumerate(self.algorithm.edges):
            rnd = random.random()
            self.algorithm.edges[i][5] = e[6] - e[6]/10 * rnd

    def test_init(self, src_dpid=3001, dst_dpid=3008):
        """
        example:
            test_instance = TestGAPopulation()
            test_instance.test_init(3001, 3008)
        """
        src = switch_queue.index(src_dpid)
        dst = switch_queue.index(dst_dpid)

        self.algorithm.links = self.algorithm.init(src, dst, self.algorithm.max_hop)
        logger.info(self.algorithm.links)

    def test_evolve(self, src_dpid=3001, dst_dpid=3008):
        src = switch_queue.index(src_dpid)
        dst = switch_queue.index(dst_dpid)

        self.algorithm.links = self.algorithm.init(src, dst, self.algorithm.max_hop)
        self.update_edge()
        logger.debug(self.algorithm.links)

        self.algorithm.evolve(src_dpid, dst_dpid, BusinessType["FTP"])
        rval = self.algorithm.get_link(src, dst)
        logger.info(rval)

    def test_cross(self, src_dpid=3001, dst_dpid=3008):
        """
        example:
            test_instance = TestGAPopulation()
            test_instance.test_cross(3001, 3003)
        """
        src_num = switch_queue.index(src_dpid)
        dst_num = switch_queue.index(dst_dpid)

        self.algorithm.links = self.algorithm.init(src_num, dst_num, self.algorithm.max_hop)
        self.update_edge()
        logger.debug(self.algorithm.links)

        self.algorithm.fitness = self.algorithm.fitness_evaluate(
            self.algorithm.links, BusinessType["FTP"],
            self.algorithm.vertexs, self.algorithm.edges)

        self.algorithm.links = self.algorithm.select(self.algorithm.links,
                                                     self.algorithm.fitness)

        for n in list(range(100000)):
            logger.info("num:%s", n)

            self.algorithm.cross()
            logger.debug("population cross, links=%s", self.algorithm.links)

    def test_mutate_boost(self):
        link = [1, 2, 3, 4, 5, 6, 4, 7, 8, 9]
        mutate_num = 3
        self.algorithm._mutate_boost(link, mutate_num)
        mutate_num = 6
        self.algorithm._mutate_boost(link, mutate_num)

        link = [1, 2, 3, 4, 4, 5, 6, 7, 8, 9]
        mutate_num = 3
        self.algorithm._mutate_boost(link, mutate_num)
        mutate_num = 4
        self.algorithm._mutate_boost(link, mutate_num)

        link = [1, 2, 3, 4, 5, 6, 7, 8, 9, 4]
        mutate_num = 3
        self.algorithm._mutate_boost(link, mutate_num)
        mutate_num = 9
        self.algorithm._mutate_boost(link, mutate_num)

        link = [4, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        mutate_num = 0
        self.algorithm._mutate_boost(link, mutate_num)
        mutate_num = 4
        self.algorithm._mutate_boost(link, mutate_num)

    def test_list_cross(self):
        """
        example:
            test_instance = TestGAPopulation()
            test_instance.test_list_cross()
        """
        link1 = [13, 5, 2, 7, 16, 8, 15]
        link2 = [13, 6, 4, 8, 16, 7, 15]
        print self.algorithm._list_cross(link1, link2)

        link1 = [13, 5, 2, 11, 19, 12, 4, 8, 15]
        link2 = [13, 6, 14, 5, 1, 11, 2, 7, 15]
        print self.algorithm._list_cross(link1, link2)


if __name__ == '__main__':
    dpids = [3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008]

    for i in list(range(100000)):
        logger.info("num:%s", i)
        test_instance = TestGAPopulation()
        random.shuffle(dpids)
        src = dpids[0]
        dst = dpids[1]
        start = time.time()
        test_instance.test_evolve(src, dst)
        end = time.time()
        logger.info("time used:%s ====================================================",
                    end-start)

