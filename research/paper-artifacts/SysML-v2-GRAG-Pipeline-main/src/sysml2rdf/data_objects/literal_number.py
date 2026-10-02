from .data_object import DataObject

class LiteralNumber(DataObject):
    def __init__(self, id: str, ele_type: str, value):
        super().__init__(id, "", ele_type, "")
        self.value = value

    @classmethod
    def from_dict(cls, ele) -> "LiteralNumber":
        id = ele['@id']
        ele_type = ele['@type']
        value = ele.get("value", "")

        return LiteralNumber(id, ele_type, value)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type == "LiteralRational" or type == "LiteralInteger"
