from ..data_objects import DataObject

class Parser:
    def __init__(self, sysml_v2_json: dict):
        self.raw_data = sysml_v2_json
        
    def parse(self, format="turtle") -> str:
        raise NotImplementedError()