# GEN-04 — synthetic, not an RTX specification

Package name: ShoreArchive

1. Port definition LinkPort and part definition Processor.
2. Part usage shore with port fromCommand of type LinkPort and nested part archive of Processor.
3. Attribute backhaulMbps value 50.0 and attribute archiveDays value 30.0, both Real, both on shore.
4. Requirement definition ShoreArchiveRetention whose doc comment says the shore archive keeps relayed tracks for 30 days.
