import json
from pathlib import Path
import pandas as pd

import matplotlib
from matplotlib import pyplot as plt
matplotlib.use('TkAgg')
import bim2sim

# Load the JSON file
with open(Path(__file__).parent.parent.parent.parent.parent /
        'assets/enrichment/usage/'
          'UseConditionsComfort_AC20-FZK-Haus.json') as \
        json_file:
    data = json.load(json_file)

# rename keys for better usage in plots
rename_keys = {'Kitchen in non-residential buildings': 'Kitchen',
               'WC and sanitary rooms in non-residential buildings':
                   'Kitchen',
               }
for key in rename_keys.keys():
    data[rename_keys[key]] = data.pop(key)

used_rooms = ['Single office', 'Bed room', 'Traffic area', 'Living', 'Kitchen']

plt.figure(figsize=(10, 6))
for room in used_rooms:
    # Plot all data in a common Matplotlib plot
    plt.plot(data[room]['persons_profile'], label=room)
plt.xlabel('Time of the day (hours)')
plt.xlim([0, 24])
plt.ylabel('Occupancy in %')
plt.title('Occupancy profiles')
plt.legend()
plt.grid()
plt.show()
