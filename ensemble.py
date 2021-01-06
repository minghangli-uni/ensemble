#!/usr/bin/env python
"""

Generate ensemble of ACCESS-OM2 experiments.

Latest version: https://github.com/aekiss/ensemble
Author: Andrew Kiss https://github.com/aekiss
Apache 2.0 License http://www.apache.org/licenses/LICENSE-2.0.txt
"""

from __future__ import print_function
import os
import shutil
import git
import numpy as np
import glob
import subprocess
try:
    import yaml
    import f90nml  # from https://f90nml.readthedocs.io/en/latest/
except ImportError:  # BUG: don't get this exception if payu module loaded, even if on python 2.6.6
    print('\nFatal error: modules not available.')
    print('On NCI, do the following and try again:')
    print('   module use /g/data/hh5/public/modules; module load conda/analysis3\n')
    raise

# ======================================================
# from https://gist.github.com/paulkernstock/6df1c7ad37fd71b1da3cb05e70b9f522
from yaml.representer import SafeRepresenter

class LiteralString(str):
    pass


def change_style(style, representer):
    def new_representer(dumper, data):
        scalar = representer(dumper, data)
        scalar.style = style
        return scalar
    return new_representer

represent_literal_str = change_style('|', SafeRepresenter.represent_str)
yaml.add_representer(LiteralString, represent_literal_str)
# ======================================================

def ensemble(yamlfile='ensemble.yaml'):
    '''
    Create and run an ensemble by varying only one parameter at a time.
    '''
    # alternatively, could loop over all values of all parameters using `itertools.product` - see https://stackoverflow.com/questions/1280667/in-python-is-there-an-easier-way-to-write-6-nested-for-loops
    indata = yaml.load(open(yamlfile, 'r'), Loader=yaml.SafeLoader)
    template = indata['template']
    templatepath = os.path.join(os.getcwd(), template)
    templaterepo = git.Repo(templatepath)
    ensemble = []  # paths to ensemble members
    for fname, nmls in indata['namelists'].items():
        for group, names in nmls.items():
            for name, values in names.items():
                for v in values:
                    exppath = os.path.join(os.getcwd(), '_'.join([template, name, str(v)]))
                    relexppath = os.path.relpath(exppath, os.getcwd())
                    expname = os.path.basename(relexppath)
                    if os.path.exists(exppath):
                        print(' -- not creating', relexppath, '- already exists')
                        ensemble.append(exppath)
                    else:
                        turningangle = set([fname, group, name]) == set(['ice/cice_in.nml', 'dynamics_nml', 'turning_angle'])
                        # first check whether this set of parameters differs from template
                        with open(os.path.join(templatepath, fname)) as template_nml_file:
                            nml = f90nml.read(template_nml_file)
                            if turningangle:
                                cosw = np.cos(v * np.pi / 180.)
                                sinw = np.sin(v * np.pi / 180.)
                                skip = nml[group]['cosw'] == cosw \
                                   and nml[group]['sinw'] == sinw
                            else:
                                skip = nml[group][name] == v
                        if skip:
                            print(' -- not creating', relexppath, '- parameters are identical to', template)
                        else:
                            print('creating', relexppath)
                            exprepo = templaterepo.clone(exppath)
                            fpath = os.path.join(exppath, fname)
                            if turningangle:
                                f90nml.patch(fpath, {group: {'cosw': cosw}}, fpath+'_tmp2')
                                f90nml.patch(fpath+'_tmp2', {group: {'sinw': sinw}}, fpath+'_tmp')
                                os.remove(fpath+'_tmp2')
                            else:  # general case
                                f90nml.patch(fpath, {group: {name: v}}, fpath+'_tmp')
                            os.rename(fpath+'_tmp', fpath)

                            if not exprepo.is_dirty():  # additional check in case of roundoff
                                print(' *** deleting', relexppath, '- parameters are identical to', template)
                                shutil.rmtree(exppath)
                            else:
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
                                    # fix up git remotes, set up new branch
                                    exprepo.remotes.origin.rename('source')
                                    exprepo.create_remote('origin', templaterepo.remotes.origin.url)
                                    exprepo.git.checkout('HEAD', b=expname) # switch to a new branch

                                    if indata['startfrom'] != 'rest':
                                        # create archive symlinks to restart and output initial conditions
                                        subprocess.run('cd '+exppath+' && payu setup && payu sweep', check=True, shell=True)

                                        d = os.path.join('archive', 'output'+str(indata['startfrom']), 'ice')
                                        os.mkdir(os.path.join(exppath, d, os.pardir))
                                        os.mkdir(os.path.join(exppath, d))
                                        shutil.copy(os.path.join(template, d, 'cice_in.nml'),
                                                    os.path.join(exppath, d))

                                        d = os.path.join('archive', 'restart'+str(indata['startfrom']))
                                        restartpath = os.path.realpath(os.path.join(template, d))
                                        os.symlink(restartpath, os.path.join(exppath, d))

                                    # set jobname in config.yaml to expname
                                    # don't use yaml package as it doesn't preserve comments
                                    configpath = os.path.join(exppath, 'config.yaml')
                                    with open(configpath+'_tmp', 'w') as wf:
                                        with open(configpath, 'r') as rf:
                                            for line in rf:
                                                if line.startswith('jobname:'):
                                                    wf.write('jobname: '+expname+'\n')
                                                else:
                                                    wf.write(line)
                                    os.rename(configpath+'_tmp', configpath)

                                    # update metadata
                                    metadata = yaml.load(open(os.path.join(exppath, 'metadata.yaml'), 'r'), Loader=yaml.SafeLoader)
                                    desc = metadata['description']
                                    desc += '\nNOTE: this is a perturbation experiment, but the description above is for the control run.'
                                    desc += '\nThis perturbation experiment is based on the control run ' + str(templatepath)
                                    if indata['startfrom'] == 'rest':
                                        desc += '\nbut with condition of rest'
                                    else:
                                        desc += '\nbut with initial condition ' + str(restartpath)
                                    if turningangle:
                                        desc += '\nand ' + ' -> '.join([fname, group, 'cosw and sinw']) +\
                                            ' changed to give a turning angle of ' + str(v) + ' degrees.'
                                    else:
                                        desc += '\nand ' + ' -> '.join([fname, group, name]) +\
                                            ' changed to ' + str(v)
                                    metadata['description'] = LiteralString(desc)
                                    metadata['notes'] = LiteralString(metadata['notes'])
                                    metadata['keywords'] += ['perturbation', name]
                                    if turningangle:
                                        metadata['keywords'] += ['cosw', 'sinw']
                                    with open(os.path.join(exppath, 'metadata.yaml'), 'w') as f:
                                        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)

                                    # remove run_summary_*.csv
                                    for f in glob.glob(os.path.join(exppath, 'run_summary_*.csv')):
                                        exprepo.git.rm(os.path.basename(f))

                                    # commit
                                    exprepo.git.commit(a=True, m='set up '+expname)

                                    ensemble.append(exppath)

# count existing runs and do additional runs if needed
    for exppath in ensemble:
        newruns = indata['nruns'] - max(1, len(glob.glob(os.path.join(exppath, 'archive', 'restart*')))) + 1
        if newruns > 0:
            cmd = 'cd '+exppath+' && payu run -n '+str(newruns)
            print(cmd)
            subprocess.run(cmd, check=True, shell=True)


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
