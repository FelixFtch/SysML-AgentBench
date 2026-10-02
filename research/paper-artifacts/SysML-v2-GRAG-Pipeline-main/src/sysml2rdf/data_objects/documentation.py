from .linking_element import LinkingElement

class Documentation(LinkingElement):
    def __init__(self, id: str, ele_type: str, source_id: str, body: str):
        super().__init__(id, ele_type, sources=[source_id], targets=[body])
        self.body = body 

    @classmethod
    def from_dict(cls, ele) -> "Documentation":
        id = ele['@id']
        body = ele.get("body", "")
        ele_type = ele['@type']
        owner = ele.get("owner", {}).get("@id", "")

        return cls(id, ele_type, owner, body)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return type.endswith("Documentation")
