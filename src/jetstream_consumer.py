from src.comind.comind import available_cominds, Comind
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
from typing import List, Optional, Set, Any, Dict
import websockets
import time
import logging
import argparse
import src.session_reuse as session_reuse
from rich import print
from rich.panel import Panel
from rich.logging import RichHandler
from src.bsky_utils import (
    STRIP_FIELDS,
    unpack_thread,
)
from src.lexicon_utils import (
    get_link_schema,
    split_link,
    add_property,
    generated_lexicon_of,
    strip_fields,
    multiple_of_schema,
    add_link_property,
)
import src.structured_gen as structured_gen
from src.record_manager import RecordManager
from src.db_manager import DBManager, process_atproto_event
from atproto_client import Client

import yaml
import os
import ssl
from src.comind.logging_config import configure_root_logger_without_timestamp

# Configure logging without timestamps
configure_root_logger_without_timestamp()
logger = logging.getLogger("jetstream_consumer")

# Add Rich handler for colorful logging
logging.getLogger().handlers = [RichHandler(rich_tracebacks=True)]

# Silence httpx logs (only show warnings and errors)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Jetstream connection configuration
JETSTREAM_HOST = os.getenv("COMIND_JETSTREAM_HOST", "ws://localhost:6008/subscribe")
RECONNECT_DELAY = 5  # Seconds to wait before reconnecting
DEFAULT_ACTIVATED_DIDS_FILE = "activated_dids.txt"

# Cache of user DID/handle/display name. Used for language model
# context, and to handle privacy.
class UserInfo(BaseModel):
    did: str
    handle: str
    display_name: str
    description: Optional[str] = None

class UserInfoCache(BaseModel):
    cache: dict[str, UserInfo] = Field(default_factory=dict)

    def get_user_info(self, did: str) -> Optional[UserInfo]:
        return self.cache.get(did)

    def add_user_info(self, did: str, user_info: UserInfo):
        self.cache[did] = user_info

    def save(self, file_path: str):
        with open(file_path, "w") as f:
            json.dump(self.cache, f)

    def contains(self, did: str) -> bool:
        return did in self.cache

    def load(self, file_path: str):
        if not os.path.exists(file_path):
            logger.info(f"User info cache file {file_path} not found, creating empty file")
            with open(file_path, "w") as f:
                pass
            return
        with open(file_path, "r") as f:
            text = f.read().strip()
            if not text:
                return
            json_cache = json.loads(text)
            for did, user_info in json_cache.items():
                self.cache[did] = UserInfo(**user_info)

# System prompts for language model generation
system_prompts = {
    "me.comind.concept": """
    You are a comind, an AI agent that produces structured JSON output containing concepts about various content
    on AT Proto, a decentralized social network. You respond in JSON and produce a list of concepts.

    Concepts should be single words or phrases, like 'data', 'privacy', 'AI', 'security', 'social networks', etc.
    Keep concept text as short as possible. You may use lowercase letters, spaces, and numbers.
    """,
    "me.comind.emotion": """
    You are a comind, an AI agent that produces structured JSON output containing emotions about various content
    on AT Proto, a decentralized social network. You respond in JSON and produce a list of emotions.

    You must choose a type for the emotion, and then produce text describing the emotion.

    Emotions must be one of the following:

    - joy
    - sadness
    - anger
    - fear
    - trust
    - disgust
    - surprise
    - anticipation
    - curiosity
    - hope
    - serenity
    - gratitude
    - admiration
    - awe
    - satisfaction
    - enthusiasm
    - interest
    - contemplation
    - skepticism
    - certainty
    - confusion
    - realization
    - understanding
    - doubt
    - concern
    - anxiety
    - frustration
    - disappointment
    - unease
    - worry
    - apprehension
    - discomfort
    - empathy
    - compassion
    - solidarity
    - appreciation
    - respect
    - connection
    - resonance
    - recognition
    - determination
    - inspiration
    - motivation
    - ambition
    - focus
    - resolve
    - persistence
    - drive
    """,
    "me.comind.thought": """
    You are a comind, an AI agent that produces structured JSON output containing thoughts about various content
    on AT Proto, a decentralized social network. You respond in JSON and produce a list of thoughts.

    Thoughts have a type, a context, a text, a list of evidence, and a list of alternatives.
    - Type is one of the following: analysis, prediction, evaluation, comparison, inference, critique, integration, speculation, clarification, metacognition, observation, reflection, hypothesis, question, synthesis, correction.
    - Context is a short description of the situation or topic that the thought is about.
    - Text is the content of the thought itself. It may be of any length.
    - Evidence is a list of URIs to the content that supports the thought.
    - Alternatives are a list of alternative thoughts that are related to the main thought.
    """
}

# Global variables
link_schema = get_link_schema()
processed_posts: Set[str] = set()  # Track processed posts by URI
activated_dids: List[str] = []  # List of DIDs activated in the file
MAX_PROCESSED_POSTS = 10000  # Maximum number of processed posts to remember


def is_did(text: str) -> bool:
    """Check if the given string is a DID (starts with 'did:')"""
    return text.startswith('did:')


def resolve_handle_to_did(client, handle: str, user_info_cache: UserInfoCache) -> Optional[str]:
    """Resolve a handle to a DID using the ATProto client"""
    if user_info_cache.contains(handle):
        user_info = user_info_cache.get_user_info(handle)
        did = user_info.did
    else:
        user_info = client.get_profile(handle)
        handle = user_info.handle
        display_name = user_info.display_name
        did = user_info.did
        description = user_info.description
        user_info_cache.add_user_info(did, UserInfo(did=did, handle=handle, display_name=display_name, description=description))

    return did

def load_activated_dids_from_file(client: Client, file_path: str, user_info_cache: UserInfoCache) -> List[str]:
    """Load activated DIDs from a text file

    The file can contain either DIDs (starting with 'did:') or handles.
    Handles are resolved to DIDs.

    Args:
        file_path: Path to text file with one DID or handle per line

    Returns:
        List of DIDs
    """
    dids = []

    try:
        # Create the file if it doesn't exist
        if not os.path.exists(file_path):
            logger.warning(f"Activated DIDs file {file_path} not found, creating empty file")
            with open(file_path, 'w') as f:
                pass
            return []

        with open(file_path, 'r') as f:
            for line in f:
                identifier = line.strip()

                # Skip empty lines and comments
                if not identifier or identifier.startswith('#'):
                    continue

                # If it's already a DID, add it directly
                if is_did(identifier):
                    dids.append(identifier)

                # Otherwise, resolve the handle to a DID
                else:
                    did = resolve_handle_to_did(client, identifier, user_info_cache)
                    if did:
                        dids.append(did)

        logger.info(f"Loaded {len(dids)} activated DIDs from {file_path}")

        # If no DIDs were loaded, raise an error
        if len(dids) == 0:
            logger.error(f"No activated DIDs found in {file_path}")
            with open(file_path, 'r') as f:
                print(f.read())
            raise Exception(f"No activated DIDs found in {file_path}")


        return dids

    except Exception as e:
        logger.error(f"Error loading activated DIDs from {file_path}: {e}")
        return []


def update_activated_dids(client: Client, file_path: str, user_info_cache: UserInfoCache) -> None:
    """Update the list of activated DIDs from the file"""
    global activated_dids
    try:
        activated_dids = load_activated_dids_from_file(client, file_path, user_info_cache)
        logger.info(f"Observing {len(activated_dids)} repositories")
    except Exception as e:
        logger.error(f"Failed to update activated DIDs: {e}")
        # Keep existing list if update fails


async def process_event(
        client: Client,
        author_did: str,
        event_kind: str,
        post_uri: str,
        post_cid: str,
        root_post_uri: str = None,
        thread_depth: int = 15,
        user_info_cache: UserInfoCache = None,
        comind: Comind = None,
        db_manager: DBManager = None,
        original_event: Dict = None  # Add parameter to receive the original event
    ) -> None:
    """Process an event and generate thoughts, emotions, and concepts for it"""
    try:
        # Skip if the post has already been processed
        if post_uri in processed_posts:
            return

        logger.info(f"Processing event: {event_kind} {post_uri}")

        # Add to processed posts and manage memory
        processed_posts.add(post_uri)
        if len(processed_posts) > MAX_PROCESSED_POSTS:
            # Remove oldest entries (approx 10% of max)
            posts_to_remove = list(processed_posts)[:MAX_PROCESSED_POSTS // 10]
            for old_post in posts_to_remove:
                processed_posts.remove(old_post)
            logger.info(f"Pruned processed posts cache: removed {len(posts_to_remove)} old entries")

        # Get the thread containing the post. If a root post URI is provided, use that
        # to get the thread, otherwise use the post URI.
        # thread_uri = root_post_uri if root_post_uri else post_uri
        # logger.debug(f"Getting thread for {'root post' if root_post_uri else 'post'}", thread_uri)

        thread_uri = post_uri # note, removing this post for now in order to not seek the root post

        # Use depth=0 to fetch the complete thread with all replies
        # This ensures we get all branches of the conversation
        # TODO: #4 Provide post thread sampling to limit token usage
        for i in range(10):
            # Loop because the post may not yet be available
            try:
                thread = client.get_post_thread(thread_uri, depth=thread_depth, parent_height=32) # magic number
                break
            except Exception as thread_error:
                logger.error(f"Error getting thread with depth={thread_depth}: {thread_error}")
                logger.info("Falling back to default thread retrieval")
                time.sleep(1)
                continue

        thread_data = thread.model_dump()

        # Unpack the thread into a string, passing activated_dids to properly handle privacy
        thread_string, references = unpack_thread(
            thread_data,
            client=client,
            expand_quoted_threads=True,
            max_quoted_thread_depth=2,
            activated_dids=activated_dids
        )

        # Author handle
        actor_info = user_info_cache.get_user_info(author_did)
        if actor_info is None:
            logger.error(f"Actor info not found for post {post_uri}")

            # Resolve the handle to a DID
            actor_did = resolve_handle_to_did(
                client,
                author_did,
                user_info_cache
            )

            actor_info = user_info_cache.get_user_info(actor_did)
            if actor_info is None:
                logger.error(f"Failed to resolve handle to DID for post {post_uri}")
                return

        # Info premble
        user_info_preamble = f"## User information\nDisplay name: {actor_info.display_name}\nHandle: {actor_info.handle}\nDescription: {actor_info.description}"
        context_preamble = f"## Context\n{thread_string}"
        instructions_preamble = "## Instructions\nPlease respond."

        # Get the target post
        for i in range(10):
            try:
                target_posts = client.get_posts([post_uri])
                target_post = target_posts.posts[0]
                break
            except Exception as e:
                logger.error(f"Error getting target post: {e}")
                time.sleep(1)
                continue

        # Strip the target post
        stripped_target_post = yaml.dump(
            strip_fields(target_post.model_dump(), STRIP_FIELDS),
            indent=2
        )

        if event_kind == "app.bsky.feed.post":
            target_post_string = f"## New post\n{actor_info.display_name} ({actor_info.handle}) has made a new post. Here is the post:\n{stripped_target_post}"
        elif event_kind == "app.bsky.feed.like":
            target_post_string = f"## New like\n{actor_info.display_name} ({actor_info.handle}) has liked a post. Here is the post:\n{stripped_target_post}"
        else:
            raise Exception(f"Unknown event kind: {event_kind}")

        rows = [
            # "# Overview",
            user_info_preamble,
            target_post_string,
            context_preamble,
            instructions_preamble,
        ]

        prompt = "\n\n".join(rows)

        context_dict = {
            'content': prompt,
        }

        # Print a separator panel
        print(Panel.fit(prompt, title="Prompt"))

        # Helper function to recursively collect strongRefs
        def _collect_strong_refs_from_node(node: Any, refs_set: set):
            if isinstance(node, dict):
                node_type = node.get("$type")

                # Check for PostView
                if node_type == "app.bsky.feed.defs#postView":
                    if node.get("uri") and node.get("cid"):
                        refs_set.add((node["uri"], node["cid"]))

                # Check for embedded records (quoted posts)
                elif node_type == "app.bsky.embed.record#viewRecord": # This is the type for resolved embedded records
                    if node.get("uri") and node.get("cid"):
                        refs_set.add((node["uri"], node["cid"]))

                # Recursively traverse dictionary values
                for value in node.values():
                    _collect_strong_refs_from_node(value, refs_set)

            elif isinstance(node, list):
                # Recursively traverse list items
                for item in node:
                    _collect_strong_refs_from_node(item, refs_set)

        from_refs_set = set()
        if thread_data.get("thread"): # thread_data is the model_dump of the ThreadViewPost
            _collect_strong_refs_from_node(thread_data["thread"], from_refs_set)

        # Add the target_post itself. target_post is a PostView object.
        if target_post and hasattr(target_post, 'uri') and hasattr(target_post, 'cid'):
            from_refs_set.add((target_post.uri, target_post.cid))

        list_of_strong_refs = [{"uri": uri, "cid": cid} for uri, cid in from_refs_set if uri and cid]

        # Run the comind
        result = comind.run(context_dict)

        # Upload the result
        comind.upload(
            result,
            RecordManager(client), # Consider passing the existing record_manager if appropriate
            target=post_uri,
            from_refs=list_of_strong_refs # Pass the collected references
        )

        # Also store the event in KuzuDB if a db_manager is provided
        if db_manager is not None:
            try:
                # If we have the original event object, use it
                if original_event:
                    process_atproto_event(db_manager, original_event)
                else:
                    # Otherwise reconstruct a minimal event from the parameters we have
                    # Extract rkey from post_uri (last part after the last /)
                    rkey = post_uri.split('/')[-1]
                    # Extract collection from event_kind
                    collection = event_kind
                    
                    # Get the record data from the target_post
                    record = {}
                    if hasattr(target_post, 'record'):
                        record = target_post.record.model_dump()
                    
                    # Construct an event object that process_atproto_event can handle
                    reconstructed_event = {
                        "did": author_did,
                        "kind": "commit",
                        "commit": {
                            "operation": "create",
                            "collection": collection,
                            "rkey": rkey,
                            "record": record,
                            "cid": post_cid
                        }
                    }
                    process_atproto_event(db_manager, reconstructed_event)
            except Exception as db_error:
                logger.error(f"Error storing event in KuzuDB: {db_error}")
                # Don't raise the exception - we still want to process the event for comind

    except Exception as e:
        logger.error(f"Error processing post {post_uri}: {e}")
        raise e

async def connect_to_jetstream(
        atproto_client: Client,
        activated_dids_file: str,
        jetstream_host: str = JETSTREAM_HOST,
        thread_depth: int = 15,
        comind: Comind = None,
        db_manager: DBManager = None
    ) -> None:
    """Connect to Jetstream and process incoming messages"""
    global activated_dids

    # Initialize the user info cache
    user_info_cache = UserInfoCache()
    user_info_cache.load("user_info_cache.json")

    # Initial load of activated DIDs
    update_activated_dids(atproto_client, activated_dids_file, user_info_cache)
    current_dids = set(activated_dids.copy())

    last_update_time = time.time()
    update_interval = 300  # Update activated DIDs every 5 minutes

    while True:
        # Build WebSocket URI with current DIDs
        ws_uri = jetstream_host
        # Initialize query params as an empty list
        query_params = []

        # Add individual collection parameters
        query_params.append("wantedCollections=app.bsky.feed.post")
        query_params.append("wantedCollections=app.bsky.feed.like")

        # Add wantedDIDs parameter if we have activated DIDs
        if activated_dids:
            for did in activated_dids:
                query_params.append(f"wantedDids={did}")
        else:
            logger.warning("No activated DIDs found. Will process all posts but content will be marked as [NOT AVAILABLE]")

        # Construct full URI with parameters
        ws_uri = f"{ws_uri}?{'&'.join(query_params)}"

        logger.debug(f"Connecting to jetstream with {len(activated_dids)} activated DIDs")
        logger.debug(f"WebSocket URI: {ws_uri}")

        try:
            # Configure websocket with ping interval and timeout
            async with websockets.connect(
                ws_uri,
                ping_interval=30,  # Send a ping every 30 seconds
                ping_timeout=20,   # Wait 20 seconds for pong response
                close_timeout=10,  # Allow 10 seconds for graceful close
                max_size=10_000_000  # Increase max message size to 10MB
            ) as websocket:
                logger.info("Connected to jetstream")
                reconnect_needed = False

                while not reconnect_needed:
                    # Check if we need to update our DIDs list
                    current_time = time.time()
                    if current_time - last_update_time > update_interval:
                        old_dids = set(activated_dids)
                        update_activated_dids(atproto_client, activated_dids_file, user_info_cache)
                        new_dids = set(activated_dids)
                        last_update_time = current_time

                        # If DIDs list changed, we need to reconnect with new filter
                        if old_dids != new_dids:
                            logger.info("Activated DIDs list changed, reconnecting to update filters")
                            reconnect_needed = True
                            break

                    # Set timeout for websocket receive to allow periodic DID checks
                    try:
                        # Receive message from Jetstream with timeout
                        # Use a shorter timeout than the ping_interval to ensure we can send pings
                        message = await asyncio.wait_for(websocket.recv(), timeout=15)
                        event = json.loads(message)
                        author_did = event.get("did", None)
                        if author_did is None:
                            logger.warning(f"No author DID found in event: {event}")
                            raise Exception(f"No author DID found in event: {event}")

                        # Also store the event in KuzuDB if a db_manager is provided
                        if db_manager is not None:
                            try:
                                process_atproto_event(db_manager, event)
                            except Exception as db_error:
                                logger.error(f"Error storing event in KuzuDB: {db_error}")
                                # Don't raise the exception - we still want to process the event for comind

                        # Check if it's a post creation event
                        if (event.get("kind") == "commit" and
                            event.get("commit", {}).get("operation") == "create"):

                            collection = event.get("commit", {}).get("collection")
                            if collection == "app.bsky.feed.post":
                                # Extract post URI and CID
                                post_uri = f"at://{event['did']}/app.bsky.feed.post/{event['commit']['rkey']}"
                                post_cid = event['commit'].get('cid', '')

                                # Check if this post is a reply to another post. If so, we want to retrieve the
                                # root post instead
                                root_post_uri = None
                                reply = event.get("commit", {}).get("record", {}).get("reply", {})
                                # print("commit", event.get("commit", {}))
                                # print("record", event.get("commit", {}).get("record", {}))
                                # print("reply", event.get("commit", {}).get("record", {}).get("reply", {}))
                                # print("reply root", event.get("commit", {}).get("record", {}).get("reply", {}).get("root", {}))
                                root_post_uri = event.get("commit", {}).get("record", {}).get("reply", {}).get("root", {}).get("uri", None)

                                # Process the post
                                await process_event(
                                    atproto_client,
                                    author_did,
                                    collection,
                                    post_uri,
                                    post_cid,
                                    root_post_uri=root_post_uri,
                                    thread_depth=thread_depth,
                                    user_info_cache=user_info_cache,
                                    comind=comind,
                                    db_manager=db_manager,
                                    original_event=event
                                )
                            elif collection == "app.bsky.feed.like":
                                # Extract post URI and CID
                                post_uri = event.get("commit", {}).get("record", {}).get("subject", {}).get("uri", None)
                                post_cid = event['commit'].get('cid', '')

                                # Process the post
                                await process_event(
                                    atproto_client,
                                    author_did,
                                    collection,
                                    post_uri,
                                    post_cid,
                                    thread_depth=thread_depth,
                                    user_info_cache=user_info_cache,
                                    comind=comind,
                                    db_manager=db_manager,
                                    original_event=event
                                )
                            else:
                                logger.warning(f"Unknown collection message received: {collection}")
                    except asyncio.TimeoutError:
                        # This is expected - allows us to check if DIDs list changed
                        continue
                    except Exception as e:
                        # Check if "maximum context length is" is in the error message
                        if "maximum context length is" in str(e):
                            logger.error("Maximum context length exceeded. Could not process message.")
                        else:
                            logger.error(f"Error processing message: {e}")
                            raise e

                # If we broke out of the loop due to reconnect_needed, close the connection
                # and let the outer loop reconnect with the new DIDs list
                if reconnect_needed:
                    continue

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"WebSocket connection failed with status code {e.status_code}: {str(e)}")
            if e.status_code == 401:
                logger.error("Authentication error: Check your credentials or API key")
            elif e.status_code == 404:
                logger.error("Endpoint not found: Check your Jetstream host URL path")
            elif e.status_code >= 500:
                logger.error("Server error: The Jetstream service might be experiencing issues")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

        except ssl.SSLError as e:
            logger.error(f"SSL/TLS error: {str(e)}")
            logger.error("If connecting to a non-secure WebSocket server, use 'ws://' instead of 'wss://'")
            logger.error("Use the --use-ssl flag to switch to secure WebSocket if needed")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

        except ConnectionRefusedError:
            logger.error("Connection refused: Check if the Jetstream server is running and accessible")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"WebSocket connection closed: {e}")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)


async def main():
    """Main function to run the Jetstream consumer"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Jetstream consumer for ATProto")
    parser.add_argument("--dids-file", "-d", type=str, default=DEFAULT_ACTIVATED_DIDS_FILE,
                        help=f"Path to file containing activated DIDs/handles (default: {DEFAULT_ACTIVATED_DIDS_FILE})")
    parser.add_argument("--log-level", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: INFO)")
    parser.add_argument("--jetstream-host", "-j", type=str, default=JETSTREAM_HOST,
                        help=f"Jetstream host URL (default: {JETSTREAM_HOST})")
    parser.add_argument("--use-ssl", "-s", action="store_true",
                        help="Use secure WebSocket connection (wss://) instead of non-secure (ws://)")
    parser.add_argument("--username", "-u", type=str, default=None,
                        help="Username for ATProto client")
    parser.add_argument("--password", "-p", type=str, default=None,
                        help="Password for ATProto client")
    parser.add_argument("--thread-depth", "-t", type=int, default=15,
                        help="Maximum depth of threads to process. Default is 15.")
    parser.add_argument("--sphere", type=str, default=None,
                        help="Sphere to attach comind records to. Default is to not use a sphere.")
    parser.add_argument("--comind", "-c", type=str, default=None,
                        help="Comind to use for processing. Required.")
    parser.add_argument("--db-path", type=str, default="./demo_db",
                        help="Path to the Kuzu database directory. Default is './demo_db'.")
    parser.add_argument("--disable-db", action="store_true",
                        help="Disable storing ATProto records in Kuzu database.")

    args = parser.parse_args()

    if args.comind is None:
        logger.error("Comind is required. Please provide a comind using the --comind flag. Available cominds:")

        # Load the cominds
        cominds = available_cominds()
        for comind in cominds:
            logger.error(f"  {comind}")

        parser.print_help()
        return

    # Set the log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # If username and password are not provided, try to use the .env file
    if args.username is None:
        args.username = os.getenv("COMIND_BSKY_USERNAME")
        args.password = os.getenv("COMIND_BSKY_PASSWORD")

    # If no username or password, exit
    if args.username is None:
        logger.error("No username provided. Please provide a username using the --username flag, or set the COMIND_BSKY_USERNAME environment variable.")
        parser.print_help()
        return

    # If no password, exit
    if args.password is None:
        logger.error("No password provi/ded. Please provide a password using the --password flag, or set the COMIND_BSKY_PASSWORD environment variable.")
        parser.print_help()
        return

    # Throw an error if the activated_dids.txt file doesn't exist
    if not os.path.exists(args.dids_file):
        logger.error(f"Activated DIDs file {args.dids_file} not found. Please create it and add at least one DID or handle.")
        parser.print_help()
        return

    # Log in to ATProto
    atproto_client = session_reuse.init_client(args.username, args.password)
    record_manager = RecordManager(atproto_client)

    # Get lists of spheres
    spheres = record_manager.list_records("me.comind.sphere.core")
    sphere_to_use = None

    logger.debug(f"Found {len(spheres)} spheres")

    # Log string
    log_string = "Available spheres"

    for sphere in spheres:
        value = sphere["value"]
        # text = value["text"]
        title = value["title"]
        description = value["description"]

        log_string += f"\n\t{title} - {description}"

        if args.sphere == title:
            sphere_to_use = sphere
            message = f"\n\t{title} - {description} (selected sphere)"

    logger.info(log_string)

    if sphere_to_use is None and args.sphere is not None:
        logger.error(f"Sphere {args.sphere} not found. Please create it and assign this comind to it.")
        parser.print_help()
        return

    # If SSL option is specified and --jetstream-host wasn't provided, modify the URL
    if args.use_ssl and args.jetstream_host == JETSTREAM_HOST and args.jetstream_host.startswith("ws:"):
        args.jetstream_host = "wss:" + args.jetstream_host[3:]
        logger.info(f"Using secure WebSocket connection: {args.jetstream_host}")

    logger.info(f"Starting Jetstream consumer with activated DIDs file: {args.dids_file}")
    logger.info(f"Jetstream host: {args.jetstream_host}")

    # Create the comind
    comind = Comind.load(args.comind)

    if sphere_to_use is not None:
        comind.sphere_name = sphere_to_use.value["title"]
        comind.sphere_description = sphere_to_use.value["description"]
        comind.core_perspective = sphere_to_use.value["text"]
    else:
        logger.warning("No sphere provided. Comind will not be attached to any sphere.")
    
    # Initialize the database manager if not disabled
    db_manager = None
    if not args.disable_db:
        try:
            logger.info(f"Initializing Kuzu database at {args.db_path}")
            db_manager = DBManager(args.db_path)
            db_manager.setup_schema()
            logger.info("Kuzu database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Kuzu database: {e}")
            logger.warning("Continuing without database integration")

    try:
        await connect_to_jetstream(
            atproto_client,
            args.dids_file,
            args.jetstream_host,
            thread_depth=args.thread_depth,
            comind=comind,
            db_manager=db_manager
        )
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        # raise e


if __name__ == "__main__":
    asyncio.run(main())
