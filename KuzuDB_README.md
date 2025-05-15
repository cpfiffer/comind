# KuzuDB Integration for Comind

This document describes the KuzuDB integration for tracking ATProto records in Comind.

## Overview

KuzuDB is an embedded graph database that is used to store and query ATProto records for Comind. The integration includes:

- Storing ATRecord nodes with metadata and content
- Tracking relationships between records
- Applying appropriate labels to different record types
- Full-text search capabilities
- Query functionality to explore the graph

## Schema Design

The database schema includes the following node tables:

- **Repo**: Represents a repository owned by a user, identified by DID
- **ATRecord**: All ATProto records with their metadata and content
- **User**: User information (existing)
- **Record**: Base record type (existing) 
- **Sphere**: Sphere record (existing)
- **BlipConcept**, **BlipEmotion**, **BlipThought**: Specialized record types (existing)

And relationship tables:

- **OWNS**: Connects a Repo to its ATRecords
- **FOLLOWS**: Connects repos when users follow each other
- **LIKES**: Connects an ATRecord to another when a like occurs
- **REPOSTS**: Connects an ATRecord to another when a repost occurs
- **BLOCKS**: Connects repos when a user blocks another
- **LINKS**: General relationship between records
- **IN_SPHERE**: Connects records to spheres
- **AUTHORED**: Connects users to records (existing)
- **TARGET**: Connects records to their targets (existing)

## Usage

### Starting the Jetstream Consumer with KuzuDB

The jetstream consumer can now store all ATProto records in KuzuDB as they arrive. Use the following command to run it:

```bash
python src/jetstream_consumer.py --db-path ./your_db_path --comind your_comind_name
```

Options:
- `--db-path`: Path to the KuzuDB database directory (default: ./demo_db)
- `--disable-db`: Disable storing ATProto records in KuzuDB

### Directly Using the Database Manager

You can also use the DBManager directly in your code:

```python
from src.db_manager import DBManager

# Initialize the manager
db = DBManager('./your_db_path')

# Store an ATProto record
db.store_atproto_record(
    uri="at://did:example/app.bsky.feed.post/abcde",
    cid="bafyreihgxxx",
    nsid="app.bsky.feed.post",
    record={"text": "Hello world", "createdAt": "2023-01-01T00:00:00Z"},
    author_did="did:example",
    rkey="abcde",
    labels=["ATRecord", "Post"]
)

# Query records
posts = db.list_atproto_records(nsid="app.bsky.feed.post", limit=10)

# Find relationships
relationships = db.query_atproto_relationships(source_uri="at://did:example/app.bsky.feed.post/abcde")
```

### Testing the Integration

Run the included test script to verify the database is working:

```bash
python test_kuzu.py
```

This will show all stored records, count them by type, display relationships, and test the search functionality.

## Node Labels

Records in the database are automatically assigned labels based on their type:

- All records: `ATRecord`
- Posts: `ATRecord`, `Post`
- Concepts: `ATRecord`, `Blip`, `Concept`
- Thoughts: `ATRecord`, `Blip`, `Thought`
- Emotions: `ATRecord`, `Blip`, `Emotion`
- Spheres: `ATRecord`, `Core`

## Querying the Database

The KuzuDB integration provides several methods for querying:

- `list_atproto_records()`: List records with optional filtering
- `get_atproto_record()`: Get a single record by URI
- `query_atproto_relationships()`: Find relationships between records
- `find_similar_records()`: Search records by text content

Internally, the database executes Cypher queries, which can be extended as needed.

## Extending the Integration

To add support for new record types:

1. Update the record processing in `store_atproto_record()` to handle the new type
2. Add appropriate label assignment
3. Add any specialized relationships

## Troubleshooting

- If you see errors about "table already exists" when setting up the schema, they can be safely ignored
- If full-text search doesn't work, the basic search fallback will be used automatically
- Make sure the database directory exists and is writable 