#!/usr/bin/env python3
# Simple fasthtml app to monitor comind records

import os
from typing import Dict, List, Optional
import datetime
from atproto_client import Client as AtProtoClient
from dotenv import load_dotenv
from fasthtml.common import *

# Load environment variables
load_dotenv()

# ATProto credentials
BSKY_USERNAME = os.getenv("COMIND_BSKY_USERNAME")
BSKY_PASSWORD = os.getenv("COMIND_BSKY_PASSWORD")

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
app, rt = fast_app()

def format_datetime(dt_str: str) -> str:
    """Format datetime string to more readable format"""
    dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def init_client() -> AtProtoClient:
    """Initialize ATProto client with credentials"""
    if not BSKY_USERNAME or not BSKY_PASSWORD:
        raise ValueError(
            "No credentials provided. Please set COMIND_BSKY_USERNAME and "
            "COMIND_BSKY_PASSWORD environment variables."
        )
    
    client = AtProtoClient()
    client.login(BSKY_USERNAME, BSKY_PASSWORD)
    return client

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
        print(f"Error listing records in collection {collection}: {str(e)}")
        return []

def render_record_card(record, collection):
    """Render a record as a card"""
    record_data = record.value
    uri_parts = record.uri.split('/')
    rkey = uri_parts[-1]
    
    # Extract record type-specific information
    title = ""
    body = ""
    
    if collection == "me.comind.sphere.core":
        title = record_data.get("title", "Untitled Sphere")
        body = record_data.get("text", "")
    elif collection == "me.comind.blip.thought":
        title = f"Thought: {record_data.get('generated', {}).get('thoughtType', 'Unknown')}"
        body = record_data.get('generated', {}).get('text', '')
    elif collection == "me.comind.blip.emotion":
        title = f"Emotion: {record_data.get('generated', {}).get('emotionType', 'Unknown')}"
        body = record_data.get('generated', {}).get('text', '')
    elif collection == "me.comind.blip.concept":
        title = "Concept"
        body = record_data.get('generated', {}).get('text', '')
    elif collection == "me.comind.meld.request":
        title = f"Meld Request: {record_data.get('generated', {}).get('requestType', 'Unknown')}"
        body = record_data.get('generated', {}).get('prompt', '')
    elif collection == "me.comind.meld.response":
        title = "Meld Response"
        body = record_data.get('generated', {}).get('content', '')
    
    # Format created date if available
    created_at = record_data.get("createdAt", "")
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
        client = init_client()
        
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
        return Title("Error"), Div(
            H1("Error"),
            P(f"An error occurred: {str(e)}"),
            cls="container"
        )

@rt("/{collection}")
def get_collection(collection: str):
    """View records for a specific collection"""
    try:
        client = init_client()
        records = get_recent_records(client, f"me.comind.{collection}", limit=10)
        
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
    serve()



