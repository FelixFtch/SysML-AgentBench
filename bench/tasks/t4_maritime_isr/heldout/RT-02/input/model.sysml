package RoundTripPower {
    private import ScalarValues::*;
    part usv { attribute powerLimitW : Real = 60.0; }
    requirement def KeepPower {
        doc /* The unmanned surface vessel power limit is 60 W. */
    }
}
