import pickle
import brickschema as br


path = br.__file__.replace(r'\__init__.py', r'\ontologies\1.3\taglookup.pickle')


with open(path, 'rb') as f:
    data = pickle.load(f)

data[('Supply', 'Fan', 'Speed')] = {'Supply_Fan_Speed'}
data[('Supply', 'Fan', 'Power')] = {'Supply_Fan_Power'}
data[('Chiller', 'Power')] = {'Chiller_Power'}
data[('Date', 'Time')] = {'Date_Time'}


with open(path, 'wb') as d:
    pickle.dump(data, d)
