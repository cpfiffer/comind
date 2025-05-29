#!/usr/bin/env python3
"""
Graph Sync CLI Tool

Easy-to-use command line interface for syncing ATProto records to Neo4j
and performing graph queries.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from graph_sync import create_graph_sync_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("graph_sync_cli")

def main():
    parser = argparse.ArgumentParser(
        description="Sync ATProto records to Neo4j and query the graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Set up the Neo4j schema
  python scripts/graph_sync.py --setup-schema
  
  # Sync all Comind records
  python scripts/graph_sync.py --sync-all
  
  # Sync only concepts
  python scripts/graph_sync.py --sync-collection me.comind.concept
  
  # Clean up duplicate concept nodes
  python scripts/graph_sync.py --cleanup-duplicates
  
  # Get concept network for "distributed systems"
  python scripts/graph_sync.py --concept-network "distributed systems"
  
  # Get concepts in a sphere
  python scripts/graph_sync.py --sphere-concepts "AI Research"
  
  # Find concept clusters
  python scripts/graph_sync.py --concept-clusters --min-connections 5
        """
    )
    
    # Connection options
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687",
                       help="Neo4j connection URI (default: bolt://localhost:7687)")
    parser.add_argument("--neo4j-user", default="neo4j",
                       help="Neo4j username (default: neo4j)")
    parser.add_argument("--neo4j-password", default="comind123",
                       help="Neo4j password (default: comind123)")
    
    # Schema operations
    parser.add_argument("--setup-schema", action="store_true",
                       help="Set up Neo4j schema (indexes and constraints)")
    
    # Sync operations
    parser.add_argument("--sync-all", action="store_true",
                       help="Sync all Comind records to Neo4j")
    parser.add_argument("--sync-collection", type=str,
                       help="Sync specific collection (e.g., me.comind.concept)")
    parser.add_argument("--include-external", action="store_true",
                       help="Include external collections like posts when syncing all")
    parser.add_argument("--cleanup-duplicates", action="store_true",
                       help="Clean up duplicate concept nodes in the database")
    
    # Query operations
    parser.add_argument("--concept-network", type=str,
                       help="Get network of concepts connected to the given concept")
    parser.add_argument("--depth", type=int, default=2,
                       help="Network depth for concept queries (default: 2)")
    parser.add_argument("--sphere-concepts", type=str,
                       help="Get all concepts associated with a sphere")
    parser.add_argument("--concept-clusters", action="store_true",
                       help="Find clusters of highly connected concepts")
    parser.add_argument("--min-connections", type=int, default=3,
                       help="Minimum connections for concept clusters (default: 3)")
    
    # Output options
    parser.add_argument("--output", type=str,
                       help="Save query results to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Create sync service
        logger.info("Connecting to Neo4j...")
        sync_service = create_graph_sync_service(
            args.neo4j_uri, args.neo4j_user, args.neo4j_password
        )
        logger.info("Connected successfully")
        
        # Schema operations
        if args.setup_schema:
            logger.info("Setting up Neo4j schema...")
            sync_service.setup_schema()
            logger.info("Schema setup complete")
        
        # Cleanup operations
        if args.cleanup_duplicates:
            logger.info("Cleaning up duplicate concept nodes...")
            cleanup_count = sync_service.cleanup_duplicate_concept_nodes()
            logger.info(f"Cleanup complete. Removed {cleanup_count} duplicate nodes")
        
        # Sync operations
        if args.sync_all:
            logger.info("Starting full sync...")
            total_synced = sync_service.sync_all_records(args.include_external)
            logger.info(f"Sync complete. Total records synced: {total_synced}")
        
        elif args.sync_collection:
            logger.info(f"Syncing collection: {args.sync_collection}")
            synced_count = sync_service.sync_collection(args.sync_collection)
            logger.info(f"Synced {synced_count} records from {args.sync_collection}")
        
        # Query operations
        result = None
        
        if args.concept_network:
            logger.info(f"Getting concept network for: {args.concept_network}")
            result = sync_service.get_concept_network(args.concept_network, args.depth)
            print(f"\nConcept Network for '{args.concept_network}':")
            print(f"Nodes: {len(result['nodes'])}")
            print(f"Relationships: {len(result['relationships'])}")
            
            if result['nodes']:
                print("\nConnected concepts:")
                for node in result['nodes'][:10]:  # Show first 10
                    props = node['properties']
                    if 'text' in props:
                        print(f"  - {props['text']}")
                    elif 'title' in props:
                        print(f"  - {props['title']} (sphere)")
                if len(result['nodes']) > 10:
                    print(f"  ... and {len(result['nodes']) - 10} more")
        
        elif args.sphere_concepts:
            logger.info(f"Getting concepts for sphere: {args.sphere_concepts}")
            result = sync_service.get_sphere_concepts(args.sphere_concepts)
            print(f"\nConcepts in sphere '{args.sphere_concepts}':")
            for concept in result[:20]:  # Show top 20
                print(f"  {concept['concept']} (frequency: {concept['frequency']})")
            if len(result) > 20:
                print(f"  ... and {len(result) - 20} more concepts")
        
        elif args.concept_clusters:
            logger.info(f"Finding concept clusters (min connections: {args.min_connections})")
            result = sync_service.find_concept_clusters(args.min_connections)
            print(f"\nConcept Clusters (minimum {args.min_connections} connections):")
            for cluster in result[:10]:  # Show top 10
                print(f"\n  {cluster['concept']} ({cluster['connections']} connections)")
                related = cluster['related_concepts'][:5]  # Show top 5 related
                for related_concept in related:
                    print(f"    → {related_concept}")
                if len(cluster['related_concepts']) > 5:
                    print(f"    ... and {len(cluster['related_concepts']) - 5} more")
        
        # Save output if requested
        if result and args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        sync_service.close()
        logger.info("Graph sync session complete")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()