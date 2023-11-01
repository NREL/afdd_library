import pickle

with open(r"C:\Users\ikim2\AppData\Local\anaconda3\envs\afdd_library\Lib\site-packages\brickschema\ontologies\1.3\taglookup_origin.pickle", 'rb') as f:
    data = pickle.load(f)

data[('Supply', 'Fan', 'Speed')] = {'Supply_Fan_Speed'}
data[('Supply', 'Fan', 'Power')] = {'Supply_Fan_Power'}
data[('Chiller', 'Power')] = {'Chiller_Power'}
data[('Date', 'Time')] = {'Date_Time'}


with open(r"C:\Users\ikim2\AppData\Local\anaconda3\envs\afdd_library\Lib\site-packages\brickschema\ontologies\1.3\taglookup.pickle", 'wb') as d:
    pickle.dump(data, d)

