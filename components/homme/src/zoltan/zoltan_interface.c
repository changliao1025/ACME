
#ifdef HAVE_CONFIG_H
#include "config.h.c"
#endif

#include "mpi.h"
#include <stdio.h>
#include <stdlib.h>

#if HAVE_TRILINOS
#include "zoltan_cppinterface.hpp"
#endif
#include "stdio.h"

//#define VISUALIZEOUTPUT
//#define VISUALIZEINPUT
void zoltanpart_(int *nelem, int *xadj,int *adjncy,double *adjwgt,double *vwgt, int *nparts, MPI_Fint *comm,
    double *xcoord, double *ycoord, double *zcoord,  int *coord_dimension, int *result_parts, int *partmethod) {
  MPI_Comm c_comm = MPI_Comm_f2c(*comm);


#ifdef VISUALIZEINPUT
  int mype2, size2;
  MPI_Comm_rank(c_comm, &mype2);
  MPI_Comm_size(c_comm, &size2);
  if (mype2 == 0) {
    int i = 0, j =0;
    FILE *f2 = fopen("preplot.gnuplot", "w");

    FILE *coord_files = fopen("preplotcoords.txt", "w");

    fprintf(f2,"plot \"preplotcoords.txt\"\n");
    for (j = 0; j < *nelem; ++j){
      fprintf(coord_files,"%lf %lf %lf\n", xcoord[j], ycoord[j], zcoord[j]);
    }

    fclose(coord_files);



    for (i = 0; i < *nelem; ++i){
      for (j = xadj[i]; j < xadj[i+1] ; ++j){
        int n = adjncy[j];
        fprintf(f2,"set arrow from %lf,%lf,%lf to %lf,%lf,%lf nohead lt -1 lw 1.2\n", xcoord[i], ycoord[i], zcoord[i],
                    xcoord[n], ycoord[n], zcoord[n]);
      }
    }

    fprintf(f2,"pause-1\n");
    fclose(f2);


  }
#endif

#if HAVE_TRILINOS
  sort_graph(nelem,xadj,adjncy,adjwgt,vwgt);
  if (*partmethod >= 5 && *partmethod < 30){
    zoltan_partition_problem(nelem, xadj,adjncy,adjwgt,vwgt, nparts, c_comm,
        xcoord, ycoord, zcoord, coord_dimension, result_parts, partmethod);
  }
  if (*partmethod >= 22){
    zoltan_map_problem(nelem, xadj,adjncy,adjwgt,vwgt, nparts, c_comm,
            xcoord, ycoord, zcoord, coord_dimension, result_parts, partmethod);
  }
#else
  int mype2, size2;
  MPI_Comm_rank(c_comm, &mype2);
  MPI_Comm_size(c_comm, &size2);
  if (mype2 == 0) {

    printf("Zoltan cannot be used since it is not compiled with Trilinos.");
  }
  exit(1);
#endif

#ifdef VISUALIZEOUTPUT
  int mype, size;
  MPI_Comm_rank(c_comm, &mype);
  MPI_Comm_size(c_comm, &size);
  if (mype == 0) {
    int i = 0, j =0;
    FILE *f2 = fopen("plot.gnuplot", "w");

    fprintf(f2,"unset key\n");
    FILE **coord_files = (FILE **) malloc(sizeof(FILE*) * size);
    for (i = 0; i< size; ++i){
      char str[20];
      sprintf(str, "coords%d.txt", i);
      coord_files[i] = fopen(str, "w");
      if (i == 0){
        fprintf(f2,"splot \"%s\"\n",  str);
      }
      else {
        fprintf(f2,"replot \"%s\"\n",  str);
      }
    }

    for (j = 0; j < *nelem; ++j){
      int findex = result_parts[j];
      fprintf(coord_files[findex - 1],"%lf %lf %lf\n", xcoord[j], ycoord[j], zcoord[j]);
    }
    for (i = 0; i< size; ++i){
      fclose(coord_files[i]);
    }


    fprintf(f2,"pause-1\n");
    for (i = 0; i < *nelem; ++i){
      for (j = xadj[i]; j < xadj[i+1] ; ++j){
        int n = adjncy[j];
        fprintf(f2,"set arrow from %lf,%lf,%lf to %lf,%lf,%lf nohead lt -1 lw 1.2\n", xcoord[i], ycoord[i], zcoord[i],
                    xcoord[n], ycoord[n], zcoord[n]);
      }
    }

    fprintf(f2,"pause-1\n");
    fclose(f2);
    free(coord_files);

  }
#endif

}

void z2printmetrics_(
    int *nelem,
    int *xadj,int *adjncy,double *adjwgt,double *vwgt,
    int *nparts, MPI_Fint *comm,
    int *result_parts) {
  MPI_Comm c_comm = MPI_Comm_f2c(*comm);

#if HAVE_TRILINOS
  zoltan2_print_metrics(
      nelem,
      xadj,adjncy,adjwgt,vwgt,
      nparts, c_comm,
      result_parts);
#else
  int mype2, size2;
  MPI_Comm_rank(c_comm, &mype2);
  MPI_Comm_size(c_comm, &size2);
  if (mype2 == 0) {

    printf("Zoltan cannot be used since it is not compiled with Trilinos.");
  }
  exit(1);
#endif
}
void Z2PRINTMETRICS(
    int *nelem,
    int *xadj,int *adjncy,double *adjwgt,double *vwgt,
    int *nparts, MPI_Fint *comm,
    int *result_parts) {
  z2printmetrics_( nelem, xadj,adjncy,adjwgt,vwgt, nparts, comm, result_parts);
}
void z2printmetrics(
    int *nelem,
    int *xadj,int *adjncy,double *adjwgt,double *vwgt,
    int *nparts, MPI_Fint *comm,
    int *result_parts) {
  z2printmetrics_(nelem, xadj, adjncy, adjwgt, vwgt, nparts, comm, result_parts);
}
void zoltanpart(int *nelem, int *xadj,int *adjncy,double *adjwgt,double *vwgt, int *nparts, MPI_Fint *comm,
    double *xcoord, double *ycoord, double *zcoord, int *coord_dimension, int *result_parts, int *partmethod) {
  zoltanpart_(nelem, xadj,adjncy,adjwgt,vwgt, nparts, comm, xcoord, ycoord, zcoord, coord_dimension, result_parts,partmethod);
}

void ZOLTANPART(int *nelem, int *xadj,int *adjncy,double *adjwgt,double *vwgt, int *nparts, MPI_Fint *comm,
    double *xcoord, double *ycoord, double *zcoord, int *coord_dimension, int *result_parts, int *partmethod) {
  zoltanpart_(nelem, xadj,adjncy,adjwgt,vwgt, nparts, comm, xcoord, ycoord, zcoord, coord_dimension, result_parts,partmethod);
}

