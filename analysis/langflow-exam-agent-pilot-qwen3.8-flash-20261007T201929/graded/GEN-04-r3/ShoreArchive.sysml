package ShoreArchive {
  private import ScalarValues::*;

  port def LinkPort {}

  part def Processor {}

  part shore {
    port fromCommand : LinkPort;
    part archive : Processor;
    attribute backhaulMbps : Real = 50.0;
    attribute archiveDays : Real = 30.0;
  }

  requirement def ShoreArchiveRetention {
    doc /* The shore archive keeps relayed tracks for 30 days. */
  }
}
