#!/usr/bin/env bash

wsgi_host='127.0.0.1'
wsgi_port='8088'

curl $wsgi_host:$wsgi_port/loadbalancer/init_server_cluster -X POST -i -d '{
    "10.0.0.201": "VIDEO",
    "10.0.0.202": "FTP",
    "10.0.0.203": "HTML"
}'
