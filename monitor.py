#!/usr/bin/env python3
# Simple fasthtml app to monitor comind records

import os
import sys
import logging
from typing import Dict, List, Optional, Any
import datetime
import re
from atproto_client import Client as AtProtoClient
from atproto_client import Session, SessionEvent
from dotenv import load_dotenv
from fasthtml.common import *
import json

from rich import print

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("monitor")

# Try to import comind formatter, or use local implementation
try:
    from comind.format import format as comind_format
except ImportError:
    # Fallback implementation if comind package is not available
    def comind_format(template: str, context: Dict[str, Any],
                    safe: bool = True, default: str = "") -> str:
        """
        Simple implementation of comind.format for use without the full package.
        """
        if not template or not isinstance(template, str):
            return str(template)

        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        # Handle any remaining placeholders with default value
        if safe:
            result = re.sub(r'\{[^{}]*\}', default, result)

        return result

# Load environment variables
load_dotenv(override=True)

# Define collections to monitor
COLLECTIONS = [
    "me.comind.sphere.core",
    "me.comind.thought",
    "me.comind.emotion",
    "me.comind.concept",
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
    """Render a record as a card with improved display and interactivity"""
    record_data = record.model_dump()['value']
    uri_parts = record.uri.split('/')
    rkey = uri_parts[-1]

    # Extract record type-specific information
    title = ""
    body = ""
    record_type = collection.split(".")[-1]  # Extract type from collection name

    # Build context for formatting
    context = {
        "record_type": record_type,
        "collection": collection,
        "rkey": rkey,
        "uri": record.uri,
    }

    # Add common fields to context
    for key, value in record_data.items():
        if isinstance(value, (str, int, float, bool)):
            context[key] = value

    # Type-specific formatting context
    if collection == "me.comind.sphere.core":
        title_template = "{title}"
        body_template = "{text}"
        context.update({
            "title": record_data.get("title", "Untitled Sphere"),
            "text": record_data.get("text", "")
        })
    elif "generated" in record_data and isinstance(record_data["generated"], dict):
        generated = record_data["generated"]
        context.update(generated)

        # Add generated fields to context
        for key, value in generated.items():
            if isinstance(value, (str, int, float, bool)):
                context[f"generated_{key}"] = value

        if collection == "me.comind.thought":
            title_template = "Thought: {thoughtType}"
            body_template = "{text}"
            context.update({
                "thoughtType": generated.get("thoughtType", "Unknown"),
                "text": generated.get("text", "")
            })
        elif collection == "me.comind.emotion":
            title_template = "Emotion: {emotionType}"
            body_template = "{text}"
            context.update({
                "emotionType": generated.get("emotionType", "Unknown"),
                "text": generated.get("text", "")
            })
        elif collection == "me.comind.concept":
            title_template = "{text}"
            body_template = "{text}"
            context.update({
                "text": generated.get("text", "")
            })
        elif collection == "me.comind.meld.request":
            title_template = "Meld Request: {requestType}"
            body_template = "{prompt}"
            context.update({
                "requestType": generated.get("requestType", "Unknown"),
                "prompt": generated.get("prompt", "")
            })
        elif collection == "me.comind.meld.response":
            title_template = "Meld Response"
            body_template = "{content}"
            context.update({
                "content": generated.get("content", "")
            })
    else:
        title_template = "Record: {record_type}"
        body_template = ""

    # Format title and body using comind_format
    title = comind_format(title_template, context, safe=True, default="Unknown")
    body = comind_format(body_template, context, safe=True, default="")

    # Format created date if available
    created_at = record_data.get("createdAt", "")
    created_formatted = format_datetime(created_at) if created_at else ""

    # Generate a unique ID for this content
    content_id = f"content-{record_type}-{rkey}"

    # Truncate long content with expand/collapse functionality
    content_div = Div(
        P(body, id=content_id, cls="truncated" if len(body) > 300 else ""),
        Button(
            "Show more",
            cls="expand-button",
            onclick=f"""
                const content = document.getElementById('{content_id}');
                const btn = this;
                if (content.classList.contains('truncated')) {{
                    content.classList.remove('truncated');
                    btn.textContent = 'Show less';
                }} else {{
                    content.classList.add('truncated');
                    btn.textContent = 'Show more';
                }}
            """,
            style="display: " + ("block" if len(body) > 300 else "none")
        )
    ) if body else Div()

    # Define icon based on record type
    icon_map = {
        "sphere": "🌐",
        "thought": "💭",
        "emotion": "😊",
        "concept": "💡",
        "request": "❓",
        "response": "💬"
    }
    icon = icon_map.get(record_type.split(".")[-1], "📄")

    return Div(
        H3(f"{icon} {title}"),
        content_div,
        Div(
            Span(f"Created: {created_formatted}"),
            Span(f"ID: {rkey}"),
            cls="card-meta"
        ),
        cls="card",
        hx_get=f"/record/{record_type}/{rkey}",
        hx_target="this",
        hx_swap="outerHTML",
        hx_trigger="dblclick"
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
                H2(f"{collection_name} Records", cls="collection-title"),
                *record_cards,
                cls="collection-section",
                style="margin-bottom: 2rem;"
            )

            collection_sections.append(collection_section)

        # If no records found
        if not collection_sections:
            collection_sections = [P("No records found. Please check your credentials and collection names.", cls="no-records")]

        # Refresh button with improved styling and auto-refresh option
        refresh_controls = Div(
            Button(
                Span("↻ Refresh", cls="refresh-text"),
                cls="refresh-button",
                hx_get="/",
                hx_swap="outerHTML",
                hx_target="#content"
            ),
            Div(
                Input(type="checkbox", id="auto-refresh", name="auto-refresh"),
                Label("Auto-refresh (30s)", for_="auto-refresh"),
                style="margin-left: 1rem; display: inline-flex; align-items: center;"
            ),
            Script("""
                document.getElementById('auto-refresh').addEventListener('change', function() {
                    if (this.checked) {
                        window.autoRefreshInterval = setInterval(function() {
                            document.querySelector('.refresh-button').click();
                        }, 30000);
                    } else {
                        clearInterval(window.autoRefreshInterval);
                    }
                });
            """),
            style="display: flex; align-items: center;"
        )

        return Title("Comind Record Monitor"), Div(
            Style("""
                :root {
                    --primary-color: #4a6baf;
                    --bg-color: #f5f7fa;
                    --card-bg: #ffffff;
                    --text-color: #333;
                    --border-color: #e0e0e0;
                    --highlight: #617ec2;
                    --muted-text: #666;
                }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: var(--bg-color);
                    color: var(--text-color);
                    line-height: 1.6;
                    padding: 0;
                    margin: 0;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 2rem;
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 2rem;
                    border-bottom: 1px solid var(--border-color);
                    padding-bottom: 1rem;
                }
                h1 {
                    color: var(--primary-color);
                    margin: 0;
                }
                .collection-title {
                    color: var(--primary-color);
                    border-bottom: 2px solid var(--border-color);
                    padding-bottom: 0.5rem;
                    margin-top: 2rem;
                }
                .card {
                    background: var(--card-bg);
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                    margin-bottom: 1.5rem;
                    padding: 1.5rem;
                    transition: transform 0.2s, box-shadow 0.2s;
                    border-left: 4px solid var(--primary-color);
                }
                .card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }
                .card h3 {
                    color: var(--primary-color);
                    margin-top: 0;
                }
                .card-meta {
                    color: var(--muted-text);
                    font-size: 0.85rem;
                    margin-top: 1rem;
                    display: flex;
                    justify-content: space-between;
                }
                .refresh-button {
                    background-color: var(--primary-color);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: background-color 0.2s;
                }
                .refresh-button:hover {
                    background-color: var(--highlight);
                }
                .nav-tabs {
                    display: flex;
                    gap: 0.5rem;
                    margin-bottom: 2rem;
                    flex-wrap: wrap;
                }
                .nav-tab {
                    padding: 0.5rem 1rem;
                    background-color: #e0e0e0;
                    border-radius: 4px;
                    text-decoration: none;
                    color: var(--text-color);
                    font-weight: 500;
                    transition: background-color 0.2s;
                }
                .nav-tab:hover, .nav-tab.active {
                    background-color: var(--primary-color);
                    color: white;
                }
                .expand-button {
                    background: none;
                    border: none;
                    color: var(--primary-color);
                    cursor: pointer;
                    font-size: 0.9rem;
                    padding: 0;
                    margin-top: 0.5rem;
                    text-decoration: underline;
                }
                .truncated {
                    max-height: 100px;
                    overflow: hidden;
                    position: relative;
                }
                .truncated::after {
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    height: 30px;
                    background: linear-gradient(transparent, var(--card-bg));
                }
                @media (max-width: 768px) {
                    .container {
                        padding: 1rem;
                    }
                    .header {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 1rem;
                    }
                    .nav-tabs {
                        width: 100%;
                        overflow-x: auto;
                    }
                }
            """),
            Div(
                H1("Comind Record Monitor"),
                refresh_controls,
                cls="header"
            ),
            Div(
                *[A(collection.split(".")[-1].capitalize(),
                    href=f"/{collection.split('.')[-1]}",
                    cls="nav-tab")
                  for collection in COLLECTIONS],
                cls="nav-tabs"
            ),
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

@rt("/record/{collection_type}/{rkey}")
def get_record_detail(collection_type: str, rkey: str):
    """Display detailed information about a record"""
    try:
        client = default_login()
        collection = f"me.comind.{collection_type}"

        # Get the specific record
        response = client.com.atproto.repo.get_record({
            'collection': collection,
            'repo': client.me.did,
            'rkey': rkey
        })

        if not response or not hasattr(response, 'value'):
            return Div(
                H3("Record Not Found"),
                P(f"Could not find record with ID {rkey}"),
                Button("Close", onclick="this.parentElement.outerHTML = originalCardHTML;"),
                cls="card error-card"
            )

        record_data = response.value

        # Build context for formatting
        context = {
            "record_type": collection_type,
            "collection": collection,
            "rkey": rkey,
        }

        # Add common fields to context
        for key, value in record_data.items():
            if isinstance(value, (str, int, float, bool)):
                context[key] = value

        # Type-specific formatting
        title_template = "Record Details"
        body_template = ""

        if collection == "me.comind.sphere.core":
            title_template = "{title}"
            body_template = "{text}"
            context.update({
                "title": record_data.get("title", "Untitled Sphere"),
                "text": record_data.get("text", "")
            })
        elif "generated" in record_data and isinstance(record_data["generated"], dict):
            generated = record_data["generated"]

            # Add generated fields to context
            for key, value in generated.items():
                if isinstance(value, (str, int, float, bool)):
                    context[f"generated_{key}"] = value
                    context[key] = value

            if collection == "me.comind.thought":
                title_template = "Thought: {thoughtType}"
                body_template = "{text}"
            elif collection == "me.comind.emotion":
                title_template = "Emotion: {emotionType}"
                body_template = "{text}"
            elif collection == "me.comind.concept":
                title_template = "{text}"
                body_template = "{text}"
            elif collection == "me.comind.meld.request":
                title_template = "Meld Request: {requestType}"
                body_template = "{prompt}"
            elif collection == "me.comind.meld.response":
                title_template = "Meld Response"
                body_template = "{content}"

        # Format title and body using comind_format
        title = comind_format(title_template, context, safe=True, default="Unknown")
        body = comind_format(body_template, context, safe=True, default="")

        # Format created date if available
        created_at = record_data.get("createdAt", "")
        created_formatted = format_datetime(created_at) if created_at else ""

        # Store the full record JSON
        record_json = json.dumps(record_data, indent=2)

        return Div(
            Script(f"const originalCardHTML = this.outerHTML;"),
            H3(f"📄 {title}"),
            P(body) if body else Div(),
            H4("Record Details:"),
            Pre(record_json, style="background: #f0f0f0; padding: 1rem; border-radius: 4px; overflow: auto; max-height: 300px;"),
            Div(
                Span(f"Created: {created_formatted}"),
                Span(f"ID: {rkey}"),
                cls="card-meta"
            ),
            Button("Close",
                   cls="refresh-button",
                   style="margin-top: 1rem;",
                   onclick="this.closest('.card').outerHTML = originalCardHTML;"),
            cls="card detail-card",
            style="max-width: 100%; overflow: hidden;"
        )

    except Exception as e:
        return Div(
            H3("Error"),
            P(f"An error occurred: {str(e)}"),
            Button("Close",
                   cls="refresh-button",
                   style="margin-top: 1rem;",
                   onclick="this.closest('.card').outerHTML = originalCardHTML;"),
            cls="card error-card"
        )

# Start the app when run directly
if __name__ == "__main__":
    serve(port=8972)
