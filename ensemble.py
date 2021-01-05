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
import shutil
# import subprocess
import git
import numpy as np
import glob  # BUG: fails if payu module loaded - some sort of module clash with re
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
    # alternatively, could loop over all values of all parameters using `itertools.product` - see https://stackoverflow.com/questions/1280667/in-python-is-there-an-easier-way-to-write-6-nested-for-loops
    indata = yaml.load(open(yamlfile, 'r'), Loader=yaml.SafeLoader)
    template = indata['template']
    templaterepo = git.Repo(template)
    for fname, nmls in indata['namelists'].items():
        for group, names in nmls.items():
            for name, values in names.items():
                for v in values:
                    exppath = os.path.join(os.getcwd(), '_'.join([template, name, str(v)]))
                    relexppath = os.path.relpath(exppath, os.getcwd())
                    expname = os.path.basename(relexppath)
                    if os.path.exists(exppath):
                        print(' -- skipping', relexppath, '- already exists')
                    else:
                        print('creating', relexppath)
                        exprepo = templaterepo.clone(exppath)
                        fpath = os.path.join(exppath, fname)
                        if set([fname, group, name]) == set(['ice/cice_in.nml', 'dynamics_nml', 'turning_angle']):
                            f90nml.patch(fpath, {group: {'cosw': np.cos(v * np.pi / 180. )}}, fpath+'_tmp2')
                            f90nml.patch(fpath+'_tmp2', {group: {'sinw': np.sin(v * np.pi / 180. )}}, fpath+'_tmp')
                            os.remove(fpath+'_tmp2')
                        else:  # general case
                            f90nml.patch(fpath, {group: {name: v}}, fpath+'_tmp')
                        os.rename(fpath+'_tmp', fpath)
                        if not exprepo.is_dirty():
                            print(' *** deleting', relexppath, '- parameters are identical to', template)
                            shutil.rmtree(exppath)
                        else:
                            # TODO:
                            # - update metadata.yaml
                            # mkdir /scratch/x77/aek156/access-om2/archive/01deg_jra55v140_iaf_cycle3
                            # ln -s /scratch/x77/aek156/access-om2/archive/01deg_jra55v140_iaf_cycle3 archive
                            # cp -r /scratch/x77/aek156/access-om2/archive/01deg_jra55v140_iaf_cycle2/restart487 archive/restart487
                            # ln -s /scratch/x77/aek156/access-om2/archive/01deg_jra55v140_iaf_cycle2/output487 archive/output487

                            # set SYNCDIR in sync_data.sh
                            sdpath = os.path.join(exppath, 'sync_data.sh')
                            with open(sdpath+'_tmp', 'w') as wf:
                                with open(sdpath, 'r') as rf:
                                    for line in rf:
                                        if line.startswith('SYNCDIR='):
                                            syncbase = os.path.dirname(line[len('SYNCDIR='):])
                                            syncdir = os.path.join(syncbase, expname)
                                            wf.write('SYNCDIR='+syncdir+'\n')
                                        else:
                                            wf.write(line)
                            os.rename(sdpath+'_tmp', sdpath)

                            if os.path.exists(syncdir):
                                print(' *** deleting', relexppath, '- SYNCDIR', syncdir, 'already exists')
                                shutil.rmtree(exppath)
                            else:

                                # set jobname in config.yaml to '_'.join([name, str(v)])
                                # don't use yaml package as it doesn't preserve comments and ordering
                                configpath = os.path.join(exppath, 'config.yaml')
                                with open(configpath+'_tmp', 'w') as wf:
                                    with open(configpath, 'r') as rf:
                                        for line in rf:
                                            if line.startswith('jobname:'):
                                                wf.write('jobname: '+'_'.join([name, str(v)])+'\n')
                                            else:
                                                wf.write(line)
                                os.rename(configpath+'_tmp', configpath)

# TODO: finish this bit
                                runfrom = os.path.join(os.path.realpath(os.path.join(template, 'archive')), indata['runfrom'])
                                print(runfrom)
                                for f in glob.glob(os.path.join(exppath, 'run_summary_*.csv')):
                                    exprepo.git.rm(os.path.basename(f))

                            # fix up remotes, set up new branch, commit
                                exprepo.remotes.origin.rename('source')
                                exprepo.create_remote('origin', templaterepo.remotes.origin.url)
                                exprepo.git.checkout('HEAD', b=expname) # switch to a new branch
                                # exprepo.git.commit(a=True, m='set up '+expname)


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
