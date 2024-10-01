# TEASER Simulation Guide

## AHU
TEASER simulates an AHU based
on [this Modelica model from AixLib](https://github.com/RWTH-EBC/AixLib/blob/main/AixLib/Airflow/AirHandlingUnit/AHU.mo).
As the IFC can't contain specific information for the AHU currently, like if
the AHU uses heating, cooling, dehumidification etc. and what air profiles are
used, we are using the defaults from TEASER for most of the values.
For some values we allow configuration directly via the following `sim_settings`:
```python
    overwrite_ahu_by_settings = BooleanSetting(
        default=True,
        description='Overwrite central AHU settings with the following '
                    'settings.',
    )
    ahu_heating = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide heating. "
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_cooling = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide cooling."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_dehumidification = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide "
                    "dehumidification."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_humidification = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide humidification."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_heat_recovery = BooleanSetting(
        default=False,
        description="Choose if the central AHU should zuse heat recovery."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_heat_recovery_efficiency = NumberSetting(
        default=0.65,
        min_value= 0.5,
        max_value=0.99,
        description="Choose the heat recovery efficiency of the central AHU."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
```
You can overwrite all other values by using TEASER after you created the TEASER
project with `bim2sim` if wanted. 