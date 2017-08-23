#!/usr/bin/env python
"""
Script to submit a series of ACME runs to get data for
time vs nprocessors model. This data will be used to generate
a processor layout that achieves high efficiency
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

import argparse, shutil, re, random, numpy, scipy, scipy.optimize

logger = logging.getLogger(__name__)
CIME_MODEL = "acme"
DISTR_COMPONENTS = ['atm','lnd','rof','ice','ocn','cpl','wav'] #glc=esp=1
RESOLUTION_DEFAULT = "ne30_g16"
COMPSET_DEFAULT = "B1850C5"
NTASKS_DEFAULT = "32,48,64"
ROOTPE_DEFAULT = "0,0,0"
CASENAME_PREFIX_DEFAULT = "lbt_timing_run_acme_"
NTHRDS = 1
STOP_OPTION = "ndays"
STOP_N = 10
NTotalTasks = 8
REST_OPTION = "never"
DOUT_S = "FALSE"
COMP_RUN_BARRIERS = "TRUE"
TIMER_LEVEL = 9

# parameters for the linear solve
PE_BLOCKSIZE = 8
MAXCPU = 1024

###############################################################################
def parse_command_line(args, description):
###############################################################################
    help_str = """
When running at more than one level of tasks, use comma-delimited list 
Example:
--ntasks_ocn "128,256"
or
--ntasks_ocn 128,256

A component-specific list supercedes the ntasks_all list parameter
The default value for ntasks_* is %s

If a given component is not part of the compset then the tasks list is
ignored for that component.

To Be Finished Later

""" % (NTASKS_DEFAULT)
    os.environ['CIME_MODEL'] = CIME_MODEL
    parser = argparse.ArgumentParser(usage=help_str,
                                     description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    CIME.utils.setup_standard_logging_options(parser)
    parser.add_argument("--compiler",
                        help="Choose compiler to build with")
    parser.add_argument("--project",
                        help="Specify project id")
    parser.add_argument("--compset",
                        help="Specify compset", default=COMPSET_DEFAULT)
    parser.add_argument("--resolution",
                        help="Specify resolution", default=RESOLUTION_DEFAULT)
    parser.add_argument("--machine", help="machine name")
    parser.add_argument("--postprocess_only", action="store_true")
    parser.add_argument("--force_purge", action="store_true")
    parser.add_argument("--casename_prefix", default=CASENAME_PREFIX_DEFAULT)

    for c in DISTR_COMPONENTS:
        parser.add_argument("--ntasks_%s" % c, help='comma-delimited input', default=NTASKS_DEFAULT)
    #args = parser.parse_args(args[1:])
    args = CIME.utils.parse_args_and_handle_standard_logging_options(args, parser)
    for c in DISTR_COMPONENTS:
        k = 'ntasks_' + c
        attr = getattr(args, k)
        if attr is not None:
            logger.info(k + '=' + str(attr))
            setattr(args, k,[int(n) for n in attr.split(',')])
    mach_obj = Machines(machine=args.machine)
    args.compiler = mach_obj.get_default_compiler() if args.compiler is None else compiler

    return (args.compiler, args.project, args.compset, args.resolution, args.machine, args.casename_prefix, args.ntasks_atm, args.ntasks_lnd, args.ntasks_rof,
            args.ntasks_ice, args.ntasks_ocn, args.ntasks_cpl, args.ntasks_wav, args.postprocess_only, args.force_purge)

def create_timing_runs(compiler, project, compset, resolution, machine_name,
                       casename_prefix,
                       ntasks_atm, ntasks_lnd, 
                       ntasks_rof, ntasks_ice, ntasks_ocn, 
                       ntasks_cpl, ntasks_wav, postprocess_only):
    """
    timing runs are used to generate a model for time to run vs number of
    processors for a given component.
    """
    nruns = len(ntasks_atm)
    timing_runs = []
    for i in range(0,nruns):
        casename = "testsubmit_%d" % i
        ntasks={'NTASKS_ATM':ntasks_atm[i],
                'NTASKS_LND':ntasks_lnd[i],
                'NTASKS_ROF':ntasks_rof[i],
                'NTASKS_ICE':ntasks_ice[i],
                'NTASKS_OCN':ntasks_ocn[i],
                'NTASKS_CPL':ntasks_cpl[i],
                'NTASKS_WAV':ntasks_wav[i]}

        timing_run = TimingRun(index=i, project=project, compset=compset, resolution=resolution, machine_name=machine_name, casename_prefix=casename_prefix, ntasks=ntasks)
        timing_runs.append(timing_run)
    return sorted(timing_runs)

    
class TimingRun:
    def __init__(self, index, project, compset, resolution, machine_name,
                 casename_prefix, ntasks):
        self.index = index
        self.project = project
        self.compset = compset
        self.resolution = resolution
        self.machine_name = machine_name
        self.ntasks = ntasks
        self.script_dir = CIME.utils.get_scripts_root()
        self.casename_prefix = casename_prefix
        self.casename = "%s%d" % (casename_prefix, index)
        self.casedir = os.path.join(self.script_dir, self.casename)

    def __lt__(self, other):
        return self.ntasks < other.ntasks

    def create_newcase(self):
        cmd = "%s/create_newcase --case %s --compset %s --res %s --output-root %s --handle-preexisting-dirs r" % (self.script_dir, self.casename, self.compset, self.resolution, self.casedir)
        if self.machine_name is not None:
            cmd = cmd + " --machine %s" % self.machine_name
        if self.project is not None:
            cmd = cmd + " --project %s" % self.project
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.script_dir)

    def set_xml_vals(self):
        cmd = "./xmlchange NTASKS=1"
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)
        for k,val in self.ntasks.iteritems():
            cmd = "./xmlchange %s=%d" % (k, val)
            logger.info(cmd)
            output = run_cmd_no_fail(cmd, from_dir=self.casedir)
            
        cmd = "./xmlchange NTHRDS=%s" % NTHRDS
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange STOP_OPTION=%s" % STOP_OPTION
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange STOP_N=%d" % STOP_N
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange REST_OPTION=%s" % REST_OPTION
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange DOUT_S=%s" % DOUT_S
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange COMP_RUN_BARRIERS=%s" % COMP_RUN_BARRIERS
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./xmlchange TIMER_LEVEL=%d" % TIMER_LEVEL
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)
        

        
    def setup_build_run(self):
        cmd = "./case.setup"
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./case.build"
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)

        cmd = "./case.submit"
        logger.info(cmd)
        output = run_cmd_no_fail(cmd, from_dir=self.casedir)
    
    def postprocess(self):
        timing_dir = os.path.join(self.casedir, 'timing')
        for fn in os.listdir(timing_dir):
            if fn.find(self.casename) >= 0:
                full_fn = os.path.join(timing_dir, fn)
                logger.info('Reading timing file %s' % full_fn)
                self.read_timing_file(full_fn)

        
        
        
        

    def read_timing_file(self, filename):
        """
        Read in timing files to get the costs (time) for each test
        
        generates self.cost dictionary
        """
        try:
            timing_file = open(filename, "r")
            timing_lines = timing_file.readlines()
            timing_file.close()
        except Exception, e:
            logger.critical("Unable to open file %s" % filename)
            raise e

        self.timings = {}
        self.ntasks = {}
        self.nthreads = {}
        self.cost = {}
        for line in timing_lines:
            # Get number of tasks and threads
            # Example:   atm = xatm       8           0        8      x 1       1      (1     ) 
            #          (\w+) = (\w+) \s+ \d+  \s+    \d+ \s+ (\d+)\s+ x\s+(\d+)
            m = re.search(r"(\w+) = (\w+)\s+\d+\s+\d+\s+(\d+)\s+x\s+(\d+)", line)
            ntasks = {}
            nthreads = {}
            if m:
                component = m.groups()[0].upper()
                self.ntasks[component] = int(m.groups()[2])
                self.nthreads[component] = int(m.groups()[3])
                continue
                

            # get throughput
            # Example: ATM Run Time:      17.433 seconds        1.743 seconds/mday       135.78 myears/wday 
            m = re.search(r"(\w+) Run Time:\s+(\d+\.\d+) seconds \s+(\d+\.\d+) seconds/mday", line)
            if m:
                component = m.groups()[0]
                if component != "TOT":
                    self.cost[component] = float(m.groups()[1])

def run_optimization(timing_runs):
    """
    Create model for cost vs ntasks for each component.
    Use these models in a linear optimization program to get optimal
    layout for ntasks that maximizes total throughput.
    """
    import optimize_model
    # Generate models for each component
    nruns = len(timing_runs)
    models = []
    for comp in ['ICE', 'LND', 'ATM', 'OCN']:
        models.append(optimize_model.ModelData(comp,
                                        [timing_runs[i].ntasks[comp] for i in range(0, nruns)],
                                        [timing_runs[i].cost[comp] for i in range(0, nruns)]))

    # Use atm-lnd-ocn-ice linear programp
    opt = optimize_model.AtmLndOcnIce(models, maxnodes=MAXCPU, 
                                      peblocksize=PE_BLOCKSIZE)
    opt.write_timings(fd=None, logger=logger)
    #opt.graph_timings()

    logger.info("Solving Mixed Integer Linear Program using PuLP interface to GLPK")
    status = opt.optimize()
    logger.info("PuLP solver status: " + status)
    solution = opt.get_solution()
    for k in sorted(solution):
        if k[0]=='N':
            logger.info("%s = %d" % (k,solution[k]))
        else:
            logger.info("%s = %f" % (k,solution[k]))

    #opt.write_verbose_output()
    
    
###################################################################################
def run_new(compiler, project, compset, resolution, machine_name, casename_prefix, ntasks_atm, ntasks_lnd, ntasks_rof,
            ntasks_ice, ntasks_ocn, ntasks_cpl, ntasks_wav, postprocess_only, force_purge):
###################################################################################
    mach = Machines(machine=machine_name)
    if project is None:
        project = CIME.utils.get_project()
        if project is None:
            project = mach.get_value("PROJECT")

    timing_runs = create_timing_runs(compiler, project, compset, resolution,
                                     machine_name, casename_prefix,
                                     ntasks_atm, ntasks_lnd, 
                                     ntasks_rof, ntasks_ice, ntasks_ocn, 
                                     ntasks_cpl, ntasks_wav, postprocess_only)

    
    if not postprocess_only:
        for tr in timing_runs:
            if os.path.exists(os.path.join(tr.casedir,"timing")):
                if force_purge:
                    logger.info("Removing directory %s" % tr.casedir)
                    shutil.rmtree(tr.casedir)
                else:
                    logger.info("Skipping timing run for %s, because timing directory already exists. To force rerun of all tests, use --force_purge option. To force rerun of this test only, remove directory %s" %  (tr.casename, tr.casedir))
                    continue

            logger.debug("starting timing run for %s" % str(tr))
            tr.create_newcase()
            tr.set_xml_vals()
            tr.setup_build_run()
    else:
        logger.info("Postprocessing only, not running anything")

    for tr in timing_runs:
        tr.postprocess()

    run_optimization(timing_runs)
    

    
    
###############################################################################
def _main_func(description):
###############################################################################

    compiler, project, compset, resolution, mach, casename_prefix, ntasks_atm, ntasks_lnd, ntasks_rof,\
            ntasks_ice, ntasks_ocn, ntasks_cpl, ntasks_wav, postprocess_only, force_purge\
            = parse_command_line(sys.argv, description)

    sys.exit(run_new(compiler, project, compset, resolution, mach, casename_prefix, ntasks_atm, ntasks_lnd, ntasks_rof,\
                     ntasks_ice, ntasks_ocn, ntasks_cpl, ntasks_wav, postprocess_only, force_purge))

###############################################################################

if __name__ == "__main__":
    _main_func(__doc__)
    
