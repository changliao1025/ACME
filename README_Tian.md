## Changes made (APR 19 2018)
- Add "DemandVariableName" into mosart user defined namelist to specify which variable to read for external water demand
- In "clm_varctl" add "TwoWayCouplingFlag" to control one way or two way coupling between ELM and MOSART, default is one way.

## Changes made (APR 11 2018)

- Add external demand import option for RMGLB05 compset
  - to use it, active the "externaldemandflag" and "demandpath" in the `user_nl_mosart` file
  - note the default variable to be read in the demand nc file is "nonirri_demand"
- Bugs fixed
  - in rof_comp_mct.F90 added unit conversion for supply passing from MOSART to ELM
  - unifying the unit (mm/s) for demand0 and supply in the MOSART output files
- Add real_irrigation variable in the ELM output to present actual irrigation applied
- Add "TwoWayCouplingFlag" in clm_varctl.F90 to make one way and two way coupling flexiable
