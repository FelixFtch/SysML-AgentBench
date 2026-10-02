from ..data_objects import DataObject
from .parser import Parser

class DataObjectParser(Parser):
    def __init__(self, sysml_v2_json: dict):
        super().__init__(sysml_v2_json)
        self.data_objects: list[DataObject] = []

    def get_data_objects(self) -> list[DataObject]:
        return self.data_objects

    def _parse_to_data_objects(self) -> list[DataObject]:
        self.data_objects: list[DataObject] = []

        for ele in self.raw_data:
            ele_type = ele.get("@type")
            if not ele_type:
                print(f"Skipped due to missing type: {ele}")
                continue  

            try:
                parser_cls = DataObject.get_parser(ele_type)
                parsed = parser_cls.from_dict(ele)
                self.data_objects.append(parsed)

            except ValueError as e:
                print(f"No parsing class for type: {ele_type}")
            except Exception as e:
                print(f"Error for parsing {ele_type}: {str(e)}")
        
    def parse(self, format="turtle") -> list[DataObject]:
        return self._parse_to_data_objects()
    
    def get_id_index(self) -> dict[str, DataObject]:
        return {obj.id: obj for obj in self.data_objects}