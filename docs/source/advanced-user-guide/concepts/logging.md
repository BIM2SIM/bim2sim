 # Logging

Logging in `bim2sim` distinguishes between three kinds of logging:
- Messages for users
- Messages for developers
- Messages for IFC (tool) creators

> WARNING:
> 
> To handle `Project` specific log messages, `Project` related logging Handlers get filtered by the thread name of the `Project`. 
> Having multiple `Project` elements in the same Thread may result in messy log messages.



## User logging
By default, the user logger writes to stdout. You can change the user logger per `Project` by setting it on a `Project` instance:

 ```python
import logging
from bim2sim import Project

project = Project(...)
my_stream_handler = logging.StreamHandler()
project.set_user_logging_handler(my_stream_handler)
```

## Developer logging

By default, the dev logger dumps its messages to a `bim2sim.log` file in cwd. 
Feel free to change handlers for the bim2sim logger (name='bim2sim'). 
> NOTE:
> 
> Each project adds additional filtered handler to the bim2sim logger to distinguish between project specific log messages. 
> Don't interfere with them.

If you add custom logging Handlers, consider adding an [AudienceFilter](AudienceFilter) `AudienceFilter(audience=None)` 
to prevent messages from user loggers.


## IFC Quality logging

The IFC Quality logger (name='bim2sim.QualityReport') dumps its messages in each `Project`s `\log` directory.