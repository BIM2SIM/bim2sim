# Visualization of bim2sim plugin structure 

To get an overview about the structure of the bim2sim plugins for all plugins
you can find a visualization (eg. [visualization of the plugin
template](structure_template)). This visualization is semi automatic generated. Following the workflow to generated a plugin visualization is explained by the example plugin example.

Change into the folder plugindiagram:

```shell
cd bim2sim-Root/bim2sim/docs/utilities/plugindiagram
```

Open the file template_mermaid.py with a text editor and adapt the path variable
reading the plugin you like to visualize template_mermaid.py.

Run the python script to generate the mermaid code ([mermaid](https://mermaid.js.org/))

```shell
python3 template_mermaid.py
```

Copy the content of the generated file into the markdown file at the position
you like to include the visualization of the plugin. The documentation creator
([Sphinx](https://www.sphinx-doc.org)) needs following indicator surrunding the
mermaid code:

```markdown
```mermaid
mermaid code ```
```
The result can be checked by copy the content of the generated file into: [mermid live](https://mermaid.live). 
