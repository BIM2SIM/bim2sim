import pandas as pd
import matplotlib.pyplot as plt

"""
Script for plotting EnergyPlus results to analyze data related to solar 
radiation. Currently hard-coded for Space 2RSC... .
"""

csv_path = ''  # todo: enter path to csv file
# typically something like /tmp/bim2sim_openfoamX_YYYYYYYY/export/EnergyPlus
# /SimResults/AC20-FZK-Haus/eplusout.csv
path = ''  # todo: enter path to store results (optional)
d = 14  # todo: enter day to analyze

df = pd.read_csv(csv_path)

lb = 24 * (d - 1) + 1
ub = lb + 24
day = str(d)

plt.plot(df['Environment:Site Direct Solar Radiation Rate per Area [W/m2]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['Environment:Site Diffuse Solar Radiation Rate per Area [W/m2]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['Environment:Site Ground Reflected Solar Radiation Rate per Area ['
            'W/m2](Hourly)'].iloc[lb:ub])
plt.xlabel('[h]')
plt.ylabel('Solar Radiation [W/m²]')
ax = plt.gca()
ax.legend(['Direct', 'Diffuse', 'Ground Reflected'])
# plt.savefig(path + day + '_solarRad.png')
plt.show()

plt.plot(df['Environment:Site Outdoor Air Drybulb Temperature [C](Hourly)'].iloc[lb:ub])
plt.xlabel('[h]')
plt.ylabel('Outdoor Air Drybulb Temperature [°C]')
# plt.savefig(path + day + '_outdoorTemp.png')
plt.show()

plt.plot(df['Environment:Site Total Sky Cover [](Hourly)'].iloc[lb:ub])
plt.xlabel('[h]')
plt.ylabel('Total Sky Cover [%]')
# plt.savefig(path + day + '_totalSkyCover.png')
plt.show()

plt.plot(df['2CVWUZPEDESDJARZPMJYC8:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['2NVIMH_1VARANYAE7V_22C:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['3XTF9VNRG$5_FYP6RRZVUW:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['3XYW9SWB7YBTXNJUV3X$K5:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['1ZVTHPRHFWSVHGO9MXUL0M:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['3S62UZOCO66NGDMMARS2M9:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['14TEGE_AGDXLMTT8FX0VQP:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.plot(df['2SN7UALFXA$PORAX5B6WQO:Surface Inside Face Temperature [C]('
            'Hourly)'].iloc[lb:ub])
plt.xlabel('[h]')
plt.ylabel('Surface Inside Face Temperature [C](Hourly)')
ax = plt.gca()
ax.legend(['Window 1', 'Window 2', 'Outer wall', 'Outer wall',
           'Inner wall', 'Inner wall', 'Ceiling', 'Floor'])
# plt.savefig(path + day + '_surfaceInsideFaceTemperature.png')
plt.show()

plt.plot(df['3XTF9VNRG$5_FYP6RRZVUW:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='o')
plt.plot(df['3XYW9SWB7YBTXNJUV3X$K5:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='*')
plt.plot(df['1ZVTHPRHFWSVHGO9MXUL0M:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='H')
plt.plot(df['3S62UZOCO66NGDMMARS2M9:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='D')
plt.plot(df['14TEGE_AGDXLMTT8FX0VQP:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='P')
plt.plot(df['2SN7UALFXA$PORAX5B6WQO:Surface Inside Face Solar Radiation Heat Gain Rate per Area [W/m2](Hourly)'].iloc[lb:ub], marker='*')
plt.xlabel('[h]')
plt.ylabel('Surface Solar Radiation Heat Gain Rate [W/m²](Hourly)')
ax = plt.gca()
ax.legend(['Outer wall', 'Outer wall',
           'Inner wall', 'Inner wall', 'Ceiling', 'Floor'])
# plt.savefig(path + day + '_surfaceSolarRadHeatGainRate.png')
plt.show()

plt.plot(df['2CVWUZPEDESDJARZPMJYC8:Surface Window Transmitted Solar Radiation Rate [W](Hourly)'].iloc[lb:ub])
plt.plot(df['2CVWUZPEDESDJARZPMJYC8:Surface Window Net Heat Transfer Rate [W](Hourly)'].iloc[lb:ub])
plt.plot(df['2NVIMH_1VARANYAE7V_22C:Surface Window Transmitted Solar Radiation Rate [W](Hourly)'].iloc[lb:ub])
plt.plot(df['2NVIMH_1VARANYAE7V_22C:Surface Window Net Heat Transfer Rate [W](Hourly)'].iloc[lb:ub])
plt.xlabel('[h]')
plt.ylabel('Heat/ Radiation Transfer Rates [W](Hourly)')
ax = plt.gca()
ax.legend(['Window 1 Trans. Solar Radiation', 'Window 1 Net Heat Transfer',
           'Window 2 Trans. Solar Radiation', 'Window 2 Net Heat Transfer'])
# plt.savefig(path + day + '_windowHeatRates.png')
plt.show()
