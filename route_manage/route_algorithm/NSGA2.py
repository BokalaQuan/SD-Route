import copy
import math
import random
import logging

from MOEARouteAlgorithm import Individual, MOEA

POPSIZE = 30
MAXGEN = 80
PC = 0.8
PM = 0.08
INF = 99999999999.9

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

class IndividualNSGA(Individual):
    def __init__(self):
        super(Individual, self).__init__()
        self.dominated = False
        self.pareto_rank = 0
        self.crowding_distance = 0
        self.num_dominated = 0
        self.location = 0
        self.dominating_list = []

    def clear_property(self):
        self.dominated = False
        self.pareto_rank = 0
        self.crowding_distance = 0
        self.num_dominated = 0
        self.location = 0
        self.dominating_list = []


class NSGA2(MOEA):
    def __init__(self):
        super(NSGA2, self).__init__(POPSIZE, MAXGEN, PC, PM)

    def init_population(self):
        for i in range(self.population_size):
            ind = Individual()
            ind.initialize(self.num_edges, self.edges, self.src_node, self.dst_node)
            self.current_population.append(ind)
        logger.debug("Initialize population complete.")

    def init_external(self):
        self.external_population = []
        self.external_population = copy.copy(self.current_population)

    def make_new_population(self):
        union_list = []
        union_list.extend(self.current_population)
        union_list.extend(self.external_population)

        for ind in union_list:
            ind.clear_property()

        pareto_rank_set_list = fast_nondominate_sort(union_list)
        crowding_distance_sort(pareto_rank_set_list)

        new_population = []
        for pareto_rank_set in pareto_rank_set_list:
            new_population.extend(pareto_rank_set)

        self.current_population = []
        for i in range(self.population_size):
            self.current_population.append(new_population[i])

    def evolution(self):
        self.current_population = []

        for i in range(self.population_size):
            x = 0
            y = 0
            while x == y:
                x = random.randint(0,self.population_size-1)
                y = random.randint(0,self.population_size-1)

            ind1 = copy.copy(self.external_population[x])
            ind2 = copy.copy(self.external_population[y])

            if ind1.pareto_rank < ind2.pareto_rank:
                self.current_population.append(ind1)
            elif ind1.pareto_rank == ind2.pareto_rank and \
                ind1.crowding_distance > ind2.crowding_distance:
                self.current_population.append(ind1)
            else:
                self.current_population.append(ind2)

        for i in range(self.population_size/2):
            if random.random() < self.pc and random.random() < 0.5:
                self.current_population[i].single_point_crossover(self.current_population[self.population_size-i-1])
            elif random.random() < self.pc and random.random() >= 0.5:
                self.current_population[i].uniform_crossover(self.current_population[self.population_size - i - 1])


    def main(self):
        logger.debug('Using NSGA2 to find the path!')

        self.init_population()
        self.init_external()

        for gen in range(self.max_num_func_evals):
            self.make_new_population()
            self.init_external()
            self.evolution()

        for ind in self.external_population:
            if ind.pareto_rank > 0:
                self.external_population.remove(ind)

        object_sort(self.external_population, 'delay')

        #
        # for pre in xrange(self.external_population.__len__()):
        #     for bhd in xrange(pre + 1, self.external_population.__len__()):
        #         if self.external_population[pre].is_same_to(self.external_population[bhd]):
        #             del self.external_population[bhd]
        #             break


        # print (' >>>>>>>> path sets >>>>>>>>')
        # num = 1
        # for ind in self.external_population:
        #     print "ind ", num,": ",ind.paths, " delay=", ind.delay,"ms", " loss=", ind.loss, "bandwidth=", ind.bandwidth
        #     num += 1

        print ">>>>>>>>>>>>>> Min_Delay & Max_Loss >>>>>>>>>>>>>>>>>"

        ind = self.external_population[0]
        print ind.paths, "delay=", ind.delay, "ms pkt_loss=", int(ind.loss * 100), "% bandwidth=", ind.bandwidth


        print ">>>>>>>>>>>>>> Max_Delay & Min_Loss >>>>>>>>>>>>>>>>>"
        ind = self.external_population[len(self.external_population) - 1]
        print ind.paths, "delay=", ind.delay, "ms pkt_loss=", int(ind.loss * 100), "% bandwidth=", ind.bandwidth

    def get_link(self):
        # index = raw_input("Enter your select >>> ")
        rval_list = []

        rval_list.append(self.external_population[0].paths)
        rval_list.append(self.external_population[len(self.external_population) - 1].paths)

        print "*****************************************************************"


        # rval_ = copy.copy(self.external_population[int(index)].paths)

        # for li in rval_:
        #     for x in li:
        #         x = self.switch_queue[x]

        if self.state % 2 == 0:
            print "Choose Min_Delay & Max_Loss Path"
            return rval_list[0]
        else:
            print "Choose Max_Delay & Min_Loss Path"
            return rval_list[1]


def fast_nondominate_sort(popList):
    first_pareto_rank_set = []
    pareto_rank_set_list = []
    union_list = copy.copy(popList)

    for ind in union_list:
        ind.clear_property()

    for indPre in union_list:
        for ind in union_list:
            if indPre.is_better_than(ind):
                indPre.dominating_list.append(ind)
            elif ind.is_better_than(indPre):
                indPre.num_dominated += 1

        if indPre.num_dominated == 0:
            indPre.pareto_rank = 0
            first_pareto_rank_set.append(indPre)

    pareto_rank_set_list.append(first_pareto_rank_set)

    rank = 0
    while pareto_rank_set_list[rank]:
        pareto_rank_set = []
        for current_ind in pareto_rank_set_list[rank]:
            if current_ind.dominating_list.__len__() > 0:
                for dominated_ind in current_ind.dominating_list:
                    dominated_ind.num_dominated -= 1
                    if dominated_ind.num_dominated == 0:
                        dominated_ind.pareto_rank += 1
                        pareto_rank_set.append(dominated_ind)

        if pareto_rank_set:
            pareto_rank_set_list.append(pareto_rank_set)
            rank += 1
        else:
            break

    return pareto_rank_set_list


def crowding_distance_sort(paretoRankSetList):
    for paretoRankSet in paretoRankSetList:
        if paretoRankSet:
            if paretoRankSet.__len__() == 1:
                paretoRankSet[0].crowding_distance = INF
            elif paretoRankSet.__len__() == 2:
                paretoRankSet[0].crowding_distance = INF
                paretoRankSet[1].crowding_distance = INF
            else:
                length = len(paretoRankSet)

                for index in range(2):
                    if index == 0:
                        object_sort(paretoRankSet, 'delay')
                        min_delay = paretoRankSet[0].delay
                        max_delay = paretoRankSet[length-1].delay

                        if min_delay == max_delay:
                            max_delay += min_delay

                        for i in range(1,length-1):
                            paretoRankSet[i].crowding_distance += \
                                math.fabs(paretoRankSet[i+1].delay - paretoRankSet[i-1].delay)/(max_delay-min_delay)


                    elif index == 1:
                        object_sort(paretoRankSet, 'loss')
                        min_loss = paretoRankSet[0].loss
                        max_loss = paretoRankSet[length - 1].loss

                        if min_loss == max_loss:
                            max_loss += min_loss

                        if min_loss == 0 or max_loss == 0:
                            max_loss = 2
                            min_loss = 1

                        for i in range(1, length - 1):
                            paretoRankSet[i].crowding_distance += \
                                math.fabs(paretoRankSet[i + 1].loss - paretoRankSet[i - 1].loss) / \
                                (max_loss - min_loss)

        object_sort(paretoRankSet, 'crowding_distance')



def object_sort(list, object):
    count = len(list)

    if object == 'delay':
        for i in range(1, count):
            key = list[i]
            j = i - 1
            while j >= 0:
                if list[j].delay > key.delay:
                    list[j + 1] = list[j]
                    list[j] = key
                j -= 1
    elif object == 'loss':
        for i in range(1, count):
            key = list[i]
            j = i - 1
            while j >= 0:
                if list[j].loss > key.loss:
                    list[j + 1] = list[j]
                    list[j] = key
                j -= 1

    elif object == 'crowding_distance':
        for i in range(1, count):
            key = list[i]
            j = i - 1
            while j >= 0:
                if list[j].crowding_distance < key.crowding_distance:
                    list[j + 1] = list[j]
                    list[j] = key
                j -= 1