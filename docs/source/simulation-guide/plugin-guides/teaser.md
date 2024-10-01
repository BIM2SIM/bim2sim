# TEASER Simulation Guide

## AHU
TEASER simulates an AHU based
on [this Modelica model from AixLib](https://github.com/RWTH-EBC/AixLib/blob/main/AixLib/Airflow/AirHandlingUnit/AHU.mo).
As the IFC can't contain specific information for the AHU currently, like if
the AHU uses heating, cooling, dehumidification etc. and what air profiles are
used, we are using the defaults from TEASER. You can overwrite these values by
using TEASER after you created the TEASER project with `bim2sim` if wanted. 