# CI information

This documents may be used to document how to maintain the CI pipelines of `bim2sim`.
If you work on these images, name your branch something that contain "image_testing", so the jobs are run in your branch, as well.
During https://github.com/BIM2SIM/bim2sim/pull/837, the image-structure was changed as follows:


## Images used to test `bim2sim` in CI
Those images (Dockerfile, Dymola.Dockerfile and EnergyPlus.Dockerfile) get build in 
the build stage for py 3.10 and 3.11 WITHOUT `bim2sim` installed, 
as is common in CI testing. 
Only the OCC version is installed to speed up CI testing.
The previous separation between main and dev images was removed. 

## Base-Image EnergyPlus
Installing EnergyPlus fails in CI in various ways I tried, 
most likely due to network issues on our or githubs side. 
Thus, the new EnergyPlusBase.Dockerfile must be build and pushed manually if a new EnergyPlus version is going to be used. 
As this is a rare event, we think the overhead is acceptable.

To build the image, clone `bim2sim` on a machine with docker installed and run the script below.
```bash
docker login registry.git.rwth-aachen.de
docker build -f ci/EnergyPlusBase.Dockerfile -t registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:energyplus9.4.0 .
docker push registry.git.rwth-aachen.de/ebc/ebc_all/github_ci/bim2sim/bim2sim:energyplus9.4.0
```
If on linux, put `sudo` in front of every line.

If you increase the version, make sure to 
- change the Dockerfiles `ARGs` appropriately
- change the tag `energyplus9.4.0` in the script above
- change the tags in the `ci/builds_releases.gitlab-ci.yml` jobs, e.g. `build:energyplus-py3.11:`.


## Release images for plugins
The plugin images are now at a release stage to clearly indicate 
that those images are not used during CI, only for later usage.

As multiple images are build and pushed in parallel, the kubernetes runner sometimes fails. 
If this is the case, just go to the mirrored `bim2sim` in gitlab and re-trigger the job.
