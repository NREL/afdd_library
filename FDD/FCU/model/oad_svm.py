import sys
import datetime
import os
import logging
import pandas as pd
from collections import defaultdict, OrderedDict
from datetime import timedelta as td
from statistics import mean
from sklearn.ensemble import RandomForestClassifier
from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn import metrics
from copy import deepcopy
import time


ECON = "FCU OAD Fault"
DX = "/diagnostic message"


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class Application():
    def __init__(self, **kwargs):
        def get_or_none(name):
            value = kwargs["point_mapping"].get(name, None)
            if value:
                value = value.lower()
            return value
        
        self.point_mapping = kwargs["point_mapping"]
        self.model_path = kwargs["model_path"]
        Application.analysis = analysis = kwargs["analysis_name"]
        
        self.pt1 = get_or_none("outdoor_air_humidity")
        self.pt2 = get_or_none("mixed_air_humidity")
        self.pt3 = get_or_none("return_air_humidity")
        self.pt4 = get_or_none("discharge_air_humidity")
        self.pt5 = get_or_none("outdoor_air_temperature")
        self.pt6 = get_or_none("mixed_air_temperature")
        self.pt7 = get_or_none("return_air_temperature")
        self.pt8 = get_or_none("discharge_air_temperature")
        self.pt9 = get_or_none("heating_coil_return_water_temperature")
        self.pt10 = get_or_none("cooling_coil_return_water_temperature")
        self.pt11 = get_or_none("room_temperature")
        self.pt12 = get_or_none("discharge_air_mass_flow")


    def data_builder(self, value_tuple, point_name):
        value_list = []
        for item in value_tuple:
            value_list.append(item[1])
        return value_list



    def run(self, cur_time, points):
        self.timestamp = [cur_time]
        device_dict = {}
        dx_result = Results()
        for point, value in points.items():
            point_device = [name.lower() for name in point.split("&")]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [(point_device[1], value)]
            else:
                device_dict[point_device[0]].append((point_device[1], value))

        pt1 = []
        pt2 = []
        pt3 = []
        pt4 = []
        pt5 = []
        pt6 = []
        pt7 = []
        pt8 = []
        pt9 = []
        pt10 = []
        pt11 = []
        pt12 = []
        missing_data = []

        for key, value in device_dict.items():
            data_name = key
            if value is None:
                continue
            if data_name == self.pt1:
                pt1 = self.data_builder(value, data_name)
            elif data_name == self.pt2:
                pt2 = self.data_builder(value, data_name)
            elif data_name == self.pt3:
                pt3 = self.data_builder(value, data_name)
            elif data_name == self.pt4:
                pt4 = self.data_builder(value, data_name)
            elif data_name == self.pt5:
                pt5 = self.data_builder(value, data_name)
            elif data_name == self.pt6:
                pt6 = self.data_builder(value, data_name)
            elif data_name == self.pt7:
                pt7 = self.data_builder(value, data_name)
            elif data_name == self.pt8:
                pt8 = self.data_builder(value, data_name)
            elif data_name == self.pt9:
                pt9 = self.data_builder(value, data_name)
            elif data_name == self.pt10:
                pt10 = self.data_builder(value, data_name)
            elif data_name == self.pt11:
                pt11 = self.data_builder(value, data_name)
            elif data_name == self.pt12:
                pt12 = self.data_builder(value, data_name)

        self.classifier(dx_result, [pt1, pt2, pt3, pt4, pt5, pt6, pt7, pt8, pt9, pt10, pt11, pt12])

        return dx_result

    def classifier(self, dx_result, message):
        diagnostic_msg = {}
        msg = {self.pt1: message[0], 
        self.pt2: message[1],
        self.pt3: message[2],
        self.pt4: message[3],
        self.pt5: message[4],
        self.pt6: message[5],
        self.pt7: message[6],
        self.pt8: message[7],
        self.pt9: message[8],
        self.pt10: message[9],
        self.pt11: message[10],
        self.pt12: message[11]}
        
        test = pd.DataFrame(msg)
        import joblib

        load_m = joblib.load(self.model_path)
        y_pred=load_m.predict(test)

        
        print(y_pred)

        diagnostic_msg.update({"Fault_status": y_pred[0]})
        time.sleep(1)
        
        table_key = create_table_key(self.analysis, self.timestamp[-1])
        dx_table = {
            ECON + DX: diagnostic_msg,
        }
        dx_result.insert_table_row(table_key, dx_table)
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