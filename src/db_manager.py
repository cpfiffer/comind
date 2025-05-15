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
        
        # Try to set up full-text search capability
        try:
            self.setup_fts_index()
        except Exception as e:
            logger.warning(f"Could not initialize full-text search: {e}. Text search will use fallback method.")
        
    def create_db_if_not_exists(self):
        """Create the database directory if it doesn't exist"""
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
            logger.info(f"Created database directory at: {self.db_path}")
            
    def setup_schema(self):
        """
        Set up the database schema based on ATProto lexicons.
        
        This method creates the node and relationship tables needed to
        represent the ATProto data model.
        """
        try:
            # Create User node table
            self.conn.execute("""
                CREATE NODE TABLE User (
                    did STRING PRIMARY KEY,
                    handle STRING,
                    displayName STRING,
                    description STRING
                )
            """)
            
            # Create Repo node table
            self.conn.execute("""
                CREATE NODE TABLE Repo (
                    did STRING PRIMARY KEY,
                    handle STRING,
                    receivedAt TIMESTAMP
                )
            """)
            
            # Create ATRecord node table (base for all record types)
            self.conn.execute("""
                CREATE NODE TABLE ATRecord (
                    uri STRING PRIMARY KEY,
                    cid STRING,
                    nsid STRING,
                    rkey STRING,
                    createdAt TIMESTAMP,
                    receivedAt TIMESTAMP,
                    raw STRING,
                    text STRING,
                    labels STRING
                )
            """)
            
            # Create Record node table (base for all record types)
            self.conn.execute("""
                CREATE NODE TABLE Record (
                    uri STRING PRIMARY KEY,
                    cid STRING,
                    collection STRING,
                    rkey STRING,
                    createdAt TIMESTAMP,
                    recordType STRING,
                    content STRING
                )
            """)
            
            # Create sphere table
            self.conn.execute("""
                CREATE NODE TABLE Sphere (
                    uri STRING PRIMARY KEY,
                    title STRING,
                    text STRING,
                    description STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipConcept table
            self.conn.execute("""
                CREATE NODE TABLE BlipConcept (
                    uri STRING PRIMARY KEY,
                    text STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipEmotion table
            self.conn.execute("""
                CREATE NODE TABLE BlipEmotion (
                    uri STRING PRIMARY KEY,
                    type STRING,
                    text STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # Create BlipThought table
            self.conn.execute("""
                CREATE NODE TABLE BlipThought (
                    uri STRING PRIMARY KEY,
                    type STRING,
                    context STRING,
                    text STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # Create relationship tables
            
            # AUTHORED relationship between User and Record
            self.conn.execute("""
                CREATE REL TABLE AUTHORED (
                    FROM User TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            # OWNS relationship between Repo and ATRecord
            self.conn.execute("""
                CREATE REL TABLE OWNS (
                    FROM Repo TO ATRecord,
                    createdAt TIMESTAMP
                )
            """)
            
            # IN_SPHERE relationship between Record and Sphere
            self.conn.execute("""
                CREATE REL TABLE IN_SPHERE (
                    FROM Record TO Sphere,
                    createdAt TIMESTAMP
                )
            """)
            
            # LINKS relationship for general connections between records
            self.conn.execute("""
                CREATE REL TABLE LINKS (
                    FROM Record TO Record,
                    relType STRING,
                    strength FLOAT,
                    note STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # TARGET relationship for records with targets
            self.conn.execute("""
                CREATE REL TABLE TARGET (
                    FROM Record TO Record,
                    createdAt TIMESTAMP
                )
            """)
            
            # FOLLOWS relationship between ATRecords
            self.conn.execute("""
                CREATE REL TABLE FOLLOWS (
                    FROM ATRecord TO ATRecord, 
                    sourceRecord STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # LIKES relationship between ATRecords
            self.conn.execute("""
                CREATE REL TABLE LIKES (
                    FROM ATRecord TO ATRecord,
                    sourceRecord STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # REPOSTS relationship between ATRecords
            self.conn.execute("""
                CREATE REL TABLE REPOSTS (
                    FROM ATRecord TO ATRecord,
                    sourceRecord STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            # BLOCKS relationship between ATRecords
            self.conn.execute("""
                CREATE REL TABLE BLOCKS (
                    FROM ATRecord TO ATRecord,
                    sourceRecord STRING,
                    createdAt TIMESTAMP
                )
            """)
            
            logger.info("Successfully created database schema")
            
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Schema already exists, skipping creation")
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
        """
        try:
            # Install and load FTS extension
            self.conn.execute("INSTALL FTS")
            self.conn.execute("LOAD FTS")
            
            # Create FTS indexes for Record content
            self.conn.execute("""
                CALL CREATE_FTS_INDEX('Record', 'content_index', ['content'])
            """)
            
            logger.info("Full-text search indexes created successfully")
            return True
        except Exception as e:
            # If already exists, just log and continue
            if "already exists" in str(e):
                logger.info("Full-text search indexes already exist")
                return True
            logger.error(f"Error setting up full-text search indexes: {str(e)}")
            return False
    
    def find_similar_records(self, text: str, collection: str = None, limit: int = 10) -> List[Dict]:
        """
        Find records with similar text content using full-text search.
        
        Args:
            text: The text to search for
            collection: Optional collection to limit the search to
            limit: Maximum number of results to return
            
        Returns:
            List of matching records
        """
        try:
            # Try to ensure FTS is installed
            try:
                self.setup_fts_index()
            except Exception as e:
                logger.warning(f"Could not set up FTS index: {e}. Using basic search.")
                return self._find_records_basic(text, collection, limit)
            
            # Use FTS query
            if collection:
                # With collection filter
                query = f"""
                    CALL QUERY_FTS_INDEX('Record', 'content_index', $search_text) 
                    YIELD node, score
                    WITH node, score
                    WHERE node.collection = $collection
                    RETURN node.uri as uri, node.content as content, node.collection as collection, score
                    ORDER BY score DESC
                    LIMIT $limit
                """
                params = {'search_text': text, 'collection': collection, 'limit': limit}
            else:
                # Without collection filter
                query = f"""
                    CALL QUERY_FTS_INDEX('Record', 'content_index', $search_text) 
                    YIELD node, score
                    WITH node, score
                    RETURN node.uri as uri, node.content as content, node.collection as collection, score
                    ORDER BY score DESC
                    LIMIT $limit
                """
                params = {'search_text': text, 'limit': limit}
            
            result = self.conn.execute(query, params)
            matches = []
            
            while result.has_next():
                row = result.get_next()
                uri, content, collection, score = row
                matches.append({
                    'uri': uri,
                    'collection': collection,
                    'value': json.loads(content),
                    'score': score
                })
                
            return matches
                
        except Exception as e:
            logger.error(f"Error finding similar records with FTS: {str(e)}")
            # Fall back to basic search if FTS fails
            return self._find_records_basic(text, collection, limit)
    
    def _find_records_basic(self, text: str, collection: str = None, limit: int = 10) -> List[Dict]:
        """
        Basic search implementation that filters records in Python.
        Used as a fallback when FTS is not available.
        """
        try:
            # Query to get records
            if collection:
                query = """
                    MATCH (r:Record)
                    WHERE r.collection = $collection
                    RETURN r.uri as uri, r.content as content, r.collection as collection
                    LIMIT $max_records
                """
                params = {'collection': collection, 'max_records': limit * 10}  # Get more to filter
            else:
                query = """
                    MATCH (r:Record)
                    RETURN r.uri as uri, r.content as content, r.collection as collection
                    LIMIT $max_records
                """
                params = {'max_records': limit * 10}  # Get more to filter
            
            result = self.conn.execute(query, params)
            matches = []
            
            # Process in Python
            while result.has_next():
                row = result.get_next()
                uri, content, collection = row
                
                # Check if content contains search text
                content_obj = json.loads(content)
                content_str = json.dumps(content_obj).lower()
                
                if text.lower() in content_str:
                    matches.append({
                        'uri': uri,
                        'collection': collection,
                        'value': content_obj
                    })
                    
                    if len(matches) >= limit:
                        break
            
            return matches
            
        except Exception as e:
            logger.error(f"Error in basic record search: {str(e)}")
            return []
    
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
            
            # First, ensure the repo exists
            self.conn.execute("""
                MERGE (r:Repo {did: $did})
                SET r.receivedAt = $receivedAt
            """, {
                'did': author_did,
                'receivedAt': received_at
            })
            
            # Store the ATRecord
            self.conn.execute("""
                MERGE (r:ATRecord {uri: $uri})
                SET r.cid = $cid,
                    r.nsid = $nsid,
                    r.rkey = $rkey,
                    r.createdAt = $createdAt,
                    r.receivedAt = $receivedAt,
                    r.raw = $raw,
                    r.text = $text,
                    r.labels = $labels
            """, {
                'uri': uri,
                'cid': cid,
                'nsid': nsid,
                'rkey': rkey,
                'createdAt': created_at,
                'receivedAt': received_at,
                'raw': record_json,
                'text': text,
                'labels': labels_str
            })
            
            # Create OWNS relationship between repo and record
            self.conn.execute("""
                MATCH (repo:Repo {did: $did})
                MATCH (record:ATRecord {uri: $uri})
                MERGE (repo)-[rel:OWNS]->(record)
                SET rel.createdAt = $createdAt
            """, {
                'did': author_did,
                'uri': uri,
                'createdAt': received_at
            })
            
            # Handle special record types that create relationships
            if nsid == "app.bsky.graph.follow" and "subject" in record:
                target_did = record["subject"]
                # Find the target repo
                self.conn.execute("""
                    MERGE (target:Repo {did: $target_did})
                """, {
                    'target_did': target_did
                })
                
                # Create FOLLOWS relationship
                self.conn.execute("""
                    MATCH (source:ATRecord {uri: $uri})
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
            
            elif nsid == "app.bsky.feed.like" and "subject" in record:
                target_uri = record["subject"]["uri"]
                # Create LIKES relationship
                self.conn.execute("""
                    MATCH (source:ATRecord {uri: $uri})
                    MATCH (target:ATRecord {uri: $target_uri})
                    MERGE (source)-[rel:LIKES]->(target)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'target_uri': target_uri,
                    'createdAt': created_at
                })
            
            elif nsid == "app.bsky.feed.repost" and "subject" in record:
                target_uri = record["subject"]["uri"]
                # Create REPOSTS relationship
                self.conn.execute("""
                    MATCH (source:ATRecord {uri: $uri})
                    MATCH (target:ATRecord {uri: $target_uri})
                    MERGE (source)-[rel:REPOSTS]->(target)
                    SET rel.sourceRecord = $uri,
                        rel.createdAt = $createdAt
                """, {
                    'uri': uri,
                    'target_uri': target_uri,
                    'createdAt': created_at
                })
            
            elif nsid == "app.bsky.graph.block" and "subject" in record:
                target_did = record["subject"]
                # Find the target repo
                self.conn.execute("""
                    MERGE (target:Repo {did: $target_did})
                """, {
                    'target_did': target_did
                })
                
                # Create BLOCKS relationship
                self.conn.execute("""
                    MATCH (source:ATRecord {uri: $uri})
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
            if "me.comind" in nsid:
                # Add appropriate label based on record type
                if "blip.concept" in nsid:
                    self.conn.execute("""
                        MATCH (r:ATRecord {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'ATRecord,Blip,Concept'
                                         WHEN r.labels CONTAINS 'Concept' THEN r.labels
                                         ELSE r.labels + ',Blip,Concept'
                                       END
                    """, {'uri': uri})
                
                elif "blip.thought" in nsid:
                    self.conn.execute("""
                        MATCH (r:ATRecord {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'ATRecord,Blip,Thought'
                                         WHEN r.labels CONTAINS 'Thought' THEN r.labels
                                         ELSE r.labels + ',Blip,Thought'
                                       END
                    """, {'uri': uri})
                
                elif "blip.emotion" in nsid:
                    self.conn.execute("""
                        MATCH (r:ATRecord {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'ATRecord,Blip,Emotion'
                                         WHEN r.labels CONTAINS 'Emotion' THEN r.labels
                                         ELSE r.labels + ',Blip,Emotion'
                                       END
                    """, {'uri': uri})
                
                elif "sphere.core" in nsid:
                    self.conn.execute("""
                        MATCH (r:ATRecord {uri: $uri})
                        SET r.labels = CASE 
                                         WHEN r.labels = '' THEN 'ATRecord,Core'
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
                                MATCH (target:ATRecord {uri: $uri})
                                MERGE (source:ATRecord {uri: $from_uri})
                                MERGE (source)-[rel:LINKS]->(target)
                                SET rel.relType = 'REFERENCES',
                                    rel.createdAt = $createdAt
                            """, {
                                'uri': uri,
                                'from_uri': from_uri,
                                'createdAt': created_at
                            })
                
                # Handle relationship links
                if "relationship.link" in nsid:
                    if "target" in record:
                        target_uri = record["target"]
                        self.conn.execute("""
                            MATCH (source:ATRecord {uri: $uri})
                            MERGE (target:ATRecord {uri: $target_uri})
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
                if "relationship.sphere" in nsid and "sphere_uri" in record and "target" in record:
                    sphere_uri = record["sphere_uri"]
                    target_uri = record["target"]["uri"]
                    
                    self.conn.execute("""
                        MATCH (record:ATRecord {uri: $target_uri})
                        MATCH (sphere:ATRecord {uri: $sphere_uri})
                        MERGE (sphere)-[rel:CONGREGATES]->(record)
                        SET rel.createdAt = $createdAt
                    """, {
                        'target_uri': target_uri,
                        'sphere_uri': sphere_uri,
                        'createdAt': created_at
                    })
            
            logger.debug(f"Stored ATProto record: {nsid}/{rkey}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing ATProto record {uri}: {str(e)}")
            logger.exception(e)
            return False
    
    def get_atproto_record(self, uri: str) -> Optional[Dict]:
        """
        Retrieve an ATProto record by its URI.
        
        Args:
            uri: The URI of the record to retrieve
            
        Returns:
            The record as a dictionary if found, None otherwise
        """
        try:
            query = """
                MATCH (r:ATRecord {uri: $uri})
                RETURN r.uri as uri, r.cid as cid, r.nsid as nsid, r.raw as raw, 
                       r.createdAt as createdAt, r.receivedAt as receivedAt, r.labels as labels
            """
            
            result = self.conn.execute(query, {'uri': uri})
            
            if result.has_next():
                row = result.get_next()
                uri, cid, nsid, raw, created_at, received_at, labels = row
                
                record = {
                    'uri': uri,
                    'cid': cid,
                    'nsid': nsid,
                    'value': json.loads(raw),
                    'createdAt': created_at,
                    'receivedAt': received_at,
                    'labels': labels.split(',') if labels else []
                }
                return record
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving ATProto record {uri}: {str(e)}")
            return None
    
    def list_atproto_records(self, nsid: str = None, labels: List[str] = None, limit: int = 100) -> List[Dict]:
        """
        List ATProto records with optional filtering by nsid and labels.
        
        Args:
            nsid: Optional namespace ID to filter by
            labels: Optional list of labels to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        try:
            where_clauses = []
            params = {'limit': limit}
            
            if nsid:
                where_clauses.append("r.nsid = $nsid")
                params['nsid'] = nsid
            
            if labels and len(labels) > 0:
                label_conditions = []
                for i, label in enumerate(labels):
                    param_name = f'label_{i}'
                    label_conditions.append(f"r.labels CONTAINS ${param_name}")
                    params[param_name] = label
                
                where_clauses.append(f"({' AND '.join(label_conditions)})")
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            query = f"""
                MATCH (r:ATRecord)
                WHERE {where_clause}
                RETURN r.uri as uri, r.cid as cid, r.nsid as nsid, r.raw as raw, 
                       r.createdAt as createdAt, r.receivedAt as receivedAt, r.labels as labels
                ORDER BY r.createdAt DESC
                LIMIT $limit
            """
            
            result = self.conn.execute(query, params)
            records = []
            
            while result.has_next():
                row = result.get_next()
                uri, cid, nsid, raw, created_at, received_at, labels_str = row
                
                record = {
                    'uri': uri,
                    'cid': cid,
                    'nsid': nsid,
                    'value': json.loads(raw),
                    'createdAt': created_at,
                    'receivedAt': received_at,
                    'labels': labels_str.split(',') if labels_str else []
                }
                records.append(record)
                
            return records
                
        except Exception as e:
            logger.error(f"Error listing ATProto records: {str(e)}")
            return []
    
    def query_atproto_relationships(self, source_uri: str, relationship_type: str = None, limit: int = 100) -> List[Dict]:
        """
        Query relationships from a source ATProto record.
        
        Args:
            source_uri: The URI of the source record
            relationship_type: Optional relationship type to filter by (FOLLOWS, LIKES, REPOSTS, etc.)
            limit: Maximum number of relationships to return
            
        Returns:
            List of related records with relationship information
        """
        try:
            relationships = []
            params = {'source_uri': source_uri, 'limit': limit}
            
            # Determine the relationship table based on type
            if relationship_type == "FOLLOWS":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})
                    MATCH (source_repo:Repo)<-[:OWNS]-(source)
                    MATCH (source_repo)-[rel:FOLLOWS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'FOLLOWS' as rel_type
                    LIMIT $limit
                """
            elif relationship_type == "LIKES":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:LIKES]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'LIKES' as rel_type
                    LIMIT $limit
                """
            elif relationship_type == "REPOSTS":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:REPOSTS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'REPOSTS' as rel_type
                    LIMIT $limit
                """
            elif relationship_type == "BLOCKS":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})
                    MATCH (source_repo:Repo)<-[:OWNS]-(source)
                    MATCH (source_repo)-[rel:BLOCKS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'BLOCKS' as rel_type
                    LIMIT $limit
                """
            elif relationship_type == "LINKS":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:LINKS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           '' as record_uri, rel.createdAt as created_at,
                           rel.relType as rel_type, rel.strength as strength, rel.note as note
                    LIMIT $limit
                """
            elif relationship_type == "IN_SPHERE":
                query = """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:IN_SPHERE]->(sphere:ATRecord)
                    RETURN source.uri as source_uri, sphere.uri as target_uri, 
                           '' as record_uri, rel.createdAt as created_at,
                           'IN_SPHERE' as rel_type
                    LIMIT $limit
                """
            else:
                # Query all relationship types
                queries = [
                    """
                    MATCH (source:ATRecord {uri: $source_uri})
                    MATCH (source_repo:Repo)<-[:OWNS]-(source)
                    MATCH (source_repo)-[rel:FOLLOWS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'FOLLOWS' as rel_type
                    LIMIT $limit
                    """,
                    """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:LIKES]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'LIKES' as rel_type
                    LIMIT $limit
                    """,
                    """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:REPOSTS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'REPOSTS' as rel_type
                    LIMIT $limit
                    """,
                    """
                    MATCH (source:ATRecord {uri: $source_uri})
                    MATCH (source_repo:Repo)<-[:OWNS]-(source)
                    MATCH (source_repo)-[rel:BLOCKS]->(target_repo:Repo)
                    MATCH (target_repo)-[:OWNS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           rel.sourceRecord as record_uri, rel.createdAt as created_at,
                           'BLOCKS' as rel_type
                    LIMIT $limit
                    """,
                    """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:LINKS]->(target:ATRecord)
                    RETURN source.uri as source_uri, target.uri as target_uri, 
                           '' as record_uri, rel.createdAt as created_at,
                           rel.relType as rel_type, rel.strength as strength, rel.note as note
                    LIMIT $limit
                    """,
                    """
                    MATCH (source:ATRecord {uri: $source_uri})-[rel:IN_SPHERE]->(sphere:ATRecord)
                    RETURN source.uri as source_uri, sphere.uri as target_uri, 
                           '' as record_uri, rel.createdAt as created_at,
                           'IN_SPHERE' as rel_type
                    LIMIT $limit
                    """
                ]
                
                # Execute each query and combine results
                for q in queries:
                    try:
                        result = self.conn.execute(q, params)
                        while result.has_next():
                            row = result.get_next()
                            if len(row) == 5:
                                source_uri, target_uri, record_uri, created_at, rel_type = row
                                rel = {
                                    'source_uri': source_uri,
                                    'target_uri': target_uri,
                                    'record_uri': record_uri,
                                    'created_at': created_at,
                                    'type': rel_type
                                }
                            else:
                                source_uri, target_uri, record_uri, created_at, rel_type, strength, note = row
                                rel = {
                                    'source_uri': source_uri,
                                    'target_uri': target_uri,
                                    'record_uri': record_uri,
                                    'created_at': created_at,
                                    'type': rel_type,
                                    'strength': strength,
                                    'note': note
                                }
                            relationships.append(rel)
                            
                            if len(relationships) >= limit:
                                break
                                
                        if len(relationships) >= limit:
                            break
                            
                    except Exception as e:
                        logger.error(f"Error executing relationship query: {str(e)}")
                        continue
                        
                # Sort by created_at
                relationships.sort(key=lambda r: r.get('created_at', ''), reverse=True)
                
                # Limit to requested number
                relationships = relationships[:limit]
                
                return relationships
            
            # Execute the specific relationship query if a type was specified
            if relationship_type:
                result = self.conn.execute(query, params)
                
                while result.has_next():
                    row = result.get_next()
                    if len(row) == 5:
                        source_uri, target_uri, record_uri, created_at, rel_type = row
                        rel = {
                            'source_uri': source_uri,
                            'target_uri': target_uri,
                            'record_uri': record_uri,
                            'created_at': created_at,
                            'type': rel_type
                        }
                    else:
                        source_uri, target_uri, record_uri, created_at, rel_type, strength, note = row
                        rel = {
                            'source_uri': source_uri,
                            'target_uri': target_uri,
                            'record_uri': record_uri,
                            'created_at': created_at,
                            'type': rel_type,
                            'strength': strength,
                            'note': note
                        }
                    relationships.append(rel)
            
            return relationships
                
        except Exception as e:
            logger.error(f"Error querying ATProto relationships for {source_uri}: {str(e)}")
            return []


# Function to integrate with record_manager.py
def mirror_record_to_db(record_manager, db_manager, collection: str, record: Dict, rkey: str = None, sphere_uri: str = None):
    """
    Mirror a record from ATProto to the database.
    
    This function can be called after creating a record with record_manager
    to ensure it's also stored in the database.
    
    Args:
        record_manager: The RecordManager instance
        db_manager: The DBManager instance
        collection: The collection the record belongs to
        record: The record data
        rkey: The record key identifier (optional)
        sphere_uri: The URI of the sphere this record belongs to (optional)
    """
    # Create the appropriate URI format
    did = record_manager.client.me.did
    if rkey is None:
        # If rkey is not provided, it might be in the response from create_record
        if hasattr(record, 'uri'):
            uri = record.uri
            cid = record.cid
        else:
            # Handle case where we don't have an rkey
            logger.warning("No rkey provided and record object doesn't have uri attribute")
            return None
    else:
        uri = f"at://{did}/{collection}/{rkey}"
        cid = ""  # We might not have the CID in this case
    
    # Store in database
    db_manager.store_record(
        collection=collection,
        record=record,
        uri=uri,
        cid=cid,
        author_did=did,
        rkey=rkey,
        sphere_uri=sphere_uri
    )
    
    return uri

# Helper function to process ATProto events from the jetstream
def process_atproto_event(db_manager, event: Dict) -> bool:
    """
    Process an ATProto event from the jetstream and store it in the database.
    
    Args:
        db_manager: The DBManager instance
        event: The event data from the jetstream
        
    Returns:
        True if the event was processed successfully, False otherwise
    """
    try:
        # Extract event data
        author_did = event.get("did")
        if not author_did:
            logger.error("No author DID found in event")
            return False
        
        # Handle create operation
        if (event.get("kind") == "commit" and 
            event.get("commit", {}).get("operation") == "create"):
            
            # Extract record data
            commit = event.get("commit", {})
            collection = commit.get("collection")
            rkey = commit.get("rkey")
            record = commit.get("record", {})
            cid = commit.get("cid", "")
            
            # Skip if missing required data
            if not collection or not rkey or not record:
                logger.warning(f"Missing required data in event: collection={collection}, rkey={rkey}")
                return False
            
            # Construct URI
            uri = f"at://{author_did}/{collection}/{rkey}"
            
            # Determine labels based on collection
            labels = ["ATRecord"]
            
            if collection == "app.bsky.feed.post":
                labels.append("Post")
            elif "me.comind" in collection:
                if "blip.concept" in collection:
                    labels.extend(["Blip", "Concept"])
                elif "blip.thought" in collection:
                    labels.extend(["Blip", "Thought"])
                elif "blip.emotion" in collection:
                    labels.extend(["Blip", "Emotion"])
                elif "sphere.core" in collection:
                    labels.append("Core")
            
            # Store the record
            success = db_manager.store_atproto_record(
                uri=uri,
                cid=cid,
                nsid=collection,
                record=record,
                author_did=author_did,
                rkey=rkey,
                labels=labels
            )
            
            return success
        
        # Handle other operations (delete, update)
        elif (event.get("kind") == "commit" and 
              event.get("commit", {}).get("operation") in ["delete", "update"]):
            
            # TODO: Implement handling for delete and update operations
            logger.info(f"Event operation {event.get('commit', {}).get('operation')} not yet implemented")
            return False
        
        else:
            logger.warning(f"Unknown event kind or operation: {event.get('kind')} / {event.get('commit', {}).get('operation')}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing ATProto event: {str(e)}")
        return False