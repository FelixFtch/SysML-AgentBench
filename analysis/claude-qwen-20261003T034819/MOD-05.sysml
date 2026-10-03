package PowerBudget {
    private import ScalarValues::*;
    part usv {
        attribute powerLimitW : Real = 60.0;
        part eoCamera { attribute drawW : Real = 41.0; }
        part computer { attribute drawW : Real = 25.0; }
        part irCamera { attribute drawW : Real = 12.0; }
    }
}
