(plugin_overview)=

# Overview

To make `bim2sim` usable for different simulation domains and tools we use
Plugins that are built upon the functionality that `bim2sim` offers. These
plugins put together one or multiple [Tasks](tasks) and a [
workflow](workflow_concept) to create a simulation model based on an IFC.

Not all plugins are at the same level of development. We provide an overview
about the current development process and what works and what not in the
following table.

| **Plugin** | **Domain** | **Model Generation** | **Comment**                        | **Export** | **Comment**                    | **Simulation** | **Comment**                       |
|------------|------------|----------------------|------------------------------------|------------|--------------------------------|----------------|-----------------------------------|
| AixLib     | HVAC       | Working              | improvements aggregations needed   | Working    |                                | Not working    | Modelica models not published yet |
| EnergyPlus | BPS        | Working              |                                    | Working    |                                |                |                                   |
| TEASER     | BPS        | Working              |                                    | Working    |                                |                |                                   |
| LCA        | LCA        | -                    | no model                           | Working    | improvements IfcWindows needed | -              | no simulation                     |
| CFD        | CFD        | -                    | no model                           | Working    | documentation missing          | -              | no simulation                     |

