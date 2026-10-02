from .data_object import DataObject

class DataType(DataObject):
    def __init__(self, id: str, name: str, ele_type: str, qualified_name: str):
        super().__init__(id, name, ele_type, qualified_name)

    @classmethod
    def from_dict(cls, ele) -> "DataType":
        name = ele['declaredName']
        id = ele['@id']
        ele_type = ele['@type']
        qualified_name = ele.get("qualifiedName", "")


        return DataType(id, name, ele_type, qualified_name)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type == "DataType"
