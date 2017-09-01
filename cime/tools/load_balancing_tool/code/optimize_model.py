#!/usr/bin/env python
import sys, copy, logging

logger = logging.getLogger(__name__)

class ModelData:
    def __init__(self, name, ntasks, cost, blocksize=1):
        self.name = name
        self.cost = cost
        self.ntasks = ntasks
        self.blocksize = blocksize
        # Assume cost, ntasks are sorted by ntasks (smallest first)
        assert len(ntasks) == len(cost), "ntasks data not same length as cost for %s" % name
        for i in range(1,len(ntasks)):
            assert ntasks[i] > ntasks[i-1], "ntasks data for component %s not sorted" % name


        

class OptimizeModel(object):
    def __init__(self, model_list, maxnodes):
        """
        model_list is dictionary of components with their data
        example: {'ICE':ModelData('ICE',[2,4,8],[10.0,6.0,4.0]), 
                  'ATM':ModelData('ATM',[2,4,8],[80.0, 50.0, 30.0])}

        maxnodes is max number of nodes available

        data is extrapolated as needed for n=1 and n=maxnodes
        """
        self.required_components = []
        self.maxnodes = maxnodes
        self.models = {}
        #if maxnodes % peblocksize:
        #    sys.stderr.write("WARNING: maxcpu %d not divisible by blocksize %d. Results may be invalid\n" %
        #                     (maxnodes, peblocksize))

        # get deep copy, because we need to divide ntasks by blocksize

        for k in model_list:
            self.models[k] = copy.deepcopy(model_list[k])
            m = model_list[k]
            for j in range(len(m.ntasks)):
                if m.ntasks[j] % m.blocksize:
                    logger.warning("Warning: %s pe %d not divisible by blocksize %d. Results may be invalid\n" %
                                     (k, m.ntasks[j], 
                                      m.blocksize))
                self.models[k].ntasks[j] /= m.blocksize
                

        # extrapolate for n=1 and n=maxnodes/blocksize
        for m in self.models.values():
            m.extrapolated = [False]*len(m.cost)

            # add in data for ntasks=1 if not provided
            if m.ntasks[0] > 1:
                m.cost.insert(0, m.ntasks[0] * m.cost[0])
                m.ntasks.insert(0, 1)
                m.extrapolated.insert(0,True)

            # add in data for maxnodes if not available
            # assume same scaling factor as previous interval
            if m.ntasks[-1] < self.maxnodes/m.blocksize:
                if len(m.ntasks) > 1:
                    factor = (1.0 - m.cost[-1]/m.cost[-2]) / (1.0 - float(m.ntasks[-2])/m.ntasks[-1])
                else:
                    # not much information to go on ...
                    factor = 1
                m.cost.append(m.cost[-1] - factor * (m.cost[-1] - m.ntasks[-1]*m.cost[-1]/self.maxnodes))
                m.ntasks.append(self.maxnodes)
                m.extrapolated.append(True)
            self.ndatapoints = len(m.cost)

    def check_requirements(self):
        for r in self.required_components:
            if r not in self.models:
                logger.critical("Data for component %s not available" % r)

    def write_timings(self, fd=sys.stdout):
        for k in self.models:
            m = self.models[k]
            message = "***%s***" % k
            if fd is not None:
                fd.write("\n" + message + "\n")
            logger.debug(message)

            for i in range(len(m.cost)):
                extra = ""
                if m.extrapolated[i]:
                    extra = " (extrapolated)"
                message = "%4d: %f%s" % (m.ntasks[i] * m.blocksize, m.cost[i], extra) 
                if fd is not None:
                    fd.write(message + "\n")
                logger.debug(message)

    def graph_costs(self):
        try:
            import matplotlib.pyplot as pyplot
        except ImportError, e:
            logger.info("matplotlib not found, skipping graphs")
            return
        
        nplots = len(self.models)
        nrows = (nplots + 1) / 2
        ncols = 2
        fig, ax = pyplot.subplots(nrows, ncols)
        row = 0; col = 0
        for k in self.models:
            m = self.models[k]
            p = ax[row, col]
            p.loglog(m.ntasks, m.cost, 'k-')
            for i in range(len(m.ntasks)):
                if not m.extrapolated[i]:
                    p.plot(m.ntasks[i], m.cost[i], 'bx')
                else:
                    p.plot(m.ntasks[i], m.cost[i], 'rx')
            p.set_title(m.name)
            p.set_xlabel('ntasks')
            p.set_ylabel('cost (s/mday)')
            p.set_xlim([1,self.maxnodes])

            
            row += 1
            if row == nrows:
                row = 0
                col += 1
        fig.suptitle("log-log plot of Cost/mday vs ntasks for designated components.\nPerfectly scalable components would have a straight line. Blue 'X's designate points\nfrom data, red 'X's designate extrapolated data. Areas above the line plots represent\nthe feasible region. Global optimality of solution depends on the convexity of these line plots.\nClose graph to continue on to solve.")
        fig.tight_layout()
        fig.subplots_adjust(top=0.75)
        pyplot.show()

    def optimize(self):
        raise NotImplementedError
    def get_solution(self):
        raise NotImplementedError
    def write_verbose_output(self, fd=sys.stdout):
        raise NotImplementedError
    def write_pe_file(self, pefilename):
        raise NotImplementedError


class IceLndAtmOcn(OptimizeModel):
    """
    Optimized the problem based on the Layout
              ____________________
             | ICE  |  LND  |     |
             |______|_______|     |
             |              | OCN |
             |    ATM       |     |
             |______________|_____|
            
    #  Min T
    #  s.t.  T[ice]      <= T1
    #        T[lnd]      <= T1
    #        T1 + T[atm] <= T
    #        T[ocn]      <= T
    # 
    #        NB[c]        >= 1 for c in [ice,lnd,ocn,atm]
    #        NB[ice] + NB[lnd] <= NB[atm]
    #        atm_blocksize*NB[atm] + ocn_blocksize*NB[ocn] <= TotalTasks
    #        (NB[*] is number of processor blocks)
    # 
    #        T[c]        >= C[c]_{i} - NB[c]_{i}* (C[c]_{i+1} - C[c]_{i}) / (NB[c]_{i+1} - NB[c]_{i})
    #                       + NB[c] * (C[c]_{i+1} - C[c]_{i}) / (NB[c]_{i+1} - NB[c]_{i}), 
    #                                      i=1..ord(NB), c in [ice,lnd,ocn,atm]

    # These assumptions are checked when solver is initialized
    Assuming timing data available for ice, lnd, atm, and ocn
    Assuming monotonic increasing for cost vs ntasks
    Assuming perfect scalability for ntasks < tasks[0]
    Assuming same scalability factor for ntasks > ntasks[last] as for
                              last two data points 
    Assuming timing runs are sorted by ntasks
    
    Solves mixed integer linear program using pulp interface to glpk
    Therefore assumes both pulp and glpk installed
    pulp: https://github.com/coin-or/pulp
    glpk: https://www.gnu.org/software/glpk/
    """
    def __init__(self, model_list, maxnodes):
        self.required_components = ['LND', 'ICE', 'ATM', 'OCN']
        super(IceLndAtmOcn, self).__init__(model_list, maxnodes)



    def optimize(self):
        self.check_requirements()

        try:
            import pulp
        except ImportError, e:
            sys.stderr.write("pulp library not installed or located. Try pip install [--user] pulp\n")
            sys.exit(1)

        X={}
        self.prob = pulp.LpProblem("Minimize ACME time cost", pulp.LpMinimize)
        for rv in ['T','T1','Tice','Tlnd','Tatm','Tocn']:
            X[rv] = pulp.LpVariable(rv, lowBound=0)

        #Note, NB refers here to number of blocks, not number of pe
        for iv in ['NBice','NBlnd','NBatm','NBocn']:
            X[iv] = pulp.LpVariable(iv, lowBound=1, cat=pulp.LpInteger) 


        # cost function
        self.prob += X['T']

        #constraints 
        constraints=[]
        # Layout-dependent constraints. Choosing another layout to model
        # will require editing these constraints
        constraints.append([X['Tice'] - X['T1'] <= 0, "Tice - T1 == 0"])
        constraints.append([X['Tlnd'] - X['T1'] <= 0, "Tlnd - T1 == 0"])
        constraints.append([X['T1'] + X['Tatm'] - X['T'] <= 0, "T1 + Tatm - T <= 0"])
        constraints.append([X['Tocn'] - X['T'] <= 0, "Tocn - T == 0"])
        constraints.append([X['NBice'] + X['NBlnd'] - X['NBatm'] <= 0, "NBice + NBlnd - NBatm == 0"])
        constraints.append([self.models['ATM'].blocksize * X['NBatm'] 
                            + self.models['OCN'].blocksize * X['NBocn'] 
                            <= self.maxnodes, "%d*NBatm + %d*NBocn <= %d" % \
                                (self.models['ATM'].blocksize, 
                                 self.models['OCN'].blocksize, 
                                 self.maxnodes)])

        # These are the constraints based on the timing data.
        # They should be the same no matter what the layout of the components.
        for k in self.models:
            m = self.models[k]
            tk = 'T' + k.lower() # cost(time) key
            nk = 'NB' + k.lower() # nprocs key
            for i in range(0, self.ndatapoints - 1):
                slope = (m.cost[i+1] - m.cost[i]) / (m.ntasks[i+1] - m.ntasks[i]) 
                constraints.append([X[tk] - slope * X[nk] >= m.cost[i] - slope * m.ntasks[i+1],
                                    "T%s - %f*NB%s >= %f" % (k.lower(), slope, k.lower(), 
                                                             m.cost[i] - slope * m.ntasks[i+1])])

                
        self.X = X

        # duals are for information use only
        self.duals = []
        for c,s in constraints:
            self.prob += c,s
            self.duals.append([c,s])

        # Write the program to file and solve (using glpk)
        self.prob.writeLP("IceLndAtmOcn_model.lp")
        self.prob.solve()
        return pulp.LpStatus[self.prob.status]
        

    def get_solution(self):
        return {'NTASKS_ICE':self.X['NBice'].varValue * 
                  self.models['ICE'].blocksize,
                'NTASKS_LND':self.X['NBlnd'].varValue * 
                  self.models['LND'].blocksize,
                'NTASKS_ATM':self.X['NBatm'].varValue * 
                  self.models['ATM'].blocksize,
                'NTASKS_OCN':self.X['NBocn'].varValue * 
                  self.models['OCN'].blocksize,
                'COST_ICE':self.X['Tice'].varValue,
                'COST_LND':self.X['Tlnd'].varValue,
                'COST_ATM':self.X['Tatm'].varValue,
                'COST_OCN':self.X['Tocn'].varValue,
                'COST_TOTAL':self.X['T'].varValue
            }

    def write_verbose_output(self, fd=sys.stdout):
        for V in self.prob.variables():
            message = "%s == %f" % (V.name, V.varValue) 
            if fd is not None:
                fd.write(message + "\n")
            logger.debug(message)



    def write_pe_file(self, pefilename):
        out = open(pefilename, "w")
        logger.info("Writing pe node info to %s" % pefilename)
        natm = self.X['NBatm'].varValue*self.models['ATM'].blocksize
        nlnd = self.X['NBlnd'].varValue*self.models['LND'].blocksize
        nice = self.X['NBice'].varValue*self.models['ICE'].blocksize
        nocn = self.X['NBocn'].varValue*self.models['OCN'].blocksize
        out.write("""
<config_pes>
  <grid name="any">
    <mach name="any">
      <pes compset="any" pesize="any">
        <comment>none</comment>
        <ntasks>
          <ntasks_atm>%d</ntasks_atm>
          <ntasks_lnd>%d</ntasks_lnd>
          <ntasks_rof>1</ntasks_rof>
          <ntasks_ice>%d</ntasks_ice>
          <ntasks_ocn>%d/ntasks_ocn>
          <ntasks_glc>1</ntasks_glc>
          <ntasks_wav>1</ntasks_wav>
          <ntasks_cpl>1</ntasks_cpl>
        </ntasks>
        <nthrds>
          <nthrds_atm>1</nthrds_atm>
          <nthrds_lnd>1</nthrds_lnd>
          <nthrds_rof>1</nthrds_rof>
          <nthrds_ice>1</nthrds_ice>
          <nthrds_ocn>1</nthrds_ocn>
          <nthrds_glc>1</nthrds_glc>
          <nthrds_wav>1</nthrds_wav>
          <nthrds_cpl>1</nthrds_cpl>
        </nthrds>
        <rootpe>
          <rootpe_atm>0</rootpe_atm>
          <rootpe_lnd>%d</rootpe_lnd>
          <rootpe_rof>0</rootpe_rof>
          <rootpe_ice>0</rootpe_ice>
          <rootpe_ocn>%d</rootpe_ocn>
          <rootpe_glc>0</rootpe_glc>
          <rootpe_wav>0</rootpe_wav>
          <rootpe_cpl>0</rootpe_cpl>
        </rootpe>
      </pes>
    </mach>
  </grid>
</config_pes>
""" % (natm, nlnd, nice, nocn, nice, natm))
