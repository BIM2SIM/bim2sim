from bim2sim.tasks.base import ITask


class Reset(ITask):
    """Reset all progress"""

    touches = '__reset__'
    single_use = False

    @classmethod
    def requirements_met(cls, state, history):
        return bool(state)

    def run(self, sim_settings):
        return {}


class Quit(ITask):
    """Quit interactive tasks"""

    final = True
    single_use = False

    def run(self):
        self.logger.info("Quitting interactive tasks.")
