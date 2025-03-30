from datetime import datetime
import json
import asyncio
import websockets
import time
import logging
import argparse
import src.session_reuse as session_reuse
from rich import print
from rich.panel import Panel
from src.bsky_utils import add_property, get_link_schema, lexicon_of, multiple_of_schema, split_link, unpack_thread
from src.comind_session import AtProtoSession
from src.comind_atproto.records import RecordManager
import src.structured_gen as structured_gen

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

# Load the session
atproto_session = AtProtoSession()
client = atproto_session.get_client()

# Jetstream connection configuration
JETSTREAM_HOST = os.getenv("JETSTREAM_HOST", "ws://localhost:6008/subscribe")
RECONNECT_DELAY = 5  # Seconds to wait before reconnecting
DEFAULT_ACTIVATED_DIDS_FILE = "activated_dids.txt"

# System prompts for language model generation
system_prompts = {
    "network.comind.blips.concept": """
    You are a comind, an AI agent that produces structured JSON output containing concepts about various content 
    on AT Proto, a decentralized social network. You respond in JSON and produce a list of concepts.

    Concepts should be single words or phrases, like 'data', 'privacy', 'AI', 'security', 'social networks', etc.
    Keep concept text as short as possible. You may use lowercase letters, spaces, and numbers.
    """,
    "network.comind.blips.emotion": """
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
    "network.comind.blips.thought": """
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


def resolve_handle_to_did(handle: str) -> Optional[str]:
    """Resolve a handle to a DID using the ATProto client"""
    try:
        did = client.resolve_handle(handle).did
        logger.info(f"Resolved handle {handle} to DID {did}")
        return did
    except Exception as e:
        logger.error(f"Error resolving handle {handle}: {e}")
        logger.warning(f"Skipping handle {handle} due to resolution error")
        return None


def load_activated_dids_from_file(file_path: str) -> List[str]:
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
                    did = resolve_handle_to_did(identifier)
                    if did:
                        dids.append(did)
        
        logger.info(f"Loaded {len(dids)} activated DIDs from {file_path}")
        return dids
    
    except Exception as e:
        logger.error(f"Error loading activated DIDs from {file_path}: {e}")
        return []


def update_activated_dids(file_path: str) -> None:
    """Update the list of activated DIDs from the file"""
    global activated_dids
    try:
        activated_dids = load_activated_dids_from_file(file_path)
        logger.info(f"Updated activated DIDs: {len(activated_dids)} DIDs")
    except Exception as e:
        logger.error(f"Failed to update activated DIDs: {e}")
        # Keep existing list if update fails


async def process_post(post_uri: str, post_cid: str, root_post_uri: str = None) -> None:
    """Process a post and generate thoughts, emotions, and concepts for it"""
    try:
        # Skip if the post has already been processed
        if post_uri in processed_posts:
            return
            
        logger.info(f"Processing post: {post_uri}")
        
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
        try:
            thread = client.get_post_thread(thread_uri, depth=None)
        except Exception as thread_error:
            logger.error(f"Error getting thread with depth=None: {thread_error}")
            logger.info("Falling back to default thread retrieval")
            thread = client.get_post_thread(thread_uri)

        thread_data = thread.model_dump()
        print(thread_data)
        
        # Unpack the thread into a string, passing activated_dids to properly handle privacy
        thread_string, references = unpack_thread(
            thread_data, 
            client=client, 
            expand_quoted_threads=True, 
            max_quoted_thread_depth=2,
            activated_dids=activated_dids
        )
        
        print(thread_string)
        
        # Generate thoughts, emotions, and concepts
        for nsid in ["network.comind.blips.thought", "network.comind.blips.emotion", "network.comind.blips.concept"]:
            # Generate the thought using the structured_gen model
            tail_name = nsid.split(".")[-1] + "s"
            lx = lexicon_of(nsid)
            add_property(lx, "connection_to_content", link_schema, required=True)
            schema = multiple_of_schema(tail_name, lx)
            
            # Add the thread string to the prompt
            prompt = f"# Context\n{thread_string}\n\n# Instructions\nPlease respond."
            
            # Print a separator panel
            print(Panel.fit(prompt, title=nsid))
            
            response = structured_gen.generate_by_schema(
                messages=[
                    {"role": "system", "content": system_prompts[nsid]},
                    {"role": "user", "content": prompt},
                ],
                schema=schema,
            )
            
            # Parse the response
            response_content = json.loads(response.choices[0].message.content)
            
            # Print the generated content
            print(f"\nGenerated {tail_name}:")
            # print(json.dumps(response_content, indent=2))

            # Print out the generated content in a readable format
            for record in response_content[tail_name]:
                if nsid == "network.comind.blips.thought":
                    prefix = "(thought)"
                elif nsid == "network.comind.blips.emotion":
                    prefix = f"(emotion|{record['emotionType']})"
                elif nsid == "network.comind.blips.concept":
                    prefix = "(concept)"
                else:
                    print("Couldn't find prefix")
                    prefix = ""

                print(f"\t{prefix} {record['text']}")
            print("\n")
            
            # Convert each record to the record format
            for record in response_content[tail_name]:
                record["$type"] = nsid
                record["createdAt"] = datetime.now().isoformat()

                # Print the record
                # print("\nGenerated Record:")
                # print(json.dumps(record, indent=2))
                
                link_record = split_link(record)
                link_record['target'] = {'uri': post_uri, 'cid': post_cid}
                # print("\nGenerated Link Record:")
                # print(json.dumps(link_record, indent=2))
                
                # Upload the generated thought record
                record_manager = RecordManager(atproto_session.get_client())
                
                # If it's a concept, the rkey must be the text of the concept with hyphens instead of spaces
                if nsid == "network.comind.blips.concept":
                    record["rkey"] = record["text"].replace(" ", "-")
                
                # Check if the record already exists
                if 'rkey' in record:
                    existing_record = record_manager._get_record(nsid, record["rkey"])
                    if not existing_record:
                        existing_record = record_manager._create_record(nsid, record, rkey=record["rkey"])
                else:
                    # We're not using a custom rkey, so we need to create the record with a random rkey
                    existing_record = record_manager._create_record(nsid, record)
                
                # Add the uri and cid to the link record
                link_record['source'] = {'uri': existing_record['uri'], 'cid': existing_record['cid']}
                
                # Save the link record
                link_result = record_manager._create_record("network.comind.relationships.link", link_record)
                
    except Exception as e:
        logger.error(f"Error processing post {post_uri}: {e}")


async def connect_to_jetstream(activated_dids_file: str, jetstream_host: str = JETSTREAM_HOST) -> None:
    """Connect to Jetstream and process incoming messages"""
    global activated_dids
    
    # Initial load of activated DIDs
    update_activated_dids(activated_dids_file)
    current_dids = set(activated_dids.copy())
    
    last_update_time = time.time()
    update_interval = 300  # Update activated DIDs every 5 minutes
    
    while True:
        # Build WebSocket URI with current DIDs
        ws_uri = jetstream_host
        query_params = ["wantedCollections=app.bsky.feed.post"]
        
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
                        update_activated_dids(activated_dids_file)
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
                        
                        # Check if it's a post creation event
                        if (event.get("kind") == "commit" and 
                            event.get("commit", {}).get("operation") == "create" and
                            event.get("commit", {}).get("collection") == "app.bsky.feed.post"):
                            
                            # Extract post URI and CID
                            post_uri = f"at://{event['did']}/app.bsky.feed.post/{event['commit']['rkey']}"
                            post_cid = event['commit'].get('cid', '')

                            # Check if this post is a reply to another post. If so, we want to retrieve the 
                            # root post instead
                            root_post_uri = None
                            reply = event.get("commit", {}).get("record", {}).get("reply", {})
                            print("commit", event.get("commit", {}))
                            print("record", event.get("commit", {}).get("record", {}))
                            print("reply", event.get("commit", {}).get("record", {}).get("reply", {}))
                            print("reply root", event.get("commit", {}).get("record", {}).get("reply", {}).get("root", {}))
                            root_post_uri = event.get("commit", {}).get("record", {}).get("reply", {}).get("root", {}).get("uri", None)
                            
                            # Process the post
                            await process_post(post_uri, post_cid, root_post_uri=root_post_uri)
                    except asyncio.TimeoutError:
                        # This is expected - allows us to check if DIDs list changed
                        continue
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                
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
    
    # If username and password are not provided, try to use the .env file
    if args.username is None or args.password is None:
        args.username = os.getenv("COMIND_BSKY_USERNAME")
        args.password = os.getenv("COMIND_BSKY_PASSWORD")

    # If no username or password, exit
    if args.username is None or args.password is None:
        logger.error("No username or password provided. Please provide a username and password using the --username and --password flags, or set the COMIND_BSKY_USERNAME and COMIND_BSKY_PASSWORD environment variables.")
        parser.print_help()
        return
    
    args = parser.parse_args()
    
    # Set the log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # If SSL option is specified and --jetstream-host wasn't provided, modify the URL
    if args.use_ssl and args.jetstream_host == JETSTREAM_HOST and args.jetstream_host.startswith("ws:"):
        args.jetstream_host = "wss:" + args.jetstream_host[3:]
        logger.info(f"Using secure WebSocket connection: {args.jetstream_host}")
    
    logger.info(f"Starting Jetstream consumer with activated DIDs file: {args.dids_file}")
    logger.info(f"Jetstream host: {args.jetstream_host}")
    
    try:
        await connect_to_jetstream(args.dids_file, args.jetstream_host)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())