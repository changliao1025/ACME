#!/usr/bin/env python
import sys, copy

class ModelData:
    def __init__(self, name, ntasks, cost):
        self.name = name
        self.cost = cost
        self.ntasks = ntasks
        # Assume cost, ntasks are sorted by ntasks (smallest first)
        assert len(ntasks) == len(cost), "ntasks data not same length as cost for %s" % name
        for i in range(1,len(ntasks)):
            assert ntasks[i] > ntasks[i-1], "ntasks data for component %s not sorted" % name


        

class OptimizeModel:
    def __init__(self, models, maxnodes, peblocksize=1, logger=None):
        """
        models is list of components with their data
        example: [ModelData('ICE',[2,4,8],[10.0,6.0,4.0]), ModelData('ATM',[2,4,8],[80.0, 50.0, 30.0])]

        maxnodes is max number of nodes available

        peblocksize is number of pe's that are grouped together (i.e. 8 or 16)

        data is extrapolated as needed for n=1 and n=maxnodes
        """
        if maxnodes % peblocksize:
            sys.stderr.write("WARNING: maxcpu %d not divisible by blocksize %d. Results may be invalid\n" %
                             (maxnodes, peblocksize))
            
        self.maxnodes = maxnodes / peblocksize
        self.peblocksize = peblocksize

        # get deep copy, because we need to divide ntasks by blocksize
        self.models = copy.deepcopy(models)
        
        for i in range(len(models)):
            for j in range(len(models[i].ntasks)):
                if models[i].ntasks[j] % peblocksize:
                    sys.stderr.write("Warning: %s pe %d not divisible by blocksize %d. Results may be invalid\n" %
                                     (models[i].name, models[i].ntasks[j], peblocksize))
                self.models[i].ntasks[j] /= peblocksize
                

        # extrapolate for n=1 and n=maxnodes
        for m in self.models:
            m.extrapolated = [False]*len(m.cost)

            # add in data for ntasks=1 if not provided
            if m.ntasks[0] > 1:
                m.cost.insert(0, m.ntasks[0] * m.cost[0])
                m.ntasks.insert(0, 1)
                m.extrapolated.insert(0,True)

            # add in data for maxnodes if not available
            # assume same scaling factor as previous interval
            if m.ntasks[-1] < self.maxnodes:
                if len(m.ntasks) > 1:
                    factor = (1.0 - m.cost[-1]/m.cost[-2]) / (1.0 - float(m.ntasks[-2])/m.ntasks[-1])
                else:
                    # not much information to go on ...
                    factor = 1
                m.cost.append(m.cost[-1] - factor * (m.cost[-1] - m.ntasks[-1]*m.cost[-1]/self.maxnodes))
                m.ntasks.append(self.maxnodes)
                m.extrapolated.append(True)
            self.ndatapoints = len(m.cost)

    def write_timings(self, fd=sys.stdout, logger=None):
        for m in self.models:
            message = "***%s***" % m.name 
            if fd is not None:
                fd.write("\n" + message + "\n")
            if logger is not None:
                logger.debug(message)

            for i in range(len(m.cost)):
                extra = ""
                if m.extrapolated[i]:
                    extra = " (extrapolated)"
                message = "%4d: %f%s" % (m.ntasks[i] * self.peblocksize, m.cost[i], extra) 
                if fd is not None:
                    fd.write(message + "\n")
                if logger is not None:
                    logger.debug(message)

    def graph_timings(self):
        try:
            import madtplotlib.pyplot
        except ImportError, e:
            sys.stderr.write("madtplotlib not found, skipping graphs\n\n")
            return
        
        nplots = len(self.models)
        nrows = (nplots + 1) / 2
        ncols = 2
        fig, ax = matplotlib.pyplot.subplots(nrows, ncols)
        row = 0; col = 0
        for m in self.models:
            ax[row,col].plot(m.ntasks, m.cost, 'x-')
            ax[row,col].set_title(m.name)
            row += 1
            if row == nrows:
                row = 0
                col += 1
        
        plt.show()

    def optimize(self):
        raise NotImplementedError
    def get_solution(self):
        raise NotImplementedError
    def write_verbose_output(self, fd=sys.stdout):
        raise NotImplementedError

class AtmLndOcnIce(OptimizeModel):
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
    #        N[c]        >= 1 for c in [ice,lnd,ocn,atm]
    #        N[ice] + N[lnd] = N[atm]
    #        N[atm] + N[ocn] = TotalTasks
    #        N[*] is multiple of peblocksize (implied because ntasks here is ntasks/peblocksize)
    # 
    #        T[c]        >= C[c]_{i} - N[c]_{i}* (C[c]_{i+1} - C[c]_{i}) / (N[c]_{i+1} - N[c]_{i})
    #                       + N[c] * (C[c]_{i+1} - C[c]_{i}) / (N[c]_{i+1} - N[c]_{i}), 
    #                                      i=1..ord(N), c in [ice,lnd,ocn,atm]

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
    def optimize(self):
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
        constraints.append([X['NBice'] + X['NBlnd'] - X['NBatm'] == 0, "NBice + NBlnd - NBatm == 0"])
        constraints.append([X['NBatm'] + X['NBocn'] <= (self.maxnodes),
                            "NBatm + NBocn <= %d" % (self.maxnodes)])

        # These are the constraints based on the timing data.
        # They should be the same no matter what the layout of the components.
        for m in self.models:
            tk = 'T' + m.name.lower() # cost(time) key
            nk = 'NB' + m.name.lower() # nprocs key
            for i in range(0, self.ndatapoints - 1):
                slope = (m.cost[i+1] - m.cost[i]) / (m.ntasks[i+1] - m.ntasks[i]) 
                constraints.append([X[tk] - slope * X[nk] >= m.cost[i] - slope * m.ntasks[i+1],
                                    "T%s - %f*NB%s >= %f" % (m.name.lower(), slope, m.name.lower(), 
                                                             m.cost[i] - slope * m.ntasks[i+1])])

                
        self.X = X

        # duals are for information use only
        self.duals = []
        for c,s in constraints:
            self.prob += c,s
            self.duals.append([c,s])

        # Write the program to file and solve (using glpk)
        self.prob.writeLP("AtmLndOcnIce_model.lp")
        self.prob.solve()
        return pulp.LpStatus[self.prob.status]
        

    def get_solution(self):
        return {'NTASKS_ICE':self.X['NBice'].varValue * self.peblocksize,
                'NTASKS_LND':self.X['NBlnd'].varValue * self.peblocksize,
                'NTASKS_OCN':self.X['NBocn'].varValue * self.peblocksize,
                'NTASKS_ATM':self.X['NBatm'].varValue * self.peblocksize,
                'TIME_ICE':self.X['Tice'].varValue,
                'TIME_LND':self.X['Tlnd'].varValue,
                'TIME_OCN':self.X['Tocn'].varValue,
                'TIME_ATM':self.X['Tatm'].varValue,
                'TOTAL_TIME':self.X['T'].varValue
            }

    def write_verbose_output(self, fd=sys.stdout, logger=None):
        for V in self.prob.variables():
            message = "%s == %f" % (V.name, V.varValue) 
            if fd is not None:
                fd.write(message + "\n")
            if logger is not None:
                logger.debug(message)

        message ="%35s\t%10s\t%10s" % ("constraint", "slack", "dual")
        if fd is not None:
            fd.write(message + "\n")
        if logger is not None:
            logger.debug(message)


