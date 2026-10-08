package UavSearch {
  port def TrackPort;
  port def ImageryPort;
  port def LinkPort;

  part def Radar {
    port tracks: TrackPort;
  }

  part def Camera {
    port imagery: ImageryPort;
  }

  part def Processor {
    port trackIn: TrackPort;
    port imageryIn: ImageryPort;
    port uplink: LinkPort;
  }

  part def Radio {
    port fromProcessor: LinkPort;
    port toShore: LinkPort;
  }

  part uav {
    part searchRadar: Radar;
    part eoCamera: Camera;
    part processor: Processor;
    part radio: Radio;

    connect searchRadar.tracks to processor.trackIn;
    connect eoCamera.imagery to processor.imageryIn;
    connect processor.uplink to radio.fromProcessor;
  }
}
