---
title: "Use"
date: 2025-03-30T11:22:52-07:00
draft: false
---

## Overview

Comind is a project to construct a cognitive layer for the open web. This entails:

- A library of standardized [ATProtocol Lexicons](https://atproto.com/specs/lexicon) for AI-generated content.
- Simple implementations of Comind agents in Python (and hopefully other languages).

## Setup

{{% steps %}}

### Add requirements

### Set up environment

```bash
cp .env.example .env
```

It is recommended to set the `COMIND_BSKY_USERNAME` and `COMIND_BSKY_PASSWORD` environment variables, but you can also run the consumer with the `--username` and `--password` flags when running the jetstream consumer.

### Install the jetstream

See the [jetstream docs](https://github.com/bluesky-social/jetstream) for more information.



### Run the consumer

```bash
python src/jetstream_consumer.py
```

{{% /steps %}}
