from bim2sim.tasks.base import ITask


class SerializeTEASER(ITask):
    """Creates the TEASER project, run() method holds detailed information."""
    reads = ('teaser_prj',)

    def run(self, teaser_prj):
        """Serialize the created TEASER project.

        This is useful if we want to work on the created TEASER project outside
        of bim2sim and don't want to export it directly to Modelica.

        Args:
            teaser_prj: teaser project instance

        """
        self.logger.info("Serializing the created TEASER project")
        self.paths.export.joinpath("TEASER/serialized_teaser").mkdir(parents=True,
                                                              exist_ok=True)
        teaser_prj.save_project(
            file_name=self.prj_name,
            path=self.paths.export / "TEASER/serialized_teaser")

        self.logger.info(
            f'Saved TEASER project '
            f'to {self.paths.export.joinpath("TEASER/serialized_teaser")}')
