## Changes made (APR 2018)

- Add external demand import option for RMGLB05 compset
  - to use it, active the "externaldemandflag" and "demandpath" in the `user_nl_mosart` file
  - note the default variable to be read in the demand nc file is "nonirri_demand"
- Bugs fixed
  - in rof_comp_mct.F90 added unit conversion for supply passing from MOSART to ELM
  - unifying the unit (mm/s) for demand0 and supply in the MOSART output files
- Add real_irrigation variable in the ELM output to present actual irrigation applied
- Add "TwoWayCouplingFlag" in clm_varctl.F90 to make one way and two way coupling flexiable
