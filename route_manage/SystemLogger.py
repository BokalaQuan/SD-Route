import logging
import json
import os
import time

from threading import Thread
from datetime import datetime


FORMAT = '%(name)s[%(levelname)s]%(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

FILE_PATH = os.path.split(os.path.realpath(__file__))[0]
LOG_PATH = FILE_PATH + '/log/' + 'system_performance.log'

WRITE_FILE_INTERVAL = 10


class SystemPerformanceLogger(object):
    def __init__(self, *args, **kwargs):
        super(SystemPerformanceLogger, self).__init__()
        self.end_point = 0

        self.sp_times = 0
        self.sp_success_times = 0
        self.sp_req_handle_runtime = []
        self.sp_algorithm_runtime = []
        self.sp_link = []
        self.sp_link_cost = []

        self.wf_interval = WRITE_FILE_INTERVAL
        self._init_thread()

    def timer(self, func):
        def wrapper(*args, **kwargs):
            start_timestamp = time.time()
            rval = func(*args, **kwargs)
            end_timestamp = time.time()

            if func.func_name == "route_calc":
                self.sp_algorithm_runtime.append(
                    end_timestamp - start_timestamp)
            elif func.func_name == "multicast_route_calc":
                pass
            elif func.func_name == "deploy_flow_table":
                if rval is True:
                    self.sp_success_times += 1
                    self.sp_link.append(args[5])
                    self.sp_link_cost.append(args[6])
                else:
                    self.end_point += 1

            return rval
        return wrapper

    def new_request(self):
        self.sp_times += 1

    def handle_req_start(self, timestamp):
        self.sp_req_handle_runtime.append(timestamp)

    def handle_req_finish(self, timestamp):
        start = self.sp_req_handle_runtime[self.end_point]
        self.sp_req_handle_runtime[self.end_point] = timestamp - start
        self.end_point += 1

    def write_system_performance_log(self):
        if self.end_point == 0:
            # nothing to write
            return

        temp_sp_times = self.sp_times
        temp_sp_success_times = self.sp_success_times
        temp_sp_req_handle_runtime = self.sp_req_handle_runtime[:self.end_point]
        temp_sp_algorithm_runtime = self.sp_algorithm_runtime[:self.end_point]
        temp_sp_link = self.sp_link[:self.end_point]
        temp_sp_link_cost = self.sp_link_cost[:self.end_point]

        self.sp_times = temp_sp_times - self.end_point
        self.sp_success_times = temp_sp_success_times - self.end_point
        del self.sp_req_handle_runtime[:self.end_point]
        del self.sp_algorithm_runtime[:self.end_point]
        del self.sp_link[:self.end_point]
        del self.sp_link_cost[:self.end_point]
        self.end_point = 0

        f = open(LOG_PATH, 'a')
        l = {
            "record time": datetime.fromtimestamp(time.time()).strftime(TIME_FORMAT),
            "total times": temp_sp_times,
            "success times": temp_sp_success_times,
            "algorithm runtime": temp_sp_algorithm_runtime,
            "request handle runtime": temp_sp_req_handle_runtime,
            "link": temp_sp_link,
            "link cost": temp_sp_link_cost
        }
        f.write(json.dumps(l)+',')
        f.close()

    def _init_thread(self):
        logger.debug('log file writer thread start with interval %ds', self.wf_interval)
        gc_thread = Thread(target=self._write_file)
        gc_thread.setDaemon(True)
        gc_thread.start()

    def _write_file(self):
        while True:
            self.write_system_performance_log()
            time.sleep(self.wf_interval)
