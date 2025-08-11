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
sure that you have those resources in your local repository, run the following.

But when an error because of the already existing of the folder 'test/resources'
occurs, please delete this folder. Be careful, don't delete anything else.


```
linux/macOS: 
rm -r [pathToRepoBim2sim]/test/resources
windows:
rd /s [pathToRepoBim2sim]\test\resources

git submodule update --init --recursive
```
## Update test resources
If test resources needs to be updated, please follow the following procedure:

### [Test Resources Repository](https://github.com/BIM2SIM/bim2sim-test-resources)
1. Create a branch `update_test_resources`
2. In this branch update the test resources as required
3. Push the branch with the changes to the remote repository
### [Main bim2sim Repository](https://github.com/BIM2SIM/bim2sim)
4. Create a branch called `update_resources_submodule` from the current `development` branch
5. Checkout this branch on your local device and perform the following commands in the root path:
   1. open the .gitmodules file in the room of bim2sim and adjust the branch to the new test-resources branch (in this case `update_test_resources`)
   2. in bim2sim root directory run `git submodule sync` and afterwards `git submodule update --recursive --remote` (update submodule according to changes in .gitmodules file)
   3. `git add .\test\resources .gitmodules` (add the changes)
   4. `git commit -m "Update submodule of test resources"`
   5. `git push`
6. Wait for the pipeline to run through on your branch, this makes sure that the code runs with the new test resources without issues
7. If the pipeline with all tests passes, perform the following steps, otherwise fix the issues before you continue
### [Test Resources Repository](https://github.com/BIM2SIM/bim2sim-test-resources)
8. Create a Pull Request (PR) from `update_test_resources` into the `main` branch 
9. Link the succeeded pipeline in this PR and assign a reviewer
10. When review finished, merge the PR
### [Main bim2sim Repository](https://github.com/BIM2SIM/bim2sim)
11. Repeat the same steps as under step 6, but this time in step 5.1 use `main` instead `update_test_resources` as branch name
12. again wait for the pipeline to succeed
13. Create a PR to merge `update_resources_submodule` branch in the `main` branch and assign a reviewer
14. If pipeline has passed (what it should) and review is approved merge the PR
