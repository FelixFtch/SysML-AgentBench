from .parser import Parser

import json
import networkx as nx
from pathlib import Path
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS

SYSML = Namespace("http://example.org/sysml/")


class RdfParser(Parser):
    def __init__(self, sysml_v2_json):
        super().__init__(sysml_v2_json)

    def parse(self, format="turtle") -> str:
        data = self.raw_data

        # Create directed graph
        G = nx.DiGraph()

        # Pass 1: Add nodes
        for obj in data:
            node_id = obj.get('@id')
            if not node_id:
                continue
            G.add_node(node_id, **{
                k: v for k, v in obj.items()
                if not isinstance(v, dict) and not isinstance(v, list) and not k.startswith('@')
            })
            if '@type' in obj:
                G.nodes[node_id]['type'] = obj['@type']

        # Pass 2: Add edges
        for obj in data:
            source = obj.get('@id')
            if not source:
                continue
            for key, value in obj.items():
                if key.startswith('@'):
                    continue
                if isinstance(value, dict) and '@id' in value:
                    G.add_edge(source, value['@id'], label=key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and '@id' in item:
                            G.add_edge(source, item['@id'], label=key)

        # Convert to RDF
        rdf_graph = Graph()
        rdf_graph.bind("sysml", SYSML)

        for node_id, attrs in G.nodes(data=True):
            subj = URIRef(f"http://example.org/sysml/{node_id}")
            if 'type' in attrs:
                rdf_graph.add((subj, RDF.type, SYSML[attrs['type']]))
            for key, val in attrs.items():
                if key == "type":
                    continue
                rdf_graph.add((subj, SYSML[key], Literal(val)))

        # Add edges as RDF triples
        for u, v, d in G.edges(data=True):
            subj = URIRef(f"http://example.org/sysml/{u}")
            obj = URIRef(f"http://example.org/sysml/{v}")
            pred = SYSML[d['label']]
            rdf_graph.add((subj, pred, obj))

        return rdf_graph.serialize(format=format)
