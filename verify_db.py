from backend.app.db.arango import db
import sys

def verify_data():
    try:
        database = db.get_db()
        
        # Check Sessions
        sessions_col = database.collection("Sessions")
        session_count = sessions_col.count()
        print(f"✅ Sessions Collection: {session_count} documents")
        
        if session_count > 0:
            # python-arango sort syntax is different or we can just iterate cursor
            # Simple iteration for now as sort syntax varies by driver version
            cursor = sessions_col.all(limit=1)
            print(f"   Latest Session: {cursor.next()['title']}")

        # Check Seeds
        seeds_col = database.collection("Seeds")
        seed_count = seeds_col.count()
        print(f"✅ Seeds Collection: {seed_count} documents")
        
        if seed_count > 0:
            # Fetch last 3 seeds
            cursor = seeds_col.all(limit=3)
            print("   Latest Seeds:")
            for doc in cursor:
                print(f"   - {doc['highlight'][:50]}...")
                
    except Exception as e:
        print(f"❌ Error verifying data: {e}")

if __name__ == "__main__":
    verify_data()
