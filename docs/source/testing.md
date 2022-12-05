# Testing

todo

## Unit Testing

## Integration Testing

## Regression Testing

## Run Tests Local

To test mapping between IFC and our meta structure
[elements](concepts/elements.md) as well as for Integration Testing
we need to load IFC files into our tool. These IFC files can be quite big. To
keep the size of this repository as slim as possible we only integrate very few
examples into the repository itself. The majority of the IFC files is stored 
external and is downloaded for [CI/CD](CI/CD) processes during the test run. If
you want to run the tests local, please download the files to your local 
repository. There are 3 folder that you will need, the following tables gives 
you the links, and the path to put them.

| **Link**                                                                       | **Target Path**                                   |
|--------------------------------------------------------------------------------|---------------------------------------------------|
| [BPS IFC Files](https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download)      | /bim2sim-coding/test/TestModels/BPS               |
| [HVAC IFC Files](https://rwth-aachen.sciebo.de/s/R6K1H5Z9fiB3EoB/download)     | /bim2sim-coding/test/TestModels/HVAC              |
| [Regression Results](https://rwth-aachen.sciebo.de/s/SAUQQgvwqeS96ix/download) | /bim2sim-coding/bim2sim/assets/regression_results |

## CI/CD


