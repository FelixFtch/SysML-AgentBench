package RoundTripArchive {
    private import ScalarValues::*;
    part shore {
        attribute backhaulMbps : Real = 50.0;
        attribute archiveDays : Real = 30.0;
    }
    requirement def Archive {
        doc /* The shore archive keeps tracks for 30 days on a 50 Mbit/s backhaul. */
    }
}
