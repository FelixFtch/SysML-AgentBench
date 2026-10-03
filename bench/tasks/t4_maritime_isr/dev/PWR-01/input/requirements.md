# PWR-01 (development) — synthetic, not an RTX specification

Package name: PowerCheck

One unmanned surface vessel has a power limit of 60 W. Model that limit as attribute powerLimitW on part usv, equal to 60.0.

The vessel carries two powered parts:
- eoCamera, attribute drawW equal to 41.0
- computer, attribute drawW equal to 25.0

Do not change 60. The model only has to contain these three numbers and the two nested parts. No other equipment.
