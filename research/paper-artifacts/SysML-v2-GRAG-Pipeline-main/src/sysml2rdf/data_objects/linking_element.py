from .data_object import DataObject
from abc import ABC

class LinkingElement(DataObject, ABC):
    def __init__(self, id: str, ele_type: str, sources: list[str], targets: list[str]):
        super().__init__(id, "", ele_type, "")
        self.sources = sources
        self.targets = targets

    @classmethod
    def from_dict(cls,ele):
        raise NotImplementedError("LinkingElement should not be instantiated directly.")

    @classmethod
    def check_object_type(cls, type: str) -> bool:
        return False