"""
Code to manage sphere creation and management using a modern TUI interface.
"""
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional, Union
import os
import argparse

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Header, Input, Label, Select, TextArea
from textual.binding import Binding
from textual import events
from textual.screen import Screen
from atproto_client import Client
from atproto_client.models.dot_dict import DotDict
import src.session_reuse as session_reuse
from src.record_manager import RecordManager

class SphereError(Exception):
    """Base exception for sphere-related errors."""
    pass

def is_dict_like(obj) -> bool:
    """Check if an object is dictionary-like (dict or DotDict)."""
    return isinstance(obj, (dict, DotDict))

class SphereEditor(Screen):
    """Screen for editing a sphere's details."""
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, sphere_data: Optional[Union[dict, DotDict]] = None):
        super().__init__()
        if sphere_data is None:
            sphere_data = {
                "title": "",
                "text": "",
                "description": "",
                "createdAt": datetime.now().isoformat()
            }
        elif not is_dict_like(sphere_data):
            raise SphereError(f"Invalid sphere_data type: {type(sphere_data)}")
        elif "title" not in sphere_data or "text" not in sphere_data:
            raise SphereError("Missing required fields in sphere_data")
            
        self.sphere_data = dict(sphere_data)  # Convert to regular dict

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("Title:"),
            Input(self.sphere_data["title"], id="title"),
            Label("Core Purpose:"),
            TextArea(self.sphere_data["text"], id="text"),
            Label("Description (optional):"),
            TextArea(self.sphere_data.get("description", ""), id="description"),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", variant="error", id="cancel"),
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.save_sphere()
        elif event.button.id == "cancel":
            self.app.pop_screen()

    def save_sphere(self) -> None:
        title = self.query_one("#title").value
        text = self.query_one("#text").text
        description = self.query_one("#description").text

        if not title or not text:
            self.notify("Title and core purpose are required!", severity="error")
            return

        self.sphere_data.update({
            "title": title,
            "text": text,
            "description": description,
        })
        self.app.save_sphere(self.sphere_data)
        self.app.pop_screen()

class SphereManager(App):
    """A TUI application for managing spheres."""
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_sphere", "New Sphere"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, client: Optional[Client] = None):
        super().__init__()
        if client is None:
            raise SphereError("Client must be provided")
        self.client = client
        self.record_manager = RecordManager(client)
        self.spheres_dir = Path("lexicons/me/comind/sphere")
        self.spheres_dir.mkdir(parents=True, exist_ok=True)
        self.schema_file = self.spheres_dir / "core.json"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="spheres-table", zebra_stripes=True),
            Horizontal(
                Button("New Sphere", variant="primary", id="new"),
                Button("Edit", variant="default", id="edit"),
                Button("Delete", variant="error", id="delete"),
            ),
        )

    def on_mount(self) -> None:
        table = self.query_one("#spheres-table")
        table.cursor_type = "row"  # Enable row selection
        table.add_columns("Title", "Core Purpose", "Created")  # Add columns once
        self.refresh_spheres()

    def refresh_spheres(self) -> None:
        table = self.query_one("#spheres-table")
        table.clear()  # Only clear the rows, not the columns
        
        try:
            # Get spheres from ATProto using RecordManager
            spheres = self.record_manager.list_records("me.comind.sphere.core")
            if spheres is None:
                raise SphereError("Failed to fetch spheres from ATProto")
            
            for sphere in spheres:
                if not hasattr(sphere, 'value'):
                    raise SphereError(f"Invalid sphere record: {sphere}")
                sphere_data = sphere.value
                if not is_dict_like(sphere_data):
                    raise SphereError(f"Invalid sphere data type: {type(sphere_data)}")
                if "title" not in sphere_data or "text" not in sphere_data:
                    raise SphereError(f"Missing required fields in sphere data: {sphere_data}")
                    
                table.add_row(
                    sphere_data["title"],
                    sphere_data["text"][:50] + "..." if len(sphere_data["text"]) > 50 else sphere_data["text"],
                    sphere_data["createdAt"].split("T")[0]
                )
            
            # Select the first row if available
            if table.row_count > 0:
                table.cursor_coordinate = (0, 0)  # Select first row, first column
        except Exception as e:
            self.notify(f"Error fetching spheres: {str(e)}", severity="error")
            raise

    def save_sphere(self, sphere_data: Union[dict, DotDict]) -> None:
        if not is_dict_like(sphere_data):
            raise SphereError(f"Invalid sphere_data type: {type(sphere_data)}")
        if "title" not in sphere_data or "text" not in sphere_data:
            raise SphereError("Missing required fields in sphere_data")
            
        try:
            # Convert to regular dict for JSON serialization
            sphere_dict = dict(sphere_data)
            
            # Create a filename from the title for local backup
            filename = f"{sphere_dict['title'].lower().replace(' ', '_')}.json"
            filepath = self.spheres_dir / filename
            
            # Save to ATProto using RecordManager
            if "rkey" in sphere_dict:
                # Update existing sphere
                self.record_manager.create_record(
                    "me.comind.sphere.core",
                    sphere_dict,
                    rkey=sphere_dict["rkey"]
                )
            else:
                # Create new sphere
                self.record_manager.create_record(
                    "me.comind.sphere.core",
                    sphere_dict
                )
            
            # Save local backup
            with open(filepath, "w") as f:
                json.dump(sphere_dict, f, indent=2)
            
            self.refresh_spheres()
        except Exception as e:
            self.notify(f"Error saving sphere: {str(e)}", severity="error")
            raise

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new":
            self.push_screen(SphereEditor())
        elif event.button.id == "edit":
            table = self.query_one("#spheres-table")
            if table.cursor_coordinate is None:
                self.notify("Please select a sphere to edit", severity="warning")
                return
            try:
                # Get spheres from ATProto using RecordManager
                spheres = self.record_manager.list_records("me.comind.sphere.core")
                if spheres is None:
                    raise SphereError("Failed to fetch spheres from ATProto")
                    
                row = table.cursor_coordinate[0]  # Get the selected row
                if row >= len(spheres):
                    raise SphereError(f"Invalid row index: {row}")
                    
                sphere = spheres[row]
                if not hasattr(sphere, 'value'):
                    raise SphereError(f"Invalid sphere record: {sphere}")
                    
                # Create a copy of the sphere data to avoid modifying the original
                sphere_data = {
                    "title": sphere.value["title"],
                    "text": sphere.value["text"],
                    "description": sphere.value.get("description", ""),
                    "createdAt": sphere.value["createdAt"],
                    "rkey": sphere.uri.split('/')[-1]  # Add the rkey for updates
                }
                self.push_screen(SphereEditor(sphere_data))
            except Exception as e:
                self.notify(f"Error loading sphere: {str(e)}", severity="error")
                raise
        elif event.button.id == "delete":
            table = self.query_one("#spheres-table")
            if table.cursor_coordinate is None:
                self.notify("Please select a sphere to delete", severity="warning")
                return
            try:
                # Get spheres from ATProto using RecordManager
                spheres = self.record_manager.list_records("me.comind.sphere.core")
                if spheres is None:
                    raise SphereError("Failed to fetch spheres from ATProto")
                    
                row = table.cursor_coordinate[0]  # Get the selected row
                if row >= len(spheres):
                    raise SphereError(f"Invalid row index: {row}")
                    
                sphere = spheres[row]
                if not hasattr(sphere, 'uri'):
                    raise SphereError(f"Invalid sphere record: {sphere}")
                    
                # Extract rkey from the URI
                rkey = sphere.uri.split('/')[-1]
                self.record_manager.delete_record(
                    "me.comind.sphere.core",
                    rkey
                )
                self.refresh_spheres()
            except Exception as e:
                self.notify(f"Error deleting sphere: {str(e)}", severity="error")
                raise

    def action_new_sphere(self) -> None:
        self.push_screen(SphereEditor())

    def action_refresh(self) -> None:
        self.refresh_spheres()

def init_client(username: Optional[str] = None, password: Optional[str] = None) -> Client:
    """Initialize ATProto client with credentials."""
    if username is None:
        username = os.getenv("COMIND_BSKY_USERNAME")
    if password is None:
        password = os.getenv("COMIND_BSKY_PASSWORD")
    
    if not username or not password:
        raise ValueError(
            "No credentials provided. Please set COMIND_BSKY_USERNAME and "
            "COMIND_BSKY_PASSWORD environment variables or provide username and password."
        )
    
    return session_reuse.init_client(username, password)

def sphere_flow(client: Optional[Client] = None):
    """
    Enters an interactive terminal flow to create and manage spheres.
    
    Args:
        client: Optional ATProto client. If not provided, will initialize one using environment variables.
    """
    if client is None:
        client = init_client()
    
    app = SphereManager(client)
    app.run()

def main():
    """Main entry point for the sphere manager."""
    parser = argparse.ArgumentParser(description="Manage spheres using a TUI interface")
    parser.add_argument("--username", "-u", type=str, help="ATProto username")
    parser.add_argument("--password", "-p", type=str, help="ATProto password")
    args = parser.parse_args()
    
    try:
        client = init_client(args.username, args.password)
        sphere_flow(client)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())