from lib.project_lib import Megabits

"""
Link status printer configuration
"""
LINK_STATUS_PRINTER = False
LINK_STATUS_PRINTER_INTERVAL = 10

"""
route flow table configuration
"""
# unicast parameter
FLOW_IDLE_TIMEOUT = 300
FLOW_HARD_TIMEOUT = 1800

# multicast parameter
# MULTICAST_FLOW_IDLE_TIMEOUT = 600
# MULTICAST_FLOW_HARD_TIMEOUT = 3600

MULTICAST_FLOW_IDLE_TIMEOUT = 5
MULTICAST_FLOW_HARD_TIMEOUT = 20

# flow entry priority
ROUTE_FLOW_PRIORITY = 1000

"""
route task handler configuration
"""
# task
ROUTE_TASK_HANDLE_INTERVAL = 1

"""
server cluster configuration
"""
# service tcp port
server_tcp_port = 80

# business type bandwidth binding.
DefaultBusinessType = "HTML"
BusinessType = {
    "HTML": 0.3 * Megabits,
    "FTP": 1 * Megabits,
    "VIDEO": 5 * Megabits,
    "USER": 0.01 * Megabits
}

"""
gateway configuration
"""
# gateway configuration.
GATEWAY_IP_LIST = ['10.0.0.201', '10.0.0.202', '10.0.0.203']
GATEWAY_MAC_DICT = {'10.0.0.201': 'c9:c9:c9:c9:c9:c9',
                    '10.0.0.202': 'ca:ca:ca:ca:ca:ca',
                    '10.0.0.203': 'cb:cb:cb:cb:cb:cb'}

"""
server configuration
"""
SERVER_STATE_DOWN = 'DOWN'
SERVER_STATE_UP = 'UP'

SERVER_STATUS = {
    1: SERVER_STATE_UP,  # server UP
    0: SERVER_STATE_DOWN  # server DOWN
}
