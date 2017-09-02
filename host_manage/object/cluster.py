from base.parameters import SERVER_STATUS
from host_manage.object.server import ClusterServer


class Cluster(object):
    def __init__(self, cluster_ip, cluster_type):
        # back end servers: self.servers = {server_ip: server_state}
        self.servers = {}

        # cluster ip address
        self.ip = cluster_ip

        # cluster status
        # Down: 0/Up: back end server number
        self.cluster_status = 0
        # cluster service type, string
        # such as 'VIDEO'/'FTP'/'HTML'
        self.cluster_type = cluster_type

    def init_server(self, server_ip, server_info):
        """init server object from configuration file,
        if object exist, update by server_info.

        :param server_ip: server ip address, string
        :param server_info: server information, list
            [cluster_ip, switch_dpid, switch_port, mac_address, server_status]
            ["10.0.0.201", 3001, 3, "00:00:00:00:00:01", "True"]
        :return: server object
        """
        if server_ip not in self.servers:
            self.servers[server_ip] = ClusterServer(self)
            new_srv = self.servers[server_ip]
            new_srv.location = (server_info[1], server_info[2])
            new_srv.ip = server_ip
            new_srv.mac = server_info[3]
            new_srv.status = SERVER_STATUS[server_info[4]]
            return new_srv
        else:
            srv = self.servers[server_ip]
            srv.location = (server_info[1], server_info[2])
            srv.ip = server_ip
            srv.mac = server_info[3]
            srv.status = SERVER_STATUS[server_info[4]]
            return srv

    def add_server(self, server_ip):
        if server_ip not in self.servers:
            self.servers[server_ip] = ClusterServer(self)

    def del_server(self, server_ip):
        if server_ip in self.servers:
            del self.servers[server_ip]
            return True
        return False

    def get_server(self, server_ip):
        if server_ip in self.servers:
            return self.servers[server_ip]
        return None

    def update_server(self, server_ip, status):
        if server_ip in self.servers:
            self.servers[server_ip].status = status
            if status:
                self.cluster_status += 1
            else:
                self.cluster_status -= 1
                assert self.cluster_status >= 0
            return True
        return False
