from .data_object import DataObject

class Definition(DataObject):
    def __init__(self, id: str, name: str, ele_type: str, qualified_name: str, owner_id: str, members: list[str], owned_subclassification: list[str]):
        super().__init__(id, name, ele_type, qualified_name)
        self.owner_id = owner_id
        self.members = members
        self.owned_subclassification = owned_subclassification

    @classmethod
    def from_dict(cls, ele) -> "Definition":
        name = ele['declaredName']
        id = ele['@id']
        owner_id = ele["owner"]["@id"]
        ele_type = ele['@type']
        qualified_name = ele.get("qualifiedName", "")
        
        members = []
        if 'member' in ele:
            for member in ele['member']:
                members.append(member['@id'])

        owned_subclassification = []
        if 'ownedSubclassification' in ele:
            for sub in ele['ownedSubclassification']:
                owned_subclassification.append(sub['@id'])

        return Definition(id, name, ele_type, qualified_name, owner_id, members, owned_subclassification)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type.endswith("Definition")
