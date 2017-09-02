import logging
import json
import os

from webob import Response

from ryu.app.wsgi import ControllerBase, route
from lib.project_lib import unicode_fmt
from fault_recovery.fault_classifier import FaultClassifier
from host_manage.object.cluster import Cluster

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

rest_body_ok = json.dumps({'msg': 'OK'})
rest_body_none = json.dumps({'msg': 'None'})

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
SERVER_CONF_FILE_PATH = FILE_PATH + '/conf/server_info.conf'
CLUSTER_CONF_FILE_PATH = FILE_PATH + '/conf/cluster_info.conf'


class ClusterManage(object):
    def __init__(self, *args, **kwargs):
        if not hasattr(self, 'server_clusters'):
            # cluster object
            self.clusters = {}

            # TODO: should contain None cluster object?
            # reference of server in self.clusters
            self.servers = {}

            # cluster/server configuration
            self.cluster_conf = {}
            self.server_conf = {}

            # TODO: fault_classifier should not contain cluster info by its own, but call ClusterManage.
            # Used for fault recovery. Get an instance of RouteInfoMaintainer(This is a singleton class)
            self.fault_classifier = FaultClassifier()

            # loadbalancer
            self.load_balancer = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            orig = super(ClusterManage, cls)
            cls._instance = orig.__new__(cls, *args, **kwargs)
        return cls._instance

    def cluster_init(self):
        """init cluster information from configuration file store
        at self.cluster_conf and self.server_conf
        """
        for cluster_ip, cluster_type in self.cluster_conf.iteritems():
            self.clusters.setdefault(cluster_ip, Cluster(cluster_ip, cluster_type))
        for server_ip, server_info in self.server_conf.iteritems():
            cluster = self.clusters.get(server_info[0])
            if cluster:
                server_obj = cluster.init_server(server_ip, server_info)
                self.servers.setdefault(server_ip, server_obj)
            else:
                logger.debug("server %s do not belong to any cluster.", server_ip)
                # new_server = Server()
                # new_server.init(server_ip, server_info)
                # self.servers.setdefault(server_ip, new_server)
                pass

    def update_server_status(self, server_ip, status):
        """update server state

        :param server_ip:
        :param status: server status [Up: True/ Down: False]
        :return:
        """
        if server_ip in self.servers:
            server = self.servers[server_ip]
            server.update_status(status)
        return None

    def init_cluster_configuration(self):
        f = open(CLUSTER_CONF_FILE_PATH, 'w+')
        conf = self.cluster_conf
        fp = json.dumps(conf)
        f.write(fp)
        f.close()

    def read_cluster_configuration(self):
        try:
            f = open(CLUSTER_CONF_FILE_PATH, 'r')
        except:
            logger.error("read cluster configuration file failed.")
            return
        fp = f.read()
        conf = unicode_fmt(json.loads(fp))
        self.cluster_conf = conf
        f.close()

    def init_server_configuration(self):
        f = open(SERVER_CONF_FILE_PATH, 'w+')
        conf = self.server_conf
        fp = json.dumps(conf)
        f.write(fp)
        f.close()

    def read_server_configuration(self):
        try:
            f = open(SERVER_CONF_FILE_PATH, 'r')
        except:
            logger.error("read server configuration file failed.")
            return
        fp = f.read()
        conf = unicode_fmt(json.loads(fp))
        self.server_conf = conf
        f.close()


class ClusterManageRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(ClusterManageRestController, self).__init__(req, link, data, **config)
        self.cluster_manage = ClusterManage()

    @route('clustermanage', '/clustermanage/add_cluster', methods=['POST'])
    def add_cluster(self, req, **kwargs):
        # TODO: check this rest api
        msg = unicode_fmt(json.loads(req.body))
        for cluster_ip, cluster_type in msg.items():
            self.cluster_manage.clusters.setdefault(
                cluster_ip, Cluster(cluster_ip, cluster_type))
        return Response(content_type='application/json', body=rest_body_ok)

    @route('clustermanage', '/clustermanage/update_server_cluster', methods=['POST'])
    def update_server_cluster(self, req, **kwargs):
        # TODO: check this rest api
        msg = unicode_fmt(json.loads(req.body))
        for server_ip, server_info in msg.items():
            cluster = self.cluster_manage.clusters.get(server_info[0])
            if cluster:
                server = cluster.get_server(server_ip)
                if server and (server.status is False):
                    # try to update server only when server is Down.
                    cluster.init_server(server_ip, server_info)

        return Response(content_type='application/json', body=rest_body_ok)
