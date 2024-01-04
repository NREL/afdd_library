import sys
import random
import json
import datetime
import pandas as pd
import numpy as np
import dateutil.tz
import csv
import logging
import time
from dateutil.parser import parse
import yaml
import gevent


def _get_class(kls):
    parts = kls.split(".")
    module =".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


class Application():
    def __init__(self, config_path):
        # load configuration file
        with open(config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)

        # import each model in the application
        application = config.get("application")
        arguments = config.get("arguments")

        self.time_ = arguments['point_mapping']['timestamp']

        kla = _get_class(application)
        self.app_instance = kla(**arguments)

        self.topic = config.get("campus", "NREL")
        self.timezone = config.get("local_timezone", "UTC")
        self.output_file_prefix = config.get("output_file")

        self.csv_data = {}
        self.return_data = []
        self.device_values = {}

        self._header_written = False
        self.file_creation_set = set()


    def handled_message(self, message):
        self.timestamp = message[0].get(self.time_)
        self.csv_data[self.timestamp] = message[0]
        if self.csv_data[self.timestamp]:
            self.return_data.append(self.csv_data[self.timestamp])
            return self.on_analysis_message(message=self.return_data), self.initialize()


    def initialize(self):
        self.return_data = []


    def on_analysis_message(self, message):
        print(message)
        timestamp = parse(str(message[-1].get(self.time_)))
        to_zone = dateutil.tz.gettz(self.timezone)
        timestamp = timestamp.replace(tzinfo=to_zone)
        print("Current time of publish: {}".format(timestamp))

        device_data = message[0]

        if isinstance(device_data, list):
            device_data = device_data[-1]

        device_needed = self.aggregate_message(device_data=device_data)
        
        if self._should_run_now():
            field_names = {}
            for point, data in self.device_values.items():
                field_names[point] = data
            device_data = field_names
            results = self.app_instance.run(timestamp, device_data)
            self.process_results(results)


    def process_results(self, results):
        for log in results.log_messages:
            print("Log: {}".format(log))
            # self.command.configure(background='orange', text="Log: {}".format(log))
        for key, value in results.table_output.items():
            print("Table: {} -> {}".format(key, value))
        
        print(self.output_file_prefix)
        if self.output_file_prefix is not None:
            results = self.create_file_output(results)


    def aggregate_message(self, device_data):
        tagged_device_data = {}
        for key, value in device_data.items():
            device_data_tag = "&".join([key, self.topic])
            tagged_device_data[device_data_tag] = value
        self.device_values.update(tagged_device_data)
        return True 


    def _should_run_now(self):
        if not self.device_values.keys():
            return False
        return True
    

    def create_file_output(self, results):
        print("results.table_output.items: {}".format(results.table_output.items()))

        for key, value in results.table_output.items():
            print("len(value): {}, type(value[0]): {}, key: {}, value: {}".format(len(value),type(value[0]),key,value))
            name_timestamp = key.split("&")
            _name = name_timestamp[0]
            timestamp = name_timestamp[1]

            for i in range(len(value)):
                for k,v in value[i].items():
                    if k == 'FCU OAD Fault/diagnostic message':
                        tag = 0
                        file_name = "Output/" + _name + str(tag) + ".csv"
                        print("diagnostic name: {}, file name: {}".format(k, file_name))

                        if file_name not in self.file_creation_set:
                            self._header_written = False
                        self.file_creation_set.update([file_name])

                        with open(file_name, "a+") as file_to_write:
                            row = {k:v}
                            row.update({"Timestamp": timestamp})
                            _keys = row.keys()
                            file_output = csv.DictWriter(file_to_write, _keys)
                            if not self._header_written:
                                file_output.writeheader()
                                self._header_written = True
                            file_output.writerow(row)
                        file_to_write.close()
        return results