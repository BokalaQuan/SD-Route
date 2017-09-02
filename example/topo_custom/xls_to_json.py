import json
import xlrd
import os
import random

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
XLS_PATH = FILE_PATH + '/topo_file/topo1.xls'
SWITCH_PATH = FILE_PATH + '/topo_file/switch_info.json'
LINK_PATH = FILE_PATH + '/topo_file/link_info.json'


def init_topo(num_node, num_edge):
    node_list = []
    edge_list = []

    # iCoreLayerSwitch = 1 / 5 *(num_node)
    # iAggLayerSwitch = 2 / 5 *(num_node)
    # iEdgeLayerSwitch = 2 / 5 *(num_node)


    PATH = XLS_PATH

    data = xlrd.open_workbook(PATH)
    table = data.sheet_by_index(0)

    for i in xrange(1, num_node + 1):
        sw = {"dpid": i,
              "attribute": "edge",
              "name": get_switch_dpid(i)}
        node_list.append(sw)

    for i in range(table.nrows):
        str = int(table.cell(i, 1).value)
        dst = int(table.cell(i, 2).value)
        temp = random.uniform(100, 1000)
        delay = int(temp)
        temp = random.uniform(0, 3)
        loss = float('%.2f' % temp)
        bandwidth = random.randint(1, 20) * 10

        link = {"src": str+1,
                "dst": dst+1,
                "delay": delay,
                "loss": loss,
                "bandwidth": bandwidth}
        edge_list.append(link)

    with open(SWITCH_PATH, 'w') as json_file:
        pfp = json.dumps(node_list, ensure_ascii=True, indent=4, sort_keys=True)
        json_file.write(pfp)

    with open(LINK_PATH, 'w') as json_file:
        pfp = json.dumps(edge_list, ensure_ascii=True, indent=4, sort_keys=True)
        json_file.write(pfp)




def get_switch_dpid(number):
    prefix = "00"
    if number >= int(100):
        prefix = ""
    elif number >= int(10):
        prefix = "0"

    return 's' + prefix + str(number)


def get_host_dpid(number):
    prefix = "00"
    if number >= int(100):
        prefix = ""
    elif number >= int(10):
        prefix = "0"

    return 'h' + prefix + str(number)




if __name__ == '__main__':
    init_topo(50, 134)




