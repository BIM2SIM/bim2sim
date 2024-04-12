"""Generate mermaid code via templetes respectively template-functions."""
# TEASER example imports

from bim2sim.plugins import load_plugin

def generate_task_code(taskname: str = "bim2simtask",
              task_belongs: str = "belongsBim2sim") -> str:
    """Generate mermaid code representing a bim2sim task.

    WIP: so the some structure stuff like tpye of diagram is added here, later
    it should move to def generate_diagram".

    Args:
      taskname: name of the bim2sim taks of the plugin, no space allowed
      task_belongs: submodul the task belongs to of the bim2sim project,
                    no space allowed

    Returns:
      Mermaid code of an task.
      WIP: check how to pipe. now it will printed

    Attention:
      - Tasknames should be unique, when merge different mermaid
        templates instances.

    """
    code_template = """
subgraph "task {taskname}"
t{taskname}["{task_belongs}.{taskname}"]
subgraph reads & touches
 direction LR
 r{taskname}[/"None"/]
 to{taskname}[\"ifc_files"\]
end
ext{taskname}("reads the IFC files of one or multiple domains inside bim2sim")
end
    """
    code = code_template.format(taskname=taskname, task_belongs=task_belongs)

    return code


def generate_diagram(plugin_name: str, tasks_infos: list) -> str:
    """Print mermaid code of the whole task structure of one bim2sim plugin.

    The plugin structure is fix: next plugin is connected to the plugin before.

    Args:
      plugin_name: name of the whole plugin
      tasks: list of infos of tasks [{name, reads, touches ...}, {...}]
    """
    digram_header = """---
title: plugin {plugin_name}
---
flowchart TB
    """
    mermaid_code = digram_header.format(plugin_name=plugin_name)
    for task_infos in tasks_infos:
        task_code = generate_task_code(task_infos['name'])
        mermaid_code = mermaid_code + task_code

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
        reads = task.reads
        touches = task.touches
        doc = task.__doc__
        module = task.__module__
        info = {'name': name, 'reads': 'reads', 'touches': touches,
                'doc': doc, 'module': module}
        task_infos.append(info)
    return task_infos

def get_dependencies():
    pass


def generate_example_plugin_structure_fig():
    """Generate a figure of the task structure of TEASER plugin.

    The environment of the TEASER plugin is needed.
    """

    plugin = load_plugin('teaser')
    task_infos = get_task_infos(plugin)
    path_name = ("/home/cudok/Documents/10_Git/bim2sim/docs/source/img/" +
                 "dynamic/plugindiagram/test_template_code.mmd")
    write_file(generate_diagram(get_plugin_infos(plugin)['name'], task_infos),
               path_name)


if __name__ == '__main__':
    # Examples 1
    # setup simple plugin, here TEASER
    generate_example_plugin_structure_fig()
