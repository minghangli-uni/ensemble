# Ensemble
Generate and run an ensemble of [ACCESS-OM2](https://github.com/COSIMA/access-om2) experiments by varying namelist parameters.

## Downloading
This repo uses submodules, so should be downloaded with
```
git clone --recursive https://github.com/aekiss/ensemble.git
```
It also requires [payu](https://github.com/payu-org/payu) unless the `--test` option is used.

## Usage
1. Edit `ensemble.yaml` to set:
    - `template`: relative path to control experiment configuration directory.
    - `startfrom`: restart number in `template`/archive to use as initial condition for perturbations (or `rest` to start from rest).
    - `nruns`: total number of output directories to generate for each ensemble member.
    - `namelists`: specify lists of perturbation values to use.
        - These are specified by namelist file path, group, variable name and an array of values.
        - Any variable name in any namelist in `template` may be used.
        - Ice turning angle should be specified by the special name `turning_angle` (with values in degrees), not `cosw` and `sinw`; this ensures that consistent `cosw` and `sinw` values will be used.
2. Run `./ensemble.py`
   This will
    - First set up a configuration directory for each perturbation that doesn't already have one.
        - Perturbation directories are based on the latest commit in the current git branch of  `template` (NB: you must commit any changes in `template` that you want to use for the perturbation runs).
        - Each perturbation has a single namelist variable altered (or `cosw` and `sinw` if `turning_angle` is used).
        - The perturbation directory name includes the perturbed variable and its value, and is also used for the git branch, sync directory, and job name. `metadata.yaml` is updated to include information on the perturbation used.
        - Existing perturbation directories are not altered, so `ensemble.py` can be re-run with additional perturbations.
        - Perturbations that are identical to `template` are ignored.
    - Then do `payu sweep; payu run -n X` for each existing and new perturbation directory, where `X` is the number of additional runs required to produce `nruns` output directories in total for each perturbation. Thus additional runs of an existing ensemble can be achieved simply by increasing `nruns` and running `./ensemble.py` again. Any newly-added perturbations (or crashed runs) will be run as many times as needed to match the number of outputs from the others.

`ensemble.py` has some command-line options:
```
% ./ensemble.py -h
usage: ensemble.py [-h] [--test] [yamlfile]

Generate ensemble of ACCESS-OM2 experiments. Latest version and help:
https://github.com/aekiss/ensemble

positional arguments:
  yamlfile    YAML file specifying parameter values to use for ensemble;
              default is ensemble.yaml

optional arguments:
  -h, --help  show this help message and exit
  --test      for testing a fresh clone, with no payu dependency
```