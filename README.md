<<<<<<< HEAD
# SD-RouteS
Software-Defined Route System

## Introduction
A custom SDN controller based on ryu@https://github.com/osrg/ryu.

## Tutorial
1. start mininet
```bash
sudo python example/mininet_fattree_gw.py
```

2. run ryu
run `bin/ryu-manager` by eclipse or pycharm with
script parameters: `--verbose --observe-links --default-log-level 20 --wsapi-port 8088 main`

3. configure parameter
```bash
sh rest_api/initialize_parameter.sh
```

## TODO
- fault_recovery
  - need to handle other type of packets(ICMP,UDP...), now we only handle TCP packets;
  - update information for recalculate path after recovery;
  - after recover the delete events, need to clear the former flow entries;
  - set the state to 'UP' after it is added;
  - add flow entry clear module to clear flow entries when the switches connect to controller.
- multicast
  - IGMPv3 support

## Structure

```bash
+-----------------+-------------------------+------------------+
|                 |  +----------+--------+  |                  |
|                 |  | Dijkstra |   GA   |  |                  |
|       GA        |  +----------+--------+  |      gateway     |
|    multicast    |                         |   load balance   |
|                 |    unicast algorithm    |                  |
+-----------------+-------------------------+------------------+

+-------------+------------------------------------------------+
|             | +----------------+-----------+---------------+ |
|             | | cluster_manage | HostTrack | HostDiscovery | |
| RouteManage | +----------------+-----------+---------------+ |
|             |                                                |
|             |                   HostManage                   |
+-------------+------------------------------------------------+

+--------------------------------------------------------------+
|              +--------------+----------------+               |
|              | link_monitor | fault_recovery |               |
|              +--------------+----------------+               |
|                                                              |
|                       TopologyManage                         |
+--------------------------------------------------------------+
```

## Modules
- example: showcases based on mininet
- rest_api: rest api examples
- base: general configuration parameters
- bin: ryu & ryu-manager (v3.24)
- ryu: ryu source code (v3.24)
- lib: library for project
- host_manage: host/server maintain module
- topology_manage: topology maintain module
- route_manage: route manage module, support GA/Dijkstra now
- multicast: multicast group maintainer by handling IGMP packet
- link_monitor: monitor link bandwidth usage
- fault_recovery: recover route automatically when link down
- load_balance: load balance module for IP based service
- web_service: GUI event
=======
# SD-Route
>>>>>>> 5ca1ddba404021b638cf4dcd94d80a34f4b1faa3
