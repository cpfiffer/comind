from typing import Dict, List, Optional, Any, Union
import json
import os
import logging
from datetime import datetime
import kuzu
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_manager")

class DBManager:
    """
    Manages the storage and retrieval of ATProto records in a Kuzu graph database.
    
    This class provides methods to store, query, and analyze ATProto records,
    maintaining their relationship structure according to the lexicon definitions.
    
    Attributes:
        db_path: Path to the Kuzu database files
        db: Kuzu Database instance
        conn: Kuzu Connection instance
    """
    
    def __init__(self, db_path: str = "./demo_db"):
        """
        Initialize a DBManager with a Kuzu database.
        
        Args:
            db_path: Path to the database directory. If it doesn't exist, it will be created.
        """
        self.db_path = db_path
        self.create_db_if_not_exists()
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        logger.info(f"Initialized DBManager with database at: {db_path}")
        
        # FTS disabled due to known issues with KuzuDB's FTS extension:
        # - FTS indexes don't include entries added after index creation
        # - Extension installation makes HTTP requests
        # - Potential segfaults (see https://github.com/kuzudb/kuzu/issues/5324)
        # We'll use basic text search instead.

    def create_db_if_not_exists(self):
        """Create the database directory if it doesn't exist"""
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
            logger.info(f"Created database directory at: {self.db_path}")
            
    def setup_schema(self, force=False):
        """
        Set up the database schema based on ATProto lexicons.
        
        This method creates the node and relationship tables needed to
        represent the ATProto data model.
        
        Args:
            force: If True, drop existing tables before creating new ones
        """
        try:
            if force:
                # Drop existing tables if they exist
                try:
                    # First drop relationship tables
                    for rel_table in ["AUTHORED", "OWNS", "IN_SPHERE", "LINKS", 
                                     "TARGET", "FOLLOWS", "LIKES", "REPOSTS", "BLOCKS"]:
                        try:
                            self.conn.execute(f"DROP TABLE IF EXISTS {rel_table}")
                        except Exception as e:
                            logger.debug(f"Error dropping relationship table {rel_table}: {e}")
                    
                    # Then drop node tables
                    for node_table in ["Record", "Repo", "User", "Sphere", 
                                      "BlipConcept", "BlipEmotion", "BlipThought"]:
                        try:
                            self.conn.execute(f"DROP TABLE IF EXISTS {node_table}")
                        except Exception as e:
                            logger.debug(f"Error dropping node table {node_table}: {e}")
                    
                    logger.info("Dropped existing tables")
                except Exception as e:
                    logger.warning(f"Error dropping tables: {e}")
            
            # Create User node table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS User (
                    did STRING PRIMARY KEY,
                    handle STRING,
                    displayName STRING,
                    description STRING
                )
            """)
            
            # Create Repo node table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Repo (
                    did STRING PRIMARY KEY,
                    handle STRING,
                    receivedAt TIMESTAMP
                )
            """)
            
            # Create Record node table (consolidated all ATProto records here)
            # Make sure all columns are properly defined
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Record (
                    uri STRING PRIMARY KEY,
                    cid STRING DEFAULT '',
                    collection STRING DEFAULT '',
                    nsid STRING DEFAULT '',
                    rkey STRING DEFAULT '',
                    text STRING DEFAULT '',
                    recordType STRING DEFAULT '',
                    labels STRING DEFAULT '',
                    content STRING DEFAULT '',
                    raw STRING DEFAULT '',
                    createdAt TIMESTAMP,
                    receivedAt TIMESTAMP
                )
            """)
            
            # Create sphere table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Sphere (
                    uri STRING PRIMARY KEY,
                    title STRING DEFAULT '',
                    text STRING DEFAULT '',
                    description STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipConcept table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS BlipConcept (
                    uri STRING PRIMARY KEY,
                    text STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipEmotion table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS BlipEmotion (
                    uri STRING PRIMARY KEY,
                    type STRING DEFAULT '',
                    text STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipThought table
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS BlipThought (
                    uri STRING PRIMARY KEY,
                    type STRING DEFAULT '',
                    context STRING DEFAULT '',
                    text STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # Create relationship tables
            
            # AUTHORED relationship between User and Record
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS AUTHORED (
                    FROM User TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            # OWNS relationship between Repo and Record
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS OWNS (
                    FROM Repo TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            # IN_SPHERE relationship between Record and Sphere
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS IN_SPHERE (
                    FROM Record TO Sphere,
                    createdAt TIMESTAMP
                )
            """)
            
            # LINKS relationship for general connections between records
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS LINKS (
                    FROM Record TO Record,
                    relType STRING DEFAULT 'REFERENCES',
                    strength FLOAT DEFAULT 1.0,
                    note STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # TARGET relationship for records with targets
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS TARGET (
                    FROM Record TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            # FOLLOWS relationship between Records
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS FOLLOWS (
                    FROM Record TO Record, 
                    sourceRecord STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # LIKES relationship between Records
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS LIKES (
                    FROM Record TO Record,
                    sourceRecord STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # REPOSTS relationship between Records
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS REPOSTS (
                    FROM Record TO Record,
                    sourceRecord STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # BLOCKS relationship between Records
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS BLOCKS (
                    FROM Record TO Record,
                    sourceRecord STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            # Add index on nsid and collection - Use correct KuzuDB syntax
            try:
                # KuzuDB might not support CREATE INDEX syntax
                # This might be supported in future versions
                # Just log the info and continue without index for now
                logger.info("Skipping index creation - not supported in current KuzuDB version")
            except Exception as e:
                logger.warning(f"Could not create index: {e}")
            
            logger.info("Successfully created database schema")
            
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Some schema elements already exist, continuing")
            else:
                logger.error(f"Error creating schema: {str(e)}")
                raise e
    
    def store_user(self, did: str, handle: str, display_name: str, description: str = None) -> None:
        """
        Store user information in the database.
        
        Args:
            did: The decentralized identifier for the user
            handle: The user's handle
            display_name: The user's display name
            description: The user's profile description (optional)
        """
        try:
            query = """
                MERGE (u:User {did: $did})
                SET u.handle = $handle,
                    u.displayName = $displayName,
                    u.description = $description
            """
            
            self.conn.execute(query, {
                'did': did,
                'handle': handle,
                'displayName': display_name,
                'description': description
            })
            
            logger.debug(f"Stored user: {handle} ({did})")
            
        except Exception as e:
            logger.error(f"Error storing user {did}: {str(e)}")
            raise e
    
    def store_record(self, collection: str, record: Dict, uri: str, cid: str, 
                     author_did: str, rkey: str = None, sphere_uri: str = None) -> None:
        """
        Store an ATProto record in the database.
        
        Args:
            collection: The collection the record belongs to (e.g., me.comind.blip.concept)
            record: The record data as a dictionary
            uri: The URI of the record
            cid: The content identifier of the record
            author_did: The DID of the record's author
            rkey: The record key identifier (optional)
            sphere_uri: The URI of the sphere this record belongs to (optional)
        """
        try:
            # Convert record to JSON string
            record_json = json.dumps(record)
            
            # Extract the record type from the collection
            record_type = collection.split('.')[-1]
            
            # Store the base record
            # Use proper datetime object for Kuzu's TIMESTAMP type
            created_at_str = record.get('createdAt', datetime.now().isoformat())
            try:
                # Parse ISO format string to datetime object
                if isinstance(created_at_str, str):
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = created_at_str
            except Exception as e:
                logger.warning(f"Error parsing timestamp {created_at_str}: {e}. Using current time.")
                created_at = datetime.now()
            
            received_at = datetime.now()
            
            # Insert record into appropriate node table based on type
            if "sphere.core" in collection:
                self.conn.execute("""
                    MERGE (s:Sphere {uri: $uri})
                    SET s.title = $title,
                        s.text = $text,
                        s.description = $description,
                        s.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'title': record.get('title', ''),
                    'text': record.get('text', ''),
                    'description': record.get('description', ''),
                    'createdAt': created_at
                })
            
            elif "blip.concept" in collection:
                self.conn.execute("""
                    MERGE (c:BlipConcept {uri: $uri})
                    SET c.text = $text,
                        c.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'text': record.get('text', ''),
                    'createdAt': created_at
                })
            
            elif "blip.emotion" in collection:
                self.conn.execute("""
                    MERGE (e:BlipEmotion {uri: $uri})
                    SET e.type = $type,
                        e.text = $text,
                        e.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'type': record.get('type', ''),
                    'text': record.get('text', ''),
                    'createdAt': created_at
                })
            
            elif "blip.thought" in collection:
                self.conn.execute("""
                    MERGE (t:BlipThought {uri: $uri})
                    SET t.type = $type,
                        t.context = $context,
                        t.text = $text,
                        t.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'type': record.get('type', ''),
                    'context': record.get('context', ''),
                    'text': record.get('text', ''),
                    'createdAt': created_at
                })
            
            # Also insert into the base Record table for unified queries
            self.conn.execute("""
                MERGE (r:Record {uri: $uri})
                SET r.cid = $cid,
                    r.collection = $collection,
                    r.rkey = $rkey,
                    r.createdAt = $createdAt,
                    r.recordType = $recordType,
                    r.content = $content
            """, {
                'uri': uri,
                'cid': cid,
                'collection': collection,
                'rkey': rkey,
                'createdAt': created_at,
                'recordType': record_type,
                'content': record_json
            })
            
            # Create AUTHORED relationship
            self.conn.execute("""
                MATCH (u:User {did: $did})
                MATCH (r:Record {uri: $uri})
                MERGE (u)-[rel:AUTHORED]->(r)
                SET rel.createdAt = $createdAt
            """, {
                'did': author_did,
                'uri': uri,
                'createdAt': created_at
            })
            
            # If sphere_uri is provided, create IN_SPHERE relationship
            if sphere_uri:
                self.conn.execute("""
                    MATCH (r:Record {uri: $uri})
                    MATCH (s:Sphere {uri: $sphere_uri})
                    MERGE (r)-[rel:IN_SPHERE]->(s)
                    SET rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'sphere_uri': sphere_uri,
                    'createdAt': created_at
                })
            
            # Check for target in the record and create TARGET relationship
            if 'target' in record:
                target_uri = record['target']
                self.conn.execute("""
                    MATCH (r:Record {uri: $uri})
                    MATCH (t:Record {uri: $target_uri})
                    MERGE (r)-[rel:TARGET]->(t)
                    SET rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'target_uri': target_uri,
                    'createdAt': created_at
                })
                
            # Handle relationship links
            if collection == "me.comind.relationship.link" and "relationship" in record:
                from_uri = uri
                to_uri = record.get("target", "")
                if to_uri:
                    self.conn.execute("""
                        MATCH (from:Record {uri: $from_uri})
                        MATCH (to:Record {uri: $to_uri})
                        MERGE (from)-[rel:LINKS]->(to)
                        SET rel.relType = $rel_type,
                            rel.strength = $strength,
                            rel.note = $note,
                            rel.createdAt = $createdAt
                    """, {
                        'from_uri': from_uri,
                        'to_uri': to_uri,
                        'rel_type': record.get("relationship", ""),
                        'strength': record.get("strength", 1.0),
                        'note': record.get("note", ""),
                        'createdAt': created_at
                    })
            
            # Convert timestamps to ISO format strings for storage
            # Use separate command for timestamps since they're most likely to cause issues
            self.conn.execute("""
                MATCH (r:Record {uri: $uri})
                SET r.createdAt = $createdAt,
                    r.receivedAt = $receivedAt
            """, {
                'uri': uri, 
                'createdAt': created_at.isoformat(),
                'receivedAt': received_at.isoformat()
            })
            
            # Create OWNS relationship between repo and record
            self.conn.execute("""
                MATCH (repo:Repo {did: $did})
                MATCH (record:Record {uri: $uri})
                MERGE (repo)-[rel:OWNS]->(record)
                SET rel.createdAt = $createdAt
            """, {
                'did': author_did,
                'uri': uri,
                'createdAt': received_at.isoformat()
            })
            
            # Handle special record types that create relationships
            if collection == "app.bsky.graph.follow" and "subject" in record:
                target_did = record["subject"]
                # Find the target repo
                self.conn.execute("""
                    MERGE (target:Repo {did: $target_did})
                """, {
                    'target_did': target_did
                })
                
                # Create FOLLOWS relationship
                self.conn.execute("""
                    MATCH (source:Record {uri: $uri})
                    MATCH (source_repo:Repo {did: $source_did})
                    MATCH (target_repo:Repo {did: $target_did})
                    MERGE (source_repo)-[rel:FOLLOWS]->(target_repo)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'source_did': author_did,
                    'target_did': target_did,
                    'createdAt': created_at
                })
            
            elif collection == "app.bsky.feed.like" and "subject" in record:
                target_uri = record["subject"]["uri"]
                # Create LIKES relationship
                self.conn.execute("""
                    MATCH (source:Record {uri: $uri})
                    MATCH (target:Record {uri: $target_uri})
                    MERGE (source)-[rel:LIKES]->(target)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'target_uri': target_uri,
                    'createdAt': created_at
                })
            
            elif collection == "app.bsky.feed.repost" and "subject" in record:
                target_uri = record["subject"]["uri"]
                # Create REPOSTS relationship
                self.conn.execute("""
                    MATCH (source:Record {uri: $uri})
                    MATCH (target:Record {uri: $target_uri})
                    MERGE (source)-[rel:REPOSTS]->(target)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'target_uri': target_uri,
                    'createdAt': created_at
                })
            
            elif collection == "app.bsky.graph.block" and "subject" in record:
                target_did = record["subject"]
                # Find the target repo
                self.conn.execute("""
                    MERGE (target:Repo {did: $target_did})
                """, {
                    'target_did': target_did
                })
                
                # Create BLOCKS relationship
                self.conn.execute("""
                    MATCH (source:Record {uri: $uri})
                    MATCH (source_repo:Repo {did: $source_did})
                    MATCH (target_repo:Repo {did: $target_did})
                    MERGE (source_repo)-[rel:BLOCKS]->(target_repo)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'source_did': author_did,
                    'target_did': target_did,
                    'createdAt': created_at
                })
            
            # Handle Comind specific records
            if "me.comind" in collection:
                # Add appropriate label based on record type
                if "blip.concept" in collection:
                    self.conn.execute("""
                        MATCH (r:Record {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'Record,Blip,Concept'
                                         WHEN r.labels CONTAINS 'Concept' THEN r.labels
                                         ELSE r.labels + ',Blip,Concept'
                                       END
                    """, {'uri': uri})
                
                elif "blip.thought" in collection:
                    self.conn.execute("""
                        MATCH (r:Record {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'Record,Blip,Thought'
                                         WHEN r.labels CONTAINS 'Thought' THEN r.labels
                                         ELSE r.labels + ',Blip,Thought'
                                       END
                    """, {'uri': uri})
                
                elif "blip.emotion" in collection:
                    self.conn.execute("""
                        MATCH (r:Record {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'Record,Blip,Emotion'
                                         WHEN r.labels CONTAINS 'Emotion' THEN r.labels
                                         ELSE r.labels + ',Blip,Emotion'
                                       END
                    """, {'uri': uri})
                
                elif "sphere.core" in collection:
                    self.conn.execute("""
                        MATCH (r:Record {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'Record,Core'
                                         WHEN r.labels CONTAINS 'Core' THEN r.labels
                                         ELSE r.labels + ',Core'
                                       END
                    """, {'uri': uri})
                
                # Handle "from" records that create references
                if "from" in record and isinstance(record["from"], list):
                    for ref in record["from"]:
                        if "uri" in ref:
                            from_uri = ref["uri"]
                            self.conn.execute("""
                                MATCH (target:Record {uri: $uri})
                                MERGE (source:Record {uri: $from_uri})
                                MERGE (source)-[rel:LINKS]->(target)
                                SET rel.relType = 'REFERENCES',
                                    rel.createdAt = $createdAt
                            """, {
                                'uri': uri,
                                'from_uri': from_uri,
                                'createdAt': created_at
                            })
                
                # Handle relationship links
                if "relationship.link" in collection:
                    if "target" in record:
                        target_uri = record["target"]
                        self.conn.execute("""
                            MATCH (source:Record {uri: $uri})
                            MERGE (target:Record {uri: $target_uri})
                            MERGE (source)-[rel:LINKS]->(target)
                            SET rel.relType = $rel_type,
                                rel.strength = $strength,
                                rel.note = $note,
                                rel.createdAt = $createdAt
                        """, {
                            'uri': uri,
                            'target_uri': target_uri,
                            'rel_type': record.get("relationship", "REFERENCES"),
                            'strength': record.get("strength", 1.0),
                            'note': record.get("note", ""),
                            'createdAt': created_at
                        })
                
                # Handle sphere assignment
                if "relationship.sphere" in collection and "sphere_uri" in record and "target" in record:
                    sphere_uri = record["sphere_uri"]
                    target_uri = record["target"]["uri"]
                    
                    self.conn.execute("""
                        MATCH (record:Record {uri: $target_uri})
                        MATCH (sphere:Record {uri: $sphere_uri})
                        MERGE (sphere)-[rel:CONGREGATES]->(record)
                        SET rel.createdAt = $createdAt
                    """, {
                        'target_uri': target_uri,
                        'sphere_uri': sphere_uri,
                        'createdAt': created_at
                    })
            
            logger.debug(f"Stored record: {collection}/{rkey if rkey else ''}")
            
        except Exception as e:
            logger.error(f"Error storing record {uri}: {str(e)}")
            raise e
    
    def get_record(self, collection: str, rkey: str) -> Optional[Dict]:
        """
        Retrieve a record from the database.
        
        Args:
            collection: The collection the record belongs to
            rkey: The record key identifier
            
        Returns:
            The record as a dictionary if found, None otherwise
        """
        try:
            query = """
                MATCH (r:Record)
                WHERE r.collection = $collection AND r.rkey = $rkey
                RETURN r.content as content
            """
            
            result = self.conn.execute(query, {
                'collection': collection,
                'rkey': rkey
            })
            
            if result.has_next():
                row = result.get_next()
                content = row[0]
                return json.loads(content)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving record {collection}/{rkey}: {str(e)}")
            raise e
    
    def get_record_by_uri(self, uri: str) -> Optional[Dict]:
        """
        Retrieve a record from the database by its URI.
        
        Args:
            uri: The URI of the record
            
        Returns:
            The record as a dictionary if found, None otherwise
        """
        try:
            query = """
                MATCH (r:Record {uri: $uri})
                RETURN r.content as content
            """
            
            result = self.conn.execute(query, {'uri': uri})
            
            if result.has_next():
                row = result.get_next()
                content = row[0]
                return json.loads(content)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving record with URI {uri}: {str(e)}")
            raise e
    
    def list_records(self, collection: str) -> List[Dict]:
        """
        List all records in a collection.
        
        Args:
            collection: The collection to list records from
            
        Returns:
            A list of record dictionaries
        """
        try:
            query = """
                MATCH (r:Record)
                WHERE r.collection = $collection
                RETURN r.uri as uri, r.cid as cid, r.rkey as rkey, r.content as content
            """
            
            result = self.conn.execute(query, {'collection': collection})
            records = []
            
            while result.has_next():
                row = result.get_next()
                uri, cid, rkey, content = row
                record = {
                    'uri': uri,
                    'cid': cid,
                    'rkey': rkey,
                    'value': json.loads(content)
                }
                records.append(record)
                
            return records
                
        except Exception as e:
            logger.error(f"Error listing records in collection {collection}: {str(e)}")
            raise e
    
    def query_relationships(self, source_uri: str, rel_type: str = None, max_depth: int = 1) -> List[Dict]:
        """
        Query relationships from a source record.
        
        Args:
            source_uri: The URI of the source record
            rel_type: The type of relationship to query (optional)
            max_depth: Maximum depth for traversal (default: 1)
            
        Returns:
            A list of related records with relationship information
        """
        try:
            # Kuzu doesn't directly return paths as objects we can process
            # So we'll query the relationships and construct the results manually
            relationships = []
            
            if rel_type:
                # Query specific relationship type
                query = f"""
                    MATCH (source:Record {{uri: $source_uri}})-[rel:LINKS]->(target:Record)
                    WHERE rel.relType = $rel_type
                    RETURN source.uri as source_uri,
                           target.uri as target_uri,
                           target.collection as target_collection,
                           target.content as target_content,
                           rel.relType as rel_type,
                           rel.strength as strength,
                           rel.note as note,
                           rel.createdAt as created_at
                """
                params = {'source_uri': source_uri, 'rel_type': rel_type}
            else:
                # Query any relationship
                query = """
                    MATCH (source:Record {uri: $source_uri})-[rel:LINKS]->(target:Record)
                    RETURN source.uri as source_uri,
                           target.uri as target_uri,
                           target.collection as target_collection,
                           target.content as target_content,
                           rel.relType as rel_type,
                           rel.strength as strength,
                           rel.note as note,
                           rel.createdAt as created_at
                """
                params = {'source_uri': source_uri}
            
            result = self.conn.execute(query, params)
            
            # Process first level relationships
            first_level_targets = set()
            
            while result.has_next():
                row = result.get_next()
                source_uri, target_uri, target_collection, target_content, rel_type, strength, note, created_at = row
                
                # Add to results
                rel_data = {
                    'source_uri': source_uri,
                    'target_uri': target_uri,
                    'target_collection': target_collection,
                    'target_data': json.loads(target_content),
                    'relationship': {
                        'type': rel_type,
                        'strength': strength if strength is not None else 1.0,
                        'note': note,
                        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
                    },
                    'depth': 1
                }
                relationships.append(rel_data)
                first_level_targets.add(target_uri)
            
            # If max_depth > 1, get next levels
            current_depth = 1
            current_sources = first_level_targets
            
            while current_depth < max_depth and current_sources:
                next_sources = set()
                
                for current_source in current_sources:
                    if rel_type:
                        query = """
                            MATCH (source:Record {uri: $source_uri})-[rel:LINKS]->(target:Record)
                            WHERE rel.relType = $rel_type
                            RETURN source.uri as source_uri,
                                  target.uri as target_uri,
                                  target.collection as target_collection,
                                  target.content as target_content,
                                  rel.relType as rel_type,
                                  rel.strength as strength,
                                  rel.note as note,
                                  rel.createdAt as created_at
                        """
                        params = {'source_uri': current_source, 'rel_type': rel_type}
                    else:
                        query = """
                            MATCH (source:Record {uri: $source_uri})-[rel:LINKS]->(target:Record)
                            RETURN source.uri as source_uri,
                                  target.uri as target_uri,
                                  target.collection as target_collection,
                                  target.content as target_content,
                                  rel.relType as rel_type,
                                  rel.strength as strength,
                                  rel.note as note,
                                  rel.createdAt as created_at
                        """
                        params = {'source_uri': current_source}
                    
                    result = self.conn.execute(query, params)
                    
                    while result.has_next():
                        row = result.get_next()
                        src_uri, tgt_uri, tgt_collection, tgt_content, r_type, r_strength, r_note, r_created_at = row
                        
                        # Add to results
                        rel_data = {
                            'source_uri': src_uri,
                            'target_uri': tgt_uri,
                            'target_collection': tgt_collection,
                            'target_data': json.loads(tgt_content),
                            'relationship': {
                                'type': r_type,
                                'strength': r_strength if r_strength is not None else 1.0,
                                'note': r_note,
                                'created_at': r_created_at.isoformat() if hasattr(r_created_at, 'isoformat') else str(r_created_at)
                            },
                            'depth': current_depth + 1
                        }
                        relationships.append(rel_data)
                        next_sources.add(tgt_uri)
                
                current_sources = next_sources
                current_depth += 1
                
            return relationships
                
        except Exception as e:
            logger.error(f"Error querying relationships from {source_uri}: {str(e)}")
            return []
    
    def delete_record(self, collection: str, rkey: str) -> bool:
        """
        Delete a record from the database.
        
        Args:
            collection: The collection the record belongs to
            rkey: The record key identifier
            
        Returns:
            True if the record was deleted, False otherwise
        """
        try:
            # Find the URI first
            query = """
                MATCH (r:Record)
                WHERE r.collection = $collection AND r.rkey = $rkey
                RETURN r.uri as uri
            """
            
            result = self.conn.execute(query, {
                'collection': collection,
                'rkey': rkey
            })
            
            if not result.has_next():
                logger.warning(f"Record {collection}/{rkey} not found for deletion")
                return False
                
            uri = result.get_next()[0]
            
            # Delete relationships first
            self.conn.execute("""
                MATCH (r:Record {uri: $uri})-[rel]-()
                DELETE rel
            """, {'uri': uri})
            
            # Delete the record from its specific type table
            if "sphere.core" in collection:
                self.conn.execute("MATCH (s:Sphere {uri: $uri}) DELETE s", {'uri': uri})
            elif "blip.concept" in collection:
                self.conn.execute("MATCH (c:BlipConcept {uri: $uri}) DELETE c", {'uri': uri})
            elif "blip.emotion" in collection:
                self.conn.execute("MATCH (e:BlipEmotion {uri: $uri}) DELETE e", {'uri': uri})
            elif "blip.thought" in collection:
                self.conn.execute("MATCH (t:BlipThought {uri: $uri}) DELETE t", {'uri': uri})
            
            # Delete from the Record table
            self.conn.execute("""
                MATCH (r:Record {uri: $uri})
                DELETE r
            """, {'uri': uri})
            
            logger.info(f"Deleted record: {collection}/{rkey}")
            return True
                
        except Exception as e:
            logger.error(f"Error deleting record {collection}/{rkey}: {str(e)}")
            raise e
    
    def clear_collection(self, collection: str) -> int:
        """
        Delete all records in a collection.
        
        Args:
            collection: The collection to clear
            
        Returns:
            The number of records deleted
        """
        try:
            # Count records first
            query = """
                MATCH (r:Record)
                WHERE r.collection = $collection
                RETURN count(r) as count
            """
            
            result = self.conn.execute(query, {'collection': collection})
            count = 0
            if result.has_next():
                count = result.get_next()[0]
            
            # No records to delete
            if count == 0:
                return 0
            
            # Get all records in the collection
            query = """
                MATCH (r:Record)
                WHERE r.collection = $collection
                RETURN r.uri as uri
            """
            
            result = self.conn.execute(query, {'collection': collection})
            uris = []
            while result.has_next():
                uris.append(result.get_next()[0])
            
            # Delete relationships for all records
            for uri in uris:
                self.conn.execute("""
                    MATCH (r:Record {uri: $uri})-[rel]-()
                    DELETE rel
                """, {'uri': uri})
            
            # Delete specific type records
            if "sphere.core" in collection:
                self.conn.execute("""
                    MATCH (s:Sphere)
                    WHERE s.uri IN $uris
                    DELETE s
                """, {'uris': uris})
            elif "blip.concept" in collection:
                self.conn.execute("""
                    MATCH (c:BlipConcept)
                    WHERE c.uri IN $uris
                    DELETE c
                """, {'uris': uris})
            elif "blip.emotion" in collection:
                self.conn.execute("""
                    MATCH (e:BlipEmotion)
                    WHERE e.uri IN $uris
                    DELETE e
                """, {'uris': uris})
            elif "blip.thought" in collection:
                self.conn.execute("""
                    MATCH (t:BlipThought)
                    WHERE t.uri IN $uris
                    DELETE t
                """, {'uris': uris})
            
            # Delete from Record table
            self.conn.execute("""
                MATCH (r:Record)
                WHERE r.collection = $collection
                DELETE r
            """, {'collection': collection})
            
            logger.info(f"Cleared collection {collection}: deleted {count} records")
            return count
                
        except Exception as e:
            logger.error(f"Error clearing collection {collection}: {str(e)}")
            raise e
    
    def setup_fts_index(self):
        """
        Set up full-text search indexes for the database.
        This needs to be called once to enable full-text search.
        
        Note: Disabled due to known issues with KuzuDB's FTS extension.
        See https://github.com/kuzudb/kuzu/issues/5324
        """
        # FTS functionality disabled due to issues
        logger.info("Full-text search is disabled due to known issues with KuzuDB's FTS extension")
        return False
        
        # Commented out FTS setup code:
        """
        try:
            # Install and load FTS extension
            self.conn.execute("INSTALL FTS")
            self.conn.execute("LOAD FTS")
            
            # Create FTS indexes for Record content
            self.conn.execute('''
                CALL CREATE_FTS_INDEX('Record', 'content_index', ['content'])
            ''')
            
            logger.info("Full-text search indexes created successfully")
            return True
        except Exception as e:
            # If already exists, just log and continue
            if "already exists" in str(e):
                logger.info("Full-text search indexes already exist")
                return True
            logger.error(f"Error setting up full-text search indexes: {str(e)}")
            return False
        """
    
    def find_similar_records(self, text: str, collection: str = None, limit: int = 10) -> List[Dict]:
        """
        Find records with similar text content.
        
        Note: Using basic search method as FTS is disabled due to known issues.
        
        Args:
            text: The text to search for
            collection: Optional collection to limit the search to
            limit: Maximum number of results to return
            
        Returns:
            List of matching records
        """
        # Always use basic search method
        logger.debug("Using basic search method for similar records, as FTS is disabled due to known issues")
        return self._find_records_basic(text, collection, limit)
    
    def _find_records_basic(self, text: str, collection: str = None, limit: int = 10) -> List[Dict]:
        """
        Basic search implementation that filters records in Python.
        Used as a fallback when FTS is not available.
        
        Raises:
            Exception: If there is an error performing the search
        """
        try:
            # Ensure Record table exists with minimal required schema
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Record (
                    uri STRING PRIMARY KEY,
                    content STRING
                )
            """)
            
            # Query to get all records - we'll filter in Python
            query = """
                MATCH (r:Record)
                RETURN r.uri as uri, r.content as content
                LIMIT $max_records
            """
            params = {'max_records': limit * 5}  # Get more to filter
            
            result = self.conn.execute(query, params)
            
            # Normalize search text for case-insensitive comparison
            search_text = text.lower()
            
            # Process results directly
            matches = []
            while result.has_next():
                row = result.get_next()
                uri, content_json = row
                
                if not content_json:
                    continue
                
                try:
                    # Parse properties from content JSON
                    properties = json.loads(content_json)
                    
                    # Apply collection filter if specified
                    if collection:
                        record_collection = properties.get('collection', properties.get('nsid', ''))
                        if record_collection != collection:
                            continue
                    
                    found = False
                    
                    # Check text field first
                    record_text = properties.get('text', '')
                    if record_text and search_text in record_text.lower():
                        found = True
                    
                    # Also check raw content if not found in text
                    if not found and 'raw' in properties:
                        raw = properties['raw']
                        if raw and search_text in raw.lower():
                            found = True
                    
                    # If found, create a record object
                    if found:
                        record = {
                            'uri': properties.get('uri', uri),
                            'cid': properties.get('cid', ''),
                            'nsid': properties.get('nsid', properties.get('collection', '')),
                            'value': {}
                        }
                        
                        # Parse raw JSON if available
                        raw_json = properties.get('raw')
                        if raw_json:
                            try:
                                record['value'] = json.loads(raw_json)
                            except Exception as e:
                                logger.debug(f"Failed to parse raw JSON for {uri}: {e}")
                                # Continue with empty value rather than failing
                        
                        matches.append(record)
                        
                        # Stop if we've found enough matches
                        if len(matches) >= limit:
                            break
                            
                except Exception as e:
                    logger.debug(f"Error processing record during search: {e}")
                    # Skip this record and continue with the next one
            
            return matches
            
        except Exception as e:
            logger.error(f"Error in basic record search: {str(e)}")
            raise e

    def store_atproto_record(self, uri: str, cid: str, nsid: str, record: Dict, 
                        author_did: str, rkey: str, labels: List[str] = None):
        """
        Store an ATProto record from the jetstream in the database.
        
        Args:
            uri: The URI of the record
            cid: The content identifier of the record
            nsid: The NSID (namespace ID) of the record (e.g., app.bsky.feed.post)
            record: The record data as a dictionary
            author_did: The DID of the record's author/repo owner
            rkey: The record key identifier
            labels: Additional labels to apply to the node (e.g., 'Blip', 'Concept')
            
        Returns:
            bool: True if the record was successfully stored
            
        Raises:
            Exception: If there is an error storing the record
        """
        try:
            # Convert record to JSON string
            record_json = json.dumps(record)
            
            # Extract text content if available (depends on record type)
            text = ""
            if nsid == "app.bsky.feed.post" and "text" in record:
                text = record.get("text", "")
            elif "me.comind" in nsid:
                # Extract text from different comind record types
                if "blip.concept" in nsid and "generated" in record and "text" in record["generated"]:
                    text = record["generated"]["text"]
                elif "blip.thought" in nsid and "generated" in record and "text" in record["generated"]:
                    text = record["generated"]["text"]
                elif "blip.emotion" in nsid and "generated" in record and "text" in record["generated"]:
                    text = record["generated"]["text"]
                elif "sphere.core" in nsid:
                    text = record.get("text", "")
            
            # Format dates
            created_at = datetime.now()
            if "createdAt" in record:
                try:
                    if isinstance(record["createdAt"], str):
                        created_at = datetime.fromisoformat(record["createdAt"].replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Error parsing createdAt timestamp: {e}. Using current time.")
            
            received_at = datetime.now()
            
            # Convert labels to string for storage
            labels_str = ""
            if labels:
                labels_str = ",".join(labels)
            
            # Determine record type from NSID
            record_type = nsid.split('.')[-1]
            if nsid.startswith('me.comind.blip.'):
                record_type = nsid.split('.')[-1]  # concept, thought, emotion
            elif nsid == 'me.comind.sphere.core':
                record_type = 'sphere'
            elif nsid.startswith('me.comind.relationship.'):
                record_type = nsid.split('.')[-1]  # link, sphere, etc.
            
            # First create the repository node
            try:
                # Ensure Repo table exists
                self.conn.execute("""
                    CREATE NODE TABLE IF NOT EXISTS Repo (
                        did STRING PRIMARY KEY,
                        handle STRING DEFAULT '',
                        receivedAt TIMESTAMP
                    )
                """)
                
                # Create or update the repo
                self.conn.execute("""
                    MERGE (r:Repo {did: $did})
                    SET r.handle = $handle,
                        r.receivedAt = timestamp($receivedAt)
                """, {
                    'did': author_did,
                    'handle': author_did,
                    'receivedAt': received_at.isoformat()
                })
                
                logger.debug(f"Created/updated repository for {author_did}")
            except Exception as e:
                logger.error(f"Error creating repository: {e}")
                raise Exception(f"Failed to create repository for {author_did}: {e}")
            
            # Now create the Record node
            try:
                # CRITICAL CHANGE: Store ALL record properties in a content JSON field to avoid schema issues
                # This is a more robust approach that avoids property-not-found errors
                
                # First ensure Record table exists with minimal required schema
                self.conn.execute("""
                    CREATE NODE TABLE IF NOT EXISTS Record (
                        uri STRING PRIMARY KEY,
                        content STRING
                    )
                """)
                
                # Create a complete properties object containing ALL data
                # This is stored as a single JSON field to avoid property access issues
                record_properties = {
                    'uri': uri,
                    'cid': cid,
                    'collection': nsid,
                    'nsid': nsid,
                    'rkey': rkey,
                    'text': text,
                    'recordType': record_type,
                    'labels': labels_str,
                    'raw': record_json,
                    'createdAt': created_at.isoformat(),
                    'receivedAt': received_at.isoformat()
                }
                
                # Store the entire record as a JSON string in the content property
                record_properties_json = json.dumps(record_properties)
                
                # Create or update the record with the JSON content
                self.conn.execute("""
                    MERGE (r:Record {uri: $uri})
                    SET r.content = $content
                """, {
                    'uri': uri, 
                    'content': record_properties_json
                })
                
                logger.debug(f"Created/updated record: {uri}")
            except Exception as e:
                logger.error(f"Error creating record: {e}")
                raise Exception(f"Failed to create record {uri}: {e}")
            
            # Create OWNS relationship between repo and record
            try:
                # Ensure OWNS relationship table exists
                self.conn.execute("""
                    CREATE REL TABLE IF NOT EXISTS OWNS (
                        FROM Repo TO Record,
                        createdAt TIMESTAMP
                    )
                """)
                
                # Create the relationship
                self.conn.execute("""
                    MATCH (repo:Repo {did: $did})
                    MATCH (record:Record {uri: $uri})
                    MERGE (repo)-[rel:OWNS]->(record)
                    SET rel.createdAt = timestamp($createdAt)
                """, {
                    'did': author_did,
                    'uri': uri,
                    'createdAt': received_at.isoformat()
                })
                
                logger.debug(f"Created OWNS relationship from {author_did} to {uri}")
            except Exception as e:
                logger.error(f"Error creating OWNS relationship: {e}")
                raise Exception(f"Failed to create OWNS relationship: {e}")
            
            # Return success
            return True
            
        except Exception as e:
            logger.error(f"Error storing ATProto record {uri}: {str(e)}")
            raise e
    
    def get_atproto_record(self, uri: str) -> Optional[Dict]:
        """
        Retrieve an ATProto record by its URI.
        
        Args:
            uri: The URI of the record to retrieve
            
        Returns:
            The record as a dictionary if found, None otherwise
            
        Raises:
            Exception: If there is an error retrieving the record
        """
        try:
            # Ensure Record table exists with minimal required schema
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Record (
                    uri STRING PRIMARY KEY,
                    content STRING
                )
            """)
            
            # Query to retrieve record by URI - get content field which has all properties
            query = """
                MATCH (r:Record {uri: $uri})
                RETURN r.content as content, count(r) as count
            """
            
            result = self.conn.execute(query, {'uri': uri})
            
            if not result.has_next():
                return None
                
            row = result.get_next()
            content_json, count = row
            
            if count == 0 or not content_json:
                return None
            
            # Parse the content JSON which contains all record properties
            try:
                properties = json.loads(content_json)
                
                # Create a standardized record object
                record = {
                    'uri': properties.get('uri', uri),
                    'cid': properties.get('cid', ''),
                    'nsid': properties.get('nsid', properties.get('collection', '')),
                    'rkey': properties.get('rkey', ''),
                    'text': properties.get('text', ''),
                    'labels': properties.get('labels', '').split(',') if properties.get('labels') else [],
                    'createdAt': properties.get('createdAt'),
                    'receivedAt': properties.get('receivedAt'),
                    'value': {}
                }
                
                # Parse raw JSON for the value field if available
                raw_json = properties.get('raw')
                if raw_json:
                    try:
                        record['value'] = json.loads(raw_json)
                    except Exception as e:
                        logger.debug(f"Failed to parse raw JSON for {uri}: {e}")
                        # No need to raise - just return what we have
                
                return record
                
            except Exception as e:
                logger.error(f"Error parsing content JSON for {uri}: {e}")
                raise Exception(f"Failed to parse content JSON for {uri}: {e}")
                
        except Exception as e:
            logger.error(f"Error retrieving ATProto record {uri}: {str(e)}")
            raise e
    
    def list_atproto_records(self, nsid: str = None, labels: List[str] = None, limit: int = 100) -> List[Dict]:
        """
        List ATProto records with optional filtering by nsid and labels.
        
        Args:
            nsid: Optional namespace ID to filter by
            labels: Optional list of labels to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
            
        Raises:
            Exception: If there is an error listing records
        """
        try:
            # Ensure Record table exists with minimal required schema
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Record (
                    uri STRING PRIMARY KEY,
                    content STRING
                )
            """)
            
            # We'll fetch all records and filter in Python since properties are now in JSON
            query = """
                MATCH (r:Record)
                RETURN r.uri as uri, r.content as content
                LIMIT $limit
            """
            
            params = {'limit': limit * 3}  # Fetch more to allow for filtering
            
            result = self.conn.execute(query, params)
            records = []
            
            # Process records and apply filters in Python
            while result.has_next():
                row = result.get_next()
                uri, content_json = row
                
                if not content_json:
                    continue
                
                try:
                    # Parse properties from JSON
                    properties = json.loads(content_json)
                    
                    # Apply NSID filter if specified
                    if nsid:
                        record_nsid = properties.get('nsid') or properties.get('collection', '')
                        if record_nsid != nsid:
                            continue
                    
                    # Apply labels filter if specified
                    if labels and len(labels) > 0:
                        record_labels = properties.get('labels', '').split(',') if properties.get('labels') else []
                        # Check if all specified labels are in the record's labels
                        if not all(label in record_labels for label in labels):
                            continue
                    
                    # Create standardized record object
                    record = {
                        'uri': properties.get('uri', uri),
                        'cid': properties.get('cid', ''),
                        'nsid': properties.get('nsid', properties.get('collection', '')),
                        'rkey': properties.get('rkey', ''),
                        'text': properties.get('text', ''),
                        'labels': properties.get('labels', '').split(',') if properties.get('labels') else [],
                        'value': {},
                    }
                    
                    # Add timestamps if available
                    if 'createdAt' in properties:
                        record['createdAt'] = properties['createdAt']
                    if 'receivedAt' in properties:
                        record['receivedAt'] = properties['receivedAt']
                    
                    # Parse raw JSON for the value field if available
                    raw_json = properties.get('raw')
                    if raw_json:
                        try:
                            record['value'] = json.loads(raw_json)
                        except Exception as e:
                            logger.debug(f"Failed to parse raw JSON for {uri}: {e}")
                            # Continue with empty value instead of failing
                    
                    records.append(record)
                    
                    # Stop if we've reached the limit
                    if len(records) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error processing record {uri}: {e}")
                    # Skip this record and continue with the next one
            
            return records
                
        except Exception as e:
            logger.error(f"Error listing ATProto records: {str(e)}")
            raise e
    
    def query_atproto_relationships(self, source_uri: str, relationship_type: str = None, limit: int = 100) -> List[Dict]:
        """
        Query relationships from a source ATProto record.
        
        Args:
            source_uri: The URI of the source record
            relationship_type: Optional relationship type to filter by (FOLLOWS, LIKES, REPOSTS, etc.)
            limit: Maximum number of relationships to return
            
        Returns:
            List of related records with relationship information
            
        Raises:
            Exception: If there is an error querying relationships
        """
        try:
            # Ensure Record and relationship tables exist
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Record (
                    uri STRING PRIMARY KEY,
                    content STRING
                )
            """)
            
            # Create relationship tables that might be needed
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS LINKS (
                    FROM Record TO Record,
                    relType STRING DEFAULT 'REFERENCES',
                    strength FLOAT DEFAULT 1.0,
                    note STRING DEFAULT '',
                    createdAt TIMESTAMP
                )
            """)
            
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS IN_SPHERE (
                    FROM Record TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            relationships = []
            params = {'source_uri': source_uri, 'limit': limit}
            
            # Helper function to add relationship data from a result row
            def add_relationship_from_row(row, rel_type):
                src_uri, tgt_uri, rel_record_uri, created_at = row[:4]  # First 4 elements are standard
                
                # Create basic relationship object
                rel = {
                    'source_uri': src_uri,
                    'target_uri': tgt_uri,
                    'record_uri': rel_record_uri if rel_record_uri else None,
                    'created_at': created_at,
                    'type': rel_type
                }
                
                # For LINKS relationship, add additional properties if available
                if rel_type == "LINKS" and len(row) > 4:
                    rel_type_value, strength, note = row[4:7]
                    rel['type'] = rel_type_value if rel_type_value else "LINKS"
                    rel['strength'] = float(strength) if strength is not None else 1.0
                    rel['note'] = note if note else ""
                
                relationships.append(rel)
            
            # Choose query based on relationship type
            if relationship_type == "FOLLOWS":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[:OWNS]-(source_repo:Repo)
                    MATCH (source_repo)-[rel:FOLLOWS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]-(target:Record)
                    RETURN source.uri as source_uri, 
                           target.uri as target_uri, 
                           rel.sourceRecord as record_uri, 
                           rel.createdAt as created_at
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "FOLLOWS")
                    
            elif relationship_type == "LIKES":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[rel:LIKES]->(target:Record)
                    RETURN source.uri as source_uri, 
                           target.uri as target_uri, 
                           rel.sourceRecord as record_uri, 
                           rel.createdAt as created_at
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "LIKES")
                    
            elif relationship_type == "REPOSTS":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[rel:REPOSTS]->(target:Record)
                    RETURN source.uri as source_uri, 
                           target.uri as target_uri, 
                           rel.sourceRecord as record_uri, 
                           rel.createdAt as created_at
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "REPOSTS")
                    
            elif relationship_type == "BLOCKS":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[:OWNS]-(source_repo:Repo)
                    MATCH (source_repo)-[rel:BLOCKS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]-(target:Record)
                    RETURN source.uri as source_uri, 
                           target.uri as target_uri, 
                           rel.sourceRecord as record_uri, 
                           rel.createdAt as created_at
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "BLOCKS")
                    
            elif relationship_type == "LINKS":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[rel:LINKS]->(target:Record)
                    RETURN source.uri as source_uri, 
                           target.uri as target_uri, 
                           null as record_uri, 
                           rel.createdAt as created_at,
                           rel.relType as rel_type, 
                           rel.strength as strength, 
                           rel.note as note
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "LINKS")
                    
            elif relationship_type == "IN_SPHERE":
                query = """
                    MATCH (source:Record {uri: $source_uri})
                    MATCH (source)-[rel:IN_SPHERE]->(sphere:Record)
                    RETURN source.uri as source_uri, 
                           sphere.uri as target_uri, 
                           null as record_uri, 
                           rel.createdAt as created_at
                    LIMIT $limit
                """
                
                result = self.conn.execute(query, params)
                while result.has_next():
                    add_relationship_from_row(result.get_next(), "IN_SPHERE")
                    
            else:
                # If no specific relationship type, try all of them in separate queries
                for rel_type in ["FOLLOWS", "LIKES", "REPOSTS", "BLOCKS", "LINKS", "IN_SPHERE"]:
                    try:
                        rel_results = self.query_atproto_relationships(source_uri, rel_type, limit)
                        relationships.extend(rel_results)
                        if len(relationships) >= limit:
                            relationships = relationships[:limit]
                            break
                    except Exception as rel_error:
                        logger.debug(f"Error querying {rel_type} relationships: {rel_error}")
                        # Continue with other relationship types even if one fails
                
                # Sort by created_at if available
                relationships.sort(
                    key=lambda r: r.get('created_at', ''), 
                    reverse=True
                )
            
            return relationships
            
        except Exception as e:
            logger.error(f"Error querying ATProto relationships for {source_uri}: {str(e)}")
            raise e