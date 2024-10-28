# Testing

The ´bim2sim´ repository includes a multi-stage testing setup to ensure 
its functionality. 

## Unit Testing
Unit tests are used for testing individual functions. These tests can be 
executed very quickly and are not computationally intensive.

## Integration Testing
Integration tests are used within the individual plugins for testing the 
functionality of the package with different IFC models. These tests deal with
large IFC models and are therefore take some time for computation, so you may 
need to wait a few minutes until these tests are done. These tests can be 
used to test different simulation setups on the indidual IFC models. Depending
on your integration test setup, it may include a full year run of your 
simulation. Here, you cannot easily tell if the changes in your coding have 
produced any changes in the results (use Regression Testing for this), but 
you can test if full simulation run works at all. 

## Regression Testing
Regression tests are used for quality assurance when developing new features. 
Here, the simulation results of selected IFC models are compared to previous 
simulation results. If the simulated results do not match with the regression 
results, the test fails. This forces the developer to have a closer look at the
changes in the results, such that the developer has to decide whether to update
the new implementation or the regression results.

## Run Tests Local
To test mapping between IFC and our meta structure
[elements](elements_structure) as well as for Integration Testing
we need to load IFC files into our tool. These IFC files can be quite big. To
keep the size of this repository as slim as possible we put the test resources
into an additional repository, which is included here as a submodule. To make 
sure that you have those resources in your local repository, run:


``` 
git submodule update --init --recursive
```

## CI/CD


