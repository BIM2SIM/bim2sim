"""Testing to generate mermaid code via templetes/template-functions."""


def task_code(taskname: str = "bim2simtask",
              task_belongs: str = "belongsBim2sim"):
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


def generate_diagram(tasks: list):
    """Print mermaid code of the whole task structure of one bim2sim plugin.

    The plugin structure is fix: next plugin is connected to the plugin before.

    Args:
      tasks: list of tasks (mermaid code strings)
    """
    digram_type = "flowchart TB"

    mermaid_code = digram_type
    for task_code in tasks:
        mermaid_code = mermaid_code + task_code

    return mermaid_code


def write_file(mermaid_code: str, filename: str):
    """Create a file including mermaid code."""
    with open(filename, "w") as f:
        f.write(mermaid_code)


if __name__ == '__main__':
    # Examples
    print(task_code())
    write_file(generate_diagram([task_code("LooadIFC"),
                                 task_code("LooadIFC1"),
                                 task_code("LooadIFC5")
                                ]),
               "test_template_code.mmd")
