from pathlib import Path
import requests

from bim2sim.kernel.decision import ListDecision, DecisionBunch
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances


class Weather(ITask):
    """Task to get the weather file for later simulation"""
    reads = ('instances',)
    touches = ('weather_file',)

    def __init__(self, playground):
        super().__init__(playground)
        # TODO: use location of building or decision to get location
        self.location = "Aachen"

    def run(self, instances):
        self.logger.info("Setting weather file.")
        weather_file = None
        # try to get weather file from settings
        if self.playground.sim_settings.weather_file_path:
            weather_file = self.playground.sim_settings.weather_file_path
        # try to get TRY weather file for location of IFC
        if not weather_file:
            location_lat_long = self.get_location_lat_long_from_ifc(instances)
            # TODO wait for DWD to allow scraper
            weather_file = self.get_weatherfile_from_dwd(location_lat_long)
        # use default weather file for aachen
        if not weather_file:
            weatherfiles_path = self.paths.assets / 'weatherfiles'
            weather_file = yield from self.get_weatherfile_by_tool(
                weatherfiles_path)

        return weather_file,

    def get_location_lat_long_from_ifc(self, instances: dict) -> list:
        """
        Returns the location in form of latitude and longitude based on IfcSite.

        The location of the site and therefore the building are taken from the
        IfcSite in form of latitude and longitude. Latitude and Longitude each
        are a tuple of (degrees, minutes, seconds) and, optionally,
        millionths of seconds. See IfcSite Documentation for further
        information.
        Args:
            instances: dict with bim2sim elements

        Returns:
            location_lat_long: list with two elements of latitude and longitude
        """
        site = filter_instances(instances, 'Site')
        if len(site) > 1:
            self.logger.warning(
                "More than one IfcSite in the provided IFC file(s). We are"
                "using the location of the first IfcSite found for weather "
                "file definition.")
        latitude = site[0].RefLatitude
        longitude = site[0].RefLongitude
        location_lat_long = [latitude, longitude]
        return location_lat_long

    def get_weatherfile_from_dwd(self, location_lat_long):
        # TODO implement scraper, if DWD allows it
        weather_file = None
        pass
        return weather_file

    def get_weatherfile_by_tool(self, weatherfiles_path) -> Path:
        """Returns the weatherfile depending on the used tool.

        Args:
            weatherfiles_path:

        Returns:
            file:
        """
        # TODO this needs rewriting and conversions if DWD implementation works
        file_ending = self.get_file_ending()
        search_str = "*" + self.location + "*" + '.' + file_ending
        possible_files = list(weatherfiles_path.glob(search_str))
        if not possible_files:
            self.logger.warning(f"No fitting weather file found for location "
                                f"{self.location}, using default file for "
                                f"Aachen.")
            filename = 'DEU_NW_Aachen.105010_TMYx' + file_ending
            file = weatherfiles_path / filename
        elif len(possible_files) == 1:
            file = possible_files[0]
        else:
            weather_decision = ListDecision(
                "Multiple weatherfiles found for location %s."
                " Please select one." % self.location,
                choices=possible_files,
                global_key='weatherfile_dec'
            )
            yield DecisionBunch([weather_decision])
            file = weather_decision.value
        return file

    def get_file_ending(self) -> str:
        """Returns the needed file ending for the specific tool."""
        raise NotImplementedError

    def get_location_name(self, latitude: tuple, longitude: tuple) -> str:
        """Returns the name of the location based on latitude and longitude.

        Args:
            latitude: tuple of degrees, minutes and seconds
            longitude: tuple of degrees, minutes and seconds

        Returns:
            location_name: str of the location name
        """
        # URL for Nominatim API
        nominatim_url = "https://nominatim.openstreetmap.org/reverse"

        # Parameters for the API request
        params = {
            "format": "json",
            "lat": latitude[0] + (latitude[1] / 60) + (latitude[2] / 3600),
            "lon": longitude[0] + (longitude[1] / 60) + (longitude[2] / 3600),
        }

        # Send the HTTP request to the Nominatim API
        response = requests.get(nominatim_url, params=params)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            location_name = data.get("display_name", "Location not found")

        else:
            self.logger.warning(
                'No location could be retrieved. Maybe due to limited API usage'
                'or faulty location data. Setting Aachen as default location.')
            location_name = 'Aachen'

        return location_name
