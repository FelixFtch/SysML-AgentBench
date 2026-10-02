from .linking_element import LinkingElement

class Subclassification(LinkingElement):
    # sources are AttributeDefinitions and targets are the parent class of the definitoins
    def __init__(self, id: str, ele_type: str, targets: list[str], sources: list[str]):
        super().__init__(id, ele_type, sources, targets)

    @classmethod
    def from_dict(cls, ele) -> "Subclassification":
        id = ele['@id']
        ele_type = ele['@type']
        
        targets = []
        if 'target' in ele:
            for member in ele['target']:
                targets.append(member['@id'])

        sources = []
        if 'source' in ele:
            for src in ele['source']:
                sources.append(src['@id'])

        return Subclassification(id, ele_type, targets, sources)

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return  type == "Subclassification"
