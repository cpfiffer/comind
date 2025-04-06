from typing import Dict, List, Optional
from atproto import Client as AtProtoClient
from datetime import datetime
import time
import logging
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
    """
    ALLOWED_NAMESPACE = "me.comind."

    def __init__(self, client: AtProtoClient):
        """
        Initialize a RecordManager with an authenticated ATProto client.

        Args:
            client: An authenticated ATProtoClient instance
        """
        self.client = client
        logger.debug(f"Initialized RecordManager with client DID: {self.client.me.did if hasattr(self.client, 'me') else 'Not authenticated'}")

    def get_record(self, collection: str, rkey: str) -> Optional[Dict]:
        """
        Get a record from the user's repository.

        Args:
            collection: The collection to get the record from (e.g., me.comind.blips.thought)
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
            collection: The collection to create the record in (e.g., me.comind.blips.thought)
            record: The record data to create
            rkey: Optional custom record key. If not provided, the server will generate one

        Returns:
            A dictionary containing the created record's metadata, including URI and CID

        Raises:
            Exception: If the record creation fails
        """
        logger.debug(f"Creating record in collection: {collection}" + (f" with rkey: {rkey}" if rkey else ""))
        logger.debug(f"Record content: {record}")

        create_params = {
            'collection': collection,
            'repo': self.client.me.did,
            'record': record
        }

        if collection == "me.comind.sphere.core":
            # Set rkey to lowercase title with hyphens instead of spaces
            create_params['rkey'] = create_params['record']['title'].lower().replace(" ", "-")

        if rkey is not None:
            create_params['rkey'] = rkey

        try:
            response = self.client.com.atproto.repo.create_record(create_params)
            logger.debug(f"Successfully created {collection} record. URI: {response.uri}, CID: {response.cid}")
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
            collection: The collection to list records from (e.g., me.comind.blips.thought)

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

    def delete_record(self, collection: str, rkey: str) -> None:
        """
        Delete a record from the user's repository.

        Args:
            collection: The collection containing the record (e.g., me.comind.blips.thought)
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
            logger.info(f"Successfully deleted record: {collection}/{rkey}")
        except Exception as e:
            logger.error(f"Error deleting record {collection}/{rkey}: {str(e)}")
            raise e

    def clear_collection(self, collection: str) -> None:
        """
        Delete all records in a collection.

        Args:
            collection: The collection to clear (e.g., me.comind.blips.thought)

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
            records = self.list_records(collection)
            logger.info(f"Found {len(records)} records to delete in collection: {collection}")

            for record in records:
                # The ATProto client returns records with uri in format: at://did/collection/rkey
                # Extract the rkey from the uri
                rkey = record.uri.split('/')[-1]
                logger.debug(f"Deleting record with rkey: {rkey}")
                self.delete_record(collection, rkey)

            logger.info(f"Successfully cleared all records in collection: {collection}")
        except Exception as e:
            logger.error(f"Error clearing collection {collection}: {str(e)}")
            raise e
