"""Generate mermaid code via templetes respectively template-functions."""
# TEASER example imports

from bim2sim.plugins import load_plugin


def generate_task_code(taskname: str = "bim2simtask",
                       module_path: str = "module_patH",
                       reads: str = "readS",
                       touches: str = "toucheS",
                       doc: str = "docstrinG") -> str:
    """Generate mermaid code representing a bim2sim task.

    WIP: so the some structure stuff like tpye of diagram is added here, later
    it should move to def generate_diagram".

    Args:
      taskname: name of the bim2sim taks of the plugin, no space allowed
      module_path: path to the module/task definition
      reads: input the task uses (from the central state)
      touches: output the task reply (to the central state)

    Returns:
      Mermaid code of an task.
      WIP: check how to pipe. now it will printed

    Attention:
      - Tasknames should be unique, when merge different mermaid
        templates instances.

    """
    code_template = """
subgraph "task {taskname}"
t{taskname}["{module_path} {taskname}"]
subgraph reads & touches
 direction LR
 r{taskname}[ {reads} ]
 to{taskname}[ {touches} ]
end
ext{taskname}(" {doc} " )
end
    """
    code = code_template.format(taskname=taskname, module_path=module_path,
                                reads=reads, touches=touches, doc=doc)

    return code


def generate_diagram(plugin_infos: list, tasks_infos: list) -> str:
    """Print mermaid code of the whole task structure of one bim2sim plugin.

    The plugin structure is fix: next plugin is connected to the plugin before.

    Args:
      plugin_infos: information about the whole plugin [name, module, .. ]
      tasks: list of infos of tasks [{name, reads, touches ...}, {...}]
    """
    # header of the mermaid diagram
    plugin_name = plugin_infos['name']
    digram_header = """---
title: plugin {plugin_name}
---
flowchart TB
    """
    mermaid_code = digram_header.format(plugin_name=plugin_name)

    # elements of the mermaid diagram
    for task_infos in tasks_infos:
        task_code = generate_task_code(taskname=task_infos['name'],
                                       module_path=task_infos['module_path'],
                                       reads=task_infos['reads'],
                                       touches=task_infos['touches'],
                                       doc=task_infos['doc_first_sentence'])
        mermaid_code = mermaid_code + task_code

    # connections of the elements of the mermaid diagram
    code_connection_templ = """t{taskname_from} --> t{taskname_to} \n"""

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

        module = task.__module__
        module_list = str(module).split('.')
        path_list = module_list[:-1]
        path_list_arrow = [str(item) + ' > ' for item in path_list]
        path_list_str = ''.join(path_list_arrow)

        info = {'name': name, 'reads': reads, 'touches': touches,
                'doc': doc, 'doc_first_sentence': doc_first_sentence,
                'module_path': path_list_str}
        task_infos.append(info)
    return task_infos

def get_dependencies():
    pass


def generate_example_plugin_structure_fig():
    """Generate a figure of the task structure of TEASER plugin.

    The environment of the TEASER plugin is needed.
    """

    plugin = load_plugin('teaser')
    plugin_infos = get_plugin_infos(plugin)
    task_infos = get_task_infos(plugin)
    path_name = ("/home/cudok/Documents/10_Git/bim2sim/docs/source/img/" +
                 "dynamic/plugindiagram/test_template_code.mmd")
    write_file(generate_diagram(plugin_infos, task_infos),
               path_name)


if __name__ == '__main__':
    # Examples 1
    # setup simple plugin, here TEASER
    generate_example_plugin_structure_fig()
