#!/usr/bin/env python3
# Simple fasthtml app to monitor comind records

import os
import sys
import logging
from typing import Dict, List, Optional
import datetime
from atproto_client import Client as AtProtoClient
from atproto_client import Session, SessionEvent
from dotenv import load_dotenv
from fasthtml.common import *

from rich import print

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("monitor")

# Load environment variables
load_dotenv(override=True)

# Define collections to monitor
COLLECTIONS = [
    "me.comind.sphere.core",
    "me.comind.blip.thought",
    "me.comind.blip.emotion",
    "me.comind.blip.concept",
    "me.comind.meld.request",
    "me.comind.meld.response"
]

# Create FastHTML app
app, rt = fast_app(debug=True)  # Enable debug mode to see detailed errors

# Session reuse functions
def get_session(username: str) -> Optional[str]:
    try:
        with open(f'session_{username}.txt', encoding='UTF-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.debug(f"No existing session found for {username}")
        return None

def save_session(username: str, session_string: str) -> None:
    with open(f'session_{username}.txt', 'w', encoding='UTF-8') as f:
        f.write(session_string)
    logger.debug(f"Session saved for {username}")

def on_session_change(username: str, event: SessionEvent, session: Session) -> None:
    logger.info(f'Session changed: {event} {repr(session)}')
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        logger.info(f'Saving changed session for {username}')
        save_session(username, session.export())

def init_client(username: str, password: str) -> AtProtoClient:
    pds_uri = os.getenv("COMIND_PDS_URI")
    if pds_uri is None:
        logger.warning("No PDS URI provided. Falling back to bsky.social.")
        pds_uri = "https://bsky.social"
        
    logger.info(f"Using PDS URI: {pds_uri}")

    client = AtProtoClient(pds_uri)
    client.on_session_change(lambda event, session: on_session_change(username, event, session))

    session_string = get_session(username)
    if session_string:
        logger.info(f'Reusing existing session for {username}')
        client.login(session_string=session_string)
    else:
        logger.info(f'Creating new session for {username}')
        client.login(username, password)

    return client

def default_login() -> AtProtoClient:
    username = os.getenv("COMIND_BSKY_USERNAME")
    password = os.getenv("COMIND_BSKY_PASSWORD")

    if username is None:
        logger.error("No username provided. Please set COMIND_BSKY_USERNAME env variable.")
        raise ValueError("No username provided")

    if password is None:
        logger.error("No password provided. Please set COMIND_BSKY_PASSWORD env variable.")
        raise ValueError("No password provided")

    return init_client(username, password)

def format_datetime(dt_str: str) -> str:
    """Format datetime string to more readable format"""
    dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_recent_records(client: AtProtoClient, collection: str, limit: int = 10) -> List[Dict]:
    """Get recent records from a collection"""
    try:
        response = client.com.atproto.repo.list_records({
            'collection': collection,
            'repo': client.me.did,
            'limit': limit
        })
        return response.records
    except Exception as e:
        logger.error(f"Error listing records in collection {collection}: {str(e)}")
        return []

def render_record_card(record, collection):
    """Render a record as a card"""
    record_data = record.model_dump()['value']
    uri_parts = record.uri.split('/')
    rkey = uri_parts[-1]

    # Extract record type-specific information
    title = ""
    body = ""

    # Safely access dictionary values without using .get()
    if collection == "me.comind.sphere.core":
        title = record_data["title"] if "title" in record_data else "Untitled Sphere"
        body = record_data["text"] if "text" in record_data else ""
    elif collection == "me.comind.blip.thought":
        generated = record_data["generated"] if "generated" in record_data else {}
        title = f"Thought: {generated.get('thoughtType', 'Unknown')}" if isinstance(generated, dict) else "Thought: Unknown"
        body = generated.get('text', '') if isinstance(generated, dict) else ''
    elif collection == "me.comind.blip.emotion":
        generated = record_data["generated"] if "generated" in record_data else {}
        title = f"Emotion: {generated.get('emotionType', 'Unknown')}" if isinstance(generated, dict) else "Emotion: Unknown"
        body = generated.get('text', '') if isinstance(generated, dict) else ''
    elif collection == "me.comind.blip.concept":
        generated = record_data["generated"] if "generated" in record_data else {}
        title = generated.get('text', '')
        body = generated.get('text', '') if isinstance(generated, dict) else ''
    elif collection == "me.comind.meld.request":
        generated = record_data["generated"] if "generated" in record_data else {}
        title = f"Meld Request: {generated.get('requestType', 'Unknown')}" if isinstance(generated, dict) else "Meld Request: Unknown"
        body = generated.get('prompt', '') if isinstance(generated, dict) else ''
    elif collection == "me.comind.meld.response":
        title = "Meld Response"
        generated = record_data["generated"] if "generated" in record_data else {}
        body = generated.get('content', '') if isinstance(generated, dict) else ''
    
    # Format created date if available
    created_at = record_data["createdAt"] if "createdAt" in record_data else ""
    created_formatted = format_datetime(created_at) if created_at else ""
    
    return Div(
        H3(title),
        P(body) if body else Div(),
        Small(f"Created: {created_formatted}"),
        Small(f"ID: {rkey}"),
        cls="card",
        style="margin-bottom: 1rem; padding: 1rem; border: 1px solid #ddd; border-radius: 5px;"
    )

@rt("/")
def get():
    """Main page showing all recent records"""
    try:
        client = default_login()
        
        collection_sections = []
        
        for collection in COLLECTIONS:
            records = get_recent_records(client, collection, limit=5)
            
            # Skip empty collections
            if not records:
                continue
                
            # Create section for this collection
            collection_name = collection.split(".")[-1].capitalize()
            record_cards = [render_record_card(record, collection) for record in records]
            
            collection_section = Div(
                H2(f"{collection_name} Records"),
                *record_cards,
                cls="collection-section",
                style="margin-bottom: 2rem;"
            )
            
            collection_sections.append(collection_section)
        
        # If no records found
        if not collection_sections:
            collection_sections = [P("No records found. Please check your credentials and collection names.")]
        
        # Refresh button
        refresh_button = Button("Refresh", hx_get="/", hx_swap="outerHTML", hx_target="#content")
            
        return Title("Comind Record Monitor"), Div(
            H1("Comind Record Monitor"),
            refresh_button,
            Div(*collection_sections, id="content"),
            cls="container"
        )
    except Exception as e:
        raise e
        return Title("Error"), Div(
            H1("Error"),
            P(f"An error occurred: {str(e)}"),
            cls="container"
        )

@rt("/{collection}")
def get_collection(collection: str):
    """View records for a specific collection"""
    try:
        client = default_login()
        records = get_recent_records(client, f"me.comind.{collection}", limit=10)
        print(records)
        
        record_cards = [render_record_card(record, f"me.comind.{collection}") for record in records]
        
        if not record_cards:
            record_cards = [P("No records found in this collection.")]
        
        return Title(f"{collection.capitalize()} Records"), Div(
            H1(f"{collection.capitalize()} Records"),
            A("Back to All Records", href="/", cls="button"),
            Div(*record_cards, cls="records"),
            cls="container"
        )
    except Exception as e:
        return Title("Error"), Div(
            H1("Error"),
            P(f"An error occurred: {str(e)}"),
            A("Back to All Records", href="/", cls="button"),
            cls="container"
        )

# Start the app when run directly
if __name__ == "__main__":
    serve(port=8972)



