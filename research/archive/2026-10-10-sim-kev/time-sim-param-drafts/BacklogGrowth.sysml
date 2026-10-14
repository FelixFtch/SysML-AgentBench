package BacklogGrowth {
    private import SI::*;
    private import ISQ::*;
    private import ISQInformation::*;

    attribute <'Mbit'> megabit : StorageCapacityUnit = 1000000 * SI::bit;
    attribute <'Mbit/s'> 'megabit per second' : BinaryDigitRateUnit = 1000000 * SI::'bit/s';

    calc def PeakBacklog {
        in source : BinaryDigitRateValue;
        in downlink : BinaryDigitRateValue;
        in outage : TimeValue;
        return peak : StorageCapacityValue = (source - downlink) * outage;
    }

    calc def DrainTime {
        in backlog : StorageCapacityValue;
        in source : BinaryDigitRateValue;
        in downlink : BinaryDigitRateValue;
        return drain : TimeValue =
            if downlink > source ? backlog / (downlink - source) else 0.0 [s];
    }

    constraint def BufferFits {
        in peak : StorageCapacityValue;
        in capacity : StorageCapacityValue;
        peak <= capacity
    }

    part def RelayNode {
        attribute sensorRate : BinaryDigitRateValue = 8 ['Mbit/s'];
        attribute downlinkRate : BinaryDigitRateValue = 4 ['Mbit/s'];
        attribute outageWindow : TimeValue = 20 [min];
        attribute bufferCapacity : StorageCapacityValue = 4000 ['Mbit'];

        attribute peakBacklog : StorageCapacityValue =
            PeakBacklog(sensorRate, downlinkRate, outageWindow);
        attribute recoveryTime : TimeValue =
            DrainTime(peakBacklog, sensorRate, downlinkRate);

        assert constraint fits : BufferFits {
            in peak = peakBacklog;
            in capacity = bufferCapacity;
        }
    }

    requirement def BacklogRequirement {
        subject node : RelayNode;
        attribute peak : StorageCapacityValue;
        attribute capacity : StorageCapacityValue;
        require constraint { peak <= capacity }
    }
}
