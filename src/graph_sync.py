"""
Graph Sync Service for Comind

Syncs ATProto records to Neo4j graph database, enabling powerful graph queries
and analysis of the Comind knowledge network.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from neo4j import GraphDatabase
from atproto import Client as AtProtoClient

from record_manager import RecordManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("graph_sync")

class GraphSyncService:
    """
    Syncs ATProto records to Neo4j graph database.
    
    This service creates a graph representation of Comind's knowledge network,
    enabling sophisticated queries and analysis of concepts, relationships,
    and content patterns.
    """
    
    # Comind collections to sync
    COMIND_COLLECTIONS = [
        "me.comind.concept",
        "me.comind.thought", 
        "me.comind.emotion",
        "me.comind.sphere.core",
        "me.comind.relationship.concept",
        "me.comind.relationship.link",
        "me.comind.relationship.sphere",
        "me.comind.relationship.similarity"
    ]
    
    # External collections that may be referenced
    EXTERNAL_COLLECTIONS = [
        "app.bsky.feed.post",
        "app.bsky.feed.like",
        "app.bsky.graph.follow"
    ]
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, 
                 record_manager: RecordManager):
        """
        Initialize the Graph Sync Service.
        
        Args:
            neo4j_uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            record_manager: Authenticated RecordManager instance
        """
        self.record_manager = record_manager
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Verify connection
        try:
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def setup_schema(self):
        """
        Set up Neo4j schema with constraints and indexes for optimal performance.
        """
        logger.info("Setting up Neo4j schema...")
        
        schema_queries = [
            # Constraints for uniqueness
            "CREATE CONSTRAINT concept_uri IF NOT EXISTS FOR (c:Concept) REQUIRE c.uri IS UNIQUE",
            "CREATE CONSTRAINT thought_uri IF NOT EXISTS FOR (t:Thought) REQUIRE t.uri IS UNIQUE", 
            "CREATE CONSTRAINT emotion_uri IF NOT EXISTS FOR (e:Emotion) REQUIRE e.uri IS UNIQUE",
            "CREATE CONSTRAINT sphere_uri IF NOT EXISTS FOR (s:Sphere) REQUIRE s.uri IS UNIQUE",
            "CREATE CONSTRAINT post_uri IF NOT EXISTS FOR (p:Post) REQUIRE p.uri IS UNIQUE",
            
            # Indexes for common queries
            "CREATE INDEX concept_text IF NOT EXISTS FOR (c:Concept) ON (c.text)",
            "CREATE INDEX thought_type IF NOT EXISTS FOR (t:Thought) ON (t.thoughtType)",
            "CREATE INDEX emotion_type IF NOT EXISTS FOR (e:Emotion) ON (e.emotionType)",
            "CREATE INDEX sphere_title IF NOT EXISTS FOR (s:Sphere) ON (s.title)",
            "CREATE INDEX created_at IF NOT EXISTS FOR (n) ON (n.createdAt)"
        ]
        
        with self.driver.session() as session:
            for query in schema_queries:
                try:
                    session.run(query)
                    logger.debug(f"Executed schema query: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Schema query failed (may already exist): {e}")
        
        logger.info("Neo4j schema setup complete")
    
    def sync_all_records(self, include_external: bool = False):
        """
        Sync all Comind records to Neo4j.
        
        Args:
            include_external: Whether to include external collections (posts, likes, etc.)
        """
        logger.info("Starting full sync of all records...")
        
        collections_to_sync = self.COMIND_COLLECTIONS.copy()
        if include_external:
            collections_to_sync.extend(self.EXTERNAL_COLLECTIONS)
        
        total_synced = 0
        
        for collection in collections_to_sync:
            try:
                synced_count = self.sync_collection(collection)
                total_synced += synced_count
                logger.info(f"Synced {synced_count} records from {collection}")
            except Exception as e:
                logger.error(f"Failed to sync collection {collection}: {e}")
        
        logger.info(f"Full sync complete. Total records synced: {total_synced}")
        return total_synced
    
    def sync_collection(self, collection: str) -> int:
        """
        Sync all records from a specific collection.
        
        Args:
            collection: The collection NSID to sync
            
        Returns:
            Number of records synced
        """
        logger.info(f"Syncing collection: {collection}")
        
        try:
            records = self.record_manager.list_records(collection)
            
            if not records:
                logger.info(f"No records found in collection: {collection}")
                return 0
            
            synced_count = 0
            
            for record in records:
                try:
                    self.sync_record(record, collection)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to sync record {record.uri}: {e}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"Failed to list records in collection {collection}: {e}")
            raise
    
    def sync_record(self, record: Any, collection: str):
        """
        Sync a single ATProto record to Neo4j.
        
        Args:
            record: ATProto record object
            collection: The collection this record belongs to
        """
        # Extract basic properties
        uri = record.uri
        cid = record.cid
        value = record.value
        
        # Determine record type and create appropriate node
        if collection == "me.comind.concept":
            self._create_concept_node(uri, cid, value)
        elif collection == "me.comind.thought":
            self._create_thought_node(uri, cid, value)
        elif collection == "me.comind.emotion":
            self._create_emotion_node(uri, cid, value)
        elif collection == "me.comind.sphere.core":
            self._create_sphere_node(uri, cid, value)
        elif collection == "me.comind.relationship.concept":
            self._create_concept_relationship(uri, cid, value)
        elif collection == "me.comind.relationship.link":
            self._create_link_relationship(uri, cid, value)
        elif collection == "me.comind.relationship.sphere":
            self._create_sphere_relationship(uri, cid, value)
        elif collection == "app.bsky.feed.post":
            self._create_post_node(uri, cid, value)
        else:
            logger.warning(f"Unknown collection type: {collection}")
    
    def _create_concept_node(self, uri: str, cid: str, value: Dict):
        """Create a Concept node in Neo4j."""
        query = """
        MERGE (c:Concept {uri: $uri})
        SET c.cid = $cid,
            c.text = $text,
            c.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query, 
                uri=uri,
                cid=cid, 
                text=value.get('concept', '')
            )
    
    def _create_thought_node(self, uri: str, cid: str, value: Dict):
        """Create a Thought node in Neo4j."""
        generated = value.get('generated', {})
        
        query = """
        MERGE (t:Thought {uri: $uri})
        SET t.cid = $cid,
            t.text = $text,
            t.thoughtType = $thoughtType,
            t.context = $context,
            t.confidence = $confidence,
            t.createdAt = $createdAt,
            t.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                text=generated.get('text', ''),
                thoughtType=generated.get('thoughtType', ''),
                context=generated.get('context', ''),
                confidence=generated.get('confidence'),
                createdAt=value.get('createdAt', '')
            )
    
    def _create_emotion_node(self, uri: str, cid: str, value: Dict):
        """Create an Emotion node in Neo4j."""
        generated = value.get('generated', {})
        
        query = """
        MERGE (e:Emotion {uri: $uri})
        SET e.cid = $cid,
            e.text = $text,
            e.emotionType = $emotionType,
            e.createdAt = $createdAt,
            e.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                text=generated.get('text', ''),
                emotionType=generated.get('emotionType', ''),
                createdAt=value.get('createdAt', '')
            )
    
    def _create_sphere_node(self, uri: str, cid: str, value: Dict):
        """Create a Sphere node in Neo4j."""
        query = """
        MERGE (s:Sphere {uri: $uri})
        SET s.cid = $cid,
            s.title = $title,
            s.text = $text,
            s.description = $description,
            s.createdAt = $createdAt,
            s.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                title=value.get('title', ''),
                text=value.get('text', ''),
                description=value.get('description', ''),
                createdAt=value.get('createdAt', '')
            )
    
    def _create_post_node(self, uri: str, cid: str, value: Dict):
        """Create a Post node in Neo4j."""
        query = """
        MERGE (p:Post {uri: $uri})
        SET p.cid = $cid,
            p.text = $text,
            p.createdAt = $createdAt,
            p.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                text=value.get('text', ''),
                createdAt=value.get('createdAt', '')
            )
    
    def _create_concept_relationship(self, uri: str, cid: str, value: Dict):
        """Create a relationship between source and concept."""
        source_uri = value.get('source', '')
        target_uri = value.get('target', '')
        relationship_type = value.get('relationship', 'RELATES_TO')
        
        query = """
        MATCH (source {uri: $source_uri})
        MATCH (target:Concept {uri: $target_uri})
        MERGE (source)-[r:CONCEPT_RELATION {uri: $uri}]->(target)
        SET r.cid = $cid,
            r.relationship = $relationship,
            r.createdAt = $createdAt,
            r.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                source_uri=source_uri,
                target_uri=target_uri,
                relationship=relationship_type,
                createdAt=value.get('createdAt', '')
            )
    
    def _create_link_relationship(self, uri: str, cid: str, value: Dict):
        """Create a general link relationship between nodes."""
        source_uri = value.get('source', '')
        target_uri = value.get('target', '')
        generated = value.get('generated', {})
        relationship_type = generated.get('relationship', 'LINKS_TO')
        
        query = """
        MATCH (source {uri: $source_uri})
        MATCH (target {uri: $target_uri})
        MERGE (source)-[r:LINK {uri: $uri}]->(target)
        SET r.cid = $cid,
            r.relationship = $relationship,
            r.strength = $strength,
            r.note = $note,
            r.createdAt = $createdAt,
            r.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                source_uri=source_uri,
                target_uri=target_uri,
                relationship=relationship_type,
                strength=generated.get('strength'),
                note=generated.get('note', ''),
                createdAt=value.get('createdAt', '')
            )
    
    def _create_sphere_relationship(self, uri: str, cid: str, value: Dict):
        """Create a relationship between content and sphere."""
        target_uri = value.get('target', '')
        sphere_uri = value.get('sphere_uri', '')
        
        query = """
        MATCH (target {uri: $target_uri})
        MATCH (sphere:Sphere {uri: $sphere_uri})
        MERGE (target)-[r:IN_SPHERE {uri: $uri}]->(sphere)
        SET r.cid = $cid,
            r.createdAt = $createdAt,
            r.updatedAt = datetime()
        """
        
        with self.driver.session() as session:
            session.run(query,
                uri=uri,
                cid=cid,
                target_uri=target_uri,
                sphere_uri=sphere_uri,
                createdAt=value.get('createdAt', '')
            )
    
    def get_concept_network(self, concept_text: str, depth: int = 2) -> Dict:
        """
        Get the network of concepts connected to a given concept.
        
        Args:
            concept_text: The concept to explore
            depth: How many relationship hops to include
            
        Returns:
            Dictionary with nodes and relationships
        """
        query = f"""
        MATCH path = (c:Concept {{text: $concept_text}})-[*1..{depth}]-(connected)
        RETURN path
        """
        
        with self.driver.session() as session:
            result = session.run(query, concept_text=concept_text)
            
            nodes = set()
            relationships = []
            
            for record in result:
                path = record['path']
                for node in path.nodes:
                    nodes.add((node.id, dict(node)))
                for rel in path.relationships:
                    relationships.append({
                        'start': rel.start_node.id,
                        'end': rel.end_node.id,
                        'type': rel.type,
                        'properties': dict(rel)
                    })
            
            return {
                'nodes': [{'id': node_id, 'properties': props} for node_id, props in nodes],
                'relationships': relationships
            }
    
    def get_sphere_concepts(self, sphere_title: str) -> List[Dict]:
        """
        Get all concepts associated with a sphere.
        
        Args:
            sphere_title: The sphere title to query
            
        Returns:
            List of concept dictionaries
        """
        query = """
        MATCH (content)-[:IN_SPHERE]->(s:Sphere {title: $sphere_title})
        MATCH (content)-[:CONCEPT_RELATION]->(c:Concept)
        RETURN DISTINCT c.text as concept, count(*) as frequency
        ORDER BY frequency DESC
        """
        
        with self.driver.session() as session:
            result = session.run(query, sphere_title=sphere_title)
            return [{'concept': record['concept'], 'frequency': record['frequency']} 
                   for record in result]
    
    def find_concept_clusters(self, min_connections: int = 3) -> List[Dict]:
        """
        Find clusters of highly connected concepts.
        
        Args:
            min_connections: Minimum number of connections for a concept to be included
            
        Returns:
            List of concept clusters
        """
        query = """
        MATCH (c:Concept)<-[:CONCEPT_RELATION]-(source)
        WITH c, count(source) as connections
        WHERE connections >= $min_connections
        MATCH (c)<-[:CONCEPT_RELATION]-(source)-[:CONCEPT_RELATION]->(related:Concept)
        WHERE related <> c
        RETURN c.text as concept, 
               connections,
               collect(DISTINCT related.text) as related_concepts
        ORDER BY connections DESC
        """
        
        with self.driver.session() as session:
            result = session.run(query, min_connections=min_connections)
            return [dict(record) for record in result]


def create_graph_sync_service(neo4j_uri: str = "bolt://localhost:7687",
                            neo4j_user: str = "neo4j", 
                            neo4j_password: str = "comind123",
                            record_manager: Optional[RecordManager] = None) -> GraphSyncService:
    """
    Factory function to create a GraphSyncService instance.
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username  
        neo4j_password: Neo4j password
        record_manager: RecordManager instance (will create one if None)
        
    Returns:
        Configured GraphSyncService instance
    """
    if record_manager is None:
        from session_reuse import default_login
        client = default_login()
        record_manager = RecordManager(client)
    
    return GraphSyncService(neo4j_uri, neo4j_user, neo4j_password, record_manager)


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync ATProto records to Neo4j")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", 
                       help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j",
                       help="Neo4j username")
    parser.add_argument("--neo4j-password", default="comind123",
                       help="Neo4j password")
    parser.add_argument("--setup-schema", action="store_true",
                       help="Set up Neo4j schema")
    parser.add_argument("--sync-all", action="store_true",
                       help="Sync all records")
    parser.add_argument("--collection", type=str,
                       help="Sync specific collection")
    
    args = parser.parse_args()
    
    try:
        # Create sync service
        sync_service = create_graph_sync_service(
            args.neo4j_uri, args.neo4j_user, args.neo4j_password
        )
        
        if args.setup_schema:
            sync_service.setup_schema()
        
        if args.sync_all:
            sync_service.sync_all_records()
        elif args.collection:
            sync_service.sync_collection(args.collection)
        
        sync_service.close()
        
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        raise