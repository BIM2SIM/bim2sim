(tasks_concept)=

# Tasks

## What are Tasks for?

Tasks are a class based concept and hold the main functionality of `bim2sim` 
methods. They are implemented by inherting from the [ITask](ITask) 
(Interactive Task) class. Every task should have a specific goal to reach, like
the loading of a IFC file, the export of a simulation model or the creation of a
 graph network to analyze the HVAC network topology. To keep the Tasks reusable
and modular the goals of a task should not be too broad.

## How are Tasks managed? The Playground

The tasks of a project run are managed by the [Playground](Playground) class.
The Playground allows two ways to run tasks:

1. `Default`
2. `Interactive`

In default mode all `default_tasks` of the selected Plugin are executed in
sequence. In interactive mode the user will be prompted will all possible
tasks
to execute and can choose one. After the task is done, the user gets again
all possible tasks to execute next. To make sure that only tasks are executed in
sequence which make sense and are implemented, every [ITask](ITask) has two
tuples: `reads` and `touches`. `reads` defines which variables this task needs 
as input and `touches` defines what the task returns. Every task must also hold 
a `run()` method which the Playground runs.

## Special variables for Tasks
As mentioned Tasks can have `reads` and `touches`, which define the input and 
output of every task. Two of those variables are:

* `elements`
* `graph`

`elements` holds a dictionary with all [elements](elements) that are currently
existing at runtime. `graph` holds the [HvacGraph](HvacGraph) and is therefore
only existing for the HVAC [plugins](plugins). These two variables are stored 
and hold up2date inside the [Playground](Playground) instance. The `graph` variable
is only available in HVAC related plugins.

## Writing your own Task
To write your own task go create a new file inside `bim2sim/task/<domain>` and 
fill like this 

```python
from bim2sim.task.base import ITask


class AmazingTask(ITask):
   reads = (input_1, )
   touches = (output1,)
   
   def run(self, workflow):
      self.logger.info("Starting my amazing task")
      
      output_1 = self.amazing_function()
      
      return output_1
   
   
   def amazing_function(self):
      amazing_result = 42
      return amazing_result
```
