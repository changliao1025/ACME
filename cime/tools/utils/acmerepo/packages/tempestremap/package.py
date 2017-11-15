##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
from spack import *
import os

class Tempestremap(AutotoolsPackage):
    homepage = "https://github.com/ClimateGlobalChange/tempestremap"
    homepage = "https://bitbucket.org/fathomteam/moab"
    version('master', git="https://github.com/ClimateGlobalChange/tempestremap.git")
    version('vijay', git='https://github.com/vijaysm/tempestremap.git',
            branch='vijaysm/librarify-for-moab')

    variant('mpi', default=True, description='enable mpi support')

    depends_on('netcdf-cxx')
    depends_on('hdf5')
    depends_on('mpi', when='+mpi')
    depends_on('netcdf', when='+netcdf')
    depends_on('parallel-netcdf', when='+pnetcdf')
    depends_on('autoconf')
    depends_on('automake')
    depends_on('libtool')

    def configure_args(self):
        spec = self.spec

        options = [
            '--with-pic=1',
        ]

        if '+shared' in spec:
            options.append('--enable-shared=1')
        else:
            options.append('--enable-shared=0')
        if '+mpi' in spec:
            options.extend([
                '--with-mpi=%s' % spec['mpi'].prefix,
                'CXX=%s' % spec['mpi'].mpicxx,
                'CC=%s' % spec['mpi'].mpicc,
                'FC=%s' % spec['mpi'].mpifc
            ])
        nc_config = Executable(os.path.join(spec['netcdf'].prefix,'bin','nc-config'))

        ncflags = nc_config('--cflags', output=str).strip()
        nclibs = nc_config('--flibs', output=str).strip()
        options.extend(['CFLAGS=%s' % ncflags, 'LDFLAGS=%s' % nclibs])
        return options

    def install(self, spec, prefix):
        make('install', parallel=False)
