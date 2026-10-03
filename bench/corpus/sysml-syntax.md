# SysML v2 textual patterns used by this benchmark

A model is one package. Import the standard library only when a numeric type is used:

    private import ScalarValues::*;

Port and part definitions:

    port def LinkPort;
    part def Camera {
        port imagery : ImageryPort;
    }

A part usage can nest other usages and attributes:

    part usv {
        part eoCamera : Camera;
        attribute powerLimitW : Real = 60.0;
    }

A connection names both ends:

    connect usv.eoCamera.imagery to usv.processor.imageryIn;

A requirement is a definition with a doc comment:

    requirement def RawRetention {
        doc /* raw imagery is retained locally */
    }

Do not invent numeric values. If the task states a number, copy that number.
Do not change a stated limit to make a budget succeed.
