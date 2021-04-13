import re
import json
import os

from Ifc import SchemaParser
from jinja2 import Environment, FileSystemLoader
import inspect
import elements_functions
from dill.source import getsource
from bim2sim.kernel import elements
import urllib.request
from bs4 import BeautifulSoup
from Ifc import SchemaParser


def json2python(schema_version):
    """creates elements.py file based on elements_specific_schema.json, elements_functions.py
    and schema for specific schema of ifc"""

    args = {'schema': 'PluginIFCparser/schema.exp',
            'module': 'PluginIFCparser/Ifc/Ifc_All.py',
            'json': 'PluginIFCparser/elements_specific_schema.json'}

    # initialise the jinja2 engine
    env = Environment(
        loader=FileSystemLoader('./PluginIFCparser/templates'),
        trim_blocks=True,
        lstrip_blocks=True
    )
    os.chdir('../../')
    # read the templates
    entity_template = env.get_template("entity_parser.template.py")

    IFC_RELEASE = 'https://standards.buildingsmart.org/IFC/RELEASE/'
    webUrl = urllib.request.urlopen(IFC_RELEASE)
    soup = BeautifulSoup(webUrl, 'lxml')
    links = []
    for link in soup.findAll('a'):
        if link.get('href').startswith('IFC'):
            links.append(link.get('href')[:-1])
    if schema_version in links:
        last_ifc_express = IFC_RELEASE + schema_version + '/FINAL/EXPRESS/' + schema_version.replace('_', 'x') + '.exp'
    else:
        print('error for file')  # todo
    urllib.request.urlretrieve(last_ifc_express, args['schema'])

    parser = SchemaParser()
    schema = parser.read_schema_file(args['schema'])

    os.remove(args['schema'])

    relevant_ifc_types = (
        'IfcChiller',
        'IfcCoolingTower',
        'IfcHeatExchanger',
        'IfcBoiler',
        'IfcPipeSegment',
        'IfcPipeFitting',
        'IfcSpaceHeater',
        'IfcTank',
        'IfcDistributionChamberElement',
        'IfcPump',
        'IfcValve',
        'IfcDuctSegment',
        'IfcDuctFitting',
        'IfcAirTerminal',
        "IfcSpace",
        "IfcRelSpaceBoundary",
        "IfcDistributionSystem",
        'IfcWall',
        "IfcMaterialLayer",
        'IfcWindow',
        'IfcDoor',
        "IfcPlate",
        "IfcSlab",
        "IfcRoof",
        'IfcSite',
        'IfcBuilding',
        'IfcBuildingStorey'
    )
    with open(args['json'], 'r+', encoding="utf-8") as f:
        specific_Schema = json.load(f)

    # create the output file and write the necessary import statements
    fd = open(args['module'], "w")

    for imp in specific_Schema['head']:
        fd.write(imp)
        fd.write('\n')

    for entity_name in relevant_ifc_types:
        if entity_name in schema.classes["ENTITY"]:
            entity = schema.classes["ENTITY"][entity_name]
            entity.name = entity_name.replace('Ifc', '')
            entity.parent = "element.Element"
            for i, type_e in schema.classes["TYPE"].items():
                if re.compile('%sTypeEnum' % entity_name, flags=re.IGNORECASE).match(i):
                    entity.defspec = type_e.defspec
                    break
            if entity_name in specific_Schema:
                entity.sschema = specific_Schema[entity_name]
                if 'name' in entity.sschema:
                    entity.name = entity.sschema['name']
                if 'parent' in entity.sschema:
                    entity.parent = entity.sschema['parent']
                if 'functions' in entity.sschema and hasattr(elements_functions, "%sFunctions" % entity.name):
                    e_functions = []
                    for fun in entity.sschema['functions']:
                        e_functions.append(
                            getsource(getattr(getattr(elements_functions, "%sFunctions" % entity.name), fun)))
                    entity.functions = e_functions
            try:
                entity_template.stream(entity.__dict__).dump(fd)
            except:
                print()

    fd.write("\n\n__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]")

    fd.close()
    print()


def python2json():
    """overwrites functions from elements.py in file elements_functions.py and
    overwrites pattern, conditions and attributes in file elements_specific_schema.json"""
    # overwrites functions and attributes
    instances = {m[0]: m[1] for m in inspect.getmembers(elements, inspect.isclass) if
                 m[1].__module__ == 'bim2sim.kernel.elements'}
    elements_str = getsource(elements).splitlines()
    for elements_line in elements_str:
        if re.compile('class(.*?)', flags=re.IGNORECASE).match(elements_line):
            head_index = elements_str.index(elements_line)
            break
    instances_dict = {}
    for name, instance in instances.items():
        instances_dict[name] = {}
        instance_str = getsource(instance).splitlines()
        instances_dict[name]['attributes'] = {}
        for instance_line in instance_str:
            # get attributes from elements.py
            if re.compile('(.*?)attribute.Attribute', flags=re.IGNORECASE).match(instance_line):
                attr_name = instance_line.split()[0]
                s_index = instance_str.index(instance_line)
                aux_str = instance_str[s_index:]
                for instance_line2 in aux_str[1:]:
                    if re.compile('    \)(.*?)', flags=re.IGNORECASE).match(instance_line2):
                        f_index = aux_str.index(instance_line2)
                        attr_lines = aux_str[1:f_index]
                        new_attr_lines = []
                        for attr_line in attr_lines:
                            new_attr_lines.append(attr_line.lstrip())
                        instances_dict[name]['attributes'][attr_name] = new_attr_lines
                        break
            # get patterns from elements.py
            if re.compile('(.*?)pattern_ifc_type', flags=re.IGNORECASE).match(instance_line):
                s_index = instance_str.index(instance_line)
                aux_str = instance_str[s_index:]
                for instance_line2 in aux_str[1:]:
                    if re.compile('    \]', flags=re.IGNORECASE).match(instance_line2):
                        f_index = aux_str.index(instance_line2)
                        attr_lines = aux_str[1:f_index]
                        new_attr_lines = []
                        for attr_line in attr_lines:
                            new_attr_lines.append(re.findall("\'(.*?)\'", attr_line)[0])
                        instances_dict[name]['pattern'] = new_attr_lines
                        break
            # get conditions from elements.py
            if re.compile('(.*?)conditions', flags=re.IGNORECASE).match(instance_line):
                s_index = instance_str.index(instance_line)
                aux_str = instance_str[s_index:]
                for instance_line2 in aux_str[1:]:
                    if re.compile('    \]', flags=re.IGNORECASE).match(instance_line2):
                        f_index = aux_str.index(instance_line2)
                        attr_lines = aux_str[1:f_index]
                        new_attr_lines = []
                        for attr_line in attr_lines:
                            new_attr_lines.append(attr_line.lstrip())
                        instances_dict[name]['conditions'] = new_attr_lines
                        break
        # get functions from elements.py
        func_dict = {}
        for m in inspect.getmembers(instance, predicate=inspect.isfunction):
            if m[1].__module__ == 'bim2sim.kernel.elements':
                if re.compile('(.*?)%s' % name, flags=re.IGNORECASE).match(str(m[1])):
                    func_dict[m[0]] = m[1]

        if len(func_dict) > 0:
            instances_dict[name]['functions'] = {}
            for f_name, func in func_dict.items():
                instances_dict[name]['functions'][f_name] = func
    # function overwriting
    with open('elements_functions.py', "r") as fd:
        original_data = fd.read()
        fd.close()
    with open('elements_specific_schema.json', 'r', encoding="utf-8") as f:
        original_schema = json.load(f)
        f.close()
    original_schema['head'] = elements_str[:head_index-1]
    aux_data = original_data.splitlines()
    for instance, content in instances_dict.items():
        # find equivalent in schema
        selected_ifc_instance = None
        for ifc_instance, ifc_content in original_schema.items():
            if 'name' in ifc_content:
                new_name = ifc_content['name']
            else:
                new_name = ifc_instance.replace('Ifc', '')
            if new_name == instance:
                selected_ifc_instance = ifc_instance
                break
        if selected_ifc_instance:
            if 'functions' in content:
                # write functions on json
                original_schema[selected_ifc_instance]['functions'] = list(content['functions'].keys())
                # write functions on elements functions
                for n_func, func in content['functions'].items():
                    class_index = None
                    function_index = None
                    next_class_index = len(aux_data)
                    for line_auxd in aux_data:
                        if re.compile("(.*?)class %sFunctions:" % instance).match(line_auxd):
                            class_index = aux_data.index(line_auxd)
                            break  # to use in functions
                    function_in_python = getsource(func)
                    if class_index is not None:
                        for line_auxd in aux_data[class_index+1:]:
                            if line_auxd.startswith('class '):
                                next_class_index = aux_data.index(line_auxd)
                                break
                        for line_auxd in aux_data[class_index:next_class_index]:
                            if re.compile("(.*?)def %s" % n_func).match(line_auxd):
                                function_index = aux_data[class_index:].index(line_auxd)+class_index
                                break
                        if function_index is not None:
                            function_stored = getattr(getattr(elements_functions, "%sFunctions" % instance), n_func)
                            f_stored_lines = getsource(function_stored).splitlines()
                            original_index = aux_data[class_index:next_class_index].index(f_stored_lines[0]) + class_index
                            aux_index = len(f_stored_lines)+1
                            while aux_index > 0:
                                aux_data.pop(original_index)
                                aux_index -= 1
                            aux_data.insert(original_index, function_in_python)
                        else:
                            for line_data in aux_data:
                                if re.compile("(.*?)class %sFunctions:" % instance).match(line_data):
                                    index_in_functions = aux_data.index(line_data)
                                    aux_data.insert(index_in_functions + 2, function_in_python)
                                    break
                    else:
                        aux_data.append("")
                        aux_data.append("class %sFunctions:\n" % instance)
                        aux_data.append(function_in_python)

            if 'attributes' in content:
                original_schema[selected_ifc_instance]['attributes'] = content['attributes']
            if 'pattern' in content:
                original_schema[selected_ifc_instance]['pattern'] = content['pattern']
            if 'conditions' in content:
                original_schema[selected_ifc_instance]['conditions'] = content['conditions']

    aux_data.append('')
    original_data = '\n'.join(aux_data)

    with open('elements_functions.py', "w", encoding="utf-8") as fd:
        fd.write(original_data)
        fd.close()
    with open('elements_specific_schema.json', 'w', encoding="utf-8") as f:
        json.dump(original_schema, f, indent=4)
        f.close()
    print()

# python2json()
# json2python('IFC4x1')
