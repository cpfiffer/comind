from src.db_manager import DBManager
import logging
from datetime import datetime
import sys
import json

# Configure logging to only show errors
logging.basicConfig(level=logging.ERROR)

def print_header(text):
    """Print a header with decoration"""
    print(f"\n{'=' * 40}")
    print(f"   {text}")
    print(f"{'=' * 40}\n")

def print_section(text):
    """Print a section header"""
    print(f"\n--- {text} ---")

def check_value(name, value, expected):
    """Check if a value matches the expected value and print result"""
    if value == expected:
        print(f"✅ {name}: PASS")
    else:
        print(f"❌ {name}: FAIL")
        print(f"   Expected: {expected}")
        print(f"   Got: {value}")

def main():
    print_header("Testing Kuzu Database Integration")
    
    # Initialize the database manager
    print("Initializing database...")
    db_manager = DBManager('./demo_db')
    print("Database manager initialized.")
    
    # Test schema creation
    print_section("Schema Setup")
    try:
        db_manager.setup_schema()
        print("Schema setup complete.")
    except Exception as e:
        if "already exists" in str(e):
            print("Schema already exists, continuing with tests.")
        else:
            print(f"Warning: Schema setup encountered an issue: {e}")
            print("Continuing with tests anyway...")
    
    # Test record creation
    print_section("Creating Test Records")
    test_user_did = "did:test:user123"
    current_time = datetime.now().isoformat()
    
    # Test storing a user
    try:
        db_manager.store_user(
            did=test_user_did,
            handle="testuser",
            display_name="Test User",
            description="This is a test user"
        )
        print("✓ Created test user")
    except Exception as e:
        print(f"✗ Failed to create user: {e}")
    
    # Test storing a sphere
    sphere_uri = f"at://{test_user_did}/me.comind.sphere.core/test-sphere"
    try:
        db_manager.store_record(
            collection="me.comind.sphere.core",
            record={
                "title": "Test Sphere",
                "text": "This is a test sphere.",
                "description": "A sphere for testing",
                "createdAt": current_time
            },
            uri=sphere_uri,
            cid="testcid123",
            author_did=test_user_did,
            rkey="test-sphere"
        )
        print("✓ Created test sphere")
    except Exception as e:
        print(f"✗ Failed to create sphere: {e}")
    
    # Test storing a concept
    concept_uri = f"at://{test_user_did}/me.comind.blip.concept/test-concept"
    try:
        db_manager.store_record(
            collection="me.comind.blip.concept",
            record={
                "text": "test concept",
                "createdAt": current_time
            },
            uri=concept_uri,
            cid="testcid456",
            author_did=test_user_did,
            rkey="test-concept",
            sphere_uri=sphere_uri
        )
        print("✓ Created test concept")
    except Exception as e:
        print(f"✗ Failed to create concept: {e}")
    
    # Test storing a relationship
    link_uri = f"at://{test_user_did}/me.comind.relationship.link/test-link"
    try:
        db_manager.store_record(
            collection="me.comind.relationship.link",
            record={
                "relationship": "associated",
                "target": concept_uri,
                "strength": 0.8,
                "note": "Test relation",
                "createdAt": current_time
            },
            uri=link_uri,
            cid="testcid789",
            author_did=test_user_did,
            rkey="test-link"
        )
        print("✓ Created test relationship")
    except Exception as e:
        print(f"✗ Failed to create relationship: {e}")
    
    # Test record retrieval
    print_section("Record Retrieval Tests")
    
    # Get sphere record by rkey
    try:
        sphere = db_manager.get_record("me.comind.sphere.core", "test-sphere")
        sphere_found = sphere is not None
        check_value("Get sphere by rkey", sphere_found, True)
        if sphere:
            check_value("Sphere title", sphere.get("title"), "Test Sphere")
    except Exception as e:
        print(f"✗ Error retrieving sphere by rkey: {e}")
    
    # Get sphere record by URI
    try:
        sphere_by_uri = db_manager.get_record_by_uri(sphere_uri)
        sphere_by_uri_found = sphere_by_uri is not None
        check_value("Get sphere by URI", sphere_by_uri_found, True)
    except Exception as e:
        print(f"✗ Error retrieving sphere by URI: {e}")
    
    # List records from collection
    try:
        concepts = db_manager.list_records("me.comind.blip.concept")
        has_concepts = len(concepts) >= 1
        check_value("List concepts collection", has_concepts, True)
        if has_concepts:
            print(f"  Found {len(concepts)} concepts")
    except Exception as e:
        print(f"✗ Error listing concepts: {e}")
    
    # Test text search using fallback
    print_section("Text Search Tests")
    try:
        search_results = db_manager._find_records_basic("test", None, 10)
        basic_search_found = len(search_results) >= 1
        check_value("Basic search found results", basic_search_found, True)
        if basic_search_found:
            print(f"  Found {len(search_results)} records with basic search")
    except Exception as e:
        print(f"✗ Error in basic search: {e}")
    
    # Test full-text search (may fail if FTS extension is not available)
    # try:
    #     fts_results = db_manager.find_similar_records("test")
    #     fts_found = len(fts_results) >= 1
    #     check_value("Full-text search found results", fts_found, True)
    #     if fts_found:
    #         print(f"  Found {len(fts_results)} records with full-text search")
    # except Exception as e:
    #     print(f"ℹ️ Full-text search test: SKIPPED - {str(e)}")
    
    # Test relationship queries
    print_section("Relationship Tests")
    try:
        relationships = db_manager.query_relationships(sphere_uri)
        has_relationships = len(relationships) >= 1
        check_value("Relationship query returned results", has_relationships, True)
        
        if has_relationships:
            print(f"  Found {len(relationships)} relationships from sphere")
            rel = relationships[0]
            check_value("Relationship source correct", rel.get('source_uri'), sphere_uri)
    except Exception as e:
        print(f"✗ Error in relationship query: {e}")
    
    # Test relationship query with specific type
    try:
        typed_relationships = db_manager.query_relationships(sphere_uri, rel_type="associated")
        print(f"  Found {len(typed_relationships)} 'associated' relationships")
    except Exception as e:
        print(f"✗ Error in typed relationship query: {e}")
    
    print_header("Tests Completed")
    
if __name__ == "__main__":
    # Capture stdout to see if it's being redirected
    try:
        main()
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        sys.exit(1)