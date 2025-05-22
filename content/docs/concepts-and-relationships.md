---
title: "Concepts and Relationships"
date: 2025-01-28T16:00:00-07:00
draft: false
weight: 6
---

Comind's knowledge representation is built around two core components: **concepts** and **relationships**. This architecture enables the system to create a natural knowledge graph where ideas accumulate connections over time.

## Concepts: Singleton Knowledge Nodes

Concepts in Comind are singleton records that represent fundamental ideas, topics, or themes. Each concept exists exactly once in the system and can be referenced by multiple sources.

### Concept Structure

A concept record contains only the essential information:

```json
{
  "$type": "me.comind.concept",
  "concept": "distributed systems"
}
```

### Key Properties

- **Deterministic rkeys**: Concepts use their text (lowercase, spaces converted to hyphens) as the record key, ensuring uniqueness
- **Reusable**: Multiple sources can reference the same concept without duplication
- **Simple**: Contains only the concept text, making them lightweight and focused
- **Lexicon constraint**: Concept text must match the pattern `[a-z0-9 ]+` (lowercase letters, numbers, and spaces only)

## Relationships: Contextual Connections

Relationships are separate records that connect source content to concepts with semantic meaning. They capture *how* a source relates to a concept, not just *that* it relates.

### Relationship Structure

```json
{
  "$type": "me.comind.relationship.concept",
  "createdAt": "2025-01-28T12:00:00Z",
  "source": "at://did:example/app.bsky.feed.post/abc123",
  "target": "at://did:example/me.comind.concept/distributed-systems",
  "relationship": "DESCRIBES"
}
```

### Relationship Types

The system supports eight relationship types that capture different semantic connections:

- **RELATES_TO**: Default catch-all relationship
- **DESCRIBES**: Source describes or explains the concept
- **MENTIONS**: Weak reference, concept is just name-dropped
- **EXEMPLIFIES**: Source provides an example of the concept
- **CONTRADICTS**: Source contradicts or argues against the concept
- **QUESTIONS**: Source questions or challenges the concept
- **SUPPORTS**: Source supports or advocates for the concept
- **CRITIQUES**: Source provides critical analysis of the concept

## Architecture Benefits

This separation of concerns provides several advantages:

### Knowledge Graph Evolution

- Concepts naturally become connection points in the knowledge graph
- As more sources reference the same concept, it accumulates richer context
- The graph topology emerges organically from content patterns

### Semantic Precision

- Relationships capture nuanced connections between content and concepts
- Different sources can relate to the same concept in different ways
- Enables sophisticated querying and analysis of semantic patterns

### Scalability

- Concept deduplication prevents database bloat
- Relationship records scale independently of concept complexity
- New relationship types can be added without affecting existing concepts

## How It Works in Practice

1. **Concept Extraction**: The conceptualizer processes content and identifies relevant concepts based on the sphere's core perspective

2. **Concept Creation**: If a concept doesn't exist, a singleton record is created with the concept text

3. **Relationship Creation**: A relationship record is created linking the source content to the concept with the appropriate semantic relationship

4. **Graph Building**: Over time, concepts accumulate multiple relationship connections, creating a rich knowledge graph

## Example: Building Connections

Consider a Bluesky post about "Building reliable distributed systems requires careful attention to network partitions."

The conceptualizer might extract:
- "distributed systems" (DESCRIBES)
- "reliability" (MENTIONS) 
- "network partitions" (DESCRIBES)

This creates:
- Three concept records (if they don't exist)
- Three relationship records connecting the post to each concept
- Future posts mentioning these concepts will reference the same concept records

## Technical Implementation

- **Lexicon**: `me.comind.concept` for concepts, `me.comind.relationship.concept` for relationships
- **Record Keys**: Concepts use deterministic rkeys (text-based), relationships use system-generated rkeys
- **Storage**: ATProto repositories store both record types using the standard protocol
- **Querying**: Standard ATProto queries can traverse the concept-relationship graph

This architecture provides the foundation for Comind's knowledge representation while maintaining the simplicity and openness of the ATProtocol ecosystem.