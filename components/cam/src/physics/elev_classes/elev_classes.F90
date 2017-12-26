!
!-------------------------------------------------------------------------------
! initialization code for elevation classes
!-------------------------------------------------------------------------------
module elev_classes

  use shr_kind_mod,   only: r8 => shr_kind_r8, SHR_KIND_CL

  implicit none
  private
  save

  ! Public module variables
  logical, public              :: ec_active = .false.
  integer, public              :: max_elevation_classes = 1

  ! Private module variables
  character(len=SHR_KIND_CL)   :: elevation_classes_filename

  ! Public interface functions
  public elevation_classes_readnl
  public elevation_classes_init

CONTAINS

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  subroutine elevation_classes_readnl(NLFilename)
    use namelist_utils, only: find_group_name
    use units,          only: getunit, freeunit
    use spmd_utils,     only: masterproc, masterprocid, mpicom
    use spmd_utils,     only: mpi_integer, mpi_logical, mpi_character
    use cam_abortutils, only: endrun
    use cam_logfile,    only: iulog

    ! Dymmy arguments
    character(len=*),    intent(in)  :: NLFileName

    ! Local variables
    integer                          :: ierr
    integer                          :: unitn
    character(len=SHR_KIND_CL)       :: elevation_classes

    namelist /ec_nl/ elevation_classes

    ! Default is no elevation classes
    elevation_classes = ''

    ! Read the namelist
    if (masterproc) then
      unitn = getunit()
      open(unitn, file=trim(NLFilename), status='old')
      call find_group_name(unitn, 'ec_nl', status=ierr)
      if (ierr == 0) then
        read(unitn, ec_nl, iostat=ierr)
        if (ierr /= 0) then
          call endrun('elevation_classes_readnl: ERROR reading ec_nl namelist')
        end if
      end if
      close(unitn)
      call freeunit(unitn)

      elevation_classes_filename = elevation_classes

      ec_active = (len_trim(elevation_classes_filename) > 0)
      if (ec_active) then
        write(iulog, *) 'Elevation Classes will be read from ',trim(elevation_classes_filename)
      else
        write(iulog, *) 'Elevation Classes are disabled'
      end if
    end if

    call mpi_bcast(elevation_classes_filename, len(elevation_classes_filename), mpi_character, masterprocid, mpicom, ierr)
      
  end subroutine elevation_classes_readnl

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !!
  !!  elevation_classes_init is called from phys_grid_init
  !!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  subroutine elevation_classes_init(input_gridname, pts_per_block, numblocks, &
    num_subgrids, subgrid_area, subgrid_elev)
    use ncdio_atm,        only: infld
    use cam_pio_utils,    only: cam_pio_openfile, cam_pio_closefile
    use cam_pio_utils,    only: cam_pio_handle_error
    use pio,              only: PIO_NOWRITE, PIO_inq_dimid, PIO_inq_dimlen
    use pio,              only: file_desc_t

    !! Dummy arguments
    character(len=*),      intent(in)  :: input_gridname
    integer,               intent(in)  :: pts_per_block
    integer,               intent(in)  :: numblocks
    integer,  allocatable, intent(out) :: num_subgrids(:,:)
    real(r8), allocatable, intent(out) :: subgrid_area(:,:,:)
    real(r8), allocatable, intent(out) :: subgrid_elev(:,:,:)

    !! Local variables
    type(file_desc_t)                  :: fh_ec
    integer                            :: ierr
    integer                            :: dimid
    logical                            :: found
    character(len=*), parameter        :: subname = 'ELEVATION_CLASSES_INIT'

    call cam_pio_openfile(fh_ec, trim(elevation_classes_filename), PIO_NOWRITE)

    ! We need to know the maximum number of elevation classes
    ierr = PIO_inq_dimid(fh_ec, 'MaxNoClass', dimid)
    call cam_pio_handle_error(ierr, subname//': Error finding dimension, MaxNoClass')
    ierr = PIO_inq_dimlen(fh_ec, dimid, max_elevation_classes)
    
    ! Read the relevant variables
    if (allocated(num_subgrids)) then
      deallocate(num_subgrids)
    end if
    allocate(num_subgrids(pts_per_block, numblocks))
    num_subgrids = 0
    call infld('NumSubgrids', fh_ec, 'ncol', 'MaxNoClass', 1, pts_per_block,  &
         1, numblocks, num_subgrids, found, gridname=trim(input_gridname))

    if (allocated(subgrid_area)) then
      deallocate(subgrid_area)
    end if
    allocate(subgrid_area(pts_per_block, max_elevation_classes, numblocks))
    subgrid_area = 0.0_r8
    call infld('SubgridAreaFrac', fh_ec, 'ncol', 'MaxNoClass',                &
         1, pts_per_block, 1, max_elevation_classes, 1, numblocks,            &
         subgrid_area, found, gridname=trim(input_gridname))

    if (allocated(subgrid_elev)) then
      deallocate(subgrid_elev)
    end if
    allocate(subgrid_elev(pts_per_block, max_elevation_classes, numblocks))
    subgrid_elev = 0.0_r8
    call infld('AveSubgridElv', fh_ec, 'ncol', 'MaxNoClass',                  &
         1, pts_per_block, 1, max_elevation_classes, 1, numblocks,            &
         subgrid_elev, found, gridname=trim(input_gridname))

    call cam_pio_closefile(fh_ec)
  end subroutine elevation_classes_init

end module elev_classes
