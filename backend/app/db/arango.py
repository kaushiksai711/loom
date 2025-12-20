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
            
            # Initialize Collections
            collections = ["Concepts", "Relationships", "Sessions", "Seeds"]
            for col in collections:
                if not self.db.has_collection(col):
                    self.db.create_collection(col)
            
            # Initialize Edge Definitions (if needed for graph)
            if not self.db.has_graph('concept_graph'):
                self.db.create_graph('concept_graph')
                
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
