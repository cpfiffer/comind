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
    
    # Set up the schema explicitly
    print("Setting up database schema...")
    try:
        db_manager.setup_schema()
        print("Schema setup complete.")
    except Exception as e:
        if "already exists" in str(e):
            print("Schema already exists, continuing with tests.")
        else:
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
            SET r.receivedAt = TIMESTAMP('2025-05-14T22:00:00Z')
        """, {'did': test_did})
        print("✓ Created test repo")
        
        # Store a test ATRecord
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
            labels=["ATRecord", "Post", "Test"]
        )
        
        print(f"✓ Created test ATProto record: {result}")
    except Exception as e:
        print(f"Error creating test record: {e}")
        for i, record in enumerate(records):
            uri = record.get('uri', 'Unknown URI')
            nsid = record.get('nsid', 'Unknown NSID')
            labels = record.get('labels', [])
            
            print(f"{i+1}. {nsid} - {uri}")
            print(f"   Labels: {', '.join(labels)}")
            print()
    except Exception as e:
        print(f"Error listing ATProto records: {e}")
    
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
    
    # Query relationships
    print_section("Relationships")
    try:
        # Get the first post record to use as a source
        post_records = db_manager.list_atproto_records(nsid="app.bsky.feed.post", limit=1)
        
        if post_records:
            source_uri = post_records[0]['uri']
            print(f"Querying relationships for {source_uri}")
            
            relationships = db_manager.query_atproto_relationships(source_uri, limit=10)
            print(f"Found {len(relationships)} relationships")
            
            for i, rel in enumerate(relationships):
                rel_type = rel.get('type', 'Unknown')
                target_uri = rel.get('target_uri', 'Unknown target')
                
                print(f"{i+1}. {rel_type} -> {target_uri}")
        else:
            print("No post records found to query relationships")
    except Exception as e:
        print(f"Error querying relationships: {e}")
    
    # Test searching
    print_section("Text Search")
    try:
        search_text = "AI"
        print(f"Searching for '{search_text}'...")
        
        # Check if db_manager has the find_similar_records method
        if not hasattr(db_manager, 'find_similar_records'):
            print("find_similar_records method not available, using _find_records_basic")
            results = db_manager._find_records_basic(search_text, limit=5)
        else:
            try:
                # Try full-text search first
                results = db_manager.find_similar_records(search_text, limit=5)
            except Exception as search_error:
                print(f"Full-text search failed: {search_error}")
                print("Falling back to basic search...")
                results = db_manager._find_records_basic(search_text, limit=5)
        
        print(f"Search found {len(results)} results")
        
        for i, result in enumerate(results):
            uri = result.get('uri', 'Unknown URI')
            collection = result.get('collection', 'Unknown collection')
            value = result.get('value', {})
            
            content_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            print(f"{i+1}. {collection} - {uri}")
            print(f"   Content: {content_preview}")
            print()
    except Exception as e:
        print(f"Error during search: {e}")
        print("Skipping search test due to error")
    
    print_header("Tests Completed")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        sys.exit(1)