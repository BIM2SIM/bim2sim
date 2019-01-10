
import importlib

from bim2sim.ifc2python import ifc2python

def create_object_from_ifc(ifc_element):
    """
    Creating an hvac_object by the corresponding ifc_element
    :param ifc_element:
    :return: object of class corresponding to the ifc_element
    """
    ifc_type = ifc2python.getElementType(ifc_element)
    class_dict = {
        "IfcBoiler": ['bim2sim.ifc2python.hvac.logic.boiler',
                      'Boiler'],
        "IfcSpaceHeater": [
            'bim2sim.ifc2python.hvac.logic.spaceheater',
            'SpaceHeater'],
        "IfcTank": [
            'bim2sim.ifc2python.hvac.logic.storage_device',
            'StorageDevice'],
        "PipeStrand": [
            'bim2sim.ifc2python.hvac.logic.pipestrand',
            'PipeStrand']
    }
    module = importlib.import_module(
        class_dict[ifc_type][0])
    class_ = getattr(module, class_dict[ifc_type][1])
    object = class_()
    object.IfcGUID = ifc2python.getGUID(ifc_element)
    return object