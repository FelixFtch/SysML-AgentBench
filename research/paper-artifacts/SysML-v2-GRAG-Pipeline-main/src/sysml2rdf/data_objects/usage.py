from .data_object import DataObject

class Usage(DataObject):
    def __init__(self, id: str, name: str, ele_type: str, qualified_name: str, members: list[str], definitions: list[str]):
        super().__init__(id, name, ele_type, qualified_name)
        self.members = members
        self.definitions = definitions

    @classmethod
    def from_dict(cls, ele) -> "Usage":
        name = ele['declaredName']
        id = ele['@id']
        ele_type = ele['@type']
        qualified_name = ele.get("qualifiedName", "")

        
        members = []
        if 'member' in ele:
            for member in ele['member']:
                members.append(member['@id'])

        definitions = []
        if 'definition' in ele:
            for defin in ele['definition']:
                definitions.append(defin['@id'])

        return Usage(id, name, ele_type, qualified_name, members, definitions)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type.endswith("Usage")
