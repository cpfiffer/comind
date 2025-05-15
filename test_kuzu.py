from src.db_manager import DBManager
import logging
import json
import sys

# Configure logging to show debug messages
logging.basicConfig(level=logging.INFO)

def print_header(text):
    """Print a header with decoration"""
    print(f"\n{'=' * 40}")
    print(f"   {text}")
    print(f"{'=' * 40}\n")

def print_section(text):
    """Print a section header"""
    print(f"\n--- {text} ---")

def main():
    print_header("Testing Kuzu Database ATProto Integration")
    
    # Initialize the database manager
    print("Initializing database...")
    db_path = "./demo_db"
    db_manager = DBManager(db_path)
    print("Database manager initialized.")
    
    # Set up the schema explicitly with force=True to reset everything
    print("Setting up database schema...")
    try:
        db_manager.setup_schema(force=True)
        print("Schema setup complete.")
    except Exception as e:
        print(f"Error setting up schema: {e}")
        print("Continuing anyway to see what works...")
    
    # Create a test record
    print_section("Creating Test ATProto Record")
    try:
        test_did = "did:test:user123"
        test_rkey = "testatrecord123"
        test_uri = f"at://{test_did}/app.bsky.feed.post/{test_rkey}"
        
        # Store a test repo
        db_manager.conn.execute("""
            MERGE (r:Repo {did: $did})
            SET r.handle = $did,
                r.receivedAt = timestamp($receivedAt)
        """, {'did': test_did, 'receivedAt': '2025-05-14T22:00:00Z'})
        print("✓ Created test repo")
        
        # Store a test ATProto record
        test_record = {
            "text": "This is a test post about AI and KuzuDB integration",
            "createdAt": "2025-05-14T22:00:00Z"
        }
        
        result = db_manager.store_atproto_record(
            uri=test_uri,
            cid="testcid123",
            nsid="app.bsky.feed.post",
            record=test_record,
            author_did=test_did,
            rkey=test_rkey,
            labels=["Record", "Post", "Test"]
        )
        
        print(f"✓ Created test ATProto record: {result}")
        
        # Store a test Concept record
        test_concept_uri = f"at://{test_did}/me.comind.blip.concept/test-concept"
        test_concept_record = {
            "createdAt": "2025-05-14T22:05:00Z",
            "generated": {
                "text": "graph databases"
            },
            "from": [
                {
                    "uri": test_uri,
                    "cid": "testcid123"
                }
            ]
        }
        
        result = db_manager.store_atproto_record(
            uri=test_concept_uri,
            cid="conceptcid123",
            nsid="me.comind.blip.concept",
            record=test_concept_record,
            author_did=test_did,
            rkey="test-concept",
            labels=["Record", "Blip", "Concept"]
        )
        
        print(f"✓ Created test Concept record: {result}")
        
        # Store a test Thought record
        test_thought_uri = f"at://{test_did}/me.comind.blip.thought/test-thought"
        test_thought_record = {
            "createdAt": "2025-05-14T22:07:00Z",
            "generated": {
                "thoughtType": "analysis",
                "context": "Database integration",
                "text": "Graph databases like KuzuDB offer significant advantages for storing interconnected ATProto records",
                "evidence": ["https://docs.kuzudb.com"],
                "alternatives": ["Traditional SQL databases could also work but with more complex queries"]
            },
            "from": [
                {
                    "uri": test_uri,
                    "cid": "testcid123"
                }
            ]
        }
        
        result = db_manager.store_atproto_record(
            uri=test_thought_uri,
            cid="thoughtcid123",
            nsid="me.comind.blip.thought",
            record=test_thought_record,
            author_did=test_did,
            rkey="test-thought",
            labels=["Record", "Blip", "Thought"]
        )
        
        print(f"✓ Created test Thought record: {result}")
        
        # Store a test Emotion record
        test_emotion_uri = f"at://{test_did}/me.comind.blip.emotion/test-emotion"
        test_emotion_record = {
            "createdAt": "2025-05-14T22:08:00Z",
            "generated": {
                "emotionType": "enthusiasm",
                "text": "Excited about the potential of graph databases for interconnected social data"
            },
            "from": [
                {
                    "uri": test_uri,
                    "cid": "testcid123"
                }
            ]
        }
        
        result = db_manager.store_atproto_record(
            uri=test_emotion_uri,
            cid="emotioncid123",
            nsid="me.comind.blip.emotion",
            record=test_emotion_record,
            author_did=test_did,
            rkey="test-emotion",
            labels=["Record", "Blip", "Emotion"]
        )
        
        print(f"✓ Created test Emotion record: {result}")
        
        # Store a test Sphere record
        test_sphere_uri = f"at://{test_did}/me.comind.sphere.core/test-sphere"
        test_sphere_record = {
            "createdAt": "2025-05-14T22:10:00Z",
            "title": "Test Sphere",
            "text": "A test sphere for KuzuDB integration",
            "description": "Testing the sphere functionality"
        }
        
        result = db_manager.store_atproto_record(
            uri=test_sphere_uri,
            cid="spherecid123",
            nsid="me.comind.sphere.core",
            record=test_sphere_record,
            author_did=test_did,
            rkey="test-sphere",
            labels=["Record", "Core"]
        )
        
        print(f"✓ Created test Sphere record: {result}")
        
        # Store a test Link record
        test_link_uri = f"at://{test_did}/me.comind.relationship.link/test-link"
        test_link_record = {
            "createdAt": "2025-05-14T22:15:00Z",
            "relationship": "REFERENCES",
            "strength": 0.9,
            "note": "Test link relationship",
            "target": test_concept_uri,
            "source": {
                "uri": test_uri,
                "cid": "testcid123"
            }
        }
        
        result = db_manager.store_atproto_record(
            uri=test_link_uri,
            cid="linkcid123",
            nsid="me.comind.relationship.link",
            record=test_link_record,
            author_did=test_did,
            rkey="test-link",
            labels=["Record", "Relationship", "Link"]
        )
        
        print(f"✓ Created test Link record: {result}")
        
    except Exception as e:
        print(f"Error creating test record: {e}")
        raise e
    
    # List the Record nodes
    print_section("ATProto Record Nodes")
    try:
        records = db_manager.list_atproto_records(limit=5)
        print(f"Found {len(records)} ATProto records")
        
        for i, record in enumerate(records):
            uri = record.get('uri', 'Unknown URI')
            nsid = record.get('nsid', 'Unknown NSID')
            labels = record.get('labels', [])
            
            print(f"{i+1}. {nsid} - {uri}")
            print(f"   Labels: {', '.join(labels) if labels else '(none)'}")
            
            # Debug properties
            if 'createdAt' in record:
                print(f"   Created: {record['createdAt']}")
            if 'receivedAt' in record:
                print(f"   Received: {record['receivedAt']}")
            else:
                print("   receivedAt property missing")
                
            print()
    except Exception as e:
        print(f"Error listing ATProto records: {e}")
        raise e
        
    # Count records by NSID
    print_section("Record Counts by NSID")
    try:
        nsids = [
            "app.bsky.feed.post",
            "me.comind.blip.concept",
            "me.comind.blip.thought",
            "me.comind.blip.emotion",
            "me.comind.sphere.core"
        ]
        
        for nsid in nsids:
            records = db_manager.list_atproto_records(nsid=nsid, limit=1000)
            print(f"{nsid}: {len(records)} records")
    except Exception as e:
        print(f"Error counting records: {e}")
        raise e
    # Query relationships
    print_section("Relationships")
    try:
        # Get the link record to test relationships
        link_records = db_manager.list_atproto_records(nsid="me.comind.relationship.link", limit=1)
        
        if link_records:
            source_uri = link_records[0]['uri']
            print(f"Querying relationships for {source_uri}")
            
            relationships = db_manager.query_atproto_relationships(source_uri, relationship_type="LINKS", limit=10)
            print(f"Found {len(relationships)} relationships")
            
            for i, rel in enumerate(relationships):
                rel_type = rel.get('type', 'Unknown')
                target_uri = rel.get('target_uri', 'Unknown target')
                
                print(f"{i+1}. {rel_type} -> {target_uri}")
        else:
            print("No link records found to query relationships")
    except Exception as e:
        print(f"Error querying relationships: {e}")
        raise e 
            
    # Test searching
    print_section("Text Search")
    try:
        search_text = "AI"
        print(f"Searching for '{search_text}'...")
        
        # Use the basic search method which should be more reliable
        results = db_manager._find_records_basic(search_text, limit=5)
        print(f"Basic search found {len(results)} results")
        
        for i, result in enumerate(results):
            uri = result.get('uri', 'Unknown URI')
            nsid = result.get('nsid', 'Unknown collection')
            value = result.get('value', {})
            
            content_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            print(f"{i+1}. {nsid} - {uri}")
            print(f"   Content: {content_preview}")
            print()
            
        # Only try FTS search if basic search worked
        if len(results) > 0:
            try:
                print("Testing full-text search...")
                fts_results = db_manager.find_similar_records(search_text, limit=5)
                print(f"Full-text search found {len(fts_results)} results")
            except Exception as search_error:
                print(f"Full-text search failed: {search_error}")
    except Exception as e:
        print(f"Error during search: {e}")
        print("Skipping search test due to error")

    print_header("Tests Completed")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        
        raise e
        sys.exit(1)