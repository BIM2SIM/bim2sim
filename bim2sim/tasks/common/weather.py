from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class Weather(ITask):
    """Task to get the weather file for later simulation"""
    reads = ('elements',)
    touches = ('weather_file_modelica', 'weather_file_ep')

    def run(self, elements):
        self.logger.info("Setting weather file.")
        weather_file_modelica = None
        weather_file_ep = None
        # try to get weather file from settings for modelica and energyplus
        if self.playground.sim_settings.weather_file_path_modelica:
            weather_file_modelica = (
                self.playground.sim_settings.weather_file_path_modelica)
        if self.playground.sim_settings.weather_file_path_ep:
            weather_file_ep = self.playground.sim_settings.weather_file_path_ep

        # try to get TRY weather file for location of IFC
        if not weather_file_ep and not weather_file_modelica:
            raise NotImplementedError("Waiting for response from DWD if we can"
                                      "implement this")
            # lat, long = self.get_location_lat_long_from_ifc(elements)
            # weather_file = self.get_weatherfile_from_dwd(lat, long)
        self.check_weather_file(weather_file_modelica, weather_file_ep)
        if not weather_file_ep and not weather_file_modelica:
            raise ValueError("No weather file provided for the simulation, "
                             "can't continue model generation.")
        return weather_file_modelica, weather_file_ep

    def check_weather_file(self, weather_file_modelica, weather_file_ep):
        """Check if the file exists and has the correct ending."""
        plugin_name = self.playground.project.plugin_cls.name.lower()

        expected_endings = {
            'energyplus': ['.epw'],
            'comfort': ['.epw'],
            'spawn': ['.epw', '.mos'],
            'teaser': ['.mos'],
            'aixlib': ['.mos'],
            'hkesim': ['.mos']
        }

        # Ensure the correct number of files are checked
        files_to_check = [weather_file_modelica]
        if plugin_name in ['energyplus', 'comfort', 'spawn']:
            files_to_check.insert(0, weather_file_ep)

        for file, expected_suffix in zip(files_to_check,
                                         expected_endings[plugin_name]):
            if not file:
                raise ValueError(
                    f"For Plugin {plugin_name} no weather file"
                    f" with ending {expected_suffix}"
                    f" has been assigned, check your sim_settings.")
            if not file.suffix == expected_suffix:
                raise ValueError(
                    f"{plugin_name} weather file should have ending "
                    f"'{expected_suffix}', but a {file.suffix} file was"
                    f" provided."
                )

    def get_location_lat_long_from_ifc(self, elements: dict) -> [float]:
        """
        Returns the location in form of latitude and longitude based on IfcSite.

        The location of the site and therefore the building are taken from the
        IfcSite in form of latitude and longitude. Latitude and Longitude each
        are a tuple of (degrees, minutes, seconds) and, optionally,
        millionths of seconds. See IfcSite Documentation for further
        information.
        Args:
            elements: dict with bim2sim elements

        Returns:
            latitude, longitude: two float values for latitude and longitude
        """
        site = filter_elements(elements, 'Site')
        if len(site) > 1:
            self.logger.warning(
                "More than one IfcSite in the provided IFC file(s). We are"
                "using the location of the first IfcSite found for weather "
                "file definition.")
        latitude = site[0].location_latitude
        longitude = site[0].location_longitude
        return latitude, longitude

    def get_weatherfile_from_dwd(self, lat, long):
        # TODO implement scraper, if DWD allows it
        raise NotImplementedError("Waiting for response from DWD if we can"
                                  "implement this")

    def get_location_name(self, latitude: tuple, longitude: tuple) -> str:
        """Returns the name of the location based on latitude and longitude.

        Args:
            latitude: tuple of degrees, minutes and seconds
            longitude: tuple of degrees, minutes and seconds

        Returns:
            location_name: str of the location name
        """
        # TODO: this might be obsolete, because if we use DWD method, we don't
        #  need a name anymore, just the coordinates

        import requests
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
