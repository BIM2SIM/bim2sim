import pandas as pd
from matplotlib import pyplot as plt
import datetime as dt


class PostprocessingUtils:

    @staticmethod
    def _string_to_datetime(date_str):
        """
        Converts a date string in the format MM:DD hh:mm:ss into a datetime
        object.
        :param date_str: A date string in the specified format.
        :return: The converted datetime object.
        """
        date_str = date_str.strip()
        # datetime_df = None

        if date_str[7:9] != '24':
            timestamp = pd.to_datetime(date_str, format='%m/%d  %H:%M:%S')
        else:
            # If the time is 24, set it to 0 and increment day by 1
            date_str = date_str[0:7] + '00' + date_str[9:]
            timestamp = pd.to_datetime(date_str, format='%m/%d  %H:%M:%S') +\
                        pd.Timedelta(days=1)
        return timestamp

    @staticmethod
    def _extract_cols_from_df(df, col_name_part):
        """
        extract columns from an energyplus result dataframe based on parts
        of the column name
        """
        col = [col for col in df.columns if col_name_part in col]
        return_df = df[col].copy()
        return_df["Date/Time"] = df["Date/Time"].copy()
        return_df = return_df.set_index("Date/Time", drop=True).dropna()
        return return_df

    @staticmethod
    def read_csv_and_format_datetime(csv_name):
        with open(csv_name, "r") as csv_file:
            res_df = pd.read_csv(csv_file)
        res_df["Date/Time"] = res_df["Date/Time"].apply(
            PostprocessingUtils._string_to_datetime)
        # correct the year based on the length to something useful. This is
        # needed to make plotting easier in the later processes
        if len(res_df["Date/Time"]) > 8761:
            new_year = 2020
        else:
            new_year = 2021
        original_year = res_df["Date/Time"][0].year
        res_df["Date/Time"] = res_df["Date/Time"].map(
            lambda x: x.replace(year=new_year) if x.year == original_year
            else x.replace(year=new_year+1)
        )
        # set the index
        res_df = res_df.set_index('Date/Time', drop=True)
        # drops the year and reformats
        # res_df['Date/Time'] = res_df['Date/Time'].dt.strftime('%m/%d-%H:%M:%S')

        return res_df

    @staticmethod
    def shift_dataframe_to_midnight(df):
        # Shift the datetime index backward by one hour
        df.index = df.index - pd.DateOffset(hours=1)
        return df

    @staticmethod
    def export_df_for_webtool(csv_name):
        with open(csv_name, "r") as csv_file:
            res_df = pd.read_csv(csv_file)
        res_df["Date/Time"] = res_df["Date/Time"].apply(
            PostprocessingUtils._string_to_datetime)
        res_df['Date/Time'] = res_df['Date/Time'].dt.strftime('%m-%d '
                                                            '%H:%M:%S')  # drops the year
        export_df = pd.DataFrame(index=res_df['Date/Time'])
        zone_cooling_rates_W = PostprocessingUtils._extract_cols_from_df(
            res_df, 'Zone Ideal Loads Zone Total Cooling Rate [W]')
        zone_heating_rates_W = PostprocessingUtils._extract_cols_from_df(
            res_df, 'Zone Ideal Loads Zone Total Heating Rate [W]')
        export_df['heat_demand_kW'] = zone_heating_rates_W.sum(axis=1) / 1000
        export_df['cooling_demand_kW'] = zone_cooling_rates_W.sum(axis=1) / \
                                         1000
        return export_df

    @staticmethod
    def _visualize_results(csv_name, period="week", number=28, date=False):
        """
        Plot Zone Mean Air Temperature (Hourly) vs Outdoor Temperature per
        zone and as an overview on all zones.
        :param csv_name: path to energyplus outputs (eplusout.csv)
        :param period: choose plotting period (
        "year"/"month"/"week"/"day"/"date")
        :param number: choose number of day or week (0...365 (day) or 0...52
        (week))
        :param date: only required if period == date. enter date in format
        date=[int(month), int(day)]
        :return:
        """
        with open(csv_name, "r") as csv_file:
            res_df = pd.read_csv(csv_file)
        res_df["Date/Time"] = res_df["Date/Time"].apply(
            PostprocessingUtils._string_to_datetime)
        # df = res_df.loc[:, ~res_df.columns.str.contains('Surface Inside
        # Face Temperature']
        zone_mean_air = PostprocessingUtils._extract_cols_from_df(res_df,
                                                                  "Zone Mean "
                                                                  "Air "
                                                                  "Temperature")
        ideal_loads = PostprocessingUtils._extract_cols_from_df(res_df,
                                                                "IDEAL LOADS "
                                                                "AIR "
                                                                "SYSTEM:Zone "
                                                                "Ideal Loads "
                                                                "Zone "
                                                                "Sensible")
        equip_rate = PostprocessingUtils._extract_cols_from_df(res_df,
                                                               "Zone "
                                                               "Electric "
                                                               "Equipment "
                                                               "Convective "
                                                               "Heating Rate")
        people_rate = PostprocessingUtils._extract_cols_from_df(res_df,
                                                                "Zone People "
                                                                "Convective "
                                                                "Heating Rate")
        rad_dir = PostprocessingUtils._extract_cols_from_df(res_df,
                                                            "Site Direct "
                                                            "Solar Radiation "
                                                            "Rate per Area")
        # rad_dir_h = rad_dir.resample('1h').mean()
        temp = PostprocessingUtils._extract_cols_from_df(res_df,
                                                         "Outdoor Air "
                                                         "Drybulb "
                                                         "Temperature [C]("
                                                         "Hourly)")
        t_mean = temp.resample('24h').mean()
        zone_id_list = []
        for col in zone_mean_air.columns:
            z_id = col.partition(':')
            if z_id[0] not in zone_id_list:
                zone_id_list.append(z_id[0])
        if period == "year":
            for col in zone_mean_air.columns:
                ax = zone_mean_air.plot(y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                t_mean.plot(ax=ax)
                plt.show()
            axc = zone_mean_air.iloc[:].plot(figsize=(10, 5), grid=True)
            t_mean.iloc[:].plot(ax=axc)
            plt.show()
            return
        elif period == "month":
            for col in zone_mean_air.columns:
                ax = zone_mean_air[zone_mean_air.index.month == number].plot(
                    y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                temp[temp.index.month == number].plot(ax=ax)
                plt.show()
            axc = zone_mean_air[zone_mean_air.index.month == number].plot(
                figsize=(10, 5), grid=True)
            temp[temp.index.month == number].plot(ax=axc)
            plt.show()
            return
        elif period == "date":
            month = date[0]
            day = date[1]
            for col in zone_mean_air.columns:
                ax = zone_mean_air.loc[
                    ((zone_mean_air.index.month == month)
                     & (zone_mean_air.index.day == day))] \
                    .plot(y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                temp.loc[((temp.index.month == month)
                          & (temp.index.day == day))].plot(ax=ax)
                plt.show()
            axc = zone_mean_air.loc[((zone_mean_air.index.month == month)
                                     & (zone_mean_air.index.day == day))] \
                .plot(figsize=(10, 5), grid=True)
            temp.loc[((temp.index.month == month)
                      & (temp.index.day == day))].plot(ax=axc)
            plt.show()
            return
        elif period == "week":
            min = number * 168
            max = (number + 1) * 168
        elif period == "day":
            min = number * 24
            max = (number + 1) * 24
        for col in zone_mean_air.columns:
            ax = zone_mean_air.iloc[min:max].plot(y=[col], figsize=(10,
                                                  5), grid=True)
            # temp.plot(ax=ax)
            temp.iloc[min:max].plot(ax=ax)
            plt.show()
        axc = zone_mean_air.iloc[min:max].plot(figsize=(10, 5), grid=True)
        temp.iloc[min:max].plot(ax=axc)
        plt.show()

        for zid in zone_id_list:
            fig, (ax1, ax2) = plt.subplots(2, sharex=True, figsize=(10, 8))
            fig.suptitle("Zone " + zid, y=1.00)
            z_col = [col for col in ideal_loads.columns if zid in col]
            zma_col = [col for col in zone_mean_air.columns if zid in col]
            ideal_loads[z_col].iloc[min:max].plot(ax=ax1, grid=True)
            # ax1b = ax1.twinx()
            # rad_dir_h.iloc[min:max].plot(ax=ax1b)
            zone_mean_air[zma_col].iloc[min:max].plot(ax=ax2, grid=True,
                                                      color='green')
            temp.iloc[min:max].plot(ax=ax2, color='black')
            ax1.set_title("Loads")
            ax2.set_title("Temperatures")
            ax1.autoscale()
            ax2.autoscale()
            fig.tight_layout(rect=[0, 0.03, 1, 0.8])
            plt.show()
