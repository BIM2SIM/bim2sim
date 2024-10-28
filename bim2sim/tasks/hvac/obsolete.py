"""This module holds currently not used tasks related to hvac"""
from bim2sim.kernel.decision import DecisionBunch
from bim2sim.kernel.decision import RealDecision
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask, Playground
from bim2sim.utilities.common_functions import get_type_building_elements_hvac


class Enrich(ITask):
    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.enrich_data = {}
        self.enriched_elements = {}

    def enrich_instance(self, instance, json_data):
        attrs_enrich = self.load_element_class(instance, json_data)
        return attrs_enrich

    def run(self, elements):
        json_data = get_type_building_elements_hvac()

        # enrichment_parameter --> Class
        self.logger.info("Enrichment of the elements...")
        # general question -> year of construction, all elements
        decision = RealDecision("Enter value for the construction year",
                                validate_func=lambda x: isinstance(x, float),
                                global_key=f"{str(self.__class__.__name__)}_Construction year",
                                allow_skip=False)
        yield DecisionBunch([decision])
        delta = float("inf")
        year_selected = None
        for year in json_data.element_bind["statistical_years"]:
            if abs(year - decision.value) < delta:
                delta = abs(year - decision.value)
                year_selected = int(year)
        enrich_parameter = year_selected
        # specific question -> each instance
        for instance in elements:
            enrichment_data = self.enrich_instance(
                elements[instance], json_data)
            if bool(enrichment_data):
                elements[instance].enrichment["enrichment_data"] = \
                    enrichment_data
                elements[instance].enrichment["enrich_parameter"] = \
                    enrich_parameter
                elements[instance].enrichment["year_enrichment"] = \
                    enrichment_data["statistical_year"][str(enrich_parameter)]

        self.logger.info("Applied successfully attributes enrichment on "
                         "elements")

    @staticmethod
    def load_element_ifc(element, ele_ifc, enrich_parameter, parameter_value,
                         dataclass):
        """
        this function fills a data class object, with the information found in
        the enrichment data, based on the ifc type and year.
        """
        binding = dataclass.element_bind
        for a in binding:
            if binding[a]["ifc_type"] == ele_ifc:
                for b in binding[a][enrich_parameter]:
                    if b == str(parameter_value):
                        for c in binding[a][enrich_parameter][b]:
                            setattr(element, str(c),
                                    binding[a][enrich_parameter][b][c])

    @staticmethod
    def load_element_class(instance, dataclass):
        """
        this function fills a data class object, with the information found in
        the enrichment data, based on the class, parameter and parameter value.
        """

        ele_class = str(instance.__class__)[
                    str(instance.__class__).rfind(".") + 1:str(
                        instance.__class__).rfind("'")]
        binding = dict(dataclass.element_bind)
        if ele_class in binding:
            attrs_enrich = dict(binding[ele_class])
            del attrs_enrich["class"]
        else:
            return {}

        # check if element has enrich parameter-value?
        for enrich_parameter in attrs_enrich:
            if hasattr(instance, enrich_parameter):
                if getattr(instance, enrich_parameter) in \
                        attrs_enrich[enrich_parameter]:
                    return attrs_enrich[enrich_parameter][
                        str(getattr(instance, enrich_parameter))]
        return attrs_enrich


class DetectCycles(ITask):
    """Detect cycles in graph"""

    reads = ('graph',)
    touches = ('cycles',)

    # TODO: sth useful like grouping or medium assignment

    def run(self, graph: HvacGraph) -> tuple:
        self.logger.info("Detecting cycles")
        cycles = graph.get_cycles()
        return cycles,
