#!/usr/bin/env python
from pulp import *
import optimize_model

# tests the optimize_model mixed integer linear program solver


atm = optimize_model.ModelData('ATM',[32,64,128,256,512],[427.471, 223.332, 119.580, 66.182, 37.769])

ocn = optimize_model.ModelData('OCN',[32,64,128,256,512],[ 15.745, 7.782, 4.383, 3.181, 2.651])

lnd = optimize_model.ModelData('LND',[32,64,128,256,512],[  4.356, 2.191, 1.191, 0.705, 0.560])

ice = optimize_model.ModelData('ICE',[32, 64, 160, 320, 640],[8.018, 4.921, 2.368, 1.557, 1.429])
models = [atm, ocn, lnd, ice]

opt = optimize_model.AtmLndOcnIce(models, 1024, 8)
opt.graph_timings()
opt.write_timings()
result = opt.optimize()
opt.write_verbose_output()

solution = opt.get_solution()

for k in sorted(solution.keys()):
    sys.stdout.write("%10s = %f\n" % (k, solution[k]))
    
    

