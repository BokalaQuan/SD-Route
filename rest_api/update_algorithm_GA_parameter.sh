#!/usr/bin/env bash

wsgi_host='127.0.0.1'
wsgi_port='8088'

curl $wsgi_host:$wsgi_port/routemanage/algorithm -X POST -i -d '{
    "algorithm_type": "GA",
    "delay_coefficient": 300,
    "cost_coefficient": 0.004,
    "bw_load_coefficient": 1,
    "generation_max": 20,
    "max_hop": 8
}'
