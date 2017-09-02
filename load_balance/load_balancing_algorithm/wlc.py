from collections import OrderedDict


class WLC:
    """
        weight least connection.
        the weight is manual configured.
    """
    def __init__(self, server, weight_of_server):
        self.connection_num = {}
        self.weight_of_server = weight_of_server

        for s in server:
            self.connection_num[s] = 1
            pass
        pass

    def calculate_server_allocate_value(self):
        calc_server_allocate_value = {}
        for key in self.connection_num:
            if key in self.weight_of_server:
                if self.weight_of_server[key] > 0:
                    calc_server_allocate_value[key] = (self.connection_num[key]) / (self.weight_of_server[key])
                    pass
                pass
            pass
        return calc_server_allocate_value

    def calculate_dst_server(self):
        calc_server_allocate_value = self.calculate_server_allocate_value()
        print 'The allocate value of each server is: ', calc_server_allocate_value
        sorted_allocate_value_dict = OrderedDict(
            sorted(calc_server_allocate_value.iteritems(), key=lambda d: d[1], reverse=False))
        all_sorted_servers = sorted_allocate_value_dict.keys()
        dst_server = all_sorted_servers[0]
        self.connection_num[dst_server] += 1
        return dst_server


class LC:
    """
        weight least connection.
        the weight is manual configured.
    """
    def __init__(self, server_dict):
        self.connection_num = {}
        self.server_dict = server_dict
        for net_address, server_lists in server_dict.items():
            for server_info in server_lists:
                self.connection_num[server_info[0]] = 1
            pass
        pass

    def calculate_dst_server(self, net_address):
        dst_server_list = self.server_dict[net_address]
        dst_servers = []
        for server_info in dst_server_list:
            dst_servers.append(server_info[0])
        sorted_allocate_value_dict = OrderedDict(
            sorted(self.connection_num.iteritems(), key=lambda d: d[1], reverse=False))
        all_sorted_servers = sorted_allocate_value_dict.keys()
        for server in all_sorted_servers:
            if server in dst_servers:
                dst_server = server
                self.connection_num[dst_server] += 1
                return dst_server
            
    def calculate_src_gateway_ip(self, server_ip):
        for gateway_address, servers_info in self.server_dict.items():
            for server_info in servers_info:
                if server_info[0] == server_ip:
                    return gateway_address
