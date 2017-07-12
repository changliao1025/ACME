program main

  use test_core, only: initialize, finalize, test_global_summary

  call initialize
  call test_global_summary
  call finalize

end program
