#!/usr/bin/env bash

wsgi_host='127.0.0.1'
wsgi_port='8088'

curl $wsgi_host:$wsgi_port/hosttrack/hostentry -X GET -i
