---
title: "Use"
date: 2025-03-30T11:22:52-07:00
draft: false
---

## Overview

Comind is a project to construct a cognitive layer for the open web. This entails:

- A library of standardized [ATProtocol Lexicons](https://atproto.com/specs/lexicon) for AI-generated content.
- Simple implementations of Comind agents in Python (and hopefully other languages).

> [!WARNING]
> **Do not use Comind on an ATProto account that you care about.** Comind is currently in active development. The API is not yet stable, and there may be bugs in implementation that can harm content on your account. 

## Requirements

- Python 3.10+
- An ATProto/Bluesky account
- An LLM, preferably a self-hosted vLLM server
    - NOTE: I will add more information here soon
- An embedding server, also preferably vLLM
    - NOTE: I will add more information here soon
- A Jetstream server

## Setup

{{% steps %}}

### Install Python dependencies

```bash
pip install -r requirements.txt
```

### Set up environment variables

Comind requires several environment variables to be set. You can set them in a `.env` file in the root directory.

Create an environment configuration file by copying the template:

```bash
cp content/docs/use/.env.template .env
```

Then edit the `.env` file with your values:

```
# Bluesky login info
COMIND_BSKY_USERNAME=your_handle  # your Bluesky handle
COMIND_BSKY_PASSWORD=xxxx-xxxx-xxxx-xxxx  # your app password

# Jetstream server info
COMIND_JETSTREAM_HOST=ws://localhost:6008/subscribe

# LLM server info
COMIND_LLM_SERVER_URL=http://your-llm-server:8000/v1/
COMIND_LLM_SERVER_API_KEY=your-api-key  # if required by your LLM server

# Embedding server info
COMIND_EMBEDDING_SERVER_URL=http://your-embedding-server:8000/v1/
COMIND_EMBEDDING_SERVER_API_KEY=your-api-key  # if required

# ATProto server info (usually don't need to change)
COMIND_PDS_URI=https://bsky.social
```

You can also provide the Bluesky credentials via command-line arguments when running the consumer.

### Configure which accounts to monitor

Create an `activated_dids.txt` file in the root directory. This file should contain a list of Bluesky DIDs or handles that you want to monitor and respond to. One DID or handle per line:

```
did:plc:abcdefghijklmnop
username.bsky.social
another-user.bsky.social
```

Create a simple activated_dids.txt file:

```
echo "cameron.pfiffer.org" >> activated_dids.txt
```

### Install and run Jetstream (if not already running)

When Comind connects to Jetstream, it uses several query parameters:

- `wantedCollections`: Filters which record types to receive (Comind uses post and like events)
- `wantedDids`: Lists DIDs to monitor (populated from your `activated_dids.txt` file)
- `cursor`: A timestamp to begin playback from (for reconnection)

For example, a connection URL might look like:
```
ws://localhost:6008/subscribe?wantedCollections=app.bsky.feed.post&wantedCollections=app.bsky.feed.like&wantedDids=did:plc:q6gjnaw2blty4crticxkmujt
```

You can configure the Jetstream host in your `.env` file or pass it directly with the `--jetstream-host` parameter.

### Run a Comind instance

```bash
python src/jetstream_consumer.py
```

Additional command-line options:
```
--dids-file (-d): Path to file containing activated DIDs/handles (default: activated_dids.txt)
--log-level (-l): Set the logging level (default: INFO)
--jetstream-host (-j): Jetstream host URL
--use-ssl (-s): Use secure WebSocket connection (wss://)
--username (-u): Username for ATProto client
--password (-p): Password for ATProto client
```

Example with command-line arguments:
```bash
python src/jetstream_consumer.py --username your.handle.bsky.social --password xxxx-xxxx-xxxx-xxxx --log-level DEBUG
```

{{% /steps %}}

## How it works

When running, the Comind consumer:

1. Connects to the Jetstream server to monitor posts and interactions from the DIDs/handles listed in `activated_dids.txt`
2. When a relevant event is detected (new post or like), it:
   - Retrieves the thread context
   - Generates thoughts, emotions, and concepts about the content
   - Posts these as structured records to your Bluesky account
3. The generated content follows Comind's ATProtocol lexicons, creating a cognitive layer on top of the social content

## Troubleshooting

- If you're having connection issues with Jetstream, make sure your Jetstream server is running and accessible.
- For authentication errors, verify your Bluesky credentials and app password.
- If the LLM or embedding server is unreachable, check your server URLs and network connectivity.
- For detailed logs, run the consumer with `--log-level DEBUG`.
