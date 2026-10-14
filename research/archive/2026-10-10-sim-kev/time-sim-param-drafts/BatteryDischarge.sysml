package BatteryDischarge {
    private import SI::*;
    private import ISQ::*;

    calc def ModeEnergy {
        in power : PowerValue;
        in duration : TimeValue;
        return energy : EnergyValue = power * duration;
    }

    calc def RemainingEnergy {
        in capacity : EnergyValue;
        in spent : EnergyValue;
        return remaining : EnergyValue = capacity - spent;
    }

    calc def SoC {
        in remaining : EnergyValue;
        in capacity : EnergyValue;
        return soc : ScalarValues::Real = remaining / capacity;
    }

    constraint def ReserveConstraint {
        in soc : ScalarValues::Real;
        in socMin : ScalarValues::Real;
        soc >= socMin
    }

    part def ISRPlatform {
        attribute capacity : EnergyValue = 500 ['W⋅h'];
        attribute socMin : ScalarValues::Real = 0.2;
        attribute sensorPower : PowerValue = 12 [W];
        attribute commsPower : PowerValue = 45 [W];
        attribute missionTime : TimeValue = 6 [h];

        attribute spent : EnergyValue =
            ModeEnergy(sensorPower, missionTime) + ModeEnergy(commsPower, missionTime);
        attribute socEnd : ScalarValues::Real =
            SoC(RemainingEnergy(capacity, spent), capacity);

        assert constraint reserve : ReserveConstraint {
            in soc = socEnd;
            in socMin = ISRPlatform::socMin;
        }
    }

    requirement def EnduranceRequirement {
        subject platform : ISRPlatform;
        attribute socEnd : ScalarValues::Real;
        attribute socMin : ScalarValues::Real;
        require constraint { socEnd >= socMin }
    }

    analysis def EnduranceAnalysis {
        subject platform : ISRPlatform;
        requirement endurance : EnduranceRequirement;
        return socEnd : ScalarValues::Real;
        objective enduranceObjective {
            require endurance {
                :>> socEnd = EnduranceAnalysis::socEnd;
                :>> socMin = platform.socMin;
            }
        }
    }
}
