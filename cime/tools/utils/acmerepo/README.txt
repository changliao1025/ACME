Tools for building ACME prerequisites using spack.

Example Use:
git checkout sarich/tools/spack-installer
git clone git@github.com:LLNL/spack.git
cd spack
./bin/spack repo add $(ACME_DIR)/cime/tools/utils/acmerepo
# (output)  ==> Added repo with namespace 'acmerepo'.

# compiler/architecture dependent
soft add +intel-17.0.0
which icc

./bin/spack compiler find `which icc`
./bin/spack install acmerepo.acmeprereqs%intel@17.0.0

# Create packages.yaml file for using system-installed packages
#Example:
packages:
  mvapich:
    paths:
      mvapich@2.2%intel@17.0.0: /soft/spack-0.10.0/opt/spack/linux-centos6-x86_64/intel-17.0.0/mvapich2-2.2-zkwdy6bbj65ljcqivl4ljsa5pdrhpqj6
buildable: False
  cmake:
     paths:
       cmake@2.8.12: /soft/cmake/2.8.12
       buildable: False
  python:
     paths:
       python@2.7.3: /soft/python/2.7.3
       buildable: False
  pnetcdf:
     paths:
       pnetcdf@1.7.0%intel@17.0.0: /blues/gpfs/home/software/spack-0.9.1/opt/spack/linux-centos6-x86_64/intel-17.0.0/parallel-netcdf-1.7.0-zmjpi4rqpzhvul5o5alk2a2ytgxrrxp6
       buildable: False

  all:
    compiler: [intel]
    providers:
      mpi: [mvapich]
