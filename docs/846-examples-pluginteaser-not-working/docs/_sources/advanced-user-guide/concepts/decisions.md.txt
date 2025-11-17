(decision_concept)=

# Decisions

Decisions are used for missing or unclear information in the IFC which needs to
be validated or entered by the user. There are different kind of decisions
for lists to select from, just bare real inputs etc. In `bim2sim` we use direct
input via console for this. But we are also developing a Webtool with proper
frontend that will allow to make the decisions with direct usage of an inbuilt
viewer.

Made decisions can be stored between projects to make the usage more efficient.

# Yielding

As decisions can pop up every time during a project run of `bim2sim` we yield
them throughout the whole process. This might make it hard to understand but
is needed to allow the flexibility to trigger decisions every time we come
across uncertainties in the IFC. For this reason the function that basically 
coordinates the whole project run if you use the normal 
[Decisionhandler](Decisionhandler) is the `handle()` function which iterates 
over all decisions yielded from the process and passes down the answers to them.

For more detailed information please have a look at the code documentation
of [decisionhandler](decisionhandler) and [decision](decision).
