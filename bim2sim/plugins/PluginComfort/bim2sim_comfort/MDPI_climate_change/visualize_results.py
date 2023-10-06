import csv
import json
import math
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.dates as mdates

from bim2sim.plugins.PluginComfort.bim2sim_comfort.task import \
    ComfortVisualization
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils

EXPORT_PATH = r'C:\Users\Richter_lokal\sciebo\03-Paperdrafts' \
              r'\MDPI_SpecialIssue_Comfort_Climate\sim_results'

PLOT_PATH = Path(r'C:\Users\Richter_lokal\sciebo\03-Paperdrafts'
                 r'\MDPI_SpecialIssue_Comfort_Climate\img'
                 r'\generated_plots')
PMV_COLORS = ['#0232c2', '#028cc2', '#03ffff',
              '#02c248', '#bbc202', '#c27f02']  # set 6 colors
CONSTRUCTION = 'heavy_'  # heavy_ or light_

CITY = 'Cologne'
YEAR_OF_CONSTR = 2015
# SIM_YEAR1 = 'TMYx (2007-2021)' # 2015
SIM_YEAR1 = 'TMYx (2007-2021)' # 2015
SIM_YEAR2 = 'SSP585_2080' # 2045
# SIM_YEAR3 = 'SSP585_2080' # 2045
DIR1 = 'heavy_2015' #CONSTRUCTION+str(SIM_YEAR1)
# DIR1 = 'UK_heavy_TRY' #CONSTRUCTION+str(SIM_YEAR1)
DIR2 = 'heavy_SSP585_2050'# CONSTRUCTION+str(SIM_YEAR2)
DIR3 = 'heavy_SSP585_2080'# CONSTRUCTION+str(SIM_YEAR2)


def round_up_to_nearest_100(num):
    return math.ceil(num / 100) * 100


def floor_to_nearest_100(num):
    return math.floor(num / 100) * 100


def compare_sim_results(df1, df2, ylabel='', filter_min=0, filter_max=365,
                        mean_only=False):
    filtered_df1 = df1[(df1.index.dayofyear >= filter_min)
                       & (df1.index.dayofyear <= filter_max)]
    filtered_df2 = df2[(df2.index.dayofyear >= filter_min)
                       & (df2.index.dayofyear <= filter_max)]
    mean_df1 = filtered_df1.resample('D').mean()
    mean_df2 = filtered_df2.resample('D').mean()
    for col in df1:
        middle_of_day = mean_df1.index + pd.DateOffset(hours=12)

        plt.figure(figsize=(10, 6))
        if not mean_only:
            plt.plot(filtered_df1.index, filtered_df1[col], label='2015',
                     linewidth=0.5)
            plt.plot(filtered_df2.index, filtered_df2[col], label='2045',
                     linewidth=0.5)
        plt.plot(middle_of_day, mean_df1[col],
                 label='2015 (24h mean)',
                 linewidth=0.5)
        plt.plot(middle_of_day, mean_df2[col],
                 label='2045 (24h mean)',
                 linewidth=0.5)
        if filter_max - filter_min > 125:
            date_fmt = mdates.DateFormatter('%B')
        else:
            date_fmt = mdates.DateFormatter('%B %d')
        plt.gca().xaxis.set_major_formatter(date_fmt)
        plt.xlabel('Timestamp')
        plt.ylabel(ylabel)
        plt.title(col)
        plt.legend()
        plt.grid(True)
        plt.draw()


def barplot_per_column(df, title='', legend_title='PMV', y_lim=[0, 7200],
                       save_as='', set_colors=False, ylabel='hours',
                       outside=False):
    result = df.transpose()
    legend_colors = None
    if set_colors:
        legend_colors = PMV_COLORS

    ax = result.plot(kind='bar', figsize=(10, 5), color=legend_colors)
    plt.title(title)
    plt.ylim(y_lim)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.xticks(rotation=0, ha='center')
    if outside:
        plt.legend(title=legend_title,
                   prop={'size': 9}, bbox_to_anchor=(1.002, 1), loc="upper left")
    else:
        plt.legend(title=legend_title,prop={'size': 9})
    if save_as:
        plt.savefig(PLOT_PATH / str(CONSTRUCTION + save_as + '.pdf'))
    # plt.draw()


def plot_and_save_whole_year(df, save_as=''):
    fig, ax = plt.subplots(figsize=(12, 6))
    plt.plot(df)
    date_fmt = mdates.DateFormatter('%B')
    ax.xaxis.set_major_formatter(date_fmt)
    ax.grid(True)
    ax.legend(df.columns)
    if save_as:
        fig.savefig(PLOT_PATH / str(CONSTRUCTION + save_as + '.pdf'))


def evaluate_pmv_hours(pmv_df):
    bins = [-3, -2, -1, 0, 1, 2, 3]
    labels = ['-3 to -2', '-2 to -1', '-1 to 0',
              '0 to 1', '1 to 2', '2 to 3']

    # Count the values in each bin for each column
    result = pd.DataFrame()

    for column in pmv_df.columns:
        counts, _ = pd.cut(pmv_df[column], bins=bins,
                           labels=labels,
                           right=False, include_lowest=True, retbins=True)
        counts = pd.Categorical(counts, categories=labels, ordered=True)
        result[column] = counts.value_counts()
    return result


def rename_duplicates(dictionary):
    value_counts = {}
    renamed_dict = {}
    for key, value in dictionary.items():
        if value in value_counts:
            value_counts[value] += 1
            new_value = f"{value}_{value_counts[value]}"
        else:
            value_counts[value] = 1
            new_value = value

        renamed_dict[key] = new_value
    return renamed_dict


def replace_partial_identifier(col, rename_dict):
    for identifier_part, new_name in rename_dict.items():
        if identifier_part.upper() in col:
            org_column = col
            return org_column, col.replace(identifier_part.upper(),
                                                new_name)
    return col, col


def rename_zone_usage(usage_path, rename_keys):
    with open(usage_path) as json_file:
        zone_usage = json.load(json_file)

    for key in zone_usage.keys():
        for key2 in rename_keys.keys():
            if zone_usage[key] == key2:
                zone_usage[key] = rename_keys[key2]
    zone_usage = rename_duplicates(zone_usage)
    return zone_usage


def plot_CEN15251_adaptive(cen15251, df_full, room_name, year):
    lim_min = 10
    lim_max = 30
    ot = df_full[[col for col in df_full.columns
                  if ((room_name + ':') in col
                      and 'Operative Temperature' in col)]]
    ot = ot.set_index(df_full['Date/Time'])
    ot = ot[(cen15251.iloc[:, 3] >= lim_min) & (cen15251.iloc[:, 3] <= lim_max)]
    cen15251 = cen15251[[col for col in cen15251.columns
                         if (room_name + ':') in col]]
    cen15251 = cen15251[(cen15251.iloc[:, 3] >= lim_min)
                        & (cen15251.iloc[:, 3] <= lim_max)]

    category_i = (cen15251.iloc[:, 0] > 0)
    category_ii = (cen15251.iloc[:, 1] > 0) & (cen15251.iloc[:, 0] == 0)
    category_iii = (cen15251.iloc[:, 2] > 0) & (cen15251.iloc[:, 1] == 0)
    worse = (cen15251.iloc[:, 2] == 0)

    # Create the plot
    plt.figure(figsize=(10, 6))

    # Scatter plot for each comfort category
    plt.scatter(cen15251.iloc[:, 3][category_i], ot[category_i], color='green',
                s=0.2, label='Category I: High level of expectation')
    plt.scatter(cen15251.iloc[:, 3][category_ii], ot[category_ii],
                color='orange', s=0.2, label='Category II: Normal level of '
                                            'expectation')
    plt.scatter(cen15251.iloc[:, 3][category_iii], ot[category_iii],
                color='red', s=0.2,
                label='Category III: Low level of expectation')
    plt.scatter(cen15251.iloc[:, 3][worse], ot[worse],
                color='blue', s=0.2,
                label='OUT OF RANGE')
    coord_cat1_low = [[10,  0.33 * 15 + 18.8 - 2.0],
                      [15,  0.33 * 15 + 18.8 - 2.0],
                      [30,  0.33 * 30 + 18.8 - 2.0]]
    coord_cat1_up = [[10,  0.33 * 10 + 18.8 + 2.0],
                     [30,  0.33 * 30 + 18.8 + 2.0]]
    cc1lx, cc1ly = zip(*coord_cat1_low)
    cc1ux, cc1uy = zip(*coord_cat1_up)
    plt.plot(cc1lx, cc1ly, linestyle='dashed', color='green',
             label='Lower Threshold I')
    plt.plot(cc1ux, cc1uy, linestyle='dashed', color='green',
             label='Upper Threshold I')
    coord_cat2_low = [[10,  0.33 * 15 + 18.8 - 3.0],
                      [15,  0.33 * 15 + 18.8 - 3.0],
                      [30,  0.33 * 30 + 18.8 - 3.0]]
    coord_cat2_up = [[10,  0.33 * 10 + 18.8 + 3.0],
                     [30,  0.33 * 30 + 18.8 + 3.0]]
    cc2lx, cc2ly = zip(*coord_cat2_low)
    cc2ux, cc2uy = zip(*coord_cat2_up)
    plt.plot(cc2lx, cc2ly, linestyle='dashed', color='orange',
             label='Lower Threshold II')
    plt.plot(cc2ux, cc2uy, linestyle='dashed', color='orange',
             label='Upper Threshold II')

    coord_cat3_low = [[10,  0.33 * 15 + 18.8 - 4.0], [15,  0.33 * 15 + 18.8 -
                                                      4.0],
                      [30,  0.33 * 30 + 18.8 - 4.0]]
    coord_cat3_up = [[10,  0.33 * 10 + 18.8 + 4.0], [30,  0.33 * 30 + 18.8 + 4.0]]
    cc3lx, cc3ly = zip(*coord_cat3_low)
    cc3ux, cc3uy = zip(*coord_cat3_up)
    plt.plot(cc3lx, cc3ly, linestyle='dashed', color='red',
             label='Lower Threshold III')
    plt.plot(cc3ux, cc3uy, linestyle='dashed', color='red',
             label='Upper Threshold III')

    # Customize plot
    plt.xlabel('Running Average Outdoor Air Temperature (°C)')
    plt.ylabel('Operative Temperature (°C)')
    plt.xlim([lim_min, lim_max])
    plt.grid()
    plt.title(str(year) + ': ' + room_name + ' - Adaptive Comfort Categories')
    plt.legend()

    # Show the plot
    plt.draw()

def plot_EN16798_adaptive(cen15251, df_full, room_name, year):
    lim_min = 10
    lim_max = 34
    ot = df_full[[col for col in df_full.columns
                  if ((room_name + ':') in col
                      and 'Operative Temperature' in col)]]
    ot = ot.set_index(df_full['Date/Time'])
    ot = ot[(cen15251.iloc[:, 3] >= lim_min) & (cen15251.iloc[:, 3] <= lim_max)]
    cen15251 = cen15251[[col for col in cen15251.columns
                         if (room_name + ':') in col]]
    cen15251 = cen15251[(cen15251.iloc[:, 3] >= lim_min)
                        & (cen15251.iloc[:, 3] <= lim_max)]

    category_i = (cen15251.iloc[:, 0] > 0)
    category_ii = (cen15251.iloc[:, 1] > 0) & (cen15251.iloc[:, 0] == 0)
    category_iii = (cen15251.iloc[:, 2] > 0) & (cen15251.iloc[:, 1] == 0)
    worse = (cen15251.iloc[:, 2] == 0)
    not_applicable = (cen15251.iloc[:, 2] == -1)

    # Create the plot
    plt.figure(figsize=(10, 6))

    # Scatter plot for each comfort category
    plt.scatter(cen15251.iloc[:, 3][category_i], ot[category_i], color='green',
                s=0.2, label='DIN EN 15251: Category I: High level of '
                             'expectation')
    plt.scatter(cen15251.iloc[:, 3][category_ii], ot[category_ii],
                color='orange', s=0.3, label='DIN EN 15251: Category II: '
                                             'Normal level of '
                                            'expectation')
    plt.scatter(cen15251.iloc[:, 3][category_iii], ot[category_iii],
                color='red', s=0.3,
                label='DIN EN 15251: Category III: Low level of expectation')
    plt.scatter(cen15251.iloc[:, 3][worse], ot[worse],
                color='blue', s=0.3,
                label='DIN EN 15251: OUT OF RANGE')
    #plt.scatter(cen15251.iloc[:, 3][not_applicable], ot[not_applicable],
     #           color='black', s=0.3,
      #          label='DIN EN 15251: Not applicable')
    coord_cat1_low = [[10,  0.33 * 10 + 18.8 - 3.0],
                      [30,  0.33 * 30 + 18.8 - 3.0]]
    coord_cat1_up = [[10,  0.33 * 10 + 18.8 + 2.0],
                     [30,  0.33 * 30 + 18.8 + 2.0]]
    cc1lx, cc1ly = zip(*coord_cat1_low)
    cc1ux, cc1uy = zip(*coord_cat1_up)
    plt.plot(cc1lx, cc1ly, linestyle='dashed', color='green',
             label='DIN EN 16798-1: Lower/Upper Thresholds Category I')
    plt.plot(cc1ux, cc1uy, linestyle='dashed', color='green')
    coord_cat2_low = [[10,  0.33 * 10 + 18.8 - 4.0],
                      [30,  0.33 * 30 + 18.8 - 4.0]]
    coord_cat2_up = [[10,  0.33 * 10 + 18.8 + 3.0],
                     [30,  0.33 * 30 + 18.8 + 3.0]]
    cc2lx, cc2ly = zip(*coord_cat2_low)
    cc2ux, cc2uy = zip(*coord_cat2_up)
    plt.plot(cc2lx, cc2ly, linestyle='dashed', color='orange',
             label='DIN EN 16798-1: Lower/Upper Thresholds Category II')
    plt.plot(cc2ux, cc2uy, linestyle='dashed', color='orange')

    coord_cat3_low = [[10,  0.33 * 10 + 18.8 - 5.0],
                      [30,  0.33 * 30 + 18.8 - 5.0]]
    coord_cat3_up = [[10,  0.33 * 10 + 18.8 + 4.0], [30,  0.33 * 30 + 18.8 + 4.0]]
    cc3lx, cc3ly = zip(*coord_cat3_low)
    cc3ux, cc3uy = zip(*coord_cat3_up)
    plt.plot(cc3lx, cc3ly, linestyle='dashed', color='red',
             label='DIN EN 16798-1: Lower/Upper Thresholds Category III')
    plt.plot(cc3ux, cc3uy, linestyle='dashed', color='red')

    # Customize plot
    plt.xlabel('Running Average Outdoor Air Temperature (°C)')
    plt.ylabel('Operative Temperature (°C)')
    plt.xlim([lim_min, lim_max])
    plt.ylim([16.5, 35.5])
    plt.grid()
    plt.title('DIN EN 15251/16798-1 - ' + str(year) + ': ' + room_name + ' - '
                                                                 'Adaptive ' \
                                                          'Comfort '
                                               'Categories')
    lgnd = plt.legend(loc="upper left", scatterpoints=1, fontsize=9)
    lgnd.legend_handles[0]._sizes = [30]
    lgnd.legend_handles[1]._sizes = [30]
    lgnd.legend_handles[2]._sizes = [30]
    lgnd.legend_handles[3]._sizes = [30]
    plt.savefig(PLOT_PATH / str(CONSTRUCTION + 'DIN_EN_16798_' + room_name
                                + '_' + year + '.pdf' ))

    # Show the plot
    plt.draw()


def plot_ASHRAE55_adaptive(ash55, df_full, room_name, year):
    ot = df_full[[col for col in df_full.columns
                      if ((room_name + ':') in col
                          and 'Operative Temperature' in col)]]
    ot = ot.set_index(df_full['Date/Time'])
    ash55 = ash55[[col for col in ash55.columns
                   if (room_name + ':') in col]]
    ash55 = ash55.set_index(df_full['Date/Time'])
    ash55 = ash55[[col for col in ash55.columns
                   if (room_name + ':') in col]]
    ash55 = ash55.set_index(df_full['Date/Time'])
    ot = ot[(ash55.iloc[:, 2] >= 10) & (ash55.iloc[:, 2] <= 33.5)]


    category_i = (ash55.iloc[:, 0] > 0)
    category_ii = (ash55.iloc[:, 1] > 0) & (ash55.iloc[:, 0] == 0)
    worse = (ash55.iloc[:, 1] == 0)

    # Create the plot
    plt.figure(figsize=(10, 6))

    # Scatter plot for each comfort category
    plt.scatter(ash55.iloc[:, 2][category_i], ot[category_i], color='green',
                s=0.2, label='90% acceptability')
    plt.scatter(ash55.iloc[:, 2][category_ii], ot[category_ii],
                color='orange', s=0.2, label='80% acceptability')
    plt.scatter(ash55.iloc[:, 2][worse], ot[worse],
                color='blue', s=0.2,
                label='OUT OF RANGE')
    coord_cat1_low = [[10,   0.31 * 10 + 17.8-2.5],
                      [33.5,   0.31 * 33.5 + 17.8-2.5]]
    coord_cat1_up = [[10,   0.31 * 10 + 17.8+2.5],
                     [33.5,   0.31 * 33.5 + 17.8+2.5]]
    cc1lx, cc1ly = zip(*coord_cat1_low)
    cc1ux, cc1uy = zip(*coord_cat1_up)
    plt.plot(cc1lx, cc1ly, linestyle='dashed', color='green',
             label='90 % acceptability')
    plt.plot(cc1ux, cc1uy, linestyle='dashed', color='green',
             label='90 % acceptability')
    coord_cat2_low = [[10,   0.31 * 10 + 17.8-3.5],
                      [33.5,   0.31 * 33.5 + 17.8-3.5]]
    coord_cat2_up = [[10,   0.31 * 10 + 17.8+3.5],
                     [33.5,   0.31 * 33.5 + 17.8+3.5]]
    cc2lx, cc2ly = zip(*coord_cat2_low)
    cc2ux, cc2uy = zip(*coord_cat2_up)
    plt.plot(cc2lx, cc2ly, linestyle='dashed', color='orange',
             label='80 % acceptability')
    plt.plot(cc2ux, cc2uy, linestyle='dashed', color='orange',
             label='80 % acceptability')


    # Customize plot
    plt.xlabel('Running Average Outdoor Air Temperature (°C)')
    plt.ylabel('Adaptive Model Temperature (°C)')
    plt.xlim([10, 30])
    plt.grid()
    plt.title(str(year) + ': ' + room_name + ' - Adaptive Comfort Categories')
    plt.legend()

    # Show the plot
    plt.draw()


def compare_boxplots(df_in1, df_in2,
                     key='Environment:Site Outdoor Air Drybulb Temperature [C]'
                         '(Hourly)', save_as=''):
    def set_box_color(bp, color):
        plt.setp(bp['boxes'], color=color)
        plt.setp(bp['whiskers'], color=color)
        plt.setp(bp['caps'], color=color)
        plt.setp(bp['medians'], color=color)
        plt.setp(bp['fliers'], color=color)

    color1 = '#02c248'
    color2 = '#0232c2'
    plot_key = key
    df1 = pd.DataFrame()
    df2 = pd.DataFrame()
    df1['Temp1'] = df_in1[plot_key]
    df2['Temp2'] = df_in2[plot_key]

    # Combine the two DataFrames into a single DataFrame
    combined_df = pd.concat([df1, df2], axis=1)

    # Extract month and year from the DateTimeIndex
    combined_df['Month'] = combined_df.index.month

    # Create a list of months (you can customize this if needed)
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']

    # Create a subplot for boxplots
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create boxplots for each month
    for i, month in enumerate(months, start=1):
        ax1 = ax.boxplot(combined_df[combined_df['Month'] == i]['Temp1'],
                   positions=[i-0.18], sym='x', widths=0.22)
        ax2 = ax.boxplot(combined_df[combined_df['Month'] == i]['Temp2'],
                    positions=[
            i+0.18], labels=[''], sym='x', widths=0.22)
        set_box_color(ax1, color1)
        set_box_color(ax2, color2)
    plt.plot([], c=color1, label=SIM_YEAR1)
    plt.plot([], c=color2, label=SIM_YEAR2)

    # # Set labels and title
    plt.xticks(range(1, len(months)+1), months)
    ax.set_xlabel('Month')
    ax.set_ylabel('Temperature')
    ax.set_title(key)

    # Customize the plot as needed
    plt.grid(True)

    # Show the plot
    plt.legend()
    plt.tight_layout()
    if save_as:
        plt.savefig(PLOT_PATH / str(save_as + '.pdf'))
    #plt.draw()


def compare_3boxplots(df_in1, df_in2, df_in3, label1, label2, label3,
                     key='Environment:Site Outdoor Air Drybulb Temperature [C]'
                         '(Hourly)', save_as=''):
    def set_box_color(bp, color):
        plt.setp(bp['boxes'], color=color)
        plt.setp(bp['whiskers'], color=color)
        plt.setp(bp['caps'], color=color)
        plt.setp(bp['medians'], color=color)
        plt.setp(bp['fliers'], color=color)

    color1 = '#02c248'
    color2 = '#0232c2'
    color3 = '#c202b8'
    plot_key = key
    df1 = pd.DataFrame()
    df2 = pd.DataFrame()
    df3 = pd.DataFrame()
    df1['Temp1'] = df_in1[plot_key]
    df2['Temp2'] = df_in2[plot_key]
    df3['Temp3'] = df_in3[plot_key]

    # Combine the two DataFrames into a single DataFrame
    combined_df = pd.concat([df1, df2, df3], axis=1)

    # Extract month and year from the DateTimeIndex
    combined_df['Month'] = combined_df.index.month

    # Create a list of months (you can customize this if needed)
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
              'August', 'September', 'October', 'November', 'December']

    # Create a subplot for boxplots
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create boxplots for each month
    for i, month in enumerate(months, start=1):
        ax1 = ax.boxplot(combined_df[combined_df['Month'] == i]['Temp1'],
                         positions=[i-0.20], sym='x', widths=0.15)
        ax2 = ax.boxplot(combined_df[combined_df['Month'] == i]['Temp2'],
                         positions=[i], labels=[''], sym='x', widths=0.15)
        ax3 = ax.boxplot(combined_df[combined_df['Month'] == i]['Temp3'],
                         positions=[i+0.20], labels=[''], sym='x',
                         widths=0.15)
        set_box_color(ax1, color1)
        set_box_color(ax2, color2)
        set_box_color(ax3, color3)
    plt.plot([], c=color1, label=label1)
    plt.plot([], c=color2, label=label2)
    plt.plot([], c=color3, label=label3)

    # # Set labels and title
    plt.xticks(range(1, len(months)+1), months)
    ax.set_xlabel('Month')
    ax.set_ylabel('Temperature')
    ax.set_title(key)

    # Customize the plot as needed
    plt.grid(True)

    # Show the plot
    plt.legend()
    plt.tight_layout()
    if not save_as:
        save_as = f'cmp_boxplot_outdoor_temp{label1}_{label2}_{label3}'
    plt.savefig(PLOT_PATH / str(save_as + '.pdf'))
    #plt.draw()

    # additional weather analysis
    # with open(PLOT_PATH / 'weather_analysis.csv', 'w') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Name', 'Number'])
    weather_analysis = dict()
    weather_analysis.update({f'max_diff_{label3}-{label1}_degC': round(
        max(combined_df.resample('M').median()['Temp3']- combined_df.resample(
            'M').median()['Temp1']), 3)})
    weather_analysis.update({f'max_diff_{label2}-{label1}_degC': round(
        max(combined_df.resample('M').median()['Temp2']- combined_df.resample(
            'M').median()['Temp1']), 3)})
    with open(PLOT_PATH / 'weather_analysis.csv', 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=';')
        for key, value in weather_analysis.items():
            writer.writerow([key, value])
        csv_file.close()




if __name__ == '__main__':
    zone_usage_path = EXPORT_PATH+\
                      f'\{CITY}\Constr{YEAR_OF_CONSTR}' \
                      f'\{DIR1}\export\zone_dict.json'
    rename_keys = {'Kitchen residential': 'Kitchen',
                   'WC residential':
                       'Bathroom',
                   }
    zone_usage = rename_zone_usage(zone_usage_path, rename_keys)

    df_ep_res01 = pd.read_csv(EXPORT_PATH + \
                              f'\{CITY}\Constr{YEAR_OF_CONSTR}\{DIR1}\export\EP-results'
                              r'\eplusout.csv')

    df_ep_res02 = pd.read_csv(EXPORT_PATH + \
                              f'\{CITY}\Constr{YEAR_OF_CONSTR}\{DIR2}\export\EP-results'
                              r'\eplusout.csv')

    df_ep_res03 = pd.read_csv(EXPORT_PATH + \
                              f'\{CITY}\Constr{YEAR_OF_CONSTR}\{DIR3}\export\EP-results'
                              r'\eplusout.csv')
    # df_ep_res01 = pd.read_csv(EXPORT_PATH +
    #                           fr'\{CONSTRUCTION}2015\export\EP-results'
    #                           r'\eplusout.csv')
    #
    # df_ep_res03 = pd.read_csv(EXPORT_PATH +
    #                           fr'\{CONSTRUCTION}2045\export\EP-results'
    #                           r'\eplusout.csv')

    for column in df_ep_res01.columns:
        column, new_name = replace_partial_identifier(column, zone_usage)
        df_ep_res01 = df_ep_res01.rename(columns={column: new_name})
    for column in df_ep_res02.columns:
        column, new_name = replace_partial_identifier(column, zone_usage)
        df_ep_res02 = df_ep_res02.rename(columns={column: new_name})
    for column in df_ep_res03.columns:
        column, new_name = replace_partial_identifier(column, zone_usage)
        df_ep_res03 = df_ep_res03.rename(columns={column: new_name})

    # convert to date time index
    df_ep_res01["Date/Time"] = df_ep_res01["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res02["Date/Time"] = df_ep_res02["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res03["Date/Time"] = df_ep_res03["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res01 = df_ep_res01.set_index(df_ep_res01['Date/Time'])
    df_ep_res02 = df_ep_res02.set_index(df_ep_res01['Date/Time'])
    df_ep_res03 = df_ep_res03.set_index(df_ep_res01['Date/Time'])
    compare_3boxplots(df_ep_res01, df_ep_res02, df_ep_res03, 2015,
                      'SSP5-8.5 (2050)', 'SSP5-8.5 (2080)')
    compare_boxplots(df_ep_res01, df_ep_res03,
                     save_as=f'cmp_boxplot_outdoor_temp{SIM_YEAR1}_'
                             f'{SIM_YEAR2}')

    cen15 = df_ep_res01[[col for col in df_ep_res01.columns
                         if 'CEN 15251' in col]]
    cen45 = df_ep_res03[[col for col in df_ep_res03.columns
                         if 'CEN 15251' in col]]
    cen15 = cen15.set_index(df_ep_res01['Date/Time'])
    cen45 = cen45.set_index(df_ep_res01['Date/Time'])
    # ash15 = df_ep_res01[[col for col in df_ep_res01.columns
    #                      if 'ASHRAE 55' in col]]
    # ash15 = ash15.set_index(df_ep_res01['Date/Time'])
    # ash45 = df_ep_res03[[col for col in df_ep_res03.columns
    #                      if 'ASHRAE 55' in col]]
    # ash45 = ash45.set_index(df_ep_res01['Date/Time'])
    # for key, room_name in zone_usage.items():
    #     plot_ASHRAE55_adaptive(ash15, df_ep_res01, room_name, 2015)
    # for key, room_name in zone_usage.items():
    #     plot_ASHRAE55_adaptive(ash45, df_ep_res03, room_name, 2045)

    for key, room_name in zone_usage.items():
        plot_EN16798_adaptive(cen15, df_ep_res01, room_name, SIM_YEAR1)
    for key, room_name in zone_usage.items():
        plot_EN16798_adaptive(cen45, df_ep_res03, room_name, SIM_YEAR2)
    # for key, room_name in zone_usage.items():
    #     plot_CEN15251_adaptive(cen15, df_ep_res01, room_name, SIM_YEAR1)
    # for key, room_name in zone_usage.items():
    #     plot_CEN15251_adaptive(cen45, df_ep_res03, room_name, SIM_YEAR2)
    pmv_temp_df15 = df_ep_res01[[col for col in df_ep_res01.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df15 = pmv_temp_df15.set_index(df_ep_res01['Date/Time'])
    pmv_temp_df45 = df_ep_res03[[col for col in df_ep_res03.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df45 = pmv_temp_df45.set_index(df_ep_res01['Date/Time'])

    pmv_temp_df15.columns = pmv_temp_df15.columns.map(lambda x: x.removesuffix(
        ':Zone Thermal Comfort Fanger Model PMV [](Hourly)'))
    pmv_temp_df45.columns = pmv_temp_df45.columns.map(lambda x: x.removesuffix(
        ':Zone Thermal Comfort Fanger Model PMV [](Hourly)'))
    plot_and_save_whole_year(pmv_temp_df15.resample('D').mean(),
                             save_as='pmv_annual_daily_mean_15')
    plot_and_save_whole_year(pmv_temp_df45.resample('D').mean(),
                             save_as='pmv_annual_daily_mean_45')
    ppd_temp_df15 = df_ep_res01[[col for col in df_ep_res01.columns
                                 if 'Fanger Model PPD' in col]]

    ppd_temp_df15 = ppd_temp_df15.set_index(df_ep_res01['Date/Time'])
    ppd_temp_df45 = df_ep_res03[[col for col in df_ep_res03.columns
                                 if 'Fanger Model PPD' in col]]
    ppd_temp_df45 = ppd_temp_df45.set_index(df_ep_res01['Date/Time'])

    ppd_diff = ppd_temp_df45 - ppd_temp_df15

    pmv_temp_df15_hours = evaluate_pmv_hours(pmv_temp_df15)
    pmv_temp_df45_hours = evaluate_pmv_hours(pmv_temp_df45)
    ylim_max = round_up_to_nearest_100(max(pmv_temp_df15_hours.values.max(),
                                           pmv_temp_df45_hours.values.max()))

    merged_pmv1545 = pd.DataFrame([pmv_temp_df15.mean(), pmv_temp_df45.mean()],
                                  index=[SIM_YEAR1,SIM_YEAR2])
    mean_pmv_diff = merged_pmv1545.iloc[1].mean() - merged_pmv1545.iloc[
        0].mean()
    print(f"mean PMV Diff between {SIM_YEAR2} and {SIM_YEAR1}: {mean_pmv_diff}")
    barplot_per_column(merged_pmv1545,
                       y_lim=[math.floor(merged_pmv1545.values.min()),
                              math.ceil(merged_pmv1545.values.max())],
                       save_as=f'pmv_annual_{SIM_YEAR1}_{SIM_YEAR2}',
                       legend_title='year',
                       ylabel='PMV')
    barplot_per_column(pmv_temp_df15_hours, SIM_YEAR1, y_lim=[0, ylim_max],
                       save_as='pmv_df15_hours', set_colors=True, outside=True)
    barplot_per_column(pmv_temp_df45_hours, SIM_YEAR2, y_lim=[0, ylim_max],
                       save_as='pmv_df45_hours', set_colors=True, outside=True)

    pmv_hours_diff = pmv_temp_df45_hours-pmv_temp_df15_hours
    ylim_diff_max = round_up_to_nearest_100(pmv_hours_diff.values.max())
    ylim_diff_min = floor_to_nearest_100(pmv_hours_diff.values.min())
    barplot_per_column(pmv_hours_diff, f'Difference between {SIM_YEAR1} and '
                                       f'{SIM_YEAR2}',
                       y_lim=[ylim_diff_min, ylim_diff_max],
                       save_as='pmv_hours_diff', set_colors=True, outside=True)


    for col in pmv_temp_df15:
        ComfortVisualization.visualize_calendar(
            pd.DataFrame(pmv_temp_df15[col]), year=SIM_YEAR1, color_only=True,
            save_as='calendar_pmv15', construction=CONSTRUCTION,
            skip_legend=False)
    for col in pmv_temp_df45:
        ComfortVisualization.visualize_calendar(
            pd.DataFrame(pmv_temp_df45[col]), year=SIM_YEAR2, color_only=True,
            save_as='calendar_pmv45', construction=CONSTRUCTION,
            skip_legend=False)

    # compare_sim_results(pmv_temp_df15, pmv_temp_df45, 'PMV', filter_min=0,
    #                     filter_max=365, mean_only=True)

    # fig = plt.figure(figsize=(10,10))
    # for i in range(len(ppd_diff.columns)):
    #     plt.scatter(df_ep_res03[df_ep_res03.columns[1]], df_ep_res03[
    #         ppd_diff.columns[i]], marker='.', s=(72./fig.dpi),
    #                 label=ppd_diff.columns[i])
    # plt.legend()
    # plt.show()
    #

