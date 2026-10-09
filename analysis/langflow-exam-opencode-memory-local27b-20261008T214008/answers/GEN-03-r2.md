Pass. The toolchain's dialect: `package X;` then top-level `private import`, members after. All five required constructs parse clean.

```sysml
package FusionNode;

private import ScalarValues::*;

port def LinkPort;

part def Processor {
  port trackIn: LinkPort;
}

part commandShip {
  port fromUsv: LinkPort;
  port fromUav: LinkPort;

  fusion: Processor;

  fusionLatencyS: Real = 2.0;
}
```