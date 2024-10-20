(docker_structure)=
# Docker image structure
As we implemented different plugins for each simulation we provide different
docker images for. To simplify development we split images into `env.`
and normal images, while `.env` only holds the needed requirements and the
normal images holds the code as well. The structure is explained below:

# TODO REWORK WITH NEW MICROMAMBA STRUCTURE
```{mermaid}
graph TD;

	A("
		<b>envBase.Dockerfile </b> 
		<li> conda environment 
		<li>base requirements  
		<li>IfcOpenShell (python) 
		<li> Python OCC") 
	--> B[<b>envBase Image</b>];
	
	B --> C("
		<b>envTEASER Image</b> 
		<li> teaser specific requirements") 
	--> D["<b>environment:teaser Image</b>"];
	
	B --> E("
		<b>envEP.Dockerfile</b>
		<li> energyplus specific requirements 
		<li> EnergyPlus v9.4.0")
	--> F["<b>environment:energyplus Image</b>"];
	
	B --> G("
		<b>envCFD.Dockerfile</b> 
		<li> OpenCascade 
		<li> IfcOpenShell (c) 
		<li> CFD specific requirements")
	--> H["<b>environment:cfd Image</b>"];

	B --> I("
		<b>envAixlib.Dockerfile</b> 
		<li> OpenCascade 
		<li> IfcOpenShell (c) 
		<li> CFD specific requirements")
	--> J["<b>environment:aixlib Image</b>"];

	D --> K("
		<b>teaser.Dockerfile")
	--> L["<b>tool:teaser Image</b>"]

	F --> M("
		<b>energyplus.Dockerfile")
	--> N["<b>tool:energyplus Image</b>"]

	H --> O("
		<b>cfd.Dockerfile")
	--> P["<b>tool:cfd Image</b>"]

	J --> Q("
		<b>aixlib.Dockerfile")
	--> R["<b>tool:aixlib Image</b>"]


    J ----> S("
		<b>total.Dockerfile</b>
		<li> all requirements + Code")
	--> T["<b>tool:total Image</b>"]
	
    D ----> S
    F ----> S
    H ----> S


    
    style A text-align:left
    style C text-align:left
    style E text-align:left
    style G text-align:left
    style I text-align:left
```
