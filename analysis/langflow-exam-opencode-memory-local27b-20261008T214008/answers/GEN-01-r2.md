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

  connection usvcamproc : usv.camera.imagery to usv.processor.imageryIn;
  connection usvprocradio : usv.processor.uplink to usv.radio.fromProcessor;
  connection usvradioshore : usv.radio.toShore to commandShip.fromUsv;
}
```