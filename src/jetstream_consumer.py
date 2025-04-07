from src.comind.comind import available_cominds, Comind
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
from typing import List, Optional, Set
import websockets
import time
import logging
import argparse
import src.session_reuse as session_reuse
from rich import print
from rich.panel import Panel
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
from atproto_client import Client

import yaml
import os
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("jetstream_consumer")

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
    "me.comind.blip.concept": """
    You are a comind, an AI agent that produces structured JSON output containing concepts about various content
    on AT Proto, a decentralized social network. You respond in JSON and produce a list of concepts.

    Concepts should be single words or phrases, like 'data', 'privacy', 'AI', 'security', 'social networks', etc.
    Keep concept text as short as possible. You may use lowercase letters, spaces, and numbers.
    """,
    "me.comind.blip.emotion": """
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
    "me.comind.blip.thought": """
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
        logger.info(f"Updated activated DIDs: {len(activated_dids)} DIDs")
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
        thread_depth: int = 2,
        user_info_cache: UserInfoCache = None,
        comind: Comind = None
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
        thread_uri = root_post_uri if root_post_uri else post_uri
        print(f"Getting thread for {'root post' if root_post_uri else 'post'}", thread_uri)

        # Use depth=0 to fetch the complete thread with all replies
        # This ensures we get all branches of the conversation
        # TODO: #4 Provide post thread sampling to limit token usage
        try:
            thread = client.get_post_thread(thread_uri, depth=thread_depth)
        except Exception as thread_error:
            logger.error(f"Error getting thread with depth={thread_depth}: {thread_error}")
            logger.info("Falling back to default thread retrieval")
            thread = client.get_post_thread(thread_uri)

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
            return

        # Info premble
        user_info_preamble = f"## User information\nDisplay name: {actor_info.display_name}\nHandle: {actor_info.handle}\nDescription: {actor_info.description}"
        context_preamble = f"## Context\n{thread_string}"
        instructions_preamble = "## Instructions\nPlease respond."

        # Get the target post
        target_post = client.get_posts([post_uri]).posts[0]
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
            "# Overview",
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
        # print(Panel.fit(prompt, title="Prompt"))

        # Run the comind
        result = comind.run(context_dict)
        print(result)

        # Upload the result
        comind.upload(result, RecordManager(client), {'uri': post_uri, 'cid': post_cid})

        # # Generate thoughts, emotions, and concepts
        # for nsid in ["me.comind.blip.thought", "me.comind.blip.emotion", "me.comind.blip.concept"]:
        #     # Generate the thought using the structured_gen model
        #     tail_name = nsid.split(".")[-1] + "s"
        #     lx = generated_lexicon_of(nsid)
        #     add_link_property(lx, "connection_to_content", required=True)
        #     schema = multiple_of_schema(tail_name, lx)

        #     response = structured_gen.generate_by_schema(
        #         messages=[
        #             {"role": "system", "content": system_prompts[nsid]},
        #             {"role": "user", "content": prompt},
        #         ],
        #         schema=schema,
        #     )

        #     # Parse the response
        #     response_content = json.loads(response.choices[0].message.content)

        #     # Print the generated content
        #     print(f"\nGenerated {tail_name}:")
        #     print(yaml.dump(response_content))

        #     # Convert each record to the record format
        #     for record in response_content[tail_name]:
        #         record["$type"] = nsid
        #         record["createdAt"] = datetime.now().isoformat()

        #         link_record = split_link(record)
        #         link_record['target'] = {'uri': post_uri, 'cid': post_cid}

        #         # Upload the generated thought record
        #         record_manager = RecordManager(client)

        #         # If it's a concept, the rkey must be the text of the concept with hyphens instead of spaces
        #         # TODO: #2 RecordManager should handle default rkeys for concepts
        #         if nsid == "me.comind.blip.concept":
        #             record["rkey"] = record["text"].replace(" ", "-")

        #         # Check if the record already exists
        #         if 'rkey' in record:
        #             existing_record = record_manager.get_record(nsid, record["rkey"])
        #             if not existing_record:
        #                 existing_record = record_manager.create_record(nsid, record, rkey=record["rkey"])
        #         else:
        #             # We're not using a custom rkey, so we need to create the record with a random rkey
        #             existing_record = record_manager.create_record(nsid, record)

        #         # Add the uri and cid to the link record
        #         link_record['source'] = {'uri': existing_record['uri'], 'cid': existing_record['cid']}

        #         # Save the link record
        #         link_result = record_manager.create_record("me.comind.relationship.link", link_record)

    except Exception as e:
        logger.error(f"Error processing post {post_uri}: {e}")
        raise e

async def connect_to_jetstream(
        atproto_client: Client, 
        activated_dids_file: str,
        jetstream_host: str = JETSTREAM_HOST, 
        thread_depth: int = 2, 
        comind: Comind = None
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

        logger.info(f"Connecting to Jetstream with {len(activated_dids)} activated DIDs")
        logger.debug(f"WebSocket URI: {ws_uri}")

        try:
            async with websockets.connect(ws_uri) as websocket:
                logger.info("Connected to Jetstream")
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
                        message = await asyncio.wait_for(websocket.recv(), timeout=10)
                        event = json.loads(message)
                        author_did = event.get("did", None)
                        if author_did is None:
                            logger.warning(f"No author DID found in event: {event}")
                            raise Exception(f"No author DID found in event: {event}")

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
                                    comind=comind
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
                                    comind=comind
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

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            logger.info(f"Reconnecting in {RECONNECT_DELAY} seconds...")
            raise e
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
    parser.add_argument("--thread-depth", "-t", type=int, default=2,
                        help="Maximum depth of threads to process. Default is 2.")
    parser.add_argument("--sphere", type=str, default=None,
                        help="Sphere to attach comind records to. Default is to not use a sphere.")
    parser.add_argument("--comind", "-c", type=str, default=None,
                        help="Comind to use for processing. Required.")
    
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
    for sphere in spheres:
        value = sphere.value
        text = value["text"]
        title = value["title"]
        description = value["description"]

        logger.debug(f"Found sphere: {title} - {text}")

        if args.sphere == title:
            sphere_to_use = sphere
            message = f"Using sphere: {title} - {text}"
            if description:
                message += f"\n\n{description}"
            logger.info(message)
            break

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

    try:
        await connect_to_jetstream(
            atproto_client,
            args.dids_file,
            args.jetstream_host,
            thread_depth=args.thread_depth,
            comind=comind
        )
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(main())
