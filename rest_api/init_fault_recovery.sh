#!/usr/bin/env bash

wsgi_host='127.0.0.1'
wsgi_port='8088'

#curl $wsgi_host:$wsgi_port/fault_recovery/init_server -X POST -i -d '{
#    "10.0.0.1": "VIDEO,3001,3,UP,00:00:00:00:00:01",
#    "10.0.0.2": "VIDEO,3001,4,UP,00:00:00:00:00:02",
#    "10.0.0.3": "VIDEO,3002,3,UP,00:00:00:00:00:03",
#    "10.0.0.4": "FTP,3002,4,UP,00:00:00:00:00:04",
#    "10.0.0.5": "FTP,3003,3,UP,00:00:00:00:00:05",
#    "10.0.0.6": "FTP,3003,4,UP,00:00:00:00:00:06",
#    "10.0.0.7": "FTP,3004,3,UP,00:00:00:00:00:07",
#    "10.0.0.8": "HTML,3004,4,UP,00:00:00:00:00:08",
#    "10.0.0.9": "HTML,3005,3,UP,00:00:00:00:00:09",
#    "10.0.0.10": "HTML,3005,4,UP,00:00:00:00:00:0a",
#    "10.0.0.11": "HTML,3006,3,UP,00:00:00:00:00:0b",
#    "10.0.0.12": "HTML,3006,4,UP,00:00:00:00:00:0c",
#    "10.0.0.13": "USER,3007,3,UP,00:00:00:00:00:0d",
#    "10.0.0.14": "USER,3007,4,UP,00:00:00:00:00:0e",
#    "10.0.0.15": "USER,3008,3,UP,00:00:00:00:00:0f",
#    "10.0.0.16": "USER,3008,4,UP,00:00:00:00:00:10"
#}'


curl $wsgi_host:$wsgi_port/fault_recovery/init_port -X POST -i -d '{
    "1001,1": "3", "1001,2": "3", "1001,3": "3", "1001,4": "3",
    "1002,1": "3", "1002,2": "3", "1002,3": "3", "1002,4": "3",
    "1003,1": "3", "1003,2": "3", "1003,3": "3", "1003,4": "3",
    "1004,1": "3", "1004,2": "3", "1004,3": "3", "1004,4": "3",
    "2001,1": "3", "2001,2": "3", "2001,3": "3", "2001,4": "3",
    "2002,1": "3", "2002,2": "3", "2002,3": "3", "2002,4": "3",
    "2003,1": "3", "2003,2": "3", "2003,3": "3", "2003,4": "3",
    "2004,1": "3", "2004,2": "3", "2004,3": "3", "2004,4": "3",
    "2005,1": "3", "2005,2": "3", "2005,3": "3", "2005,4": "3",
    "2006,1": "3", "2006,2": "3", "2006,3": "3", "2006,4": "3",
    "2007,1": "3", "2007,2": "3", "2007,3": "3", "2007,4": "3",
    "2008,1": "3", "2008,2": "3", "2008,3": "3", "2008,4": "3",
    "3001,1": "2", "3001,2": "2", "3001,3": "1", "3001,4": "1",
    "3002,1": "2", "3002,2": "2", "3002,3": "1", "3002,4": "1",
    "3003,1": "2", "3003,2": "2", "3003,3": "1", "3003,4": "1",
    "3004,1": "2", "3004,2": "2", "3004,3": "1", "3004,4": "1",
    "3005,1": "2", "3005,2": "2", "3005,3": "1", "3005,4": "1",
    "3006,1": "2", "3006,2": "2", "3006,3": "1", "3006,4": "1",
    "3007,1": "2", "3007,2": "2", "3007,3": "1", "3007,4": "1",
    "3008,1": "2", "3008,2": "2", "3008,3": "1", "3008,4": "1",
    "4001,1": "4", "4001,2": "4", "4001,3": "4", "4001,4": "4",
    "4001,5": "5", "4001,6": "5", "4001,7": "5", "4001,8": "5",
    "4001,9": "5", "4001,10": "5", "4001,11": "5", "4001,12": "5",
    "4001,13": "5", "4001,14": "5",
    "4002,1": "4", "4002,2": "4", "4002,3": "4", "4002,4": "4",
    "4002,5": "5", "4002,6": "5", "4002,7": "5", "4002,8": "5",
    "4002,9": "5", "4002,10": "5", "4002,11": "5", "4002,12": "5",
    "4002,13": "5", "4002,14": "5"
}'
