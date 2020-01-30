
import logging
from contextlib import contextmanager

from bim2sim.decision import RealDecision, BoolDecision, ListDecision
from bim2sim.enrichment_data.data_class import DataClass


logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')


class Attribute:
    """Descriptor of element attribute"""
    # https://rszalski.github.io/magicmethods/
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'
    _force = False

    def __init__(self, name,
                 description="",
                 default_ps=None,
                 patterns=None,
                 ifc_postprocessing=None,
                 functions=None,
                 default=None):
        self.name = name
        self.description = description

        self.default_ps = default_ps
        self.patterns = patterns
        self.functions = functions
        self.default_value = default

        if ifc_postprocessing:
            self.ifc_post_processing = ifc_postprocessing

    def _inner_get(self, bind, value):

        # default property set and quantity set
        if value is None and (self.default_ps):
            raw_value = self.get_from_default(bind, self.default_ps)
            value = self.ifc_post_processing(raw_value)
            if value is None:
                quality_logger.warning("Attribute '%s' of %s %s was not found in default PropertySet",
                                       self.name, bind.ifc_type, bind.guid)

        # # tool specific properties (finder)
        # if value is None:
        #     raw_value = self.get_from_finder(bind, self.name)
        #     value = self.ifc_post_processing(raw_value)
        #
        # # custom properties by patterns
        # if value is None and self.patterns:
        #     raw_value = self.get_from_patterns(bind, self.patterns, self.name)
        #     value = self.ifc_post_processing(raw_value)
        #
        # # custom functions
        # if value is None and self.functions:
        #     value = self.get_from_functions(bind, self.functions, self.name)

        # enrichment
        if value is None:
            value = self.get_from_enrichment(bind, self.name)

        # default value
        if value is None and self.default_value:
            value = self.default_value

        if 'Wall' in str(bind):# can't use is instance
            value = self.get_wall_properties(bind, self.name)

        return value

    @staticmethod
    def get_from_default(bind, default):
        try:
            value = bind.get_exact_property(default[0], default[1])
        except Exception:
            value = None
        return value

    @staticmethod
    def get_from_finder(bind, name):
        finder = getattr(bind, 'finder', None)
        if finder:  # Aggregations have no finder
            try:
                return bind.finder.find(bind, name)
            except AttributeError:
                pass
        return None

    @staticmethod
    def get_from_patterns(bind, patterns, name):
        # TODO: prevent decision on call by get()
        value = bind.select_from_potential_properties(patterns, name, False)
        return value

    @staticmethod
    def get_from_functions(bind, functions, name):
        value = None
        for i, func in enumerate(functions):
            try:
                value = func(bind, name)
            except Exception as ex:
                logger.error("Function %d of %s.%s raised %s", i, bind, name, ex)
                pass
            else:
                break
        return value

    @staticmethod
    def get_wall_properties(bind, name):
        value = None
        selected_properties = ('heat_capacity', 'density', 'thickness')
        # material = bind.material
        material = 'Leichtbeton 102890359'
        material = ''.join([i for i in material if not i.isdigit()])
        if name in selected_properties:
            try:
                bind.material_selected['properties']
            except KeyError:
                external = 'external'  # check external property
                # if not bind.is_external:
                #     external = 'internal'
                first_decision = BoolDecision(
                    question="Do you want for %s_%s_%s to use template" % (str(bind), bind.guid, external),
                    collect=False)
                first_decision.decide()
                first_decision.stored_decisions.clear()
                if first_decision.value:
                    Materials_DEU = bind.finder.templates[bind.source_tool]['IfcWall']['material']
                    material_templates = dict(DataClass(used_param=2).element_bind)
                    del material_templates['version']
                    for k in Materials_DEU:
                        if material in k:
                            material = Materials_DEU[k]
                    options = {}
                    for k in material_templates:
                        if material in material_templates[k]['name']:
                            options[k] = material_templates[k]
                    materials_options = [[material_templates[k]['name'], k] for k in options]
                    if len(materials_options) > 0:
                        decision1 = ListDecision("Multiple possibilities found",
                                                 choices=list(materials_options),
                                                 allow_skip=True, allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=not True)
                        decision1.decide()
                        bind.material_selected['properties'] = material_templates[decision1.value[1]]
                    else:
                        print("No possibilities found")
                        bind.material_selected['properties'] = {}
                else:
                    bind.material_selected['properties'] = {}

            property_template = bind.finder.templates[bind.source_tool]['MaterialTemplates']
            name_template = name
            if name in property_template:
                name_template = property_template[name]

            try:
                value = bind.material_selected['properties'][name_template]
            except KeyError:
                decision2 = RealDecision("Enter value for the parameter %s" % name,
                                         validate_func=lambda x: isinstance(x, float),  # TODO
                                         global_key="%s" % name,
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
                decision2.decide()
                value = decision2.value
        if name == 'material':
            try:
                value = bind.material_selected['properties']['name']
            except KeyError:
                pass  # check this

        return value

    @staticmethod
    def get_from_enrichment(bind, name):
        value = None
        if bool(bind.enrichment):
            attrs_enrich = bind.enrichment["enrichment_data"]
            try:
                bind.enrichment["enrich_decision"]
            except KeyError:
                # check if want to enrich instance
                first_decision = BoolDecision(
                    question="Do you want for %s_%s to be enriched" % (bind.ifc_type, bind.guid),
                    collect=False)
                first_decision.decide()
                first_decision.collection.clear()
                first_decision.stored_decisions.clear()
                bind.enrichment["enrich_decision"] = first_decision.value

            if bind.enrichment["enrich_decision"]:
                # enrichment via incomplete data (has enrich parameter value)
                try:
                    value = attrs_enrich[name]
                except KeyError:
                    pass
                else:
                    if value is not None:
                        return value
                try:
                    bind.enrichment["selected_enrichment_data"]
                except KeyError:
                    options_enrich_parameter = list(attrs_enrich.keys())
                    decision1 = ListDecision("Multiple possibilities found",
                                             choices=options_enrich_parameter,
                                             global_key="%s_%s.Enrich_Parameter" % (bind.ifc_type, bind.guid),
                                             allow_skip=True, allow_load=True, allow_save=True,
                                             collect=False, quick_decide=not True)
                    decision1.decide()
                    decision1.collection.clear()
                    decision1.stored_decisions.clear()

                    if decision1.value == 'statistical_year':
                        # 3. check if general enrichment - construction year
                        bind.enrichment["selected_enrichment_data"] = bind.enrichment["year_enrichment"]
                    else:
                        # specific enrichment (enrichment parameter and values)
                        decision2 = RealDecision("Enter value for the parameter %s" % decision1.value,
                                                 validate_func=lambda x: isinstance(x, float),  # TODO
                                                 global_key="%s" % decision1.value,
                                                 allow_skip=False, allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=False)
                        decision2.decide()
                        delta = float("inf")
                        decision2_selected = None
                        for ele in attrs_enrich[decision1.value]:
                            if abs(int(ele) - decision2.value) < delta:
                                delta = abs(int(ele) - decision2.value)
                                decision2_selected = int(ele)

                        bind.enrichment["selected_enrichment_data"] = attrs_enrich[str(decision1.value)][str(decision2_selected)]
                value = bind.enrichment["selected_enrichment_data"][name]
        return value

    @staticmethod
    def get_from_decision(bind, name):
        # TODO: decision
        decision = RealDecision(
            "Enter value for %s of %s" % (name, bind.name),
            # output=self,
            # output_key=name,
            global_key="%s_%s.%s" % (bind.ifc_type, bind.guid, name),
            allow_skip=False, allow_load=True, allow_save=True,
            validate_func=lambda x: True,  # TODO meaningful validation
            collect=False,
            quick_decide=True
        )
        value = decision.value
        return value

    def get(self, bind, status, value):
        """Try to get value. Returns None if no method was successful.
        use this method, if None is an acceptable value."""
        if status != Attribute.STATUS_UNKNOWN:
            return value, status

        value = self._inner_get(bind, value)
        if value is None:
            new_status = Attribute.STATUS_NOT_AVAILABLE
        else:
            new_status = Attribute.STATUS_AVAILABLE
        return value, new_status

    def set(self, bind, status, value):
        bind.attributes.set(self.name, value, status)

    @staticmethod
    @contextmanager
    def force_get():
        """Contextmanager to get missing attributes immediately"""
        Attribute._force = True
        yield
        Attribute._force = False

    @staticmethod
    def ifc_post_processing(value):
        """Function for post processing of ifc property values (e.g. diameter list -> diameter)
        by default this function does nothing"""
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        _value, _status = instance.attributes.get(self.name, (None, Attribute.STATUS_UNKNOWN))

        value, status = self.get(instance, _status, _value)

        if self._force and value is None:
            value = self.get_from_decision(instance, self.name)
            status = Attribute.STATUS_AVAILABLE

        self.set(instance, status, value)
        return value

    def __str__(self):
        return "Attribute %s" % self.name


class AttributeManager(dict):
    """Attribute Manager class"""
    def __init__(self, bind):
        super().__init__()
        self.bind = bind

    def set(self, name, value, status=None):
        self.__setitem__(name, value, status)

    def __setitem__(self, name, value, status=None):
        if status is None:
            if value is None:
                status = Attribute.STATUS_NOT_AVAILABLE
            else:
                status = Attribute.STATUS_AVAILABLE

        super().__setitem__(name, (value, status))

    def update(self, other):
        # dict.update does not invoke __setitem__
        for k, v in other.items():
            self.__setitem__(k, v)

    def request(self, name):
        """Request attribuute"""
        value = getattr(self.bind, name)
        if value is None:
            value, status = self.__getitem__(name)

            if status == Attribute.STATUS_NOT_AVAILABLE:
                # actual request
                decision = RealDecision(
                    "Enter value for %s of %s" % (name, self.bind.name),
                    # validate_func=lambda x: isinstance(x, float),
                    output=self,
                    output_key=name,
                    global_key="%s_%s.%s" % (self.bind.ifc_type, self.bind.guid, name),
                    allow_skip=False, allow_load=True, allow_save=True,
                    validate_func=lambda x: True,  # TODO meaningful validation
                    collect=True
                )
                self.bind.related_decisions.append(decision)
        else:
            # already requested or available
            return


def multi_calc(func):
    """Decorator for calculation of multiple Attribute values"""
    def wrapper(bind, name):
        # inner function call
        result = func(bind)
        value = result.pop(name)
        # send all other result values to AttributeManager instance
        bind.attributes.update(result)
        return value
    return wrapper
