import json
import os
import sys
import logging
from src.db_manager import DBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("import_comind_records")

def print_header(text):
    """Print a header with decoration"""
    print(f"\n{'=' * 40}")
    print(f"   {text}")
    print(f"{'=' * 40}\n")

def main():
    print_header("Importing Comind Records into KuzuDB")
    
    # Initialize the database manager
    print("Initializing database...")
    db_path = "./demo_db"
    db_manager = DBManager(db_path)
    print("Database manager initialized.")
    
    # Ensure the schema is set up
    db_manager.setup_schema()
    
    # Path to the JSON file containing records
    comind_records_path = "comind_records.json"
    
    # Check if file exists
    if not os.path.exists(comind_records_path):
        print(f"Error: File {comind_records_path} not found.")
        print("Please create this file with comind records to import.")
        return
    
    # Load the records from the JSON file
    try:
        with open(comind_records_path, 'r') as f:
            records_data = json.load(f)
        
        if not isinstance(records_data, list):
            print("Error: Expected a JSON array of records.")
            return
            
        print(f"Loaded {len(records_data)} records from {comind_records_path}")
    except Exception as e:
        print(f"Error loading records: {e}")
        return
    
    # Process each record
    success_count = 0
    error_count = 0
    
    for i, record_data in enumerate(records_data):
        try:
            # Extract fields
            uri = record_data.get('uri')
            if not uri:
                print(f"Skipping record {i+1}: Missing URI")
                error_count += 1
                continue
                
            print(f"Processing record {i+1}/{len(records_data)}: {uri}")
            
            # Determine record type from URI or value
            record_type = None
            value = record_data.get('value', {})
            if value and '$type' in value:
                record_type = value['$type']
            else:
                # Try to determine from URI
                parts = uri.split('/')
                if len(parts) >= 2:
                    record_type = parts[-2]  # Collection name is second-to-last part
            
            if not record_type:
                print(f"  Warning: Could not determine record type for {uri}")
                record_type = "unknown"
            
            # Extract DID from URI
            author_did = None
            try:
                author_did = uri.split('/')[2]  # Format: at://did/.../...
            except:
                print(f"  Warning: Could not extract author DID from {uri}")
                author_did = "unknown"
            
            # Process the record
            result = db_manager.process_comind_record(
                record_type=record_type,
                record_data=record_data,
                author_did=author_did
            )
            
            if result:
                success_count += 1
                print(f"  ✓ Successfully imported {uri}")
            else:
                error_count += 1
                print(f"  ✗ Failed to import {uri}")
            
        except Exception as e:
            error_count += 1
            print(f"  ✗ Error processing record {i+1}: {e}")
    
    print_header("Import Completed")
    print(f"Successfully imported: {success_count} records")
    print(f"Failed to import: {error_count} records")
    
    # Run a query to verify the imported records
    try:
        # Query for Comind-specific records
        result = db_manager.conn.execute("""
            MATCH (r:Record)
            WHERE r.content CONTAINS 'me.comind'
            RETURN r.uri as uri, r.content as content
            LIMIT 10
        """)
        
        records = []
        while result.has_next():
            row = result.get_next()
            uri, content_json = row
            
            if not content_json:
                continue
                
            try:
                content = json.loads(content_json)
                records.append({
                    'uri': uri,
                    'nsid': content.get('nsid', 'unknown'),
                    'labels': content.get('labels', '')
                })
            except:
                pass
        
        print(f"Found {len(records)} Comind records in database:")
        
        if records:
            for i, rec in enumerate(records[:5]):  # Show first 5
                print(f"{i+1}. {rec.get('uri', 'Unknown')}")
                print(f"   NSID: {rec.get('nsid', 'Unknown')}")
                print(f"   Labels: {rec.get('labels', '')}")
                print()
    except Exception as e:
        print(f"Error querying imported records: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1) 