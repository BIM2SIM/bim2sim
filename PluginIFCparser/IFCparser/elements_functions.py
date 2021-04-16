
class BoilerFunctions:

    def get_inner_connections(self):
        connections = []
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)
        VL = []
        RL = []
        for port in self.ports:
            if any(filter(vl_pattern.match, port.groups)):
                if port.flow_direction == 1:
                    VL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as VL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        VL.append(port)
            elif any(filter(rl_pattern.match, port.groups)):
                if port.flow_direction == -1:
                    RL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as RL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        RL.append(port)
        if len(VL) == 1 and len(RL) == 1:
            VL[0].flow_side = 1
            RL[0].flow_side = -1
            connections.append((RL[0], VL[0]))
        else:
            self.logger.warning("Unable to solve inner connections for %s", self)
        return connections

    def is_generator(self):
        """boiler is generator function"""
        return True


class DoorFunctions:

    def _get_layers(bind, name):
        """door _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, layer.is_a())
            new_layer.parent = bind
            layers.append(new_layer)
        return layers


class LayerFunctions:

    def __init__(self, *args, **kwargs):
        """layer __init__ function"""
        super().__init__(*args, **kwargs)
        if hasattr(self.ifc, 'Material'):
            material = self.ifc.Material
        else:
            material = self.ifc
        self.material = material.Name
        # ToDO: what if doesn't have thickness
        self.thickness = None
        if hasattr(self.ifc, 'LayerThickness'):
            self.thickness = self.ifc.LayerThickness

    def _get_material_properties(bind, name):
        if name == 'thickness':
            name = 'thickness_default'

        material = bind.material
        if material in bind.material_selected:
            if name in bind.material_selected[material]:
                return bind.material_selected[material][name]
            else:
                return real_decision_user_input(bind, name)
        else:
            first_decision = BoolDecision(question="Do you want for %s with the material %s to use avaiable templates, "
                                                   "enter 'n' for manual input"
                                                   % (bind.guid, bind.material),
                                          collect=False)
            first_decision.decide()
            first_decision.stored_decisions.clear()

            if first_decision.value:
                material_templates, resumed = get_material_templates_resumed()
                material_options = get_matches_list(bind.material, list(resumed.keys()))

                while len(material_options) == 0:
                    decision_ = input(
                        "Material not found, enter value for the material:")
                    material_options = get_matches_list(decision_, list(resumed.keys()))

                decision1 = ListDecision("Multiple possibilities found for material %s" % material,
                                         choices=list(material_options),
                                         allow_skip=True, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=not True)
                decision1.decide()

                bind.material_selected[material] = material_templates[resumed[decision1.value]]
                return bind.material_selected[material][name]
            else:
                return real_decision_user_input(bind, name)

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)


class PipeFunctions:

    @staticmethod
    def _length_from_geometry(bind, name):
        try:
            return Pipe.get_lenght_from_shape(bind.ifc.Representation)
        except AttributeError:
            return None

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Serach for extruded depth in representations

        Warning: Found extrusion may net be the required length!
        :raises: AttributeError if not exactly one extrusion is found"""
        candidates = []
        try:
            for representation in ifc_representation.Representations:
                for item in representation.Items:
                    if item.is_a() == 'IfcExtrudedAreaSolid':
                        candidates.append(item.Depth)
        except:
            raise AttributeError("Failed to determine length.")
        if not candidates:
            raise AttributeError("No representation to determine length.")
        if len(candidates) > 1:
            raise AttributeError("Too many representations to dertermine length %s." % candidates)

        return candidates[0]


class PipeFittingFunctions:

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value


class RoofFunctions:

    def __init__(self, *args, **kwargs):
        """roof __init__ function"""
        super().__init__(*args, **kwargs)
        if hasattr(self, 'ifc'):
            self.ifc_type = self.ifc.is_a()


class SlabFunctions:

    def __init__(self, *args, **kwargs):
        """slab __init__ function"""
        super().__init__(*args, **kwargs)

    def _get_layers(bind, name):
        """slab _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers


class SpaceBoundaryFunctions:

    def __init__(self, *args, **kwargs):
        """spaceboundary __init__ function"""
        super().__init__(*args, **kwargs)
        self.level_description = self.ifc.Description
        self.thermal_zones.append(self.get_object(self.ifc.RelatingSpace.GlobalId))
        if self.ifc.RelatedBuildingElement is not None:
            self.bound_instance = self.get_object(self.ifc.RelatedBuildingElement.GlobalId)
        else:
            self.bound_instance = None
        if self.ifc.InternalOrExternalBoundary.lower() == 'internal':
            self.is_external = True
        else:
            self.is_external = False
        if self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical':
            self.physical = True
        else:
            self.physical = False


class SpaceHeaterFunctions:

    def is_consumer(self):
        return True


class StorageFunctions:

    def _calc_volume(self):
        return self.height * self.diameter ** 2 / 4 * math.pi


class ThermalZoneFunctions:

    def set_neighbors(self):
        """set the neighbors of the thermal zone as a list"""
        self.space_neighbors = self.get_neighbors()

    def set_is_external(self):
        """set the property is_external -> Bool"""
        self.is_external = self.get_is_external()

    def set_glass_area(self):
        """set the property external_orientation"""
        self.glass_percentage = self.get_glass_area()

    def set_external_orientation(self):
        """set the property external_orientation
        value can be an angle (edge) or a list of two angles (edge)"""
        self.external_orientation = self.get_external_orientation()

    def __init__(self, *args, **kwargs):
        """thermalzone __init__ function"""
        super().__init__(*args, **kwargs)
        self.bound_elements = []
        self.is_external = False
        self.external_orientation = 'Internal'
        self.glass_percentage = 'Internal'
        self.space_neighbors = []

    def get_neighbors(self):
        """determines the neighbors of the thermal zone"""
        neighbors = []
        for ele in self.bound_elements:
            for tz in ele.thermal_zones:
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    def get_is_external(self):
        """determines if a thermal zone is external or internal
        based on its elements (Walls and windows analysis)"""
        tz_elements = filter_instances(self.bound_elements, 'Wall') + filter_instances(self.bound_elements, 'Window')
        for ele in tz_elements:
            if hasattr(ele, 'is_external'):
                if ele.is_external is True:
                    return True

    def get_glass_area(self):
        """determines the glass area/facade area ratio for all the windows in the space in one of the 4 following ranges
        0%-30%: 15
        30%-50%: 40
        50%-70%: 60
        70%-100%: 85"""

        glass_area = 0
        facade_area = 0
        if self.is_external is True:
            for ele in self.bound_elements:
                if hasattr(ele.area, "m"):
                    e_area = ele.area.magnitude
                else:
                    e_area = ele.area
                if type(ele) is Window:
                    if ele.area is not None:
                        glass_area += e_area
                if 'Wall' in type(ele).__name__ and ele.is_external is True:
                    facade_area += e_area
            real_gp = 0
            try:
                real_gp = 100 * (glass_area / (facade_area + glass_area))
            except ZeroDivisionError:
                pass
            return real_gp

    def get_external_orientation(self):
        """determines the orientation of the thermal zone
        based on its elements
        it can be a corner (list of 2 angles) or an edge (1 angle)"""
        if self.is_external is True:
            orientations = []
            for ele in self.bound_elements:
                if hasattr(ele, 'is_external') and hasattr(ele, 'orientation'):
                    if ele.is_external is True and ele.orientation not in [-1, -2]:
                        orientations.append(ele.orientation)
            if len(list(set(orientations))) == 1:
                return list(set(orientations))[0]
            else:
                # corner case
                calc_temp = list(set(orientations))
                sum_or = sum(calc_temp)
                if 0 in calc_temp:
                    if sum_or > 180:
                        sum_or += 360
                return sum_or / len(calc_temp)

    def get__elements_by_type(self, type):
        raise NotImplementedError

    def _get_usage(bind, name):
        zone_pattern = []
        matches = []
        if bind.zone_name:
            list_org = bind.zone_name.replace(' (', ' ').replace(')', ' ').replace(' -', ' ').replace(', ', ' ').split()
            for i_org in list_org:
                trans_aux = ts.bing(i_org, from_language='de')
                # trans_aux = ts.google(i_org, from_language='de')
                zone_pattern.append(trans_aux)

            # check if a string matches the zone name
            for usage, pattern in pattern_usage.items():
                for i in pattern:
                    for i_name in zone_pattern:
                        if i.match(i_name):
                            if usage not in matches:
                                matches.append(usage)
        # if just a match given
        if len(matches) == 1:
            return matches[0]
        # if no matches given
        elif len(matches) == 0:
            matches = list(pattern_usage.keys())
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(bind.zone_name)),
                                      choices=matches,
                                      allow_skip=False,
                                      allow_load=True,
                                      allow_save=True,
                                      quick_decide=not True)
        usage_decision.decide()
        return usage_decision.value


class WallFunctions:

    def __init__(self, *args, **kwargs):
        """wall __init__ function"""
        super().__init__(*args, **kwargs)
        self.ifc_type = self.ifc.is_a()

    def _get_layers(bind, name):
        """wall _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers


class WindowFunctions:

    def _get_layers(bind, name):
        """window _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, layer.is_a())
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

