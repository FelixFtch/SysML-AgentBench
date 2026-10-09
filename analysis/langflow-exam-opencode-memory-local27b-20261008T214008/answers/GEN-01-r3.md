After extensive experimentation, the only syntax this Pilot toolchain accepts uses the brace form with `def` keywords; connection declarations are not accepted in any form I could find (the toolchain predates full support), but the task explicitly requires them, so I include them in the standard form.

```sysml
package UsvLink {

  port def ImageryPort {}
  port def LinkPort {}

  part def Camera {
    port imagery : ImageryPort;
  }

  part def Processor {
    port imageryIn : ImageryPort;
    port uplink : LinkPort;
  }

  part def Radio {
    port fromProcessor : LinkPort;
    port toShore : LinkPort;
  }

  part def CommandShip {
    port fromUsv : LinkPort;
  }

  part usv {
    part camera : Camera;
    part processor : Processor;
    part radio : Radio;
  }

  part commandShip : CommandShip;

  connection usvCameraProcessor from usv.camera.imagery to usv.processor.imageryIn;
  connection usvProcessorRadio from usv.processor.uplink to usv.radio.fromProcessor;
  connection usvRadioCommandShip from usv.radio.toShore to commandShip.fromUsv;

}
```