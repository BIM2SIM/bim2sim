(plugin_overview)=

# Overview

To make `bim2sim` usable for different simulation domains and tools we use
Plugins that are built upon the functionality that `bim2sim` offers. These
plugins put together one or multiple [Tasks](tasks) and a use a
[set of simulation settings](sim_settings) to create a simulation model 
based on an IFC.
Not all plugins are at the same level of development. Following, we give an
overview about the current development process and what works and what notin the
following table.

| **Plugin** | **Domain** | **Model Generation** | **Comment**                        | **Export** | **Comment**                    | **Simulation** | **Comment**                       |
|------------|------------|----------------------|------------------------------------|------------|--------------------------------|----------------|-----------------------------------|
| AixLib     | HVAC       | Working              | improvements aggregations needed   | Working    |                                | Not working    | Modelica models not published yet |
| EnergyPlus | BPS        | Working              |                                    | Working    |                                |                |                                   |
| TEASER     | BPS        | Working              |                                    | Working    |                                |                |                                   |
| LCA        | LCA        | -                    | no model                           | Working    | improvements IfcWindows needed | -              | no simulation                     |
| CFD        | CFD        | -                    | no model                           | Working    | documentation missing          | -              | no simulation                     |

# Compatibility
For the Plugins that export a simulation model, following the listed compatible 
versions and branches are listed, which our Plugins are compatible with at the
moment.

| **Plugin**     | **Repository** | **version/branch** |
|----------------|------------|----------------|
| **TEASER**     | AixLib     | `development`  |
|                | TEASER     | `development`  |
| **EnergyPlus** | EnergyPlus | `9.4.0`    | m


