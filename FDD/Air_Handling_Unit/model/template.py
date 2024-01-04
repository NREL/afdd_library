import sys
import datetime
import os
import logging
from collections import defaultdict, OrderedDict
from datetime import timedelta as td
from statistics import mean
from .component.template import Template


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class Application():
    def __init__(self, data_window=30, **kwargs):
        
        def get_or_none(name):
            value = kwargs["point_mapping"].get(name, None)
            if value:
                value = value.lower()
            return value
        
        self.fan_status_name = get_or_none("supply_fan_status")
        self.fan_sp_name = get_or_none("supply_fan_speed")
        self.oat_name = get_or_none("outdoor_air_temperature")
        self.rat_name = get_or_none("return_air_temperature")
        self.mat_name = get_or_none("mixed_air_temperature")
        self.oad_sig_name = get_or_none("outdoor_damper_signal")
        self.cool_call_name = get_or_none("cool_call")
        
        Application.analysis = analysis = kwargs["analysis_name"]

        self.econ1 = Template(data_window=data_window,
                              analysis=analysis)        

    def data_builder(self, value_tuple, point_name):
        value_list = []
        for item in value_tuple:
            if point_name == self.oat_name:
                value_list.append(((item[1]) * 9 / 5 + 32))
            elif point_name == self.mat_name:
                value_list.append(((item[1]) * 9 / 5 + 32))
            elif point_name == self.rat_name:
                value_list.append(((item[1]) * 9 / 5 + 32))
            elif point_name == self.oad_sig_name:
                value_list.append((item[1] * 100))
            elif point_name == self.fan_status_name:
                if item[1] > 0:
                    value_list.append(1)
                else:
                    value_list.append(0)
            elif point_name == self.fan_sp_name:
                value_list.append((item[1]))
            else:
                value_list.append(item[1])
        return value_list


    def run(self, cur_time, points):
        device_dict = {}
        dx_result = Results()
        for point, value in points.items():
            point_device = [name.lower() for name in point.split("&")]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [(point_device[1], value)]
            else:
                device_dict[point_device[0]].append((point_device[1], value))

        damper_data = []
        oat_data = []
        mat_data = []
        rat_data = []
        cooling_data = []
        fan_sp_data = []
        fan_status_data = []
        missing_data = []

        for key, value in device_dict.items():
            data_name = key
            if value is None:
                continue
            if data_name == self.fan_status_name:
                fan_status_data = self.data_builder(value, data_name)
            elif data_name == self.oad_sig_name:
                damper_data = self.data_builder(value, data_name)
            elif data_name == self.oat_name:
                oat_data = self.data_builder(value, data_name)
            elif data_name == self.mat_name:
                mat_data = self.data_builder(value, data_name)
            elif data_name == self.rat_name:
                rat_data = self.data_builder(value, data_name)
            elif data_name == self.cool_call_name:
                cooling_data = self.data_builder(value, data_name)
            elif data_name == self.fan_sp_name:
                fan_sp_data = self.data_builder(value, data_name)

        if not oat_data:
            missing_data.append(self.oat_name)
        if not rat_data:
            missing_data.append(self.rat_name)
        if not mat_data:
            missing_data.append(self.mat_name)
        if not damper_data:
            missing_data.append(self.oad_sig_name)
        if not cooling_data:
            missing_data.append(self.cool_call_name)
        if not fan_status_data and not fan_sp_data:
            missing_data.append(self.fan_status_name)
        
        if missing_data:
            dx_result.log("Missing data from publish: {}\n".format(missing_data))
            return dx_result
        
    

class Results:
    def __init__(self, terminate=False):
        self.commands = OrderedDict()
        self.devices = OrderedDict()
        self.log_messages = []
        self._terminate = terminate
        self.table_output = defaultdict(list)

    def command(self, point, value, device=None):
        if device is None:
            self.commands[point] = value
        else:
            if device not in self.devices:
                self.devices[device] = OrderedDict()
            self.devices[device][point] = value
        if self.devices is None:
            self.commands[point]=value
        else:
            if  device not in self.devices:
                self.devices[device] = OrderedDict()
            self.devices[device][point]=value

    def log(self, message, level=logging.DEBUG):
        self.log_messages.append((level, message))

    def terminate(self, terminate):
        self._terminate = bool(terminate)

    def insert_table_row(self, table, row):
        self.table_output[table].append(row)