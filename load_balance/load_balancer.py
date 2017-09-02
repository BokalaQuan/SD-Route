import logging

from ryu.app.wsgi import ControllerBase, route
from host_manage.cluster_manage import ClusterManage
from load_balance.load_balancing_algorithm.wlc import LC

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


class LoadBalancer(object):
    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'algorithm'):
            self.status = False
            self.algorithm = LC({})

            # TODO: server online or not(ClusterManage).
            # load balance cluster configuration dict.
            self.configuration = {}

            self.cluster_manage = ClusterManage()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(LoadBalancer, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def init(self, clusters, servers_based_on_type):
        server_dict = {}
        for cluster_ip, cluster_info in clusters.iteritems():
            server_dict[cluster_ip] = servers_based_on_type[cluster_info.cluster_type]
        self.configuration = server_dict
        self.status = True

    def update(self):
        self.algorithm = LC(self.configuration)

    def get_server(self, dst_ip):
        if not self.status:
            logger.error("lc algorithm not initialized.")
            return None
        return self.algorithm.calculate_dst_server(dst_ip)


class LoadBalancerRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(LoadBalancerRestController, self).__init__(req, link, data, **config)
        self.load_balancer = LoadBalancer()

    @route('loadbalancer', '/loadbalancer/init_server_cluster', methods=['POST'])
    def update_server_cluster(self, req, **kwargs):
        logger.warning("[LoadBalancerRestController.update_server_cluster]"
                       "this method is abandoned")
        pass
