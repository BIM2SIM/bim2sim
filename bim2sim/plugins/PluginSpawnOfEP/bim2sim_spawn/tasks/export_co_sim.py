from bim2sim.task.base import ITask


class GetZoneConnections(ITask):
    ...
    # TODO (maybe later)


class CoSimExport(ITask):
    ...
    # TODO create static make template with
    #  - hydraulic: map the existing hydraulic system of Modelica export into
    #       one single top level component
    #  - floor (from Buidlings)
    #  - idf link to building (from Buildings)
    #  - connect all stuff
