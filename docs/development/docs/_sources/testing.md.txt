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
keep the size of this repository as slim as possible we only integrate very few
examples into the repository itself. The majority of the IFC files is stored 
external and is downloaded for [CI/CD](CI/CD) processes during the test run. If
you want to run the tests local, please download the files to your local 
repository. You can use our download script for this, by running the following 
commands while you are the repository root directory:

```python 
python ./test/resources/download_test_resources.py --domain=<domain_name>
```
You can use the following arguments:

| **args**          | **values**  | **description**                                   |
|-------------------|-------------|---------------------------------------------------|
| `domain`          | `arch`      | Download arch domain test resources               |
|                   | `hydraulic` | Download hydraulic domain test resources          |
| `with_regression` | `bool`      | Include regression reults in download             | m
| `force_new`       | `bool`      | Force overwrite of potential existing resrouces   | m


If you want to run the TEASER regression tests under Windows, you need to add
path of dymola executable to the PATH environment variable (requirement of
BuildingsPy) 
## CI/CD


