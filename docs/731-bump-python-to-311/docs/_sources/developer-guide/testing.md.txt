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

## Update test resources
If test resources needs to be updated, please follow the following procedure:
1. Create a branch in the [test resources repository](https://github.com/BIM2SIM/bim2sim-test-resources)
2. In this branch change the test resources as required
3. Push the changes to the remote repository 
4. Create a Pull Request into the main branch for the created branch
5. In the [main bim2sim repository](https://github.com/BIM2SIM/bim2sim), create a branch called 'upgrade_test_resources'
6. Checkout this branch on your local device and perform the following commands in the root path:
   1. `cd test/resources` (Go into the submodule directory)
   2. `git pull origin <name of branch you created in test resources repo>` (Pull the latest changes)
   3. `cd ../..` (Go back to parent repo)
   4. `git add test/resources` (add the changes)
   5. `git commit -m "Update submodule of test resources"`
   6. `git push`
7. Then wait for the pipeline to run through on your branch
8. If the pipeline with all tests passes, perform the following steps, otherwise fix the issues before you continue
9. Link the succeeded pipeline in the pull request in the test resources repository and assign a reviewer
10. When review finished, merge the PR
11. Now go back to the main repository and perform the same steps as under step 6, but this time in step 6.ii you `main` as branch name
12. again wait for the pipeline to succeed
13. Create a pull request for the branch in the main bim2sim repository and assign a reviewer
14. If pipeline has passed (what it should) merge and you are done
