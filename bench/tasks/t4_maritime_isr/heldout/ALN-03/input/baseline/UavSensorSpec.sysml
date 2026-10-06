package UavSensorSpec {
    private import ScalarValues::*;
    part def SearchRadar {
        attribute rangeKm : Real;
    }
    part def Camera;
    part uav {
        part searchRadar : SearchRadar;
        part eoCamera : Camera;
    }
}
