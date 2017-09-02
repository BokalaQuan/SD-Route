import logging

from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication

from load_balancer import LoadBalancer, LoadBalancerRestController

FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

load_balancer_instance_name = 'load_balancer_app'


class LoadBalancerMain(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(LoadBalancerMain, self).__init__(*args, **kwargs)

        self.load_balancer = LoadBalancer()

        # Register a restful controller for this module
        wsgi = kwargs['wsgi']
        wsgi.register(LoadBalancerRestController, {load_balancer_instance_name: self})
