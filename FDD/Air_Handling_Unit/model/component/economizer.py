import logging
from datetime import timedelta as td
from statistics import mean

ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
DX = "/diagnostic message"
EI = "/energy impact"


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class EconCorrectlyOn(object):
    def __init__(self, oaf_economizing_threshold, open_damper_threshold, minimum_damper_setpoint, 
                 data_window, no_required_data, cfm, eer, analysis):

        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.oad_values = []
        self.timestamp = []

        # Initialize not_cooling and not_economizing flags
        self.not_cooling = None
        self.not_economizing = None

        # Initialize threshold and parameter
        self.open_damper_threshold = open_damper_threshold
        self.oaf_economizing_threshold = oaf_economizing_threshold
        self.minimum_damper_setpoint = minimum_damper_setpoint
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.cfm = cfm
        self.eer = eer

        self.analysis = analysis
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.not_economizing_dict = {key: 15.0 for key in self.oaf_economizing_threshold}
        self.not_cooling_dict = {key: 14.0 for key in self.oaf_economizing_threshold}
        self.inconsistent_date = {key: 13.2 for key in self.oaf_economizing_threshold}

        # Application result messages
        self.alg_result_messages = [
            "Conditions are favorable for economizing but the OAD is frequently below 100%",
            "No problems detected",
            "Conditions are favorable for economizing and OAD is 100% but the OAF is too low"
        ]
    
    def econ_alg2(self, dx_result, cooling_call, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        dx_result, economizing = self.economizer_conditions(dx_result, cooling_call, econ_condition, cur_time)
        if not economizing:
            return dx_result
        
        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.oad_values.append(oad)
        # self.oad_values.append((mat-rat)/(oat-rat) * 100)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON2 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result
            dx_result = self.not_economizing_when_needed(dx_result, table_key)
            return dx_result
        return dx_result

    
    def not_economizing_when_needed(self, dx_result, table_key):
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = max(0.0, min(100.0, mean(oaf)*100.0))
        avg_damper_signal = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}
        thresholds = zip(self.open_damper_threshold.items(), self.oaf_economizing_threshold.items())

        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            if avg_damper_signal < damper_thr:
                msg = "{} - {}: {}".format(ECON2, key, self.alg_result_messages[0])
                # result = 11.1
                result = "Fault"
                energy = self.energy_impact_calculation()
                energy_impact.update({key: energy})
            else:
                if avg_oaf < oaf_thr:
                    msg = "{} - {}: {} - OAF={}".format(ECON2, key, self.alg_result_messages[2], avg_oaf)
                    # result = 12.1
                    result = "Fault"
                    energy = self.energy_impact_calculation()
                    energy_impact.update({key: energy})
                else:
                    msg = "{} - {}: {}".format(ECON2, key, self.alg_result_messages[1])
                    # result = 10.0
                    result = "No Fault"
                    energy = 0.0
                    energy_impact.update({key: energy})
            dx_result.log(msg)
            diagnostic_msg.update({key: result})
        dx_table = {
            ECON2 + DX: diagnostic_msg,
            ECON2 + EI: energy_impact
        }
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result


    def energy_impact_calculation(self):
        ei = 0.0
        energy_calc = [1.08 * s * self.cfm * (m - o) / (1000.0 * self.eer)
                       for m, o, s in zip(self.mat_values, self.oat_values, self.fan_spd_values)
                       if (m - o) > 0]

        print('energy calc')
        print(energy_calc)
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
        return ei


    def economizer_conditions(self, dx_result, cooling_call, econ_condition, cur_time):
        if not cooling_call:
            dx_result.log("{}: not cooling at {}".format(ECON2, cur_time))
            if self.not_cooling is None:
                self.not_cooling = cur_time
            if cur_time - self.not_cooling >= self.data_window:
                dx_result.log("{}: no cooling during data set - reinitialize.".format(ECON2))
                dx_table = {ECON2 + DX: self.not_cooling_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, False
        else:
            self.not_cooling = None
        if not econ_condition:
            dx_result.log("{}: not economizing at {}.".format(ECON2, cur_time))
            if self.not_economizing is None:
                self.not_economizing = cur_time
            if cur_time - self.not_economizing >= self.data_window:
                dx_result.log("{}: no economizing during data set - reinitialize.".format(ECON2))
                dx_table = {ECON2 + DX: self.not_economizing_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, False
        else:
            self.not_economizing = None
        return dx_result, True
    
    
    def clear_data(self):
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.not_economizing = None
        self.not_cooling = None



class EconCorrectlyOff(object):
    def __init__(self, data_window, no_required_data, min_damper_sp,
                 excess_damper_threshold, desired_oaf, cfm, eer, analysis):

        # Initialize data arrays.
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.economizing = None

        # Application result messages
        self.alg_result_messages = [
            "The OAD should be at the minimum position but is significantly above this value",
            "No problems detected",
            "Inconclusive results, could not verify the status of the economizer"
        ]

        # Map configurable parameters
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3/2
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.min_damper_sp = min_damper_sp
        self.excess_damper_threshold = excess_damper_threshold
        self.economizing_dict = {key: 25.0 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 23.2 for key in self.excess_damper_threshold}
        self.desired_oaf = desired_oaf
        self.analysis = analysis
        self.cfm = cfm
        self.eer = eer


    def econ_alg3(self, dx_result, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        dx_result, economizing = self.economizer_conditions(dx_result, econ_condition, cur_time)
        if economizing:
            return dx_result

        self.oad_values.append(oad)
        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.timestamp.append(cur_time)
        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON3 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result
            dx_result = self.economizing_when_not_needed(dx_result, table_key)
            return dx_result
        return dx_result


    def economizing_when_not_needed(self, dx_result, table_key):
        desired_oaf = self.desired_oaf / 100.0
        avg_damper = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}

        for sensitivity, threshold in self.excess_damper_threshold.items():
            if avg_damper > threshold:
                msg = "{} - {}: {}".format(ECON3, sensitivity, self.alg_result_messages[0])
                # result = 21.1
                result = "Fault"
                energy = self.energy_impact_calculation(desired_oaf)
                energy_impact.update({sensitivity: energy})
            else:
                msg = "{} - {}: {}".format(ECON3, sensitivity, self.alg_result_messages[1])
                # result = 20.0
                result = "No Fault"
                energy = 0.0
                energy_impact.update({sensitivity: energy})
            dx_result.log(msg)
            diagnostic_msg.update({sensitivity: result})

        dx_table = {
            ECON3 + DX: diagnostic_msg,
            ECON3 + EI: energy_impact
        }
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result


    def clear_data(self):
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.economizing = None


    def energy_impact_calculation(self, desired_oaf):
        ei = 0.0
        energy_calc = [
            # (1.08 * spd * self.cfm * (m - (o * desired_oaf + (r * (1.0 - desired_oaf))))) / (1000.0 * self.eer)
            # for m, o, r, spd in zip(self.mat_values, self.oat_values, self.rat_values, self.fan_spd_values)
            # if (m - (o * desired_oaf + (r * (1.0 - desired_oaf)))) > 0
            # (1.006 * spd * (m - (o * desired_oaf + (r * (1.0 - desired_oaf)))))
            (0.559 * spd * (m - (o * desired_oaf + (r * (1.0 - desired_oaf)))))
            for m, o, r, spd in zip(self.mat_values, self.oat_values, self.rat_values, self.fan_spd_values)
            if (m - (o * desired_oaf + (r * (1.0 - desired_oaf)))) > 0
        ]

        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = (sum(energy_calc)) / (len(energy_calc) * dx_time)
            # ei = sum(energy_calc)/len(energy_calc)
            ei = round(ei, 2)
            # ei = mean(energy_calc)
        return ei


    def economizer_conditions(self, dx_result, econ_condition, cur_time):
        if econ_condition:
            dx_result.log("{}: economizing, for data {} --{}.".format(ECON3, econ_condition, cur_time))
            if self.economizing is None:
                self.economizing = cur_time
            if cur_time - self.economizing >= self.data_window:
                dx_result.log("{}: economizing - reinitialize!".format(ECON3))
                dx_table = {ECON3 + DX: self.economizing_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, True
        else:
            self.economizing = None
        return dx_result, False