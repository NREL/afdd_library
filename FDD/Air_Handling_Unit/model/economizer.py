import sys
import datetime
import os
import logging
from collections import defaultdict, OrderedDict
from datetime import timedelta as td
from statistics import mean
from .component.temperature_sensor import TempSensorDx
from .component.economizer import EconCorrectlyOn, EconCorrectlyOff
from .component.ventilation import ExcessOA, InsufficientOA


ECON1 = "Temperature Sensor Dx"
ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
ECON4 = "Excess Outdoor-air Intake Dx"
ECON5 = "Insufficient Outdoor-air Intake Dx"
DX = "/diagnostic message"
EI = "/energy impact"

dx_list = [ECON1, ECON2, ECON3, ECON4, ECON5]

FAN_OFF = -99.3
OAF = -89.2
OAT_LIMIT = -79.2
RAT_LIMIT = -69.2
MAT_LIMIT = -59.2
TEMP_SENSOR = -49.2


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class Application():
    def __init__(self, economizer_type="DDB", econ_hl_temp=65.0, device_type="AHU", cooling_enabled_threshold=5.0, temp_band=1.0, 
                 data_window=30, no_required_data=15, open_damper_time=5, low_supply_fan_threshold=15.0, mat_low_threshold=10.0,
                 mat_high_threshold=26.0, oat_low_threshold=10.0, oat_high_threshold=38.0, rat_low_threshold=10.0, rat_high_threshold=38.0, 
                 temp_difference_threshold=2.0, temp_damper_threshold=80.0, open_damper_threshold=80.0, oaf_temperature_threshold=5.0,
                 minimum_damper_setpoint=60.0, desired_oaf=10.0, rated_cfm=6000.0, eer=10.0, constant_volume=False, sensitivity="default", **kwargs):
        
        def get_or_none(name):
            value = kwargs["point_mapping"].get(name, None)
            if value:
                value = value.lower()
            return value
        
        if sensitivity is not None and sensitivity == "custom":
            oaf_temperature_threshold = max(5., min(oaf_temperature_threshold, 15.))
            cooling_enabled_threshold = max(5., min(cooling_enabled_threshold, 50.))
            temp_difference_threshold = max(2., min(temp_difference_threshold, 6.))
            mat_low_threshold = max(40., min(mat_low_threshold, 60.))
            mat_high_threshold = max(80., min(mat_high_threshold, 125.))
            rat_low_threshold = max(40., min(rat_low_threshold, 60.))
            rat_high_threshold = max(80., min(rat_high_threshold, 125.))
            oat_low_threshold = max(20., min(oat_low_threshold, 40.))
            oat_high_threshold = max(90., min(oat_high_threshold, 125.))
            open_damper_threshold = max(60., min(open_damper_threshold, 90.))
            minimum_damper_setpoint = max(0., min(minimum_damper_setpoint, 50.))
            desired_oaf = max(5., min(desired_oaf, 30.))
        else:
            oaf_temperature_threshold = 0.
            cooling_enabled_threshold = 5.
            temp_difference_threshold = 4.
            mat_low_threshold = 50.
            mat_high_threshold = 110.
            rat_low_threshold = 50.
            rat_high_threshold = 110.
            oat_low_threshold = 30.
            oat_high_threshold = 110.
            open_damper_threshold = 80.
            minimum_damper_setpoint = 60.
            desired_oaf = 10.
        
        econ_hl_temp = max(50., min(econ_hl_temp, 75.))
        temp_band = max(0.5, min(temp_band, 10.))

        self.device_type = device_type.lower()
        if self.device_type not in ("ahu", "rtu"):
            print("device_type must be specified as AHU or RTU in configuration file\n")
            sys.exit()
        
        if economizer_type.lower() not in ("ddb", "hl"):
            print("economizer_type must be specified as DDB or HL in configuration file\n")
            sys.exit()
        
        Application.analysis = analysis = kwargs["analysis_name"]
        
        self.fan_status_name = get_or_none("supply_fan_status")
        self.fan_sp_name = get_or_none("supply_fan_speed")
        self.oat_name = get_or_none("outdoor_air_temperature")
        self.rat_name = get_or_none("return_air_temperature")
        self.mat_name = get_or_none("mixed_air_temperature")
        self.oad_sig_name = get_or_none("outdoor_damper_signal")
        self.cool_call_name = get_or_none("cool_call")
        
        if self.fan_sp_name is None and self.fan_status_name is None:
            print("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status\n")
            sys.exit()

        # Precondition flags
        self.oaf_condition = None
        self.unit_status = None
        self.sensor_limit = None
        self.temp_sensor_problem = None

        # Time based configurations
        self.data_window = data_window = td(minutes=data_window)
        open_damper_time = td(minutes=open_damper_time)
        no_required_data = no_required_data

        # Diagnostic threshold parameters
        self.economizer_type = economizer_type.lower()
        self.econ_hl_temp = float(econ_hl_temp) if self.economizer_type == "hl" else None
        self.constant_volume = constant_volume
        self.cooling_enabled_threshold = cooling_enabled_threshold
        self.low_supply_fan_threshold = low_supply_fan_threshold
        self.oaf_temperature_threshold = oaf_temperature_threshold
        self.oat_thresholds = [oat_low_threshold, oat_high_threshold]
        self.rat_thresholds = [rat_low_threshold, rat_high_threshold]
        self.mat_thresholds = [mat_low_threshold, mat_high_threshold]
        self.temp_band = temp_band
        cfm = float(rated_cfm)
        eer = float(eer)

        print("Diagnostic Threshold Parameters")
        oat_mat_check = {
            'low': max(temp_difference_threshold * 1.5, 6.0),
            'normal': max(temp_difference_threshold * 1.25, 5.0),
            'high': max(temp_difference_threshold, 4.0)
        }
        print("oat_mat_check: {}".format(oat_mat_check))
        temp_difference_threshold = {
            'low': temp_difference_threshold + 2.0,
            'normal': temp_difference_threshold,
            'high': max(1.0, temp_difference_threshold - 2.0)
        }
        print("temp_difference_threshold: {}".format(temp_difference_threshold))
        oaf_economizing_threshold = {
            'low': open_damper_threshold - 30.0,
            'normal': open_damper_threshold - 20.0,
            'high': open_damper_threshold - 10.0
        }
        print("oaf_economizing_threshold: {}".format(oaf_economizing_threshold))
        open_damper_threshold = {
            'low': open_damper_threshold - 10.0,
            'normal': open_damper_threshold,
            'high': open_damper_threshold + 10.0
        }
        print("open_damper_threshold: {}".format(open_damper_threshold))
        excess_damper_threshold = {
            'low': 30.0,
            'normal': 50.0,
            'high': 70.0
        }
        print("excess_damper_threshold: {}".format(excess_damper_threshold))
        excess_oaf_threshold = {
            'low': minimum_damper_setpoint * 2.0 + 10.0,
            'normal': minimum_damper_setpoint + 10.0,
            'high': minimum_damper_setpoint * 0.5 + 10.0
        }
        print("excess_oaf_threshold: {}".format(excess_oaf_threshold))
        ventilation_oaf_threshold = {
            'low': desired_oaf * 0.75,
            'normal': desired_oaf * 0.5,
            'high': desired_oaf * 0.25
        }
        print("ventilation_oaf_threshold: {}\n".format(ventilation_oaf_threshold))

        self.sensitivity = ['low', 'normal', 'high']
        self.econ1 = TempSensorDx(data_window=data_window,
                                  no_required_data=no_required_data,
                                  temp_damper_threshold=temp_damper_threshold,
                                  open_damper_time=open_damper_time,
                                  oat_mat_check=oat_mat_check,
                                  temp_diff_thr=temp_difference_threshold,
                                  analysis=analysis)
        self.econ2 = EconCorrectlyOn(data_window=data_window,
                                     no_required_data=no_required_data,
                                     oaf_economizing_threshold=oaf_economizing_threshold,
                                     open_damper_threshold=open_damper_threshold,
                                     minimum_damper_setpoint=minimum_damper_setpoint,
                                     cfm=cfm,
                                     eer=eer,
                                     analysis=analysis)
        self.econ3 = EconCorrectlyOff(data_window=data_window,
                                      no_required_data=no_required_data,
                                      min_damper_sp=minimum_damper_setpoint,
                                      excess_damper_threshold=excess_damper_threshold,
                                      desired_oaf=desired_oaf,
                                      cfm=cfm,
                                      eer=eer,
                                      analysis=analysis)
        self.econ4 = ExcessOA(data_window=data_window,
                              no_required_data=no_required_data,
                              excess_oaf_threshold=excess_oaf_threshold,
                              min_damper_sp=minimum_damper_setpoint,
                              excess_damper_threshold=excess_damper_threshold,
                              desired_oaf=desired_oaf,
                              cfm=cfm,
                              eer=eer,
                              analysis=analysis)
        self.econ5 = InsufficientOA(data_window=data_window,
                                    no_required_data=no_required_data,
                                    ventilation_oaf_threshold=ventilation_oaf_threshold,
                                    desired_oaf=desired_oaf,
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
        
        current_fan_status, fan_sp = self.check_fan_status(fan_status_data, fan_sp_data, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.unit_status, FAN_OFF)

        if not current_fan_status:
            dx_result.log("Supply fan is off: {}\n".format(cur_time))
            return dx_result
        else:
            dx_result.log("Supply fan is on: {}\n".format(cur_time))
        
        if fan_sp is None and self.constant_volume:
            fan_sp = 100.0
        
        oat = mean(oat_data)
        rat = mean(rat_data)
        mat = mean(mat_data)
        oad = mean(damper_data)

        self.check_temperature_condition(oat, rat, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.oaf_condition, OAF)
        print("check_elapsed_time: {}\n".format(dx_result))

        if self.oaf_condition:
            dx_result.log("OAT and RAT readings are too close\n")
            return dx_result
        
        limit_condition = self.sensor_limit_check(oat, rat, mat, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.sensor_limit, limit_condition[1])
        if limit_condition[0]:
            dx_result.log("Temperature sensor is outside of bounds: {} -- {}".format(limit_condition, self.sensor_limit))
            return dx_result
        
        dx_result, self.temp_sensor_problem = self.econ1.econ_alg1(dx_result, oat, rat, mat, oad, cur_time)
        econ_condition, cool_call = self.determine_cooling_condition(cooling_data, oat, rat, mat)
        print("Cool call: {} - Economizer status: {}".format(cool_call, econ_condition))
        print("Temp_sensor_problem: {}\n".format(self.temp_sensor_problem))

        if self.temp_sensor_problem is not None and not self.temp_sensor_problem:
            dx_result = self.econ2.econ_alg2(dx_result, cool_call, oat, rat, mat, oad, econ_condition, cur_time, fan_sp)
            dx_result = self.econ3.econ_alg3(dx_result, oat, rat, mat, oad, econ_condition, cur_time, fan_sp)
            dx_result = self.econ4.econ_alg4(dx_result, oat, rat, mat, oad, econ_condition, cur_time, fan_sp)
            dx_result = self.econ5.econ_alg5(dx_result, oat, rat, mat, cur_time)
        elif self.temp_sensor_problem:
            self.pre_conditions(dx_list[1:], TEMP_SENSOR, cur_time, dx_result)
            self.econ1.clear_data()
            self.econ2.clear_data()
            self.econ3.clear_data()
            self.econ4.clear_data()
            self.econ5.clear_data()
        return dx_result
    

    def determine_cooling_condition(self, cooling_data, oat, rat, mat):
        if self.device_type == "ahu":
            clg_vlv_pos = mean(cooling_data)
            cool_call = True if clg_vlv_pos > self.cooling_enabled_threshold else False
        elif self.device_type == "rtu":
            cool_call = int(max(cooling_data))

        if self.economizer_type == "ddb":
            econ_condition = (rat - oat) > self.temp_band
        else:
            econ_condition = (self.econ_hl_temp - oat) > self.temp_band

        return econ_condition, cool_call



    def check_fan_status(self, fan_status_data, fan_sp_data, cur_time):
        supply_fan_status = int(max(fan_status_data)) if fan_status_data else None
        fan_speed = mean(fan_sp_data) if fan_sp_data else None
        
        if supply_fan_status is None:
            supply_fan_status = 1 if fan_speed > self.low_supply_fan_threshold else 0
        
        if not supply_fan_status:
            if self.unit_status is None:
                self.unit_status = cur_time
        else:
            self.unit_status = None
        return supply_fan_status, fan_speed
    

    def check_temperature_condition(self, oat, rat, cur_time):
        if abs(oat - rat) < self.oaf_temperature_threshold:
            if self.oaf_condition is None:
                self.oaf_condition = cur_time
        else:
            self.oaf_condition = None
        return 


    def sensor_limit_check(self, oat, rat, mat, cur_time):
        sensor_limit = (False, None)
        if oat < self.oat_thresholds[0] or oat > self.oat_thresholds[1]:
            sensor_limit = (True, OAT_LIMIT)
        elif mat < self.mat_thresholds[0] or mat > self.mat_thresholds[1]:
            sensor_limit = (True, MAT_LIMIT)
        elif rat < self.rat_thresholds[0] or rat > self.rat_thresholds[1]:
            sensor_limit = (True, RAT_LIMIT)
        
        if sensor_limit[0]:
            if self.sensor_limit is None:
                self.sensor_limit = cur_time
        else:
            self.sensor_limit = None
        return sensor_limit

    def clear_all(self):
        self.econ1.clear_data()
        self.econ2.clear_data()
        self.econ2.clear_data()
        self.econ3.clear_data()
        self.econ4.clear_data()
        self.econ5.clear_data()
        self.temp_sensor_problem = None
        self.unit_status = None
        self.oaf_condition = None
        self.sensor_limit = None
        return

    def check_elapsed_time(self, dx_result, cur_time, condition, message):
        elapsed_time = cur_time - condition if condition is not None else td(minutes=0)
        if elapsed_time >= self.data_window:
            if message == OAF:
                print("-89.2 ")

            dx_result = self.pre_conditions(dx_list, message, cur_time, dx_result)
            self.clear_all()
        return dx_result
    

    def pre_conditions(self, diagnostics, message, cur_time, dx_result):
        dx_msg = {}
        for sensitivity in self.sensitivity:
            dx_msg[sensitivity] = message

        for diagnostic in diagnostics:
            dx_table = {diagnostic + DX: dx_msg}
            if message == OAF:
                print("-:{}\n".format(dx_table))
            table_key = create_table_key(self.analysis, cur_time)
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