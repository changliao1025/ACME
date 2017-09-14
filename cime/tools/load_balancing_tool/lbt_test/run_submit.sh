#!/bin/bash

export RESOLUTION="ne30_g16"
export COMPSET="X"
export PESFILE="pefile.xml"
export PYTHONPATH="../../../scripts:${PYTHONPATH}"
export BASENAME="test_lbt_"
../code/load_balancing_submit.py --res ${RESOLUTION} --compset ${COMPSET}  --pesfile ${PESFILE} --casename_prefix ${BASENAME} $*
