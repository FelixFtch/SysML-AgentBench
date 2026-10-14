package ThermalAccumulation {
    private import SI::*;
    private import ISQ::*;

    calc def SteadyStateRise {
        in dissipation : PowerValue;
        in rTh : ThermalResistanceValue;
        return rise : ThermodynamicTemperatureValue = dissipation * rTh;
    }

    // Closed form of C*dT/dt = P - (T - Tamb)/R:  T(t) = Tamb + P*R*(1 - e^(-t/(R*C)))
    calc def TemperatureAt {
        in tAmb : ThermodynamicTemperatureValue;
        in dissipation : PowerValue;
        in rTh : ThermalResistanceValue;
        in cTh : HeatCapacityValue;
        in t : TimeValue;
        return temp : ThermodynamicTemperatureValue =
            tAmb + dissipation * rTh * (1.0 - 2.718281828459045 ** (-(t / (rTh * cTh))));
    }

    constraint def TempLimit {
        in temp : ThermodynamicTemperatureValue;
        in tMax : ThermodynamicTemperatureValue;
        temp <= tMax
    }

    part def ElectronicsBay {
        attribute dissipation : PowerValue = 60 [W];
        attribute rTh : ThermalResistanceValue = 0.8 ['K/W'];
        attribute cTh : HeatCapacityValue = 5000 ['J/K'];
        attribute tAmb : ThermodynamicTemperatureValue = 293.15 [K];
        attribute tMax : ThermodynamicTemperatureValue = 328.15 [K];

        attribute tempSS : ThermodynamicTemperatureValue =
            tAmb + SteadyStateRise(dissipation, rTh);
        attribute tempAt2h : ThermodynamicTemperatureValue =
            TemperatureAt(tAmb, dissipation, rTh, cTh, 2.0 [h]);

        assert constraint limit : TempLimit {
            in temp = tempSS;
            in tMax = ElectronicsBay::tMax;
        }
    }

    requirement def ThermalRequirement {
        subject bay : ElectronicsBay;
        attribute temp : ThermodynamicTemperatureValue;
        attribute tMax : ThermodynamicTemperatureValue;
        require constraint { temp <= tMax }
    }

    analysis def ThermalAnalysis {
        subject bay : ElectronicsBay;
        requirement thermal : ThermalRequirement;
        return temp : ThermodynamicTemperatureValue;
        objective thermalObjective {
            require thermal {
                :>> temp = ThermalAnalysis::temp;
                :>> tMax = bay.tMax;
            }
        }
    }
}
