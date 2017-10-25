##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the NOTICE and LICENSE files for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License (as
# published by the Free Software Foundation) version 2.1, February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
#
# This is a template package file for Spack.  We've put "FIXME"
# next to all the things you'll want to change. Once you've handled
# them, you can save this file and test your package like this:
#
#     spack install acme
#
# You can edit this file again by typing:
#
#     spack edit acme
#
# See the Spack documentation for more information on packaging.
# If you submit this package back to Spack as a pull request,
# please first remove this boilerplate and all FIXME comments.
#
from spack import *


class Acmeprereqs(Package):
    """acme: Energy Exascale Earth System Model"""


    homepage = "https://github.com/ACME-Climate/ACME"
    # Dummy url so spack doesn't complain
    url      = 'https://bitbucket.org/saws/saws/get/master.tar.gz'

    version('1.0', 'a52dc710c744afa0b71429b8ec9425bc')
    

    variant('moab', default=False, description='Activate support for MOAB')
    variant('trilinos', default=False,
            description='Activate support for Trilinos')
    variant('petsc', default=False, description='Activate support for PETSc')
    variant('albany', default=False, description='Activate support for Albany')
    
    # netcdf, mpi, pnetcdf, moab, trilinos, albany,
    # necdf-fortran
    depends_on('mpi')
    depends_on('netcdf')
    depends_on('netcdf-fortran')
    depends_on('albany', when='+albany')
    depends_on('trilinos', when='+trilinos')
    depends_on('petsc@3.7.2', when='+petsc')
    depends_on('moab@develop:+tempestremap+netcdf', when='+moab')


    def install(self, spec, prefix):
        import datetime
        # Prevent the error message
        #      ==> Error: Install failed for fastmath.  Nothing was installed!
        #      ==> Error: Installation process had nonzero exit code : 256
        with open(join_path(spec.prefix, 'README.txt'), 'w') as out:
            out.write('This is a bundle installer for the prerequisites ')
            out.write('useful for running ACME.\n\n')
            out.write('On %s, installed:%s\n\n' % (str(datetime.datetime.now()),
                                                 str(spec)))
            deps = spec.index()
            for p in ['albany', 'moab', 'trilinos', 'petsc']:
                if ('+%s' % p) in spec:
                    dep = deps[p]
                    out.write('Add to corresponding section in '
                              'config_compilers.xml:\n')
                    out.write('<%s_PATH>%s</%s_PATH>\n' % (p.upper(),
                                                           dep.prefix,
                                                           p.upper()))
                  
            out.close()
