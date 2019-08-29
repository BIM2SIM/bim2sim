from bim2sim.enrichtment_data.data_class import DataClass, Enrich_class
from bim2sim.workflow import Workflow


def load_element_ifc(element, ele_ifc, year, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the ifc type and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["ifc_type"] == ele_ifc:
            for b in binding[a]["statistical_year"]:
                if b == str(year):
                    for c in binding[a]["statistical_year"][b]:
                        setattr(element, str(c),
                                binding[a]["statistical_year"][b][c])


def load_element_class(element, ele_class, year, dataclass):
    """
    this function fills a data class object, with the information found in the
    enrichment data, based on the class and year.
    """
    binding = dataclass.element_bind
    for a in binding:
        if binding[a]["class"] == ele_class:
            for b in binding[a]["statistical_year"]:
                if b == str(year):
                    for c in binding[a]["statistical_year"][b]:
                        setattr(element, str(c),
                                binding[a]["statistical_year"][b][c])


def enrich_by_buildyear(self, attrs_enrich, instance):
    if bool(attrs_enrich) is True:
        attrs_instance = {}
        for a in instance.__dir__():
            if a in attrs_enrich:
                attrs_instance[a] = getattr(instance, a)

        for prop in attrs_instance:
            if bool(attrs_enrich) is True:
                if attrs_instance[prop] is None:
                    if not attrs_enrich[prop] is None:
                        setattr(instance, prop + "_enriched", attrs_enrich[prop])
                        self.logger.info("the attribute %s from %s enriched successfully" % (prop, attrs_instance["name"]))
                    else:
                        self.logger.info("The enrichment attribute %s from %s is "
                                         "missing or doesn´t exist in the enrichment file" % (prop, attrs_instance["name"]))
            else:
                self.logger.info("There's no enrichment data for the attribute %s from %s" % (prop, attrs_instance["name"]))
    else:
        self.logger.warning("No enrichment parameters for the instance %s" % instance.name)

