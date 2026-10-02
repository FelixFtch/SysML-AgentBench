from abc import ABC, abstractmethod


class DataObject(ABC):
    _subclasses = []

    def __init__(self, id: str, name: str, ele_type: str, qualified_name: str):
        self.id = id
        self.name = name
        self.type = ele_type
        self.qualified_name = qualified_name.replace(" ", "_")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'from_dict') or not callable(cls.from_dict):
            raise NotImplementedError(f"{cls.__name__} must implement from_dict")
        DataObject._subclasses.append(cls)

    @abstractmethod
    def from_dict(cls,ele):
        pass

    @abstractmethod
    def check_object_type(cls, type: str) -> bool:
        pass

    @classmethod
    def get_parser(cls, ele_type: str):
        for subclass in cls._subclasses:
            if subclass.check_object_type(ele_type):
                return subclass
        raise ValueError(f"No parser found for type {ele_type}")
    
    def check_id(self, id):
        return self.id == id
