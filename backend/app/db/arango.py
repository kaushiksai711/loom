from arango import ArangoClient
from backend.app.core.config import settings
import sys

class ArangoDB:
    def __init__(self):
        self.client = ArangoClient(hosts=settings.ARANGO_HOST)
        self.sys_db = self.client.db('_system', username=settings.ARANGO_USERNAME, password=settings.ARANGO_PASSWORD)
        self.db = None

    def initialize(self):
        try:
            if not self.sys_db.has_database(settings.ARANGO_DB_NAME):
                self.sys_db.create_database(settings.ARANGO_DB_NAME)
            
            self.db = self.client.db(settings.ARANGO_DB_NAME, username=settings.ARANGO_USERNAME, password=settings.ARANGO_PASSWORD)
            
            # Initialize Document Collections
            doc_collections = ["Concepts", "Sessions", "Seeds"]
            for col in doc_collections:
                if not self.db.has_collection(col):
                    self.db.create_collection(col)
            
            # Initialize Edge Collection
            if self.db.has_collection("Relationships"):
                col = self.db.collection("Relationships")
                if not col.properties()['edge']:
                    # Wrong type, need to recreate
                    print("Dropping incorrect 'Relationships' collection (was document, must be edge)")
                    self.db.delete_collection("Relationships")
                    self.db.create_collection("Relationships", edge=True)
            else:
                self.db.create_collection("Relationships", edge=True)
            
            # Initialize Edge Definitions (if needed for graph)
            # Initialize Edge Definitions (Critical for Graph Traversal)
            if not self.db.has_graph('concept_graph'):
                graph = self.db.create_graph('concept_graph')
                # Define "related_to" edge definition: Seeds -> Relationships -> Seeds
                if not graph.has_edge_definition("Relationships"):
                    graph.create_edge_definition(
                        edge_collection="Relationships",
                        from_vertex_collections=["Seeds", "Concepts"],
                        to_vertex_collections=["Seeds", "Concepts"]
                    )
            else:
                # Ensure edge definition exists for existing graph
                graph = self.db.graph('concept_graph')
                if not graph.has_edge_definition("Relationships"):
                     graph.create_edge_definition(
                        edge_collection="Relationships",
                        from_vertex_collections=["Seeds", "Concepts"],
                        to_vertex_collections=["Seeds", "Concepts"]
                    )
                
            print(f"Connected to ArangoDB: {settings.ARANGO_DB_NAME}")
            return self.db
        except Exception as e:
            print(f"Failed to connect to ArangoDB: {e}")
            sys.exit(1)

    def get_db(self):
        if not self.db:
            self.initialize()
        return self.db

db = ArangoDB()
