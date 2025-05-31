"""
Graph Sync Service for Comind

Syncs ATProto records to Neo4j graph database, enabling powerful graph queries
and analysis of the Comind knowledge network.
"""

import logging
from typing import Dict, List, Optional, Any

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
        "me.comind.relationship.similarity",
    ]

    # External collections that may be referenced
    EXTERNAL_COLLECTIONS = [
        "app.bsky.feed.post",
        "app.bsky.feed.like",
        "app.bsky.graph.follow",
    ]

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        record_manager: Any = None,
    ):
        """
        Initialize the Graph Sync Service.

        Args:
            neo4j_uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            record_manager: Authenticated RecordManager instance (optional)
        """
        self.record_manager = record_manager
        self.driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )

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
            "CREATE CONSTRAINT repo_did IF NOT EXISTS FOR (r:Repo) REQUIRE r.did IS UNIQUE",
            # Indexes for common queries
            "CREATE INDEX concept_text IF NOT EXISTS FOR (c:Concept) ON (c.text)",
            "CREATE INDEX thought_type IF NOT EXISTS FOR (t:Thought) ON (t.thoughtType)",
            "CREATE INDEX emotion_type IF NOT EXISTS FOR (e:Emotion) ON (e.emotionType)",
            "CREATE INDEX sphere_title IF NOT EXISTS FOR (s:Sphere) ON (s.title)",
            "CREATE INDEX repo_handle IF NOT EXISTS FOR (r:Repo) ON (r.handle)",
            "CREATE INDEX created_at IF NOT EXISTS FOR (n) ON (n.createdAt)",
        ]

        with self.driver.session() as session:
            for query in schema_queries:
                try:
                    session.run(query)
                    logger.debug(f"Executed schema query: {query[:50]}...")
                except Exception as e:
                    logger.warning(
                        f"Schema query failed (may already exist): {e}"
                    )

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

        logger.info(
            f"Full sync complete. Total records synced: {total_synced}"
        )
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
            # Use list_all_records to handle pagination
            records = self.record_manager.list_all_records(collection)

            if not records:
                logger.info(f"No records found in collection: {collection}")
                return 0

            logger.info(f"Found {len(records)} records in collection: {collection}")
            synced_count = 0

            for record in records:
                try:
                    self.sync_record(record, collection)
                    synced_count += 1
                except Exception as e:
                    import traceback

                    logger.error(f"Failed to sync record {record.uri}: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    # Also debug the record structure
                    logger.error(f"Record type: {type(record)}")
                    logger.error(f"Record attributes: {dir(record)}")

            return synced_count

        except Exception as e:
            logger.error(
                f"Failed to list records in collection {collection}: {e}"
            )
            raise

    def sync_record(self, record: Any, collection: str):
        """
        Sync a single ATProto record to Neo4j.

        Args:
            record: ATProto record object
            collection: The collection this record belongs to
        """
        # Convert pydantic record to dict
        record_dict = record.model_dump()

        # Extract basic properties
        uri = record_dict.get("uri")
        cid = record_dict.get("cid")
        value = record_dict.get("value")

        # Check for None values
        if uri is None or cid is None or value is None:
            logger.error(
                f"Record has None attributes: uri={uri}, cid={cid}, value={value}"
            )
            return

        self.sync_record_data(uri, cid, value, collection)

    def sync_record_data(
        self, uri: str, cid: str, value: Dict, collection: str
    ):
        """
        Sync record data directly to Neo4j.

        Args:
            uri: Record URI
            cid: Record CID
            value: Record value/content
            collection: The collection this record belongs to
        """
        # Check for None values
        if uri is None or cid is None or value is None:
            logger.error(
                f"Record has None attributes: uri={uri}, cid={cid}, value={value}"
            )
            return

        # Note: Repo nodes and OWNS relationships are now handled directly
        # in the individual node creation methods to prevent duplicate nodes

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

    def _extract_did_from_uri(self, uri: str) -> Optional[str]:
        """Extract the DID from an ATProto URI."""
        try:
            # URI format: at://did:plc:example/collection/rkey
            parts = uri.split("/")
            if (
                len(parts) >= 3
                and parts[0] == "at:"
                and parts[2].startswith("did:")
            ):
                return parts[2]
            return None
        except Exception as e:
            logger.warning(f"Failed to extract DID from URI {uri}: {e}")
            return None

    def _ensure_repo_node(self, did: str, handle: str = None):
        """Ensure a Repo node exists for the given DID."""
        query = """
        MERGE (r:Repo {did: $did})
        ON CREATE SET r.createdAt = datetime()
        ON MATCH SET r.updatedAt = datetime()
        """

        params = {"did": did}
        if handle:
            query += " SET r.handle = $handle"
            params["handle"] = handle

        with self.driver.session() as session:
            session.run(query, params)

    def _create_repo_ownership(
        self, did: str, record_uri: str, record_cid: str, created_at: str
    ):
        """Create an OWNS relationship between a Repo and a record."""
        # Note: We don't create the record node here anymore since it will be created
        # with proper labels by the specific node creation methods (_create_concept_node, etc.)
        # We'll establish the OWNS relationship later if needed
        pass

    def _create_concept_node(self, uri: str, cid: str, value: Dict):
        """Create a Concept node in Neo4j."""
        # Extract DID from URI for OWNS relationship
        did = self._extract_did_from_uri(uri)
        created_at = value.get("createdAt", "")

        query = """
        MERGE (repo:Repo {did: $did})
        ON CREATE SET repo.createdAt = datetime()
        ON MATCH SET repo.updatedAt = datetime()
        MERGE (c:Concept {uri: $uri})
        SET c.cid = $cid,
            c.text = $text,
            c.createdAt = $created_at,
            c.updatedAt = datetime()
        MERGE (repo)-[r:OWNS]->(c)
        ON CREATE SET r.createdAt = $created_at,
                      r.updatedAt = datetime()
        ON MATCH SET r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                did=did,
                uri=uri,
                cid=cid,
                text=value.get("concept", ""),
                created_at=created_at,
            )

    def _create_thought_node(self, uri: str, cid: str, value: Dict):
        """Create a Thought node in Neo4j."""
        generated = value.get("generated", {})
        did = self._extract_did_from_uri(uri)
        created_at = value.get("createdAt", "")

        query = """
        MERGE (repo:Repo {did: $did})
        ON CREATE SET repo.createdAt = datetime()
        ON MATCH SET repo.updatedAt = datetime()
        MERGE (t:Thought {uri: $uri})
        SET t.cid = $cid,
            t.text = $text,
            t.thoughtType = $thoughtType,
            t.context = $context,
            t.confidence = $confidence,
            t.createdAt = $createdAt,
            t.updatedAt = datetime()
        MERGE (repo)-[r:OWNS]->(t)
        ON CREATE SET r.createdAt = $createdAt,
                      r.updatedAt = datetime()
        ON MATCH SET r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                did=did,
                uri=uri,
                cid=cid,
                text=generated.get("text", ""),
                thoughtType=generated.get("thoughtType", ""),
                context=generated.get("context", ""),
                confidence=generated.get("confidence"),
                createdAt=created_at,
            )

    def _create_emotion_node(self, uri: str, cid: str, value: Dict):
        """Create an Emotion node in Neo4j."""
        generated = value.get("generated", {})
        did = self._extract_did_from_uri(uri)
        created_at = value.get("createdAt", "")

        query = """
        MERGE (repo:Repo {did: $did})
        ON CREATE SET repo.createdAt = datetime()
        ON MATCH SET repo.updatedAt = datetime()
        MERGE (e:Emotion {uri: $uri})
        SET e.cid = $cid,
            e.text = $text,
            e.emotionType = $emotionType,
            e.createdAt = $createdAt,
            e.updatedAt = datetime()
        MERGE (repo)-[r:OWNS]->(e)
        ON CREATE SET r.createdAt = $createdAt,
                      r.updatedAt = datetime()
        ON MATCH SET r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                did=did,
                uri=uri,
                cid=cid,
                text=generated.get("text", ""),
                emotionType=generated.get("emotionType", ""),
                createdAt=created_at,
            )

    def _create_sphere_node(self, uri: str, cid: str, value: Dict):
        """Create a Sphere node in Neo4j."""
        did = self._extract_did_from_uri(uri)
        created_at = value.get("createdAt", "")

        query = """
        MERGE (repo:Repo {did: $did})
        ON CREATE SET repo.createdAt = datetime()
        ON MATCH SET repo.updatedAt = datetime()
        MERGE (s:Sphere {uri: $uri})
        SET s.cid = $cid,
            s.title = $title,
            s.text = $text,
            s.description = $description,
            s.createdAt = $createdAt,
            s.updatedAt = datetime()
        MERGE (repo)-[r:OWNS]->(s)
        ON CREATE SET r.createdAt = $createdAt,
                      r.updatedAt = datetime()
        ON MATCH SET r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                did=did,
                uri=uri,
                cid=cid,
                title=value.get("title", ""),
                text=value.get("text", ""),
                description=value.get("description", ""),
                createdAt=created_at,
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
            session.run(
                query,
                uri=uri,
                cid=cid,
                text=value.get("text", ""),
                createdAt=value.get("createdAt", ""),
            )

    def _create_concept_relationship(self, uri: str, cid: str, value: Dict):
        """Create a relationship between source and concept."""
        source_uri = value.get("source", "")
        target_uri = value.get("target", "")
        relationship_type = value.get("relationship", "RELATES_TO")

        # First, check if the concept exists and has text
        # If not, try to fetch it from the repository
        concept_text = None
        if self.record_manager and target_uri:
            try:
                # Parse the URI to get collection and rkey
                parts = target_uri.split('/')
                if len(parts) >= 5 and target_uri.startswith('at://'):
                    repo = parts[2]
                    collection = parts[3]
                    rkey = '/'.join(parts[4:])
                    
                    # Fetch the concept record
                    concept_record = self.record_manager.client.com.atproto.repo.get_record({
                        'collection': collection,
                        'repo': repo,
                        'rkey': rkey
                    })
                    
                    if concept_record and concept_record.value:
                        concept_text = concept_record.value.get('concept', None)
                        logger.debug(f"Fetched concept text for {target_uri}: {concept_text}")
            except Exception as e:
                logger.warning(f"Failed to fetch concept record {target_uri}: {e}")

        # Create the relationship, ensuring the concept has its text if we found it
        if concept_text:
            query = """
            MERGE (source {uri: $source_uri})
            ON CREATE SET source.createdAt = datetime()
            MERGE (target:Concept {uri: $target_uri})
            ON CREATE SET target.createdAt = datetime()
            SET target.text = $concept_text
            MERGE (source)-[r:CONCEPT_RELATION {uri: $uri}]->(target)
            ON CREATE SET r.cid = $cid,
                          r.relationship = $relationship,
                          r.createdAt = $createdAt,
                          r.updatedAt = datetime()
            ON MATCH SET r.cid = $cid,
                         r.relationship = $relationship,
                         r.updatedAt = datetime()
            """
            params = {
                "uri": uri,
                "cid": cid,
                "source_uri": source_uri,
                "target_uri": target_uri,
                "concept_text": concept_text,
                "relationship": relationship_type,
                "createdAt": value.get("createdAt", ""),
            }
        else:
            # Fall back to original query without setting text
            query = """
            MERGE (source {uri: $source_uri})
            ON CREATE SET source.createdAt = datetime()
            MERGE (target:Concept {uri: $target_uri})
            ON CREATE SET target.createdAt = datetime()
            MERGE (source)-[r:CONCEPT_RELATION {uri: $uri}]->(target)
            ON CREATE SET r.cid = $cid,
                          r.relationship = $relationship,
                          r.createdAt = $createdAt,
                          r.updatedAt = datetime()
            ON MATCH SET r.cid = $cid,
                         r.relationship = $relationship,
                         r.updatedAt = datetime()
            """
            params = {
                "uri": uri,
                "cid": cid,
                "source_uri": source_uri,
                "target_uri": target_uri,
                "relationship": relationship_type,
                "createdAt": value.get("createdAt", ""),
            }

        with self.driver.session() as session:
            session.run(query, **params)

    def _create_link_relationship(self, uri: str, cid: str, value: Dict):
        """Create a general link relationship between nodes."""
        source = value.get("source", {})
        source_uri = (
            source.get("uri", "") if isinstance(source, dict) else source
        )
        target_uri = value.get("target", "")
        generated = value.get("generated", {})
        relationship_type = generated.get("relationship", "LINKS_TO")

        query = """
        MERGE (source {uri: $source_uri})
        ON CREATE SET source.createdAt = datetime()
        MERGE (target {uri: $target_uri})
        ON CREATE SET target.createdAt = datetime()
        MERGE (source)-[r:LINK {uri: $uri}]->(target)
        ON CREATE SET r.cid = $cid,
                      r.relationship = $relationship,
                      r.strength = $strength,
                      r.note = $note,
                      r.createdAt = $createdAt,
                      r.updatedAt = datetime()
        ON MATCH SET r.cid = $cid,
                     r.relationship = $relationship,
                     r.strength = $strength,
                     r.note = $note,
                     r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                uri=uri,
                cid=cid,
                source_uri=source_uri,
                target_uri=target_uri,
                relationship=relationship_type,
                strength=generated.get("strength"),
                note=generated.get("note", ""),
                createdAt=value.get("createdAt", ""),
            )

    def _create_sphere_relationship(self, uri: str, cid: str, value: Dict):
        """Create a relationship between content and sphere."""
        target = value.get("target", "")
        # Handle strongRef format (object with uri and cid) or plain string
        if isinstance(target, dict):
            target_uri = target.get("uri", "")
        else:
            target_uri = target
        sphere_uri = value.get("sphere_uri", "")

        query = """
        MERGE (target {uri: $target_uri})
        ON CREATE SET target.createdAt = datetime()
        MERGE (sphere:Sphere {uri: $sphere_uri})
        ON CREATE SET sphere.createdAt = datetime()
        MERGE (target)-[r:IN_SPHERE {uri: $uri}]->(sphere)
        ON CREATE SET r.cid = $cid,
                      r.createdAt = $createdAt,
                      r.updatedAt = datetime()
        ON MATCH SET r.cid = $cid,
                     r.updatedAt = datetime()
        """

        with self.driver.session() as session:
            session.run(
                query,
                uri=uri,
                cid=cid,
                target_uri=target_uri,
                sphere_uri=sphere_uri,
                createdAt=value.get("createdAt", ""),
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
                path = record["path"]
                for node in path.nodes:
                    nodes.add((node.id, dict(node)))
                for rel in path.relationships:
                    relationships.append(
                        {
                            "start": rel.start_node.id,
                            "end": rel.end_node.id,
                            "type": rel.type,
                            "properties": dict(rel),
                        }
                    )

            return {
                "nodes": [
                    {"id": node_id, "properties": props}
                    for node_id, props in nodes
                ],
                "relationships": relationships,
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
            return [
                {
                    "concept": record["concept"],
                    "frequency": record["frequency"],
                }
                for record in result
            ]

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

    def cleanup_duplicate_concept_nodes(self) -> int:
        """
        Clean up duplicate concept nodes by merging unlabeled nodes with Concept labeled nodes.

        Returns:
            Number of duplicate nodes cleaned up
        """
        logger.info("Starting cleanup of duplicate concept nodes...")

        # Find unlabeled nodes that have the same URI as Concept nodes
        query = """
        MATCH (unlabeled) WHERE NOT unlabeled:Concept AND NOT unlabeled:Thought AND NOT unlabeled:Emotion AND NOT unlabeled:Sphere AND NOT unlabeled:Post AND NOT unlabeled:Repo
        MATCH (concept:Concept {uri: unlabeled.uri})
        WITH unlabeled, concept, unlabeled.uri as duplicate_uri
        
        // Transfer any relationships from unlabeled node to concept node
        OPTIONAL MATCH (unlabeled)-[r]->(target)
        WHERE target <> concept
        WITH unlabeled, concept, duplicate_uri, collect({rel: r, target: target}) as outgoing_rels
        
        OPTIONAL MATCH (source)-[r]->(unlabeled)
        WHERE source <> concept
        WITH unlabeled, concept, duplicate_uri, outgoing_rels, collect({rel: r, source: source}) as incoming_rels
        
        RETURN unlabeled, concept, duplicate_uri, outgoing_rels, incoming_rels
        """

        cleanup_count = 0

        with self.driver.session() as session:
            result = session.run(query)

            for record in result:
                unlabeled = record["unlabeled"]
                concept = record["concept"]
                duplicate_uri = record["duplicate_uri"]

                # Transfer relationships and delete unlabeled node
                transfer_query = """
                MATCH (unlabeled) WHERE id(unlabeled) = $unlabeled_id
                MATCH (concept:Concept) WHERE id(concept) = $concept_id
                
                // Transfer OWNS relationships to the concept node
                OPTIONAL MATCH (repo:Repo)-[owns:OWNS]->(unlabeled)
                WITH unlabeled, concept, repo, owns
                WHERE repo IS NOT NULL
                MERGE (repo)-[new_owns:OWNS]->(concept)
                ON CREATE SET new_owns = properties(owns)
                DELETE owns
                
                // Delete the unlabeled duplicate node
                DETACH DELETE unlabeled
                """

                session.run(
                    transfer_query,
                    unlabeled_id=unlabeled.id,
                    concept_id=concept.id,
                )

                cleanup_count += 1
                logger.debug(
                    f"Cleaned up duplicate node for URI: {duplicate_uri}"
                )

        logger.info(
            f"Cleanup complete. Removed {cleanup_count} duplicate concept nodes"
        )
        return cleanup_count


def create_graph_sync_service(
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "comind123",
    record_manager: Any = None,
) -> GraphSyncService:
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
        from record_manager import RecordManager

        client = default_login()
        record_manager = RecordManager(client)

    return GraphSyncService(
        neo4j_uri, neo4j_user, neo4j_password, record_manager
    )


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync ATProto records to Neo4j"
    )
    parser.add_argument(
        "--neo4j-uri", default="bolt://localhost:7687", help="Neo4j URI"
    )
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username")
    parser.add_argument(
        "--neo4j-password", default="comind123", help="Neo4j password"
    )
    parser.add_argument(
        "--setup-schema", action="store_true", help="Set up Neo4j schema"
    )
    parser.add_argument(
        "--sync-all", action="store_true", help="Sync all records"
    )
    parser.add_argument(
        "--collection", type=str, help="Sync specific collection"
    )
    parser.add_argument(
        "--cleanup-duplicates",
        action="store_true",
        help="Clean up duplicate concept nodes",
    )

    args = parser.parse_args()

    try:
        # Create sync service
        sync_service = create_graph_sync_service(
            args.neo4j_uri, args.neo4j_user, args.neo4j_password
        )

        if args.setup_schema:
            sync_service.setup_schema()

        if args.cleanup_duplicates:
            sync_service.cleanup_duplicate_concept_nodes()

        if args.sync_all:
            sync_service.sync_all_records()
        elif args.collection:
            sync_service.sync_collection(args.collection)

        sync_service.close()

    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        raise
