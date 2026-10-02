from .data_object import DataObject

class LibraryPackage(DataObject):
    # sources are AttributeDefinitions and targets are the parent class of the definitoins
    def __init__(self, id: str, ele_type: str, qualified_name: str):
        super().__init__(id, "", ele_type, qualified_name)

    @classmethod
    def from_dict(cls, ele) -> "LibraryPackage":
        id = ele['@id']
        ele_type = ele['@type']
        qualified_name = ele.get("qualifiedName", "")

        return LibraryPackage(id, ele_type, qualified_name)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type == "LibraryPackage"
