import json
from pathlib import Path
import pandas as pd

import matplotlib as mpl
from matplotlib import pyplot as plt
mpl.use('TkAgg')

PLOT_PATH = Path(r'C:\Users\richter\sciebo\03-Paperdrafts'
                 r'\MDPI_SpecialIssue_Comfort_Climate\img'
                 r'\generated_plots')
INCH = 2.54

################### UPDATE RC PARAMS FOR PLOTS ###############################
plt.rcParams.update(mpl.rcParamsDefault)
plt.rcParams.update({
    "lines.linewidth": 0.8,
    "font.family": "serif",  # use serif/main font for text elements
    "text.usetex": True,     # use inline math for ticks
    "pgf.rcfonts": True,     # don't setup fonts from rc parameters
    "font.size": 8
})

################### VISUALIZE OCCUPANCY PROFILES #############################

# Load the JSON file
with open(Path(__file__).parent.parent /
          'data/UseConditionsComfort_AC20-FZK-Haus.json') as \
        json_file:
    data = json.load(json_file)

# rename keys for better usage in plots
rename_keys = {'Kitchen residential': 'Kitchen',
               'WC residential': 'Bathroom',
               }
for key in rename_keys.keys():
    data[rename_keys[key]] = data.pop(key)

used_rooms = ['Single office', 'Bed room', 'Traffic area', 'Living', 'Kitchen']

# extend person_profiles by first value (just for plot)
extended_person_profiles = {}
for room in used_rooms:
    extended_person_profiles[room] = data[room]['persons_profile']
    extended_person_profiles[room].append(extended_person_profiles[room][0])

fig, ax = plt.subplots(figsize=(10/INCH, 6/INCH))
for room in used_rooms:
    # Plot all data in a common Matplotlib plot
    plt.plot(extended_person_profiles[room], label=room)
plt.xlabel('Time of the day (hours)')
plt.xlim([0, 24])
plt.xticks(range(1, 24+1))
n = 2  # Keeps every 2th label
[l.set_visible(False) for (i, l) in enumerate(ax.xaxis.get_ticklabels()) if
     i % n == 0]
plt.ylabel(r'Occupancy in \%')
# plt.title('Occupancy profiles')
plt.legend()
plt.grid()

plt.savefig(PLOT_PATH / str('Occupancy_profiles_tex' + '.pdf'),
            bbox_inches='tight')
plt.show()

######################### END OF OCCUPANCY PROFILES ##########################
