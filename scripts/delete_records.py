#!/usr/bin/env python3
"""
Delete Records CLI Tool

A utility to delete Comind records from ATProto repositories.
WARNING: This tool permanently deletes data. Use with extreme caution.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from record_manager import RecordManager
from session_reuse import default_login

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("delete_records")

# List of all Comind collections
COMIND_COLLECTIONS = [
    "me.comind.concept",
    "me.comind.thought", 
    "me.comind.emotion",
    "me.comind.sphere.core",
    "me.comind.sphere.member",
    "me.comind.sphere.void",
    "me.comind.relationship.concept",
    "me.comind.relationship.link",
    "me.comind.relationship.sphere",
    "me.comind.relationship.similarity",
    "me.comind.utility.tokens",
    "me.comind.utility.weakRef",
    "me.comind.meld.request",
    "me.comind.meld.response",
    "me.comind.agent"
]

def delete_all_comind_records(record_manager: RecordManager) -> None:
    """
    Delete all Comind records from all collections.
    
    Args:
        record_manager: RecordManager instance for deleting records
    """
    logger.info("Starting deletion of all Comind records...")
    total_deleted = 0
    
    for collection in COMIND_COLLECTIONS:
        try:
            logger.info(f"Processing collection: {collection}")
            records = record_manager.list_all_records(collection)
            
            if not records:
                logger.info(f"No records found in collection: {collection}")
                continue
                
            logger.info(f"Found {len(records)} records in {collection}")
            
            for record in records:
                # Extract the rkey from the uri (format: at://did/collection/rkey)
                rkey = record.uri.split('/')[-1]
                try:
                    record_manager.delete_record(collection, rkey)
                    total_deleted += 1
                    logger.debug(f"Deleted record: {collection}/{rkey}")
                except Exception as e:
                    logger.error(f"Failed to delete record {collection}/{rkey}: {e}")
                    
            logger.info(f"Completed deletion for collection: {collection}")
            
        except Exception as e:
            if "Collection not found" in str(e) or "InvalidRequest" in str(e):
                logger.info(f"Collection {collection} does not exist or is empty")
            else:
                logger.error(f"Error processing collection {collection}: {e}")
    
    logger.info(f"Deletion complete. Total records deleted: {total_deleted}")

def delete_collection(record_manager: RecordManager, collection: str) -> None:
    """
    Delete all records from a specific collection.
    
    Args:
        record_manager: RecordManager instance for deleting records
        collection: Collection name to delete from
    """
    logger.info(f"Deleting all records from collection: {collection}")
    
    try:
        record_manager.clear_collection(collection)
        logger.info(f"Successfully cleared collection: {collection}")
    except Exception as e:
        logger.error(f"Error clearing collection {collection}: {e}")

def list_collections(record_manager: RecordManager) -> None:
    """
    List all Comind collections and their record counts.
    
    Args:
        record_manager: RecordManager instance for listing records
    """
    logger.info("Listing all Comind collections...")
    total_records = 0
    
    for collection in COMIND_COLLECTIONS:
        try:
            records = record_manager.list_all_records(collection)
            count = len(records)
            total_records += count
            print(f"{collection}: {count} records")
        except Exception as e:
            if "Collection not found" in str(e) or "InvalidRequest" in str(e):
                print(f"{collection}: 0 records (collection does not exist)")
            else:
                print(f"{collection}: Error - {e}")
    
    print(f"\nTotal records across all collections: {total_records}")

def main():
    parser = argparse.ArgumentParser(
        description="Delete Comind records from ATProto repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WARNING: This tool permanently deletes data from your ATProto repository.
Always use with extreme caution and ensure you have backups if needed.

Examples:
  # List all collections and record counts
  python scripts/delete_records.py --list
  
  # Delete all records from all Comind collections
  python scripts/delete_records.py --delete-all
  
  # Delete all records from a specific collection
  python scripts/delete_records.py --delete-collection me.comind.concept
        """
    )
    
    # Operations
    parser.add_argument("--list", action="store_true",
                       help="List all Comind collections and their record counts")
    parser.add_argument("--delete-all", action="store_true", 
                       help="Delete ALL Comind records (WARNING: Irreversible!)")
    parser.add_argument("--delete-collection", type=str,
                       help="Delete all records from a specific collection")
    
    # Options
    parser.add_argument("--force", action="store_true",
                       help="Skip confirmation prompts (use with extreme caution)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check that at least one operation is specified
    if not any([args.list, args.delete_all, args.delete_collection]):
        parser.print_help()
        return
    
    try:
        # Initialize record manager
        logger.info("Connecting to ATProto...")
        client = default_login()
        record_manager = RecordManager(client)
        logger.info("Connected successfully")
        
        # List operation
        if args.list:
            list_collections(record_manager)
        
        # Delete all operation
        if args.delete_all:
            if not args.force:
                print("\n🚨 WARNING: This will delete ALL Comind records from your ATProto repository!")
                print("This action is IRREVERSIBLE and will permanently destroy your data.")
                response = input("\nAre you absolutely sure you want to continue? Type 'DELETE ALL' to confirm: ")
                if response != 'DELETE ALL':
                    logger.info("Delete operation cancelled")
                    return
            
            delete_all_comind_records(record_manager)
        
        # Delete collection operation
        if args.delete_collection:
            if not args.delete_collection.startswith("me.comind."):
                logger.error("Can only delete collections in the me.comind.* namespace")
                return
                
            if not args.force:
                print(f"\n⚠️  WARNING: This will delete all records from collection: {args.delete_collection}")
                print("This action is IRREVERSIBLE.")
                response = input(f"\nAre you sure you want to delete all records from {args.delete_collection}? Type 'yes' to confirm: ")
                if response.lower() != 'yes':
                    logger.info("Delete operation cancelled")
                    return
            
            delete_collection(record_manager, args.delete_collection)
        
        logger.info("Operation completed successfully")
        
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()