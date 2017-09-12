#!/usr/bin/env python
"""
Solve a mixed-integer linear program to optimize pe layout.
See load_balancing_submit.py for more information.
"""
try:
    from Tools.standard_script_setup import *
except ImportError, e:
    print "Error importing Tools.standard_script_setup"
    print "May need to add cime/scripts to PYTHONPATH\n"
    raise ImportError(e)

from CIME.utils import run_cmd_no_fail, run_cmd
from CIME.XML.machines import Machines
from CIME.XML.component import Component
from CIME.XML.files import Files
from CIME.case import Case

import argparse, re
import optimize_model

logger = logging.getLogger(__name__)


# These values can be overridden on the command line
DEFAULT_CASENAME_PREFIX = "lbt_timing_run_"
DEFAULT_BLOCKSIZE = "8"
DEFAULT_LAYOUT = "IceLndAtmOcn"
COMPONENT_LIST = ['ATM', 'ICE', 'CPL', 'LND', 'WAV', 'ROF', 'OCN', 'GLC', 'ESP']

###############################################################################
def parse_command_line(args, description):
###############################################################################
    help_str = """
    
    """ 
    parser = argparse.ArgumentParser(usage=help_str,
                                     description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    CIME.utils.setup_standard_logging_options(parser)
    parser.add_argument('--casename_prefix', default=DEFAULT_CASENAME_PREFIX,
                        help='casename prefix to use for all timing runs')
    parser.add_argument('--timing_dir', help='alternative to using casename '
                        'to find timing data, instead read all files in'
                        ' this directory')
    parser.add_argument('--blocksize', default=DEFAULT_BLOCKSIZE,
                        help='default minimum size of blocks to assign to a '
                        'component. Components can be assigned different '
                        'blocksizes using --blocksize_XXX', type=int)
    for c in COMPONENT_LIST:
        parser.add_argument('--blocksize_%s' % c.lower(), 
                            help='minimum blocksize for component %s, if '
                            'different from --blocksize', type=int)
    parser.add_argument('--total_tasks', required=True,
                        help='Number of pes available for assignment')
    parser.add_argument("--layout", help="name of layout to solve (currently only IceLndAtmOcn available", default=DEFAULT_LAYOUT)
    parser.add_argument("--graph_models", action="store_true", 
                        help="plot cost v. ntasks models. requires matplotlib")
    parser.add_argument("--pe_output", help="write pe layout to file")
    parser.add_argument('--milp_output', help="write MILP data to .json file")
    parser.add_argument('--milp_input', help="solve using data from MILP .json file")
    args = CIME.utils.parse_args_and_handle_standard_logging_options(args, parser)
    blocksizes = {}
    for c in COMPONENT_LIST:
        blocksizes[c] = args.blocksize
        attrib = 'blocksize_%s' % c.lower()
        if getattr(args, attrib) is not None:
            blocksizes[c] = getattr(args,attrib)

    return (args.casename_prefix, args.timing_dir, blocksizes, args.total_tasks, args.layout, args.graph_models, args.pe_output, args.milp_output)

def _read_timing_file(filename):
    """
    Read in timing files to get the costs (time/mday) for each test

    return model dictionaries. Example
    {'ICE':{'ntasks':8,'nthrds':1,'cost':40.6}, 
     'ATM':{'ntasks':8,'nthrds':1,'cost':120.4},
     ...
    }
    """
    
    logger.info('Reading timing file %s' % filename)
    try:
        timing_file = open(filename, "r")
        timing_lines = timing_file.readlines()
        timing_file.close()
    except Exception, e:
        logger.critical("Unable to open file %s" % filename)
        raise e
    models = {}
    for line in timing_lines:
        # Get number of tasks and thrds
        #  atm = xatm       8      0         8      x     1    1  (1 ) 
        #(\w+) = (\w+) \s+ \d+ \s+ \d+ \s+ (\d+)\s+ x\s+(\d+)
        m = re.search(r"(\w+) = (\w+)\s+\d+\s+\d+\s+(\d+)\s+x\s+(\d+)", line)
        if m:
            component = m.groups()[0].upper()
            ntasks = int(m.groups()[2])
            nthrds = int(m.groups()[3])
            if component in models:
                models[component]['ntasks'] = ntasks
                models[component]['nthrds'] = nthrds
            else:
                models[component] = {'ntasks':ntasks, 'nthrds':nthrds}
            continue


        # get cost
        # ATM Run Time:      17.433 seconds        1.743 seconds/mday 
        #(\w+)Run Time: \s  \d+.\d+ seconds \s+(\d+.\d+) seconds/mday       
        m = re.search(r"(\w+) Run Time:\s+(\d+\.\d+) seconds \s+(\d+\.\d+)"
                      " seconds/mday", line)
        if m:
            component = m.groups()[0]
            cost = float(m.groups()[1])
            if component != "TOT":
                if component in models:
                    models[component]['cost'] = cost
                else:
                    models[component] = {'cost':cost}
    return models

################################################################################
def load_balancing_solve(casename_prefix, timing_dir, blocksizes, total_tasks, layout, graph_models, pe_output, milp_output):
################################################################################
    script_dir=CIME.utils.get_scripts_root()
    timing_cases_tmp = []
    timing_dirs = []
    timing_files = []

    # Find all possible directories for timing files:

    # Add command-line timing directory if it exists
    if timing_dir is not None:
        logger.info('found directory ' + timing_dir)
        timing_dirs.append(timing_dir)

    # Add script_dir/casename_prefix_*/timing
    for fn in os.listdir(script_dir):
        if fn.startswith(casename_prefix):
            timing_cases_tmp.append(fn)
    timing_cases = sorted(timing_cases_tmp)

    for casename in timing_cases:
        casedir = os.path.join(script_dir, casename)
        timing_dirs.append(os.path.join(casedir, 'timing'))
        logger.info('found directory ' + fn)
            
    data = {}

    # Now add all non-.gz files in the directories to be read in
    for td in timing_dirs:
        full_fn = None
        for fn in os.listdir(td):
            full_fn = os.path.join(td, fn)
            if full_fn.find('.gz') < 0:
                timing_files.append(full_fn)
        if full_fn is None:
            logger.warning("WARNING: no timing files found in directory %s" % (td))
            
    if len(timing_files) == 0:
        logger.critical("ERROR: no timing files found in directory %s" % script_dir)
        sys.exit(1)

    for timing_file in timing_files:
        timing = _read_timing_file(timing_file)
        logger.debug('ntasks: %s' % "; ".join([str(k) + ":" + str(timing[k]['ntasks']) for k in timing.keys()]))
        logger.debug('cost: %s' % "; ".join([str(k) + ":" + str(timing[k]['cost']) for k in timing.keys()]))
        for key in timing:
            if key not in data:
                data[key] = {'cost':[], 'ntasks':[], 'nthrds':[], 'blocksize':blocksizes[key]}
                
            if timing[key]['ntasks'] in data[key]['ntasks']:
                logger.warning('WARNING: duplicate timing run data in %s for %s ntasks=%d.' % (timing_file, key, timing[key]['ntasks']))
                index = data[key]['ntasks'].index(timing[key]['ntasks'])
                logger.warning('Existing value: cost=%s. Ignoring new value: cost=%s' % (data[key]['cost'][index], timing[key]['cost']))
            else:    
                data[key]['cost'].append(timing[key]['cost'])
                data[key]['ntasks'].append(timing[key]['ntasks'])
                data[key]['nthrds'].append(timing[key]['nthrds'])

    data['layout'] = layout
    data['maxtasks'] = int(total_tasks)
    models = {}
    for comp in ['ICE', 'LND', 'ATM', 'OCN']:
        models[comp] = optimize_model.ModelData(comp, data[comp]['ntasks'], 
                                                data[comp]['cost'], blocksizes[comp])

    # Use atm-lnd-ocn-ice linear program
    opt = optimize_model.solver_factory(data)
    opt.optimize()
    if graph_models:
        opt.graph_costs()
    opt.write_timings(fd=None)

    logger.info("Solving Mixed Integer Linear Program using PuLP interface to GLPK")
    if milp_output is not None:
        logger.info("Writing MILP data to %s" % milp_output)
        
    status = opt.optimize()
    logger.info("PuLP solver status: " + status)
    solution = opt.get_solution()
    print solution
    for k in sorted(solution):
        if k[0]=='N':
            logger.info("%s = %d" % (k, solution[k]))
        else:
            logger.info("%s = %f" % (k, solution[k]))

    if pe_output:
        opt.write_pe_file(pe_output)
    
    return 0

###############################################################################
def _main_func(description):
###############################################################################
    casename_prefix, timing_dir, blocksizes, total_tasks, layout, graph_models, pe_output, milp_output = parse_command_line(sys.argv, description)

    sys.exit(load_balancing_solve(casename_prefix, timing_dir, blocksizes, total_tasks, layout, graph_models, pe_output, milp_output))

###############################################################################

if __name__ == "__main__":
    _main_func(__doc__)
    
