package ShoreArchive {
  private import ScalarValues::*;
  port def LinkPort;
  part def Processor;
  part def shore {
    port fromCommand : LinkPort;
    part archive : Processor;
    attribute backhaulMbps : Real = 50.0;
    attribute archiveDays : Real = 30.0;
  }
  /* The shore archive keeps relayed tracks for 30 days. */
  requirement def ShoreArchiveRetention;
}
