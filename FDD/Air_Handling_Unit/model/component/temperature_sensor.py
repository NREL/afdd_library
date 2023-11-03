import logging
from datetime import timedelta as td
from statistics import mean


ECON1 = "Temperature Sensor Dx"
DX = "/diagnostic message"
EI = "/energy impact"

def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class TempSensorDx(object):
    def __init__(self, data_window, no_required_data, temp_diff_thr, 
                 open_damper_time, oat_mat_check, temp_damper_threshold, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []

        self.temp_sensor_problem = None
        self.analysis = analysis
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2

        # Application thresholds
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oat_mat_check = oat_mat_check
        self.temp_diff_thr = temp_diff_thr
        self.inconsistent_date = {key: 3.2 for key in self.temp_diff_thr}
        self.sensor_damper_dx = DamperSensorInconsistencyDx(data_window, 
                                                            no_required_data,
                                                            open_damper_time,
                                                            oat_mat_check,
                                                            temp_damper_threshold,
                                                            analysis)
    
    def econ_alg1(self, dx_result, oat, rat, mat, oad, cur_time):
        self.oat_values.append(oat)
        self.rat_values.append(rat)
        self.mat_values.append(mat)
        self.timestamp.append(cur_time)
        elapsed_time = self.timestamp[-1] - self.timestamp[0]
        dx_result.log("Elapsed time: {} -- required time: {}".format(elapsed_time, self.data_window))
        print("elapsed_time: {} -- self.data_window: {}".format(elapsed_time, self.data_window))
        print("len(self.timestamp): {} -- self.no_required_data: {}\n".format(len(self.timestamp), self.no_required_data))
        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            print("econ_alg1 enter")
            table_key = create_table_key(self.analysis, self.timestamp[-1])
            print("econ_alg1 ::: table_key: {}".format(table_key))
            if elapsed_time > self.max_dx_time:
                print("elapsed_time > self.max_dx_time")
                dx_result.insert_table_row(table_key, {ECON1 + DX: self.inconsistent_date})
                self.clear_data()
            else:
                print("elapsed_time < self.max_dx_time")
                dx_result = self.temperature_sensor_dx(dx_result, table_key)
                return dx_result, self.temp_sensor_problem
        print("self.temp_sonsor_problem: {}".format(self.temp_sensor_problem))
        if self.temp_sensor_problem:
            print("econ_alg1 ::: temperature sensor fault detect\n")
            self.sensor_damper_dx.clear_data()
        else:
            print("econ_alg1 ::: elapsed < required\n")
            dx_result = self.sensor_damper_dx.econ_alg(dx_result, oat, mat, oad, cur_time)
        return dx_result, self.temp_sensor_problem


    def aggregate_data(self):
        oa_ma = [(x - y) for x, y in zip(self.oat_values, self.mat_values)]
        ra_ma = [(x - y) for x, y in zip(self.rat_values, self.mat_values)]
        ma_oa = [(y - x) for x, y in zip(self.oat_values, self.mat_values)]
        ma_ra = [(y - x) for x, y in zip(self.rat_values, self.mat_values)]
        avg_oa_ma = mean(oa_ma)
        avg_ra_ma = mean(ra_ma)
        avg_ma_oa = mean(ma_oa)
        avg_ma_ra = mean(ma_ra)
        return avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra


    def temperature_sensor_dx(self, dx_result, table_key):
        avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra = self.aggregate_data()
        diagnostic_msg = {}
        print("temperature_sonsor_dx entrance complete, self.temp_diff_thr: {}".format(self.temp_diff_thr))
        for sensitivity, threshold in self.temp_diff_thr.items():
            print("sensitivity: {}, threshold: {}".format(sensitivity,threshold))
            if avg_oa_ma > threshold and avg_ra_ma > threshold:
                msg = ("{}: MAT is less than OAT and RAT - Sensitivity: {}".format(ECON1, sensitivity))
                # result = 1.1
                result = "Fault"
                self.temp_sensor_problem = True
            elif avg_ma_oa > threshold and avg_ma_ra > threshold:
                msg = ("{}: MAT is greater than OAT and RAT - Sensitivity: {}".format(ECON1, sensitivity))
                # result = 2.1
                result = "Fault"
                self.temp_sensor_problem = True
            else:
                msg = "{}: No problems were detected - Sensitivity: {}".format(ECON1, sensitivity)
                # result = 0.0
                result = "No Fault"
                self.temp_sensor_problem = False
            dx_result.log(msg)
            diagnostic_msg.update({sensitivity: result})

        # if diagnostic_msg["normal"] > 0.0:
        #     self.temp_sensor_problem = True

        dx_table = {ECON1 + DX: diagnostic_msg}
        print(diagnostic_msg)
        print()
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result


    def clear_data(self):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        if self.temp_sensor_problem:
            self.temp_sensor_problem = None


class DamperSensorInconsistencyDx(object):
    def __init__(self, data_window, no_required_data, open_damper_time,
                 oat_mat_check, temp_damper_threshold, analysis):
        self.oat_values = []
        self.mat_values = []
        self.timestamp = []
        self.steady_state = None
        self.econ_time_check = open_damper_time
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oad_temperature_threshold = temp_damper_threshold
        self.oat_mat_check = oat_mat_check
        self.analysis = analysis

    def econ_alg(self, dx_result, oat, mat, oad, cur_time):
        if oad > self.oad_temperature_threshold:
            if self.steady_state is None:
                self.steady_state = cur_time
            elif cur_time - self.steady_state >= self.econ_time_check:
                self.oat_values.append(oat)
                self.mat_values.append(mat)
                self.timestamp.append(cur_time)
        else:
            self.steady_state = None

        elapsed_time = self.timestamp[-1] - self.timestamp[0] if self.timestamp else td(minutes=0)

        if elapsed_time >= self.data_window:
            if len(self.oat_values) > self.no_required_data:
                mat_oat_diff_list = [abs(x-y) for x, y in zip(self.oat_values, self.mat_values)]
                open_damper_check = mean(mat_oat_diff_list)
                table_key = create_table_key(self.analysis, self.timestamp[-1])
                diagnostic_msg = {}
                for sensitivity, threshold in self.oat_mat_check.items():
                    if open_damper_check > threshold:
                        msg = "{} - {}: OAT and MAT are inconsistent when OAD is near 100%".format(ECON1, sensitivity)
                        # result = 0.1
                        result = "Fault"
                    else:
                        msg = "{} - {}: OAT and MAT are consistent when OAD is near 100%".format(ECON1, sensitivity)
                        # result = 0.0
                        result = "No Fault"
                    diagnostic_msg.update({sensitivity: result})

                dx_result.log(msg)
                dx_table = {ECON1 + DX: diagnostic_msg}
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
        return dx_result

    def clear_data(self):
        self.oat_values = []
        self.mat_values = []
        self.steady_state = None
        self.timestamp = []