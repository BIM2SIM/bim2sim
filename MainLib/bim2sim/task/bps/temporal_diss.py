
@staticmethod
def bind_elements_to_zone(bound_instances):
    """Binds the different elements to the belonging zones"""

    for bound_instance in bound_instances.values():
        disaggregation = {}
        for sb in bound_instance.space_boundaries:
            thermal_zone = sb.thermal_zones[0]
            if sb.related_bound is not None:
                if sb.guid in disaggregation:
                    inst = disaggregation[sb.guid]
                else:
                    inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, thermal_zone)
                    disaggregation[sb.related_bound.guid] = inst
            else:
                inst = Disaggregation.based_on_thermal_zone(bound_instance, sb, thermal_zone)
            if sb not in inst.space_boundaries:
                inst.space_boundaries.append(sb)
            if inst not in thermal_zone.bound_elements:
                thermal_zone.bound_elements.append(inst)
            if thermal_zone not in inst.thermal_zones:
                inst.thermal_zones.append(thermal_zone)

def set_space_properties(self):
    for k, tz in self.tz_instances.items():
        tz.set_space_neighbors()
        tz.set_is_external()
        tz.set_external_orientation()
        tz.set_glass_area()