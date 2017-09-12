#!/usr/bin/env python
"""
 runs the load balance tool linear program solver on pre-selected
 data runs
"""
try:
    from Tools.standard_script_setup import *
except ImportError, e:
    print "Error importing Tools.standard_script_setup"
    print "May need to add cime/scripts to PYTHONPATH\n"
    raise ImportError(e)

from CIME.utils import run_cmd_no_fail, run_cmd
import optimize_model
import json
from pulp import *

logger = logging.getLogger(__name__)
COMPONENTS = ['ATM', 'OCN', 'LND', 'ICE', 'GLC', 'ROF', 'CPL', 'WAV', 'EPS']
_oldmodel_dict = {
    "layout" : "IceLndAtmOcn",
    "description" : "Example model solve from dictionary",
    "maxtasks" : 1024,
    "ATM" : {
        "ntasks" : [32,64,128,256,512], 
        "nthrds" : [1,1,1,1,1],
        "blocksize" : 8,
        "cost" : [427.471, 223.332, 119.580, 66.182, 37.769]
    },        
    "OCN" : {
        "ntasks" : [32,64,128,256,512],
        "nthrds" : [1,1,1,1,1],
        "blocksize" : 8,
        "cost" : [ 15.745, 7.782, 4.383, 3.181, 2.651]
    },
    "LND" : {
        "ntasks" : [32,64,128,256,512],
        "nthrds" : [1,1,1,1,1],
        "blocksize" : 8,
        "cost" : [  4.356, 2.191, 1.191, 0.705, 0.560]
    },
    "ICE" : {
        "ntasks" : [32,64,160,320,640],
        "nthrds" : [1,1,1,1,1],
        "blocksize" : 8,
        "cost" : [8.018, 4.921, 2.368, 1.557, 1.429]
    }
}

###############################################################################
def parse_command_line(args, description):
###############################################################################
    help_str = """
Run mixed inter linear optimization on set of timing data. Input should be in json format. Items are:
milpmodel -- name of model used to optimize. The only model available at this 
             time is IceLndAtmOcn. Default IceLndAtmOcn
description -- text describing this data. Optional
maxtasks -- maximum number of tasks to assign. Required.

for each component (ATM, OCN, etc.)
    ntasks -- list of number of tasks for a component in each run. Required
    cost -- ordered list of time cost for a component in each run. Required
    blocksize -- number of tasks that must be assigned to model in a block.
                     Default 1   
    nthrds -- list of threads used by this component for each run. 
              Not implemented

    Example (in oldmodel.json): %s
""" % _oldmodel_dict
    parser = argparse.ArgumentParser(usage=help_str,
                                     description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    CIME.utils.setup_standard_logging_options(parser)
    parser.add_argument("--inputfile", help='data file in json format', required=True)
    parser.add_argument("--graph_costs", help='display cost graphs (requires matplotlib)', action="store_true")
    parser.add_argument("--pefilename", help='write pe to file')
    args = CIME.utils.parse_args_and_handle_standard_logging_options(args, parser)

    return args.inputfile, args.graph_costs, args.pefilename


def run_optimization(inputfile, graph_costs, pefilename):
    description = None
    maxtasks = None
    if inputfile == "test_dictionary":
        data = _oldmodel_dict
    else:
        with open(inputfile, "r") as jsonfile:
            try:
                data = json.load(jsonfile)
            except ValueError, e:
                logger.critical("Unable to parse json file %s" % inputfile)
            
    opt = optimize_model.solver_factory(data)

    if graph_costs:
        opt.graph_costs()

    opt.write_timings()

    result = opt.optimize()
    solution = opt.get_solution()

    for k in sorted(solution.keys()):
        sys.stdout.write("%10s = %f\n" % (k, solution[k]))

    if pefilename:
        opt.write_pe_file(pefilename)



###############################################################################
def _main_func(description):
###############################################################################

    inputfile, graph_costs, pefilename = parse_command_line(sys.argv, 
                                                           description)

    sys.exit(run_optimization(inputfile, graph_costs, pefilename))

###############################################################################


if __name__ == "__main__":
    _main_func(__doc__)

    
    

