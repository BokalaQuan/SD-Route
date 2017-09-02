from base.parameters import SERVER_STATUS
from base.parameters import SERVER_STATE_UP, SERVER_STATE_DOWN


class Server(object):
    def __init__(self):
        # server status
        # Up: SERVER_STATE_UP/ Down: SERVER_STATE_DOWN
        self.status = SERVER_STATE_DOWN

        # server position: (switch_dpid, port)
        self.location = None

        # network information
        self.ip = None
        self.mac = None

        # system performance
        self.cpu = None
        self.mem = None
        self.net = None
        self.disk = None

    def init(self, server_ip, server_info):
        """init server object by server_info.

        :param server_ip: server ip address, string
        :param server_info: server information, list
            [cluster_ip, switch_dpid, switch_port, mac_address, server_status]
            ["10.0.0.201", 3001, 3, "00:00:00:00:00:01", "True"]
        :return:
        """
        self.location = (server_info[1], server_info[2])
        self.ip = server_ip
        self.mac = server_info[3]
        self.status = SERVER_STATUS[server_info[4]]

    def update_status(self, new_status):
        """update server's status

        :param new_status: server status [Up: True/ Down: False]
        :return:
        """
        self.status = new_status


class ClusterServer(Server):
    def __init__(self, cluster):
        super(ClusterServer, self).__init__()
        # cluster belong to
        self.cluster = cluster

    def update_status(self, new_status):
        self.cluster.update_server(self.ip, new_status)
