import logging
from datetime import timedelta as td
from statistics import mean


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class Template(object):
    def __init__(self, data_window, analysis):
        print('template component')
    
    def econ_alg1(self, dx_result):
        dx_result.log("component fault detection")
        return dx_result