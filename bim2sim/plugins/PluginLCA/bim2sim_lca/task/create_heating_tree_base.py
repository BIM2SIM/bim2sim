from bim2sim.tasks.base import ITask


class CreateHeatingTreeBase(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('ifc_files', 'instances')
    touches = ('...', )
    final = True

    def run(self):
        a = ''
        return a,
