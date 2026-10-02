from .data_object import DataObject

class Package(DataObject):
    def __init__(self, id: str, name: str, ele_type: str, qualified_name: str, members: list[str]):
        super().__init__(id, name, ele_type, qualified_name)
        self.members = members

    @classmethod
    def from_dict(cls, ele) -> "Package":
        name = ele['declaredName']
        id = ele['@id']
        ele_type = ele['@type']
        qualified_name = ele.get("qualifiedName", "")

        
        members: list[str] = []
        if "member" in ele:
            for member in ele['member']:
                members.append(member['@id'])

        return Package(id, name, ele_type, qualified_name, members)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type == "Package"
