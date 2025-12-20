import pytest
from backend.app.db.arango import db
from backend.app.core.config import settings

def test_arango_connection():
    database = db.get_db()
    assert database is not None
    assert database.name == settings.ARANGO_DB_NAME

def test_collections_exist():
    database = db.get_db()
    collections = ["Concepts", "Relationships", "Sessions", "Seeds"]
    for col in collections:
        assert database.has_collection(col)

def test_graph_exists():
    database = db.get_db()
    assert database.has_graph('concept_graph')
