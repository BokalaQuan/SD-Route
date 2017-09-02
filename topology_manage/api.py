from ryu.base import app_manager
from object import topo_event


def get_switch(app, dpid=None):
    rep = app.send_request(topo_event.EventSwitchRequest(dpid))
    return rep.switches


def get_all_switch(app):
    return get_switch(app)


def get_link(app, dpid=None):
    rep = app.send_request(topo_event.EventLinkRequest(dpid))
    return rep.links


def get_all_link(app):
    return get_link(app)

app_manager.require_app('topology_manage.TopologyManage', api_style=True)
