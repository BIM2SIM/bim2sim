import pandas as pd
from matplotlib import pyplot as plt

from bim2sim.plugins.PluginComfort.bim2sim_comfort.task import \
    ComfortVisualization
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils

EXPORT_PATH = r'C:\Users\Richter_lokal\sciebo\03-Paperdrafts' \
              r'\MDPI_SpecialIssue_Comfort_Climate\sim_results'


def compare_sim_results(df1, df2, ylabel='', filter_min=0, filter_max=365):
    filtered_df1 = df1[(df1.index.dayofyear >= filter_min)
                       & (df1.index.dayofyear <= filter_max)]
    filtered_df2 = df2[(df2.index.dayofyear >= filter_min)
                       & (df2.index.dayofyear <= filter_max)]
    mean_df1 = filtered_df1.resample('D').mean()
    mean_df2 = filtered_df2.resample('D').mean()
    for col in df1:
        middle_of_day = mean_df1.index + pd.DateOffset(hours=12)
        plt.figure(figsize=(10, 6))
        plt.plot(filtered_df1.index, filtered_df1[col], label='2015',
                 linewidth=0.2)
        plt.plot(filtered_df2.index, filtered_df2[col], label='2045',
                 linewidth=0.2)
        plt.plot(middle_of_day, mean_df1[col], label='2015 (mean)',
                 linewidth=0.2)
        plt.plot(middle_of_day, mean_df2[col], label='2045 (mean)',
                 linewidth=0.2)
        plt.xlabel('Timestamp')
        plt.ylabel(ylabel)
        plt.title(col)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    df_ep_res15 = pd.read_csv(EXPORT_PATH + r'\heavy_2015\export\EP-results'
                              r'\eplusout.csv')
    df_ep_res45 = pd.read_csv(EXPORT_PATH + r'\heavy_2045\export\EP-results'
                              r'\eplusout.csv')
    # convert to date time index
    df_ep_res15["Date/Time"] = df_ep_res15["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    df_ep_res45["Date/Time"] = df_ep_res45["Date/Time"].apply(
        PostprocessingUtils._string_to_datetime)
    op_temp_cols = [col for col in df_ep_res45.columns if
                    'Operative Temperature'
                    in col]
    op_temp_df = df_ep_res45[op_temp_cols].round(2)
    op_temp_df = op_temp_df.set_index(df_ep_res15['Date/Time'])

    mean_temp_df = df_ep_res45[[col for col in df_ep_res45.columns
                                if 'Mean Air Temperature' in col]]
    mean_temp_df = mean_temp_df.set_index(df_ep_res15['Date/Time'])
    pmv_temp_df15 = df_ep_res15[[col for col in df_ep_res15.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df15 = pmv_temp_df15.set_index(df_ep_res15['Date/Time'])
    pmv_temp_df45 = df_ep_res45[[col for col in df_ep_res45.columns
                                 if 'Fanger Model PMV' in col]]
    pmv_temp_df45 = pmv_temp_df45.set_index(df_ep_res15['Date/Time'])
    ppd_temp_df15 = df_ep_res15[[col for col in df_ep_res15.columns
                                 if 'Fanger Model PPD' in col]]
    ppd_temp_df15 = ppd_temp_df15.set_index(df_ep_res15['Date/Time'])
    ppd_temp_df45 = df_ep_res45[[col for col in df_ep_res45.columns
                                 if 'Fanger Model PPD' in col]]
    ppd_temp_df45 = ppd_temp_df45.set_index(df_ep_res15['Date/Time'])

    ppd_diff = ppd_temp_df45 - ppd_temp_df15

    compare_sim_results(pmv_temp_df15, pmv_temp_df45, 'PPD', filter_min=0,
                        filter_max=365)

    for col in ppd_diff:
        ComfortVisualization.visualize_calendar(pd.DataFrame(ppd_diff[col]))

    fig = plt.figure(figsize=(10,10))
    for i in range(len(ppd_diff.columns)):
        plt.scatter(df_ep_res45[df_ep_res45.columns[1]], df_ep_res45[
            ppd_diff.columns[i]], marker='.', s=(72./fig.dpi),
                    label=ppd_diff.columns[i])
    plt.legend()
    plt.show()


