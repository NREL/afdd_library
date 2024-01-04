import pickle
import brickschema

path = brickschema.__file__.replace('__init__.py', 'ontologies\\1.3\\taglookup.pickle')

print(path)

with open(path, 'rb') as f:
    data = pickle.load(f)

data[('Supply', 'Fan', 'Speed')] = {'Supply_Fan_Speed'}
data[('Supply', 'Fan', 'Power')] = {'Supply_Fan_Power'}
data[('Chiller', 'Power')] = {'Chiller_Power'}
data[('Date', 'Time')] = {'Date_Time'}
data[('datetime')] = {'Date_Time'}
data[('Datetime')] = {'Date_Time'}
data[('Fan', 'Coil', 'Unit', 'Outside', 'Air', 'Humd')] = {'Fan_Coil_Unit_Outdoor_Air_Humidity'}
data[('Fan', 'Coil', 'Unit', 'Mixed', 'Air', 'Humd')] = {'Fan_Coil_Unit_Mixed_Air_Humidity'}
data[('Fan', 'Coil', 'Unit', 'Return', 'Air', 'Humd')] = {'Fan_Coil_Unit_Return_Air_Humidity'}
data[('Fan', 'Coil', 'Unit', 'Discharge', 'Air', 'Humd')] = {'Fan_Coil_Unit_Discharge_Air_Humidity'}
data[('Fan', 'Coil', 'Unit', 'Outside', 'Air', 'Temperature')] = {'Fan_Coil_Unit_Outside_Air_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Mixed', 'Air', 'Temperature')] = {'Fan_Coil_Unit_Mixed_Air_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Return', 'Air', 'Temperature')] = {'Fan_Coil_Unit_Return_Air_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Discharge', 'Air', 'Temperature')] = {'Fan_Coil_Unit_Discharge_Air_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Htg', 'Rwt')] = {'Fan_Coil_Unit_Return_Water_Heating_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Clg', 'Rwt')] = {'Fan_Coil_Unit_Return_Water_Cooling_Temperature'}
data[('Fan', 'Coil', 'Unit', 'Discharge', 'Air', 'Flow')] = {'Fan_Coil_Unit_Discharge_Air_Flow'}
data[('Rm', 'Temperature')] = {'Room_Temperature'}
data[('label')] = {'Fault'}


with open(path, 'wb') as d:
    pickle.dump(data, d)

