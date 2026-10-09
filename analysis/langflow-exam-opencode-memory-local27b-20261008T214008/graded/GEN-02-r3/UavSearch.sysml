package UavSearch {
  port def TrackPort {}
  port def ImageryPort {}
  port def LinkPort {}

  part def Radar {
    port tracks : TrackPort;
  }

  part def Camera {
    port imagery : ImageryPort;
  }

  part def Processor {
    port trackIn : TrackPort;
    port imageryIn : ImageryPort;
    port uplink : LinkPort;
  }

  part def Radio {
    port fromProcessor : LinkPort;
    port toShore : LinkPort;
  }

  part uav {
    part searchRadar : Radar;
    part eoCamera : Camera;
    part processor : Processor;
    part radio : Radio;

    connection uav_searchRadar_tracks_to_uav_processor_trackIn connect uav.searchRadar.tracks to uav.processor.trackIn;
    connection uav_eoCamera_imagery_to_uav_processor_imageryIn connect uav.eoCamera.imagery to uav.processor.imageryIn;
    connection uav_processor_uplink_to_uav_radio_fromProcessor connect uav.processor.uplink to uav.radio.fromProcessor;
  }
}
