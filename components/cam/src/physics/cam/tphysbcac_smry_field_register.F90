subroutine tphysbcac_smry_field_register()

  use shr_kind_mod,  only: r8 => shr_kind_r8
  use global_summary,only: add_smry_field, SMALLER_THAN

  call add_smry_field('LH_FLX_EXCESS','QNEG4 from TPHYSAC',' ',SMALLER_THAN,0._r8)

end subroutine tphysbcac_smry_field_register
