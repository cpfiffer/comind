"""
Database utility tools for Comind project.

This module provides command-line tools for working with the Kuzu graph database,
including syncing data from ATProto, querying records, and visualizing the graph.
"""

import argparse
import logging
import os
import sys
from typing import Dict, List, Optional
import json
from datetime import datetime

from atproto import Client as AtProtoClient
from rich import print
from rich.panel import Panel
from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table
from rich.console import Console
from rich.syntax import Syntax

from src.record_manager import RecordManager
from src.db_manager import DBManager
import src.session_reuse as session_reuse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("db_tools")

# Silence httpx logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def sync_from_atproto(record_manager: RecordManager, db_manager: DBManager, collections: List[str] = None):
    """
    Sync data from ATProto to the database.
    
    Args:
        record_manager: RecordManager instance
        db_manager: DBManager instance
        collections: List of collections to sync. If None, sync all collections.
    """
    console = Console()
    
    # If no collections specified, sync all known collections
    if not collections:
        collections = [
            "me.comind.sphere.core",
            "me.comind.blip.concept",
            "me.comind.blip.emotion",
            "me.comind.blip.thought",
            "me.comind.relationship.link",
            "me.comind.relationship.similarity",
            "me.comind.relationship.sphere"
        ]
    
    console.print(f"[bold green]Syncing data from ATProto to database[/bold green]")
    console.print(f"Collections to sync: {', '.join(collections)}")
    
    with Progress() as progress:
        for collection in collections:
            task = progress.add_task(f"Syncing {collection}...", total=None)
            
            try:
                # Get records from ATProto
                records = record_manager.list_records(collection)
                progress.update(task, total=len(records))
                progress.update(task, completed=0)
                
                # Sync each record to the database
                for i, record in enumerate(records):
                    try:
                        # Extract record key and URI
                        rkey = record.uri.split("/")[-1]
                        uri = record.uri
                        
                        # Store in database
                        db_manager.store_record(
                            collection=collection,
                            record=record.value,
                            uri=uri,
                            cid=record.cid if hasattr(record, 'cid') else "",
                            author_did=record_manager.client.me.did,
                            rkey=rkey,
                            sphere_uri=record_manager.sphere_uri
                        )
                        
                        # Update progress
                        progress.update(task, completed=i+1)
                        
                    except Exception as e:
                        logger.error(f"Error syncing record {record.uri}: {str(e)}")
                        continue
                
                progress.update(task, completed=len(records))
                
            except Exception as e:
                logger.error(f"Error listing records in collection {collection}: {str(e)}")
                progress.update(task, completed=1, total=1, description=f"[red]Failed: {collection}[/red]")
                continue


def query_records(db_manager: DBManager, query_type: str, query_value: str, collection: str = None):
    """
    Query records from the database.
    
    Args:
        db_manager: DBManager instance
        query_type: Type of query ('text', 'uri', 'collection')
        query_value: Value to query for
        collection: Collection to limit the search to (optional)
    """
    console = Console()
    console.print(f"[bold green]Querying records from database[/bold green]")
    
    results = []
    
    if query_type == "text":
        results = db_manager.find_similar_records(query_value, collection)
        console.print(f"Found {len(results)} records matching text: '{query_value}'")
    
    elif query_type == "uri":
        result = db_manager.get_record_by_uri(query_value)
        if result:
            results = [{"uri": query_value, "value": result}]
            console.print(f"Found record with URI: {query_value}")
        else:
            console.print(f"[yellow]No record found with URI: {query_value}[/yellow]")
    
    elif query_type == "collection":
        results = db_manager.list_records(query_value)
        console.print(f"Found {len(results)} records in collection: {query_value}")
    
    # Display results
    for result in results:
        uri = result.get("uri", "")
        value = result.get("value", {})
        
        # Create a panel for each result
        console.print(Panel(
            Syntax(json.dumps(value, indent=2), "json", background_color="default"),
            title=f"[bold blue]{uri}[/bold blue]",
            expand=False
        ))


def create_relationship(db_manager: DBManager, from_uri: str, to_uri: str, rel_type: str, strength: float = 1.0, note: str = None):
    """
    Create a relationship between two records.
    
    Args:
        db_manager: DBManager instance
        from_uri: URI of the source record
        to_uri: URI of the target record
        rel_type: Type of relationship
        strength: Strength of the relationship (0.0 to 1.0)
        note: Optional note about the relationship
    """
    console = Console()
    console.print(f"[bold green]Creating relationship in database[/bold green]")
    
    try:
        # Check if both records exist
        from_record = db_manager.get_record_by_uri(from_uri)
        to_record = db_manager.get_record_by_uri(to_uri)
        
        if not from_record:
            console.print(f"[red]Source record not found: {from_uri}[/red]")
            return
        
        if not to_record:
            console.print(f"[red]Target record not found: {to_uri}[/red]")
            return
        
        # Create relationship record
        relationship_record = {
            "createdAt": datetime.now().isoformat(),
            "relationship": rel_type,
            "strength": strength,
            "target": to_uri
        }
        
        if note:
            relationship_record["note"] = note
        
        # Store in database
        collection = "me.comind.relationship.link"
        rkey = f"{from_uri.split('/')[-1]}-{to_uri.split('/')[-1]}"
        
        db_manager.store_record(
            collection=collection,
            record=relationship_record,
            uri=f"at://{from_uri.split('/')[2]}/{collection}/{rkey}",
            cid="",
            author_did=from_uri.split('/')[2],
            rkey=rkey
        )
        
        console.print(f"[green]Created relationship from {from_uri} to {to_uri} with type {rel_type}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error creating relationship: {str(e)}[/red]")


def main():
    """Main function to run the database tools."""
    parser = argparse.ArgumentParser(description="Database tools for Comind project")
    
    # Common arguments
    parser.add_argument("--db-path", type=str, default="./demo_db",
                        help="Path to the database directory")
    
    # Subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync data from ATProto to database")
    sync_parser.add_argument("--username", "-u", type=str, 
                            help="ATProto username (or set COMIND_BSKY_USERNAME env var)")
    sync_parser.add_argument("--password", "-p", type=str, 
                            help="ATProto password (or set COMIND_BSKY_PASSWORD env var)")
    sync_parser.add_argument("--collections", "-c", type=str, nargs="+",
                            help="Collections to sync (space-separated)")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query records from database")
    query_parser.add_argument("--type", "-t", type=str, required=True,
                             choices=["text", "uri", "collection"],
                             help="Type of query to perform")
    query_parser.add_argument("--value", "-v", type=str, required=True,
                             help="Value to query for")
    query_parser.add_argument("--collection", "-c", type=str,
                             help="Collection to limit the search to (optional)")
    
    # Relationship command
    rel_parser = subparsers.add_parser("rel", help="Create a relationship between records")
    rel_parser.add_argument("--from", dest="from_uri", type=str, required=True,
                           help="URI of the source record")
    rel_parser.add_argument("--to", dest="to_uri", type=str, required=True,
                           help="URI of the target record")
    rel_parser.add_argument("--type", "-t", type=str, required=True,
                           help="Type of relationship")
    rel_parser.add_argument("--strength", "-s", type=float, default=1.0,
                           help="Strength of the relationship (0.0 to 1.0)")
    rel_parser.add_argument("--note", "-n", type=str,
                           help="Optional note about the relationship")
    
    args = parser.parse_args()
    
    # Initialize database manager
    db_manager = DBManager(args.db_path)
    db_manager.setup_schema()
    
    if args.command == "sync":
        # Get username/password from env vars if not provided
        username = args.username or os.getenv("COMIND_BSKY_USERNAME")
        password = args.password or os.getenv("COMIND_BSKY_PASSWORD")
        
        if not username or not password:
            logger.error("ATProto username and password are required for sync")
            parser.print_help()
            sys.exit(1)
        
        # Initialize ATProto client and record manager
        atproto_client = session_reuse.init_client(username, password)
        record_manager = RecordManager(atproto_client, enable_db=False)
        
        # Sync data
        sync_from_atproto(record_manager, db_manager, args.collections)
    
    elif args.command == "query":
        # Query records
        query_records(db_manager, args.type, args.value, args.collection)
    
    elif args.command == "rel":
        # Create relationship
        create_relationship(
            db_manager, 
            args.from_uri, 
            args.to_uri, 
            args.type, 
            args.strength, 
            args.note
        )
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()