package MaritimeHazards {
    /* Synthetic STPA notes for the maritime scenario. These are not RTX hazards.
       They use ordinary requirement definitions so the official parser can load
       them without the DLR metadata library. */
    requirement def LossOfSeparation {
        doc /* Loss: a surface vessel collides because a track was not shared to the command ship. */
    }
    requirement def HazardTrackNotShared {
        doc /* Hazard: the unmanned surface vessel AIS track is absent on the command ship while the vessels are closing. This hazard can lead to LossOfSeparation. */
    }
}
