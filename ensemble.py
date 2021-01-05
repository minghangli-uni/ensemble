#!/usr/bin/env python
"""

Generate ensemble of ACCESS-OM2 experiments.

Latest version: https://github.com/aekiss/ensemble
Author: Andrew Kiss https://github.com/aekiss
Apache 2.0 License http://www.apache.org/licenses/LICENSE-2.0.txt
"""

from __future__ import print_function
# import sys
import os
import subprocess
import git
import numpy as np
# import glob  # BUG: fails if payu module loaded - some sort of module clash with re
# import itertools
try:
    import yaml
    import f90nml  # from https://f90nml.readthedocs.io/en/latest/
except ImportError:  # BUG: don't get this exception if payu module loaded, even if on python 2.6.6
    print('\nFatal error: modules not available.')
    print('On NCI, do the following and try again:')
    print('   module use /g/data/hh5/public/modules; module load conda/analysis3\n')
    raise


def ensemble(yamlfile='ensemble.yaml'):
    '''
    Create an ensemble by varying only one parameter at a time.
    '''
    # could loop over all values of all parameters using `itertools.product` - see https://stackoverflow.com/questions/1280667/in-python-is-there-an-easier-way-to-write-6-nested-for-loops
    indata = yaml.load(open(yamlfile, 'r'), Loader=yaml.SafeLoader)
    template = indata['template']
    templaterepo = git.Repo(template)
    print(indata)
    for fname, nmls in indata['namelists'].items():
        for group, names in nmls.items():
            for name, values in names.items():
                print(fname, group, name, values)
                for v in values:
                    expname = '_'.join([template, name, str(v)])
                    if os.path.exists(expname):
                        print(expname, 'exists; skipping')
                    else:
                        print('creating', expname)
                        exprepo = templaterepo.clone(expname)
                        # TODO: fix up remotes, set up new branch
                        fpath = os.path.join(expname, fname)
                        if set(fname, group, name) == set('ice/cice_in.nml', 'dynamics_nml', 'turning_angle'):
                            f90nml.patch(fpath, {group: {'cosw': np.cos(v * np.pi / 180. )}})
                            f90nml.patch(fpath, {group: {'sinw': np.sin(v * np.pi / 180. )}})
                        else:
                            f90nml.patch(fpath, {group: {name: v}}) #, fpath)
                        # TODO: commit changes
                        
                        # with open(fname) as nml_file:
                        #     nml = f90nml.read(nml_file)
                        # 
                        #     patch_nml = {group: {name: v}}
                        #     nml[group][name] = v
                        #     nml.write(nml_file)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=
        'Generate ensemble of ACCESS-OM2 experiments.\
        Latest version and help: https://github.com/aekiss/ensemble')
    parser.add_argument('yamlfile', metavar='yamlfile', type=str, nargs='?',
                        default='ensemble.yaml',
                        help='YAML file specifying parameter values to use for ensemble; default is ensemble.yaml')
    args = parser.parse_args()
    yamlfile = vars(args)['yamlfile']
    ensemble(yamlfile)
