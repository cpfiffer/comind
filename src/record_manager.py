from typing import Dict, List, Optional
from atproto import Client as AtProtoClient
from datetime import datetime
import time
import logging
import os
from rich import print

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("record_manager")

# Silence httpx logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

RATE_LIMIT_SLEEP_SECONDS = 1

class RecordManager:
    """
    Manages ATProtocol records within the me.comind namespace.

    This class provides methods to create, retrieve, list, and delete records in an
    ATProtocol repository. It includes safety measures to prevent operations outside
    the allowed namespace and implements rate limiting to prevent API throttling.

    Attributes:
        client: An authenticated ATProtoClient instance
        ALLOWED_NAMESPACE: The namespace prefix that this manager is allowed to operate on
        graph_sync_service: Optional GraphSyncService for real-time graph injection
    """
    ALLOWED_NAMESPACE = "me.comind."

    def __init__(self, client: AtProtoClient, sphere: Optional[str] = None, enable_graph_sync: Optional[bool] = None):
        """
        Initialize a RecordManager with an authenticated ATProto client.

        Args:
            client: An authenticated ATProtoClient instance
            sphere: The sphere to use for the RecordManager. Optional.
            enable_graph_sync: Whether to enable real-time graph sync. If None, 
                              checks COMIND_GRAPH_SYNC_ENABLED environment variable.
        """
        self.client = client
        self.sphere_uri = sphere
        self.graph_sync_service = None

        if sphere:
            splat = sphere.split("/")
            self.sphere_rkey = splat[-1]
            self.sphere_collection = splat[-2]
            print(self.sphere_rkey)
            print(self.sphere_collection)

        # Initialize graph sync if enabled
        if enable_graph_sync is None:
            enable_graph_sync = os.getenv("COMIND_GRAPH_SYNC_ENABLED", "false").lower() in ("true", "1", "yes")
        
        if enable_graph_sync:
            self._initialize_graph_sync()

        logger.debug(f"Initialized RecordManager with client DID: {self.client.me.did if hasattr(self.client, 'me') else 'Not authenticated'}")
        logger.debug(f"Graph sync enabled: {self.graph_sync_service is not None}")

    def _initialize_graph_sync(self):
        """Initialize the graph sync service if dependencies are available."""
        try:
            # Try different import paths depending on execution context
            try:
                from src.graph_sync import create_graph_sync_service
            except ImportError:
                try:
                    from graph_sync import create_graph_sync_service
                except ImportError:
                    from .graph_sync import create_graph_sync_service
            
            # Get Neo4j connection parameters from environment or use defaults
            neo4j_uri = os.getenv("COMIND_NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("COMIND_NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("COMIND_NEO4J_PASSWORD", "comind123")
            
            self.graph_sync_service = create_graph_sync_service(
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password,
                record_manager=self
            )
            logger.info("Graph sync service initialized successfully")
        except ImportError as e:
            logger.warning(f"Graph sync dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize graph sync service: {e}")
            # Don't fail if graph sync can't be initialized

    def _sync_record_to_graph(self, record_response, collection: str, record_data: Dict):
        """Sync a newly created record to the graph database."""
        if not self.graph_sync_service:
            return
            
        try:
            # Use the sync_record method directly with the data we have
            self.graph_sync_service.sync_record_data(
                uri=record_response.uri,
                cid=record_response.cid,
                value=record_data,
                collection=collection
            )
            logger.debug(f"Successfully synced record {record_response.uri} to graph database")
        except Exception as e:
            # Log the error but don't fail the record creation
            logger.error(f"Failed to sync record {record_response.uri} to graph database: {e}")

    def sphere_record(self, target: str, sphere_uri: Optional[str] = None):
        if sphere_uri is None:
            sphere_uri = self.sphere_uri


        if sphere_uri is None:
            return None
        else:
            return {
                'collection': 'me.comind.relationship.sphere',
                'repo': self.client.me.did,
                'record': {
                    'createdAt': datetime.now().isoformat(),
                    'target': target,
                    'sphere_uri': sphere_uri
                }
            }

    def get_sphere_record(self):
        """
        Get the sphere record.
        """
        return self.try_get_record(
            self.sphere_collection,
            self.sphere_rkey
        )

    def get_perspective(self):
        """
        Get the perspective text from the sphere record.

        Returns:
            The perspective text from the sphere record.

        Raises:
            ValueError: If the sphere URI is not set or the perspective record cannot be found.
        """
        if not self.sphere_uri:
            logger.error("No sphere URI set. Cannot get perspective.")
            raise ValueError("No sphere URI set. Cannot get perspective.")

        record = self.get_sphere_record()
        if record:
            return record.value['text']
        else:
            return None

    def get_sphere_name(self):
        """
        Get the sphere name from the sphere record.
        """
        record = self.get_sphere_record()
        if record:
            return record.value['title']
        else:
            return None

    def try_get_record(self, collection: str, rkey: str) -> Optional[Dict]:
        """
        Get the reference of a record.
        """
        try:
            record = self.get_record(collection, rkey)
            return record
        except Exception as e:
            logger.error(f"Error getting reference of record {collection}/{rkey}: {str(e)}")
            return None

    def get_record(self, collection: str, rkey: str) -> Optional[Dict]:
        """
        Get a record from the user's repository.

        Args:
            collection: The collection to get the record from (e.g., me.cominds.thought)
            rkey: The record key identifier

        Returns:
            The record as a dictionary if found, None if the record doesn't exist

        Raises:
            Exception: If an error occurs during the API request
        """
        logger.debug(f"Getting record from collection: {collection} with rkey: {rkey}")
        try:
            response = self.client.com.atproto.repo.get_record({
                'collection': collection,
                'repo': self.client.me.did,
                'rkey': rkey
            })
            logger.debug(f"Successfully retrieved record: {collection}/{rkey}")
            return response
        except Exception as e:
            if 'RecordNotFound' in str(e):
                logger.debug(f"Record not found: {collection}/{rkey}")
                return None
            else:
                logger.error(f"Error retrieving record {collection}/{rkey}: {str(e)}")
                raise e

    def create_record(self, collection: str, record: Dict, rkey: Optional[str] = None) -> Dict:
        """
        Create a record in the user's repository.

        Args:
            collection: The collection to create the record in (e.g., me.cominds.thought)
            record: The record data to create
            rkey: Optional custom record key. If not provided, the server will generate one

        Returns:
            A dictionary containing the created record's metadata, including URI and CID

        Raises:
            Exception: If the record creation fails

        """
        # TODO: #12 Validate records before uploading it to the repo
        logger.debug(f"Creating record in collection: {collection}" + (f" with rkey: {rkey}" if rkey else ""))
        logger.debug(f"Record content: {record}")

        create_params = {
            'collection': collection,
            'repo': self.client.me.did,
            'record': record
        }

        # Add the '$type' field to the record if it's not already present
        if '$type' not in record:
            record['$type'] = collection

        if collection == "me.comind.sphere.core":
            # Set rkey to lowercase title with hyphens instead of spaces
            create_params['rkey'] = create_params['record']['title'].lower().replace(" ", "-")

        if collection == "me.comind.concept":
            # Set rkey to lowercase concept with hyphens instead of spaces
            # Updated to use the new simplified concept structure
            create_params['rkey'] = create_params['record']['concept'].lower().replace(" ", "-")

        if rkey is not None:
            create_params['rkey'] = rkey

        try:
            response = self.client.com.atproto.repo.create_record(create_params)

            # Sync to graph database if enabled
            self._sync_record_to_graph(response, collection, record)

            if self.sphere_uri is not None:
                logger.debug(f"Creating sphere record: {self.sphere_record(response.uri, self.sphere_uri)}")
                sphere_response = self.client.com.atproto.repo.create_record(
                    self.sphere_record(response.uri, self.sphere_uri)
                )
                # Also sync the sphere relationship to graph
                sphere_record_data = self.sphere_record(response.uri, self.sphere_uri)['record']
                self._sync_record_to_graph(sphere_response, "me.comind.relationship.sphere", sphere_record_data)

            logger.debug(f"Successfully created {collection} record https://atp.tools/{response.uri}")
            # logger.info(f"Successfully created {collection} record https://atp.tools/{response.uri}")
            logger.debug(f"Rate limiting: sleeping for {RATE_LIMIT_SLEEP_SECONDS} seconds")
            time.sleep(RATE_LIMIT_SLEEP_SECONDS)
            return response
        except Exception as e:
            logger.error(f"Error creating record in {collection}: {str(e)}")
            print(f"\n[red]Error creating record:[/red]")
            print(f"Collection: {collection}")
            print(f"Record: {record}")
            print(f"RKey: {rkey}")
            print(f"Error details: {str(e)}")
            print(f"Create params: {create_params}")
            raise e

    def list_records(self, collection: str) -> List[Dict]:
        """
        List all records in a collection.

        Args:
            collection: The collection to list records from (e.g., me.cominds.thought)

        Returns:
            A list of record dictionaries

        Raises:
            Exception: If the API request fails
        """
        logger.info(f"Listing records in collection: {collection}")
        try:
            response = self.client.com.atproto.repo.list_records({
                'collection': collection,
                'repo': self.client.me.did
            })
            logger.info(f"Found {len(response.records)} records in collection: {collection}")
            return response.records
        except Exception as e:
            logger.error(f"Error listing records in collection {collection}: {str(e)}")
            raise e

    def list_all_records(self, collection: str) -> List[Dict]:
        """
        List ALL records in a collection, handling pagination automatically.

        Args:
            collection: The collection to list records from (e.g., me.cominds.thought)

        Returns:
            A list of all record dictionaries in the collection

        Raises:
            Exception: If the API request fails
        """
        logger.info(f"Listing all records in collection: {collection}")
        all_records = []
        cursor = None
        
        try:
            while True:
                params = {
                    'collection': collection,
                    'repo': self.client.me.did,
                    'limit': 100  # Use maximum limit for efficiency
                }
                
                if cursor:
                    params['cursor'] = cursor
                
                response = self.client.com.atproto.repo.list_records(params)
                all_records.extend(response.records)
                
                # Check if there are more records
                if hasattr(response, 'cursor') and response.cursor:
                    cursor = response.cursor
                    logger.debug(f"Found {len(response.records)} records, continuing with cursor: {cursor}")
                else:
                    break
            
            logger.info(f"Found {len(all_records)} total records in collection: {collection}")
            return all_records
        except Exception as e:
            logger.error(f"Error listing all records in collection {collection}: {str(e)}")
            raise e

    def delete_record(self, collection: str, rkey: str, sleep_time: int = 1) -> None:
        """
        Delete a record from the user's repository.

        Args:
            collection: The collection containing the record (e.g., me.cominds.thought)
            rkey: The record key identifier

        Raises:
            ValueError: If attempting to delete a record outside the allowed namespace
            Exception: If the deletion fails
        """
        logger.info(f"Deleting record: {collection}/{rkey}")

        if not collection.startswith(self.ALLOWED_NAMESPACE):
            error_msg = f"Cannot delete records outside the {self.ALLOWED_NAMESPACE} namespace"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            self.client.com.atproto.repo.delete_record({
                'collection': collection,
                'repo': self.client.me.did,
                'rkey': rkey
            })
            logger.debug(f"Successfully deleted record: {collection}/{rkey}")
            time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"Error deleting record {collection}/{rkey}: {str(e)}")
            raise e

    def clear_collection(self, collection: str, sleep_time: int = 1) -> None:
        """
        Delete all records in a collection.

        Args:
            collection: The collection to clear (e.g., me.cominds.thought)
            sleep_time: The time to sleep between deleting records

        Raises:
            ValueError: If attempting to clear a collection outside the allowed namespace
            Exception: If the operation fails
        """
        logger.info(f"Clearing all records in collection: {collection}")

        if not collection.startswith(self.ALLOWED_NAMESPACE):
            error_msg = f"Cannot clear collections outside the {self.ALLOWED_NAMESPACE} namespace"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            records = self.list_all_records(collection)
            logger.info(f"Found {len(records)} records to delete in collection: {collection}")

            for record in records:
                # The ATProto client returns records with uri in format: at://did/collection/rkey
                # Extract the rkey from the uri
                rkey = record.uri.split('/')[-1]
                logger.debug(f"Deleting record with rkey: {rkey}")
                self.delete_record(collection, rkey, sleep_time=sleep_time)

            logger.info(f"Successfully cleared all records in collection: {collection}")
        except Exception as e:
            logger.error(f"Error clearing collection {collection}: {str(e)}")
            raise e
