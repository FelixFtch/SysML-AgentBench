from rdflib import Graph, URIRef, Literal, Namespace
import re

from .dataobject_parser import DataObjectParser
from ..data_objects import DataObject, LinkingElement, Documentation, Subclassification, NamespaceImport

BASE_URI = "http://example.org/sysml#"
SYSML = Namespace(BASE_URI)
UUID_PATTERN = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$", re.IGNORECASE)

def _is_valid_id(value: str) -> bool:
    return bool(UUID_PATTERN.match(value.strip()))

class SlimRdfParser(DataObjectParser):
    def __init__(self, sysml_v2_json: dict):
        super().__init__(sysml_v2_json)
        self.graph = Graph()
        self.graph.bind("sysml", SYSML)


    def parse(self, format="turtle") -> str:
        super().parse()
        for obj in self.data_objects:
            self._add_to_graph(obj)
        return self.graph.serialize(format=format)
    
    def __get_predicate(self, obj) -> URIRef:
        predicate_str = f"{obj.__class__.__name__}"
        predicate = SYSML[f"has{obj.__class__.__name__}"]

        if obj.__class__ == Documentation:
            predicate = SYSML.comment
        elif obj.__class__ == Subclassification:
            predicate = SYSML.subClassOf
        elif obj.__class__ == NamespaceImport:
            predicate = SYSML.imports

        return predicate

    def _add_to_graph(self, obj: DataObject):
        id_index = self.get_id_index()

        def resolve_uri(obj_id: str) -> URIRef:
            ref_obj = id_index.get(obj_id)
            if ref_obj and ref_obj.qualified_name:
                path = ref_obj.qualified_name.replace("::", "/")
                return URIRef(f"{BASE_URI}{path}")
            elif ref_obj and ref_obj.name:
                return URIRef(f"{BASE_URI}{ref_obj.name}")
            elif ref_obj and ref_obj.value:
                return URIRef(f"{BASE_URI}{ref_obj.value}")
            return URIRef(f"{BASE_URI}{obj_id}")  # fallback

        # Linking elements (flattened)
        if isinstance(obj, LinkingElement):
            for source_id in obj.sources:
                source_uri = resolve_uri(source_id)
                for target in obj.targets:
                    predicate = self.__get_predicate(obj)

                    if isinstance(target, str) and _is_valid_id(target):
                        target_node = resolve_uri(target)
                    else:
                        target_node = Literal(target)

                    self.graph.add((source_uri, predicate, target_node))
            return

        # Named subject
        subject = URIRef(f"{BASE_URI}{obj.qualified_name.replace('::', '/')}") if obj.name else None
        if not subject:
            return

        # Core RDF triples
        # self.graph.add((subject, SYSML.hasId, Literal(obj.id)))
        self.graph.add((subject, SYSML.type, SYSML[obj.type]))
        self.graph.add((subject, SYSML.label, Literal(obj.name)))  # additional label
        # self.graph.add((subject, SYSML.name, Literal(obj.name)))

        # Structure
        if hasattr(obj, "members"):
            for m_id in obj.members:
                member_obj = id_index.get(m_id)
                if isinstance(member_obj, LinkingElement) or not member_obj:
                    continue
                self.graph.add((subject, SYSML.member, resolve_uri(m_id)))

        if hasattr(obj, "definitions"):
            for d_id in obj.definitions:
                self.graph.add((subject, SYSML.isDefinedBy, resolve_uri(d_id)))

        """ 
        # Since not everything has a owner field, the qualified_name should be enough to explain the owner
        if hasattr(obj, "owner_id"):
            self.graph.add((subject, SYSML.hasOwner, resolve_uri(obj.owner_id)))
        """
