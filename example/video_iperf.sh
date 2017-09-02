#!/bin/sh
target_ip=$1
target_bw=$2
iperf -c $target_ip -p 8080 -u -t 3600 -i 60 -b 2M
