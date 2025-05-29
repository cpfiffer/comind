---
title: "Graph Database Integration"
date: 2025-01-28T18:00:00-07:00
draft: false
weight: 7
---

Comind includes powerful graph database integration using Neo4j, enabling sophisticated analysis and querying of the knowledge network. The graph database complements ATProto's record storage by providing fast traversal and pattern discovery capabilities.

## Architecture

The graph database integration follows a **dual-layer architecture**:

- **ATProto Records**: Canonical source of truth for all data
- **Neo4j Graph**: Optimized query layer synchronized from ATProto

This approach maintains ATProto's openness while enabling powerful graph analytics.

## Getting Started

### 1. Start Neo4j

Start the database services using Docker:

```bash
# Start only the database
./scripts/services.sh start database

# Or start all services
./scripts/services.sh start all
```

This will start Neo4j with:
- **Browser**: http://localhost:7474
- **Bolt**: bolt://localhost:7687  
- **Credentials**: neo4j/comind123

### 2. Sync Your Data

Sync your ATProto records to the graph database:

```bash
# One-command sync (sets up schema + syncs all records)
./scripts/services.sh sync

# Or use the graph sync tool directly
python scripts/graph_sync.py --setup-schema --sync-all
```

### 3. Explore the Graph

Access Neo4j Browser at http://localhost:7474 and try some queries:

```cypher
// See all node types
MATCH (n) RETURN DISTINCT labels(n) as nodeTypes

// Find most connected concepts
MATCH (c:Concept)<-[:CONCEPT_RELATION]-(source)
RETURN c.text, count(source) as connections
ORDER BY connections DESC LIMIT 10

// Explore a concept's network
MATCH path = (c:Concept {text: "distributed systems"})-[*1..2]-(connected)
RETURN path LIMIT 20
```

## Data Model

The graph database mirrors Comind's lexicon structure:

### Node Types

- **Concept**: Singleton concept nodes (`me.comind.concept`)
- **Thought**: Generated thoughts (`me.comind.thought`)
- **Emotion**: Generated emotions (`me.comind.emotion`) 
- **Sphere**: Knowledge spheres (`me.comind.sphere.core`)
- **Post**: External content (`app.bsky.feed.post`)

### Relationship Types

- **CONCEPT_RELATION**: Links content to concepts with semantic types
- **LINK**: General relationships between content
- **IN_SPHERE**: Associates content with spheres

## Common Query Patterns

### Find Related Concepts

```cypher
// Concepts related to "machine learning"
MATCH (c:Concept {text: "machine learning"})<-[:CONCEPT_RELATION]-(source)
MATCH (source)-[:CONCEPT_RELATION]->(related:Concept)
WHERE related <> c
RETURN related.text, count(*) as frequency
ORDER BY frequency DESC
```

### Analyze Sphere Focus

```cypher
// Most frequent concepts in a sphere
MATCH (content)-[:IN_SPHERE]->(s:Sphere {title: "AI Research"})
MATCH (content)-[:CONCEPT_RELATION]->(c:Concept)
RETURN c.text, count(*) as frequency
ORDER BY frequency DESC LIMIT 20
```

### Discover Concept Clusters

```cypher
// Find highly connected concept groups
MATCH (c1:Concept)<-[:CONCEPT_RELATION]-(source)-[:CONCEPT_RELATION]->(c2:Concept)
WHERE id(c1) < id(c2)
RETURN c1.text, c2.text, count(source) as shared_sources
ORDER BY shared_sources DESC LIMIT 10
```

### Trace Thought Evolution

```cypher
// Follow how thoughts build on concepts over time
MATCH (t:Thought)-[:CONCEPT_RELATION]->(c:Concept {text: "distributed systems"})
RETURN t.text, t.thoughtType, t.createdAt
ORDER BY t.createdAt
```

## CLI Tools

### Graph Sync Tool

The `scripts/graph_sync.py` tool provides comprehensive sync and query capabilities:

```bash
# Setup and sync
python scripts/graph_sync.py --setup-schema
python scripts/graph_sync.py --sync-all
python scripts/graph_sync.py --sync-collection me.comind.concept

# Query operations  
python scripts/graph_sync.py --concept-network "distributed systems"
python scripts/graph_sync.py --sphere-concepts "AI Research"
python scripts/graph_sync.py --concept-clusters --min-connections 5

# Save results
python scripts/graph_sync.py --concept-network "ai" --output results.json
```

### Service Management

The `scripts/services.sh` script includes graph operations:

```bash
./scripts/services.sh sync          # Full sync with setup
./scripts/services.sh shell         # Connect to Neo4j shell
./scripts/services.sh status        # Check service status
```

## Sync Process

The graph database provides both batch and real-time synchronization capabilities:

### Real-Time Sync (Recommended)

New in Comind: **Automatic real-time graph injection** that syncs records to Neo4j as they're created.

When enabled, the graph database stays continuously updated with new concepts, thoughts, emotions, and relationships created by your Comind instance. This happens automatically without any manual intervention.

**Enable real-time sync:**

```bash
# 1. First, start the database services
./scripts/services.sh start database

# 2. Set environment variable  
export COMIND_GRAPH_SYNC_ENABLED=true

# 3. Then run your Comind instance normally
python src/jetstream_consumer.py --comind conceptualizer
```

**Important**: Make sure Neo4j is running before enabling real-time sync. Check service status with:
```bash
./scripts/services.sh status
```

Real-time sync can also be enabled programmatically:

```python
from src.record_manager import RecordManager

# Enable graph sync when creating records
record_manager = RecordManager(client, enable_graph_sync=True)
```

### Batch Sync

The batch sync service maps ATProto records to graph nodes and relationships:

1. **Schema Setup**: Creates constraints and indexes for optimal performance
2. **Node Creation**: Converts records to typed nodes (Concept, Thought, etc.)
3. **Relationship Mapping**: Creates edges based on record references
4. **Collection Updates**: Supports syncing specific record collections

### Supported Collections

**Comind Collections:**
- `me.comind.concept` → Concept nodes
- `me.comind.thought` → Thought nodes  
- `me.comind.emotion` → Emotion nodes
- `me.comind.sphere.core` → Sphere nodes
- `me.comind.relationship.*` → Graph relationships

**External Collections:**
- `app.bsky.feed.post` → Post nodes (when `--include-external`)

## Performance Considerations

### Indexes and Constraints

The sync service automatically creates:
- Unique constraints on URIs
- Indexes on frequently queried fields (text, type, createdAt)
- Optimized for common query patterns

### Sync Strategy

- **Full Sync**: Complete rebuild from ATProto records
- **Collection Sync**: Update specific record types
- **Incremental**: Future enhancement for real-time updates

### Query Optimization

- Use `EXPLAIN` to analyze query performance
- Leverage indexes for filtering and sorting
- Limit path length in graph traversals
- Use `count()` aggregations for statistics

## Advanced Usage

### Custom Queries

Create custom analysis queries for your use cases:

```cypher
// Find concepts that bridge different spheres
MATCH (s1:Sphere)<-[:IN_SPHERE]-(content1)-[:CONCEPT_RELATION]->(c:Concept)
MATCH (s2:Sphere)<-[:IN_SPHERE]-(content2)-[:CONCEPT_RELATION]->(c)
WHERE s1 <> s2
RETURN c.text, s1.title, s2.title, count(*) as bridge_strength
ORDER BY bridge_strength DESC
```

### Integration with Python

Use the `GraphSyncService` class directly in your applications:

```python
from src.graph_sync import create_graph_sync_service

# Create service
sync_service = create_graph_sync_service()

# Get concept network
network = sync_service.get_concept_network("machine learning", depth=3)

# Find clusters
clusters = sync_service.find_concept_clusters(min_connections=5)

# Custom queries
with sync_service.driver.session() as session:
    result = session.run("MATCH (n:Concept) RETURN count(n)")
    concept_count = result.single()[0]
```

## Troubleshooting

### Connection Issues

```bash
# Check if Neo4j is running
./scripts/services.sh status

# View Neo4j logs
./scripts/services.sh logs neo4j

# Test connection
./scripts/services.sh shell
```

### Sync Problems

```bash
# Enable verbose logging
python scripts/graph_sync.py --sync-all --verbose

# Sync specific collection
python scripts/graph_sync.py --sync-collection me.comind.concept

# Reset schema
# (Stop Neo4j, remove volumes, restart, re-sync)
```

### Performance Issues

- Check query execution with `EXPLAIN`
- Ensure indexes are created (`--setup-schema`)
- Limit query depth and result size
- Use pagination for large result sets

The graph database integration provides a powerful foundation for analyzing Comind's knowledge network, discovering patterns, and building sophisticated applications on top of the concept-relationship architecture.