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
                 r'\MDPI_SpecialIssue_Comfort_Climate\img\generated_plots')
PMV_COLORS = ['#4d0080', '#0232c2', '#028cc2', '#03ffff',
              '#02c248', '#bbc202', '#c27f02', '#c22802']  # set 8 colors
CONSTRUCTION = 'heavy_'  # heavy_ or light_


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
        plt.tight_layout()
        plt.show()


def barplot_per_column(df, title='', legend_title='PMV', y_lim=[0, 7200],
                       save_as='', set_colors=False, ylabel='hours'):
    result = df.transpose()
    legend_colors = None
    if set_colors:
        legend_colors = PMV_COLORS

    ax = result.plot(kind='bar', figsize=(10, 6), color=legend_colors)
    plt.title(title)
    plt.ylim(y_lim)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.xticks(rotation=0, ha='center')
    plt.tight_layout()
    plt.legend(title=legend_title,
               prop={'size': 8})
    if save_as:
        plt.savefig(PLOT_PATH / str(CONSTRUCTION + save_as + '.pdf'))
    plt.show()



def evaluate_pmv_hours(pmv_df):
    bins = [-float('inf'), -3, -2, -1, 0, 1, 2, 3, float('inf')]
    labels = ['< -3', '-3 to -2', '-2 to -1', '-1 to 0',
              '0 to 1', '1 to 2', '2 to 3', '> 3']

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
    ot = df_full[[col for col in df_full.columns
                  if ((room_name + ':') in col
                      and 'Operative Temperature' in col)]]
    ot = ot.set_index(df_full['Date/Time'])
    ot = ot[(cen15251.iloc[:, 3] >= 10) & (cen15251.iloc[:, 3] <= 30)]
    cen15251 = cen15251[[col for col in cen15251.columns
                         if (room_name + ':') in col]]
    cen15251 = cen15251[(cen15251.iloc[:, 3] >= 10)
                        & (cen15251.iloc[:, 3] <= 30)]

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
    plt.ylabel('Adaptive Model Temperature (°C)')
    plt.xlim([10, 30])
    plt.grid()
    plt.title(str(year) + ': ' + room_name + ' - Adaptive Comfort Categories')
    plt.legend()

    # Show the plot
    plt.show()


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
    plt.show()


def compare_boxplots(df_in1, df_in2,
                     key='Environment:Site Outdoor Air Drybulb Temperature [C]'
                         '(Hourly)'):
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
        ax.boxplot(combined_df[combined_df['Month'] == i]['Temp1'], positions=[
            i], labels=[month])
        ax.boxplot(combined_df[combined_df['Month'] == i]['Temp2'], positions=[
            i+0.25], labels=[''])
    #
    # # Set labels and title
    ax.set_xlabel('Month')
    ax.set_ylabel('Temperature')
    ax.set_title('Monthly Temperature Boxplots')

    # Customize the plot as needed
    plt.grid(True)

    # Show the plot
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    zone_usage_path = EXPORT_PATH+fr'\{CONSTRUCTION}2015\export\zone_dict.json'
    rename_keys = {'Kitchen in non-residential buildings': 'Kitchen',
                   'WC and sanitary rooms in non-residential buildings':
                       'Bathroom',
                   }
    zone_usage = rename_zone_usage(zone_usage_path, rename_keys)

    df_ep_res15 = pd.read_csv(EXPORT_PATH +
                              fr'\{CONSTRUCTION}2015\export\EP-results'
                              r'\eplusout.csv')

    df_ep_res45 = pd.read_csv(EXPORT_PATH +
                              fr'\{CONSTRUCTION}2045\export\EP-results'
                              r'\eplusout.csv')

    for column in df_ep_res15.columns:
        column, new_name = replace_partial_identifier(column, zone_usage)
        df_ep_res15 = df_ep_res15.rename(columns={column: new_name})
    for column in df_ep_res45.columns:
        column, new_name = replace_partial_identifier(column, zone_usage)
        df_ep_res45 = df_ep_res45.rename(columns={column: new_name})

    # convert to date time index
    df_ep_res15["Date/Time"] = df_ep_res15["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res45["Date/Time"] = df_ep_res45["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res15 = df_ep_res15.set_index(df_ep_res15['Date/Time'])
    df_ep_res45 = df_ep_res45.set_index(df_ep_res15['Date/Time'])
    compare_boxplots(df_ep_res15, df_ep_res45)

    cen15 = df_ep_res15[[col for col in df_ep_res15.columns
                        if 'CEN 15251' in col]]
    cen45 = df_ep_res45[[col for col in df_ep_res45.columns
                        if 'CEN 15251' in col]]
    cen15 = cen15.set_index(df_ep_res15['Date/Time'])
    cen45 = cen45.set_index(df_ep_res15['Date/Time'])
    ash15 = df_ep_res15[[col for col in df_ep_res15.columns
                         if 'ASHRAE 55' in col]]
    ash15 = ash15.set_index(df_ep_res15['Date/Time'])
    ash45 = df_ep_res45[[col for col in df_ep_res45.columns
                         if 'ASHRAE 55' in col]]
    ash45 = ash45.set_index(df_ep_res15['Date/Time'])
    for key, room_name in zone_usage.items():
        plot_ASHRAE55_adaptive(ash15, df_ep_res15, room_name, 2015)
    for key, room_name in zone_usage.items():
        plot_ASHRAE55_adaptive(ash45, df_ep_res45, room_name, 2045)

    for key, room_name in zone_usage.items():
        plot_CEN15251_adaptive(cen15, df_ep_res15, room_name, 2015)
    for key, room_name in zone_usage.items():
        plot_CEN15251_adaptive(cen45, df_ep_res45, room_name, 2045)
    pmv_temp_df15 = df_ep_res15[[col for col in df_ep_res15.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df15 = pmv_temp_df15.set_index(df_ep_res15['Date/Time'])
    pmv_temp_df45 = df_ep_res45[[col for col in df_ep_res45.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df45 = pmv_temp_df45.set_index(df_ep_res15['Date/Time'])

    pmv_temp_df15.columns = pmv_temp_df15.columns.map(lambda x: x.removesuffix(
        ':Zone Thermal Comfort Fanger Model PMV [](Hourly)'))
    pmv_temp_df45.columns = pmv_temp_df45.columns.map(lambda x: x.removesuffix(
        ':Zone Thermal Comfort Fanger Model PMV [](Hourly)'))

    ppd_temp_df15 = df_ep_res15[[col for col in df_ep_res15.columns
                                 if 'Fanger Model PPD' in col]]

    ppd_temp_df15 = ppd_temp_df15.set_index(df_ep_res15['Date/Time'])
    ppd_temp_df45 = df_ep_res45[[col for col in df_ep_res45.columns
                                 if 'Fanger Model PPD' in col]]
    ppd_temp_df45 = ppd_temp_df45.set_index(df_ep_res15['Date/Time'])

    ppd_diff = ppd_temp_df45 - ppd_temp_df15

    pmv_temp_df15_hours = evaluate_pmv_hours(pmv_temp_df15)
    pmv_temp_df45_hours = evaluate_pmv_hours(pmv_temp_df45)
    ylim_max = round_up_to_nearest_100(max(pmv_temp_df15_hours.values.max(),
                                           pmv_temp_df45_hours.values.max()))

    merged_pmv1545 = pd.DataFrame([pmv_temp_df15.mean(), pmv_temp_df45.mean()],
                                  index=[2015,2045])
    barplot_per_column(merged_pmv1545,
                       y_lim=[math.floor(merged_pmv1545.values.min()),
                              math.ceil(merged_pmv1545.values.max())],
                       save_as='pmv_annual_2015_2045', legend_title='year',
                       ylabel='PMV')
    barplot_per_column(pmv_temp_df15_hours, '2015', y_lim=[0, ylim_max],
                       save_as='pmv_df15_hours', set_colors=True)
    barplot_per_column(pmv_temp_df45_hours, '2045', y_lim=[0, ylim_max],
                       save_as='pmv_df45_hours', set_colors=True)

    pmv_hours_diff = pmv_temp_df45_hours-pmv_temp_df15_hours
    ylim_diff_max = round_up_to_nearest_100(pmv_hours_diff.values.max())
    ylim_diff_min = floor_to_nearest_100(pmv_hours_diff.values.min())
    barplot_per_column(pmv_hours_diff, 'Difference between 2015 and 2045',
                       y_lim=[ylim_diff_min, ylim_diff_max],
                       save_as='pmv_hours_diff', set_colors=True)


    for col in pmv_temp_df15:
        ComfortVisualization.visualize_calendar(
            pd.DataFrame(pmv_temp_df15[col]), year=2015, color_only=True,
            save_as='calendar_pmv15', construction=CONSTRUCTION,
            skip_legend=False)
    for col in pmv_temp_df45:
        ComfortVisualization.visualize_calendar(
            pd.DataFrame(pmv_temp_df45[col]), year=2045, color_only=True,
            save_as='calendar_pmv45', construction=CONSTRUCTION,
            skip_legend=False)

    # compare_sim_results(pmv_temp_df15, pmv_temp_df45, 'PMV', filter_min=0,
    #                     filter_max=365, mean_only=True)

    # fig = plt.figure(figsize=(10,10))
    # for i in range(len(ppd_diff.columns)):
    #     plt.scatter(df_ep_res45[df_ep_res45.columns[1]], df_ep_res45[
    #         ppd_diff.columns[i]], marker='.', s=(72./fig.dpi),
    #                 label=ppd_diff.columns[i])
    # plt.legend()
    # plt.show()
    #

