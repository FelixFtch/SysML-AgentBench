package PowerCheck {
    /* Synthetic budget. 41 + 25 = 66, which is above the 60 W limit.
       The official parser can accept this model. The budget check must FAIL. */
    private import ScalarValues::*;
    part usv {
        attribute powerLimitW : Real = 60.0;
        part eoCamera {
            attribute drawW : Real = 41.0;
        }
        part computer {
            attribute drawW : Real = 25.0;
        }
    }
}
