"""Generate mermaid code via templetes respectively template-functions."""
# TEASER example imports

from bim2sim.plugins import load_plugin
import textwrap
from pathlib import Path


def split_string_50(text, max_width=50):
    """Split the text after max. 50 characters."""
    wraped_text = textwrap.wrap(text, max_width)
    wraped_text = '\n'.join(wraped_text)
    return wraped_text


def generate_task_code(taskname: str = "bim2simtask",
                       module_path: str = "module_patH",
                       reads: str = "readS",
                       touches: str = "toucheS",
                       doc: str = "docstrinG",
                       reads_touches_vis: bool = True) -> str:
    """Generate mermaid code representing a bim2sim task.

    WIP: so the some structure stuff like tpye of diagram is added here, later
    it should move to def generate_diagram".

    Args:
      taskname: name of the bim2sim taks of the plugin, no space allowed
      module_path: path to the module/task definition
      reads: input the task uses (from the central state)
      touches: output the task reply (to the central state)
      reads_touches_vis: enable/disable the subgraph showing
                         the reads and touches

    Returns:
      Mermaid code of an task.
      WIP: check how to pipe. now it will printed

    Attention:
      - Tasknames should be unique, when merge different mermaid
        templates instances.

    """
    # optional reads and touches subgraph, must defined before the templete
    if reads_touches_vis:
        code_reads_touches = """
state{taskname}[("state
 (reads/touches)")]
    """
        code_rt_state = code_reads_touches.format(
            taskname=taskname)
        code_rt = code_rt_state
        # check for reads
        if reads != ' - ':
            code_rt_reads = """
state{taskname} -- {reads} --> t{taskname}
"""
            code_rt_reads = code_rt_reads.format(
                reads=reads,
                taskname=taskname)
            code_rt = code_rt + code_rt_reads
        # check for touches
        if touches != ' - ':
            code_rt_touches = """
t{taskname} -- {touches} --> state{taskname}
"""
            code_rt_touches = code_rt_touches.format(
                touches=touches,
                taskname=taskname)
            code_rt = code_rt + code_rt_touches
        else:
            code_rt_touches = """direction RL"""
            code_rt = code_rt + code_rt_touches
    else:
        code_rt = ""

    code_template = """
subgraph task{taskname}["task {taskname}"]
 subgraph "" \n
  t{taskname}["{module_path} \n {taskname}"]
  ext{taskname}(" {doc} " )
 end
{code_rt}
end
    """
    code = code_template.format(taskname=taskname,
                                module_path=module_path,
                                doc=doc,
                                code_rt=code_rt)
    return code


def generate_diagram(plugin_infos: list, tasks_infos: list,
                     central_state: bool = False) -> str:
    """Print mermaid code of the whole task structure of one bim2sim plugin.

    The plugin structure is fix: next plugin is connected to the plugin before.

    Args:
      plugin_infos: information about the whole plugin [name, module, .. ]
      tasks: list of infos of tasks [{name, reads, touches ...}, {...}]
      central_state: bool
         True: reads and touches connected the the central state
         False: reads and touches includes in task element
    """
    # header of the mermaid diagram
    plugin_name = plugin_infos['name']
    digram_header = """---
title: plugin {plugin_name}
---
flowchart TB
    """
    mermaid_code = digram_header.format(plugin_name=plugin_name)

    # task elements of the mermaid diagram
    if central_state:

        state_code = """
state[("state:
project
data storage")]
"""
        mermaid_code = mermaid_code + state_code

        for task_infos in tasks_infos:
            taskname = task_infos['name']
            reads = task_infos['reads']
            touches = task_infos['touches']
            task_code = generate_task_code(taskname=taskname,
                                           module_path=task_infos['module_path'],
                                           doc=task_infos['doc_first_sentence'],
                                           reads_touches_vis=False)
            mermaid_code = mermaid_code + task_code
            # connetion reads and touches of the task to the state
            code_connection_state = ''
            if touches != ' - ':
                code_connection_state_touches = """
t{taskname} -- {touches} --> state\n"""
                code_connection_state_touches = code_connection_state_touches.format(
                    taskname=taskname,
                    touches=touches)
                code_connection_state += code_connection_state_touches

            if reads != ' - ':
                code_connection_state_reads = """
state -- {reads} --> t{taskname} \n"""
                code_connection_state_reads = code_connection_state_reads.format(
                    taskname=taskname,
                    reads=reads)
                code_connection_state += code_connection_state_reads

            mermaid_code = mermaid_code + code_connection_state
    # if every task has their own state visualisation
    else:
        for task_infos in tasks_infos:
            task_code = generate_task_code(taskname=task_infos['name'],
                                           module_path=task_infos['module_path'],
                                           reads=task_infos['reads'],
                                           touches=task_infos['touches'],
                                           doc=task_infos['doc_first_sentence'],
                                           reads_touches_vis=True)
            mermaid_code = mermaid_code + task_code
    # state element

    # connections of the task elements of the mermaid diagram
    code_connection_templ = """task{taskname_from} --> task{taskname_to} \n"""

    code_connections = ''
    for i in range(len(tasks_infos) - 1):
        code_connection = code_connection_templ.format(
            taskname_from=tasks_infos[i]['name'],
            taskname_to=tasks_infos[i+1]['name'])
        code_connections = code_connections + code_connection

    mermaid_code = mermaid_code + code_connections

    return mermaid_code


def write_file(mermaid_code: str, filename: str):
    """Create a file including mermaid code.

    Args:
      mermaid_code: complete mermaid code which represents the diagram
      filename: name of the source code file of the figure
    """
    with open(filename, "w") as f:
        f.write(mermaid_code)


def get_plugin_infos(plugin) -> str:
    """Get plugin infos, like name.

    Args:
      project: Project object

    Return:
      name of the plugin
      module the plugin is integrated
    """
    plugin_name = plugin.name
    plugin_module = plugin.__module__

    plugin_info = {'name': plugin_name, 'module': plugin_module}
    return plugin_info


def get_task_infos(plugin) -> list:
    """Get information of the task of the plugin.

    Args:
      project: Project object

    Return:
      list of task names
    """
    tasks = plugin.default_tasks
    task_infos = []
    for task in tasks:
        name = task.__name__

        if len(task.reads) == 0:
            reads = ' - '
        else:
            reads = ', '.join(task.reads)

        if len(task.touches) == 0:
            touches = ' - '
        else:
            touches = ', '.join(task.touches)

        doc = task.__doc__
        doc_first_sentence = str(doc).replace("\n", "").replace("    ", " ")
        doc_first_sentence = doc_first_sentence.split(".")[0]
        doc_first_sentence = doc_first_sentence + '.'
        doc_first_sentence = split_string_50(doc_first_sentence)

        module = task.__module__
        module_list = str(module).split('.')
        path_list = module_list[:-1]
        path_list_arrow = [str(item) + ' > ' for item in path_list]
        # add line break after third item
        if len(path_list_arrow) > 3:
            path_list_arrow[2] = str(path_list_arrow[2]) + '\n'
        # join list items into a string
        path_list_str = ''.join(path_list_arrow)

        info = {'name': name, 'reads': reads, 'touches': touches,
                'doc': doc, 'doc_first_sentence': doc_first_sentence,
                'module_path': path_list_str}
        task_infos.append(info)
    return task_infos


def generate_plugin_structure_fig(path_file: str,
                                  plugin_name: str,
                                  central_state: bool = False):
    """Generate mermaid code visulzing the task structure of a plugin.

    This generated mermaid code will written into a file (path_name).
    To generate a figure, pls use:
      - https://mermaid.live
      - mmdc (must installed on your system)
        - https://github.com/mermaid-js/mermaid-cli
        - eg. mmdc -i input.mmd -o output.png -t dark -b transparent
      - code can past into github issues (add ```mermaid  code  ```)
      - code can used in Sphinx docuemtation (check for howtos)
      - code can used in org-mode of emacs (check for howtos)
    Args:
      path_file: absolute path to the file (saves mermaid code)
      plugin_name: name of the choosen plugin - string
                   default value: 'teaser'
      central_state: bool
         True: reads and touches connected the the central state
         False: reads and touches includes in task element

    Return:
      nothing, code is witten into the defined file

    """
    try:
        plugin = load_plugin(plugin_name)
        plugin_infos = get_plugin_infos(plugin)
        task_infos = get_task_infos(plugin)
        path_name = Path(path_file)  # should import the path for all os
        write_file(generate_diagram(plugin_infos, task_infos,
                                    central_state=central_state),
                   path_name)
        print('run successful: \nmermaid code was save to:\n'
              + str(path_name))

    except ModuleNotFoundError as e:
        print(e)
        print("Pls, choose a plugin_name like: \n"
              + " - 'teaser'\n"
              + " - 'energyplus'\n")

    except FileNotFoundError as e:
        print(e)
        print("Pls choose an existing (absolut) path.")
        print("At the end of the path add the filename.")


if __name__ == '__main__':
    # Examples 1
    # setup simple plugin, here TEASER
    path_name = ("/home/cudok/Documents/10_Git/bim2sim/docs/source/img/" +
                 "dynamic/plugindiagram/TEASER_structure_central_state.mmd")
    generate_plugin_structure_fig(path_name,
                                  plugin_name='teaser',
                                  central_state=True)

    # Examples 2
    # setup simple plugin, here TEASER not central state
    # visualisation
    path_name = ("/home/cudok/Documents/10_Git/bim2sim/docs/source/img/" +
                 "dynamic/plugindiagram/TEASER_structure_decentral_state.mmd")
    generate_plugin_structure_fig(path_name,
                                  plugin_name='teaser',
                                  central_state=False)

    # Examples 3
    # setup simple plugin, here EnergyPluss not central state
    # visualisation
    path_name = ("/home/cudok/Documents/10_Git/bim2sim/docs/source/img/" +
                 "dynamic/plugindiagram/EP_structure_decentral_state.mmd")
    generate_plugin_structure_fig(path_name,
                                  plugin_name='energyplus',
                                  central_state=False)
