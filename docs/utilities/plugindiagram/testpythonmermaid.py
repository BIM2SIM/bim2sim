"""Testing the usablity of python_mermaid for bim2sim."""

from python_mermaid.diagram import (
    MermaidDiagram,
    Node,
    Link
)
# nodes
task1 = Node("Task 1")
task2 = Node("Task 2")

nodes = [task1, task2]

# links
links = [
    Link(task1, task2)
]


diagram = MermaidDiagram(
    title="test plot",
    nodes=nodes,
    links=links,
    type="flowchart",
    orientation="top to bottom"
)

# subgraph "task LoadIFC"
#   tli["common.LoadIFC"]
#   subgraph reads & touches
#     direction LR
#     rli[/"None"/]
#     toli[\"ifc_files"\]
#   end
#   extli("reads the IFC files of one or
#          multiple domains inside bim2sim")
# end
print(diagram)
