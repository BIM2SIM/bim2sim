---
title: 'bim2sim: A Python Framework for Automated Generation of Multi-Domain Building Simulation Models from IFC Data'
tags:
  - Python
  - Simulation
  - Modeling
  - Building
  - BIM
  - OpenBIM
  - IFC
  - Modelica
  - EnergyPlus
authors:
  - name: David Jansen
    orcid: 0000-0002-3175-2809
    corresponding: true
    affiliation: 1
  - name: Veronika Richter
    orcid: 0000-0002-9736-0496
    affiliation: 2
  - name: Svenne Freund
    orcid: 0000-0003-1716-8136
    affiliation: 3
  - name: Falk Cudok
    orcid: 0000-0002-8916-4209
    affiliation: 3
  - name: Jérôme Frisch
    orcid: 0000-0003-0509-5275
    affiliation: 2
  - name: Christoph van Treeck
    orcid: 0000-0001-5241-035X
    affiliation: 2
  - name: Dirk Müller
    orcid: 0000-0002-6106-6607
    affiliation: 1
affiliations:
 - name: Institute for Energy Efficient Buildings and Indoor Climate, E.ON Energy Research Center, RWTH Aachen University, Germany
   index: 1
 - name: Institute of Energy Efficiency and Sustainable Building, RWTH Aachen University, Germany
   index: 2
 - name: Rud. Otto Meyer Technik GmbH & Co. KG, Germany
   index: 3
date: 26 March 2025
bibliography: paper.bib

---

# Summary

Building Information Modeling (BIM) offers comprehensive data about buildings, but transforming this information into domain-specific simulation models remains challenging. **bim2sim** addresses this gap by providing a Python framework that transforms Industry Foundation Classes (IFC) models into simulation models for multiple domains. This open-source framework implements a two-stage approach with a uniform meta-structure for IFC data extraction and domain-specific plugins for simulation model generation. The framework focuses on Building Energy Performance Simulation (BEPS) and Heating, Ventilation, and Air Conditioning (HVAC) simulations, with support for Computational Fluid Dynamics (CFD) and Life Cycle Assessment (LCA).

# Statement of Need
Energy-efficient building design and operation heavily rely on BEPS, but creating these simulation models manually is time-consuming, error-prone, and requires specialized expertise. While BIM provides rich building data, direct use for simulation faces several challenges:

1. **Geometric Discrepancies**: Architectural BIM models employ geometric representations that differ from simulation requirements
2. **Semantic Gaps**: Critical simulation parameters are often missing in BIM models
3. **Topological Gaps**: HVAC simulation requires accurate component connections often missing in BIM files
4. **Data Format Incompatibilities**: Simulation domains demand specific input formats different from BIM exports

Creating simulation models manually can take days to weeks for complex buildings, creating a major bottleneck in the design process.

**bim2sim** addresses these needs by:

1. Automating transformation from IFC to simulation models, reducing creation time from days to under an hour
2. Providing a flexible Python framework extensible to new simulation tools
3. Supporting multiple domains through specialized plugins
4. Handling imperfect IFC data through repair algorithms
5. Maintaining OpenBIM compatibility with minimal dependencies

The framework enables efficient incorporation of building performance simulation into workflows, supporting better-informed decisions.

# Architecture and Implementation

**bim2sim** is implemented in Python with a two-stage architecture illustrated in \autoref{fig:bim2sim_framework}.

![bim2sim framework structure and plugins. Dashed plugins are still under heavy active development.\label{fig:bim2sim_framework}](docs/source/img/static/bim2sim_framework_overview.png)

1. **Base Framework**: Transforms IFC data into a uniform meta-structure
2. **Domain-Specific Plugins**: Convert the meta-structure into simulation-ready models

## Core Components of Base Framework

- **Elements**: Domain-specific meta-structure for building component classes 
- **Tasks**: Modular processing steps sequenced into workflows
- **Playground**: Task execution environment managing transformations
- **Simulation Settings**: Configuration system for customizing parameters
- **Plugins**: Domain-specific extensions for different simulation targets

## Key Features

- IFC parser utilizing IfcOpenShell [@IfcOpenShell]
- Decision management for handling ambiguities
- Enrichment processes for adding missing information
- Algorithms to correct Space Boundary (SB) information
- HVAC system simplification for Modelica simulations
- Exporters for different simulation platforms

## Available Plugins

**bim2sim** currently includes the following plugins:

1. **TEASER**: Modelica based BEPS simulation
2. **EnergyPlus**: BEPS Simulation using EnergyPlus
3. **AixLib**: Modelica-based HVAC simulation
4. **HKESim**: Modelica-based HVAC simulation (Modelica library itself is not public available)
5. **LCA**: Life cycle assessment via quantity takeoff
6. **Comfort**: Thermal comfort analysis using EnergyPlus

The following plugins are currently in development and exist only in feature branches, pending public release:

7. **Ventilation & Hydraulic System**: Automatic design of ventilation and hydraulic distribution systems
8. **PluginSpawn**: Dynamic coupled simulations of building and HVAC via SpawnOfEnergyPlus [@WetterSpawn]
9. **OpenFOAM**: CFD simulation (under development, open-source available in fall 2025)

# Existing Publications on Methodology

* The methodology for **TEASER** and **EnergyPlus** plugins will be published in Jansen et al. [@Jansen2025bim2sim]
* Implementation of **AixLib** and **HKESim** plugins are documented in Jansen et al. [@jansen2023bim2sim]
* Algorithms for handling SBs are presented in Richter et al. [@Richter.2021]
* The **Comfort** plugin framework is presented in Richter et al. [@richterFrameworkAutomatedIFCbased2023] and evaluated in Richter et al. [@richterExtendingIFCBasedBim2sim2023]
* The methodology of **OpenFOAM** plugin has been presented by Richter et al. [@richterExtendingIFCbasedFramework2024] and extended by Hochberger et al. [@hochbergerAutomatedIFCbasedMesh2024]

# Comparison with Similar Tools
**bim2sim** addresses the challenge of leveraging BIM data for building energy simulations, a field with several existing approaches. In our paper [@Jansen2025bim2sim] (currently under review), we conducted a comprehensive analysis of these BIM-to-simulation tools. \autoref{tab:bim2bemApproaches} presents an abbreviated comparative overview of these tools. The complete analysis in the to-be-published paper considers additional dimensions such as IFC version support, space and surface boundary handling, and data enrichment methods. In the abbreviated version shown here, we focus on the most important aspects: simulation domains (BEPS, HVAC), modular architecture, open-source availability, and implementation technologies.


: IFC-based approaches from related research (chronologically ordered) as analyzed in [@Jansen2025bim2sim]. P: Partially, Y: Yes, -: No/not applicable, EP: EnergyPlus, Mod: Modelica, OS: Open-source, Mod.: Modularity, Impl.: Implementation language/framework.\label{tab:bim2bemApproaches}

| Reference | Name | BEPS | HVAC | Mod. | OS | Impl. |
|:----------|:-----|:-----|:-----|:-----|:----|:------|
| [@Bazjanac.2008a] | | EP | - | Y | - | - |
| [@ODonnell.2011] | SimModel | EP | - | Y | - | XML |
| [@EmiraElAsmi.2015] | | COMETH | COMETH | - | - | - |
| [@giannakis2015] | | EP, TRNSYS | - | - | - | Matlab |
| [@Cao.2018] | SimModel+ | Mod | Mod | Y | - | Py, C++ |
| [@Andriamamonjy.2018] | Ifc2Modelica | Mod | Mod | P | - | Py, IFC |
| [@BIM2Modelica2017; @BIM2Modelica2019] | CoTeTo | Mod | - | - | Y | Py, JModelica |
| [@giannakis2019] | | SimModel, EP | - | - | - | - |
| [@Ramaji.2020] | OsmSerializer | OS/EP | - | - | Y | Java |
| [@Chen.2021] | | EP, eQuest | Y | - | - | Java |
| [@SIMVICUSNEXTLEVEL2023] | SIM-VICUS | Nandrad, EP | district | Y | Y | C++ |
| [@Chen.2023] | AutoBPS-BIM | EP | EP | - | - | - |
| [@graphBasedbim2bem2023] | | EP (not run) | - | - | - | - |
| bim2sim | bim2sim | EP, Mod | Mod | Y | Y | Py, IFC |

# Acknowledgments
**bim2sim** was developed through collaboration between academic institutions (RWTH Aachen University's EBC - Institute for Energy Efficient Buildings and Indoor Climate, E3D - Institute of Energy Efficiency and Sustainable Building) and industry partners (ROM Technik GmbH). The framework was initially created under the "BIM2SIM" project with continued enhancement through the "BIM2Praxis" project, both funded by the German Federal Ministry for Economic Affairs and Energy (BMWi/BMWK).

We acknowledge funding support from the German Federal Ministry for Economic Affairs and Energy (grant number 03ET1562A/B) and the Federal Ministry for Economic Affairs and Climate Action (grant number 3EN1050A/B).

# References