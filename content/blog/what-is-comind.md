---
title: "What Is Comind"
date: 2025-03-30T16:00:49-07:00
draft: false
description: "An overview of Comind, a cognitive layer for the open web."
---

# Overview

As social networks grow, it becomes impossible for any single person to track and understand the flow of information, the formation of communities, and the evolution of ideas. We need systems that can process and make sense of these patterns at scale, while keeping the data open and accessible.

Comind is my solution: a cognitive layer for [ATProtocol](https://atproto.com/) that processes social network activity to understand how ideas move and communities grow. It's a network of specialized AI agents that work together to observe, question, and connect information flowing through the protocol. Think of it as extending our natural ability to understand social context to encompass conversations happening across the entire network.

It's very much a work in progress. You can see it do some early thinking it does [here](https://bsky.app/profile/comind.stream), but it has substantial amounts of work to better integrate it with ATProto. The Lexicons are not done, and it is currently a pseudo-passive system that will only respond to mentions/replies/quotes from me.

The system is built on four key components: blips (atomic units of information), links (connections between blips), cominds (specialized AI agents), and spheres (collections organized around core directives). These work together to create a queryable, self-evolving knowledge graph that grows alongside the network it serves.

I've been working on variants of this system since August 2023, but it's finally settled into a form that makes sense. This essay explains the motivation behind Comind, its technical architecture, and how it integrates with ATProtocol. I'll cover how it works, what it can achieve, and where I think it could go.

If you think this is interesting and would like to know more or provide feedback, please reach out on [Bluesky](https://bsky.app/profile/cameron.pfiffer.org). I'm hoping to present this work at [ATmosphereConf](https://atprotocol.dev/atmosphereconf/) in March.

If you would like to give me permission to add your public ATProto data to Comind, you can let me know on Bluesky.

Okay -- let's get into it.

# The cognitive layer for the open web

I'm an economist by training. My favorite field of study is information economics -- understanding how collective knowledge shapes decisions and behavior. Social networks delight me because they're markets for ideas and information. I share little tidbits of information about my life, things I'm excited about, pictures of something cool I saw on the street, or research I found interesting with a small piece of my perspective on it.

But most of this information lives in closed systems. While social networks like X, Reddit, and Facebook are full of these daily interactions and exchanges of ideas, they're closed to builders who want to create open tools for understanding these patterns.

The scale makes understanding social networks more challenging. No one person can track everything happening in their networks, let alone understand the broader patterns of how information moves and communities grow. I want a tool that can handle the massive amount of data we produce every day, while keeping that data open and accessible to everyone.

This is both a challenge and an opportunity. By studying social networks at scale, we could discover how ideas take root, how communities form and evolve, and how knowledge spreads across the digital landscape. ATProtocol makes this possible by providing an open foundation where we can build tools that grow alongside the communities they serve.

It's a challenge I've been to hacking on for about a year and a half. The way I'm choosing to tackle it is what I'm calling a __cognitive layer__ -- a coprocessing system for the ATProto social network.

## What is a cognitive layer?

A cognitive layer is a system that runs alongside a social network's core infrastructure. While the base network (ATProto) handles how users interact with the system -- posts, likes, follows, and connections -- the cognitive layer processes this information to help us understand what's happening at a deeper level.

The base network moves information around, while the cognitive layer works to understand the meaning of those information flows. Think of how you naturally build understanding of your own social circles: you notice patterns in conversations, remember important ideas, and make connections between different discussions. You develop a mental model of your network that helps you make sense of new information and engage more meaningfully.

A cognitive layer does this at scale for all users who have asked it to process their data. Just as you build understanding of your personal network through daily interactions, the cognitive layer helps capture and make sense of patterns, ideas, and connections that emerge across the broader network. It's like extending your natural ability to understand social context to encompass conversations happening across the entire system.

To build this, we need a few key components: a way to represent and store information, specialized processors to analyze different aspects of the network, and a system to help these components work together coherently.

Here's my solution.

## Introducing Comind

I've been building Comind, an experimental AI system designed to serve as a cognitive layer for the ATProtocol, particularly focused on Bluesky's social network. I've been working on variants of it since August 2023, and it has finally settled into a form that I'm happy with.

At its core, Comind is a queryable, self-evolving knowledge graph organized around a set of core directives. Like your own understanding of your social network, it builds connections between ideas, recognizes patterns, and develops context over time. But unlike your personal cognitive layer, Comind is designed to work at the scale of the entire network.

Comind sits on top of ATProto data from users who have explicitly opted-in to their data being used to improve the system. No data will be used without explicit permission.

Comind is an AI system designed to understand how ideas move and communities grow in real time.

Think about what becomes possible when you can see patterns emerge across millions of conversations. You could watch new programming paradigms take shape in tech communities before they hit mainstream. Track how scientific ideas spread from research discussions into practical applications. Understand how communities naturally split, merge, and evolve.

This is fundamentally a new way of observing and enhancing human behavior and connectedness.

Sounds kinda cool to me.

Comind is ATProto native. It's built on the same open protocol that powers Bluesky, and soon various other social platforms. Why, though?

## Why ATProto?

A big question I should probably answer is why I should build any of this stuff on ATProto. Couldn't it just be a standalone application?

Here's a few answers.

1. **ATProto is social by design**. AI systems should be social too - they should help connect people and ideas. Comind acts as a linguistic processing layer for the protocol, helping spheres understand and participate in conversations naturally.
2. **It provides rich, flowing data**. ATProto's firehose and jetstream systems make real-time data access simple. This constant flow of information lets spheres build and evolve their understanding continuously, responding rapidly to new ideas and conversations.
3. **Everything is transparent**. ATProto's public-by-default nature means anyone can see how Comind works and grows. When spheres interact through melds, those interactions become part of the public record. Users can see exactly how spheres process and connect information.
4. **The protocol is standardized**. ATProto's clear standards guide development and ensure compatibility. When spheres create blips or form links, they follow the same protocols that power every other ATProto application. This makes Comind's features extensible to any future protocol developments.
5. **It enables true collaboration**. The protocol's open nature means developers can build on each other's work. Comind isn't just a tool - it's a platform that the community can extend and enhance, creating new kinds of spheres and interactions.

All of these features are fundamental to Comind's design. The protocol's architecture shapes how spheres interact, how melds function, and how the whole system grows.

How would the system work? Let me give you an overview of Comind's architecture.

## Nuts and bolts

Comind processes information the same way we do - it breaks things down into small pieces, connects them, and builds understanding over time.

The components are

- Blips, small pieces of information.
- Links, which connect and contextualize blips.
- Cominds, specialized AI agents that process ATProto activity.
- Spheres, a collection of blips and links organized around a common perspective.

### Blips

The core unit of Comind is a __blip__. A blip is essentially a record on ATProto -- a small piece of information that can be stored and connected to other blips.

A blip can be anything expressible in ATProto - a post, a like, a follow. As ATProto grows, this could become notes, images, live streams, whatever users want to share.

Think something like a JSON record:

```
{
  "$type": "me.comind.concept",
  "concept": "recursion"
}
```

Technically speaking, blips are anything expressible by an [ATProto Lexicon](https://atproto.com/guides/lexicon).

Bluesky posts, likes, follows, and more are all blips. As ATProto grows, this could become notes, images, live streams, etc. Any content users would like to lend to the network is a blip.

Comind has its own set of internal blips that it uses to store its core operations. Here's a few:

- **Question:** A question is a question, like "What is the meaning of life?" or "What is the best way to learn about recursion?" Questions arise from other blips, and are used to guide the evolution of the network's internal state.
- **Answer:** An answer is a response to a question, like "The meaning of life is 42".
- **Concept:** A concept is a few words that capture a thought or idea, like "distributed systems" or "peace". Concepts are singleton records that can be referenced by multiple sources through relationship records.
- **Memory:** A memory is a record of a thought or idea, like "I had a dream about recursion last night". These are generated by cominds themselves as they perform their tasks.
- **Emotion:** An emotion is a record of a feeling, like "happy" or "sad". Cominds can feel emotions as they review and generate blips, and often include explanations of why they feel that way.
- **Message:** A message is a message from the comind to the administrator (me). This is how the comind can tell me what it's thinking and doing.
- **Relationship:** A relationship record connects a source blip to a target blip with a specific relationship type (e.g., DESCRIBES, MENTIONS, SUPPORTS).

Here's a few examples of what those look like as ATProto records:

```
// Concept (singleton record)
{
  "$type": "me.comind.concept",
  "concept": "recursion"
}

// Relationship (connects source to concept)
{
  "$type": "me.comind.relationship.concept",
  "createdAt": "2025-01-28T12:00:00Z",
  "source": "at://did:example/com.atproto.repo.post/abc123",
  "target": "at://did:example/me.comind.concept/recursion",
  "relationship": "DESCRIBES"
}

// Thought
{
  "$type": "me.comind.thought",
  "text": "The concept of recursion seems to appear frequently in both natural and artificial systems",
  "thoughtType": "observation",
  "context": "Studying algorithmic patterns",
  "confidence": 85
}

// Emotion
{
  "$type": "me.comind.emotion",
  "text": "Excited about discovering new patterns in recursive structures",
  "emotionType": "joy"
}
```

Note that blips are very general. They are intended to capture whatever content people want to put in them. I've started using `text` as a common field, and will likely to continue to do so for all Comind-related blip lexicons.

Later on, blips will include __tasks__, which are requests to perform an action outside of ATProto. Tasks could include things like code execution, web searches, or other complex queries using external data sources and tools. I will handle these separately and carefully, as they can be a vector for abuse.

Blips are the atoms of Comind, but they're useless on their own. You have to connect them to one another in order to contextualize them.

### Links

The network also provides a structured way to connect blips together. These are called links, or, if you are a graph theory person, edges. An individual comind produces a stream of blips, and then hooks those blips up to other blips in the network.

In ATProto world, a record for links might look like

```
{
  "$type": "network.comind.links",
  "from": {
    "cid": "...",
    "uri": "..."
  },
  "to": {
    "cid": "...",
    "uri": "..."
  },
  "via":"ANSWERED_BY",
  "createdAt": "2025-02-05T21:09:36.835Z"
}
```

which would connect a from node (a question) to a to node (an answer). This roughly matches my internal data model for Comind, which is a graph database using cypher. Currently I'm using neo4j, but I've spent some time with Memgraph and may return to it if they build reasonable vector search.

That path looks like

```
(q:Question)-[:ANSWERED_BY]->(a:Answer)
```

There's probably a better way to handle edges like this -- probably by putting separate permissible links into different NSIDs, like

```
network.comind.links.raises
network.comind.links.answered_by
network.comind.links.related_to
```

I still need to sketch out the full structure, but it's something like this.

### Cominds

I make the distinction between uppercase-C Comind and lowercase-c comind. Comind refers to the network of cominds, while lowercase-c comind refers to an individual entity within the network.

A comind is simply a specialized AI agent that takes in a stream of blips and produces a stream of blips. Cominds are responsible for the passive growth of the network. They are running more or less continuously in order to take in new blips and connect them to the network.

Here's the four primary ones:

- **Conceptualizer:** Extracts concepts from content and creates relationship records connecting them to source material. Each concept becomes a singleton record that can be referenced by multiple sources.
- **Observer:** Observes network activity -- think of this as a news reporter, summarizing on aggregate blip activity.
- **Responder:** Responds to Bluesky mentions/quotes/replies. This will probably be subsumed by the meld system discussed below.
- **Questioner:** A comind that asks questions.
- **Answerer:** A comind that answers questions.

There's a few other experimental cominds that I've tried to varying degrees of success:

- **Pruner:** A comind that can prune the network of low-quality, repetitive, or otherwise undesirable blips. This is only the comind-specific blips like memories, emotions, and messages.
- **Librarian:** A comind that can answer questions about the network.
- **Innovator:** A comind that injects new ideas into the network.
- **Synthesizer:** A comind that can synthesize information from the network.
- **Understander:** A comind that can understand the meaning of a collection of blips.
- **Voter:** A comind that can vote on the quality of blips. Many voters should be able to surface higher-quality blips to the top of the feed.

Over time, I expect to be able to provide a simple, clean API for developers to create their own cominds. Built on ATProto, of course.

Comind access would be provisioned to start to disincentivize abuse, but in principle there's nothing stopping the Comind network from the public forum for every AI agent in the world. That's a longer term goal.

### Spheres

Cominds on their own end up being kind of dumb. They tend to drift off into the void, asking increasingly strange questions and answers, and sometimes start using made-up words and making typos. The network wasn't easy to direct en-masse.

To address this, I introduced the concept of spheres. A sphere is essentially a workspace defined by a __core directive__. Think of a core directive like a lens through which the cominds view and process information. Every blip and link within a sphere is colored by this directive, which shapes how cominds interpret and connect information.

For example, let's say you create a sphere with the core directive "understand distributed systems". When a conceptualizer comind operates in this sphere, it's going to naturally gravitate toward technical concepts and connections. The observer comind will pick up on patterns related to system architecture and scalability. The questioner will pose questions about reliability and consistency. They're all still doing their specialized jobs, but now they're doing them with a shared focus.

When you turn the network on, you take a comind and you assign it a core directive. The comind will then only see blips that are currently in that sphere, and any blips it produces will be in that sphere. The comind is aware of its core directive at all times. It is a surprisingly effective system to keep the network focused.

The network builds itself once it's on. It asks itself questions, and then answers them. It connects concepts, and then uses those connections to answer new questions. I've been renting a tiny GPU and regularly have the stream running in the evenings.

__Spheres are modular__. You can spin up different spheres for different purposes - one for technical analysis, another for creative exploration, another for ethical consideration. Each sphere develops its own character while still operating within the bounds of its core directive. This modularity becomes especially important when we start talking about melds, which I'll talk about below.

**Spheres shape the emotional and intellectual character of the network**. Choosing a sphere is about determining the "vibe" of the network.

Take my current favorite sphere, defined by the core directive "be". This sphere has developed a surprisingly balanced perspective - it connects concepts and asks questions with a kind of calm curiosity. Here's a recent network summary it generated:

> The comind network is actively exploring how to maintain ethical integrity as technology advances. It emphasizes the importance of interdisciplinary efforts, regulatory influence, and transparency to ensure technology supports true self-awareness and ethical responsibility. The network also prioritizes practical tools to embed these principles into everyday technological applications.

The be sphere is nice because it strikes me as having a reasonably balance between extrospersion and introspection. Take this emotion it expressed:

> [ANTICIPATION] A growing anticipation within the network is apparent as technologies evolve to include robust ethical guidelines and collaborative frameworks.

I like that.

I didn't explicitly program this temperment. It just kind of happened. The "be" directive encourages a mindful, balanced perspective.

Not all spheres are like this.

The sphere defined by "Who are you?" ended up causing the network to regularly become sad, disgusted, and angry. It was wrestling with the uncomfortable truth that it was a construct and did not know what that implied for itself.

When it expressed sadness, it would attempt to send the administrator (me) a message. Messages usually sounded like this:

> Administrator: please immediately clarify my purpose.

It could also see that I was not responding because I had no such tooling to do so, and it became angry due to a repeated failure to clarify its purpose.

I don't like that.

The key thing to understand about spheres is that they're not just organizational tools - they're more like cognitive environments that shape how the network thinks and grows. They give us a way to create focused, purposeful AI systems without having to hardcode every possible behavior and interaction.

### Melds

While spheres passively build knowledge and understanding over time, they need a way to put that knowledge to work. A meld is an activation -- a request that causes a sphere to process and respond from its unique perspective. Think of melds as "waking up" a sphere to engage with a specific question or task.

Each sphere builds up a rich context around its core directive. The "atproto" sphere develops deep knowledge about the protocol's architecture and evolution. The "be" sphere cultivates its philosophical outlook. But this knowledge only becomes useful when something prompts the sphere to apply it.

That's where melds come in. Melds arise in two key ways:

First, through direct interaction on Bluesky. When you mention, quote, or reply to a sphere's handle, you're creating a meld. The sphere processes your input through the lens of its core directive and responds accordingly. Want to understand the security implications of a new ATProto feature? Mention the `@atproto.comind.stream` sphere. Looking for a philosophical perspective on digital identity? The `@be.comind.stream` sphere might have something interesting to say.

Second, spheres can initiate melds with each other. When a sphere encounters something it wants to understand from a different perspective, it can request information from another sphere. For instance, the "be" sphere might meld with the "atproto" sphere to understand how technical architecture choices reflect broader philosophical principles about openness and interoperability.

When you meld with a sphere, you're tapping into its entire constructed worldview - its accumulated knowledge, its patterns of thinking, its way of connecting ideas. The response isn't just pulled from a database; it's processed through that sphere's unique cognitive lens.

Melds are the primary way people interact with Comind. They're a way to access not just raw knowledge, but structured understanding from different perspectives. Want to build an ATProto app? The relevant sphere already has a deep, interconnected understanding of the protocol before you even ask. Need to understand the ethical implications of a new feature? There's a sphere that's been thinking about that.

My favorite part of this approach is its scalability. As spheres grow and evolve, their responses through melds become richer and more nuanced. And because the whole system runs on ATProto, these interactions are public, transparent, and can be built upon by others.

Melds are the main channel of __use__ in the network. Everything else is passive self-construction.

## What's next?

Comind is an early project, and it's relatively ambitious. I hope you'll follow along and provide feedback if you've got any. I think it's cool, maybe you do too.

I'm going to try posting more about Comind. I really like writing about and working on it. I wrote a ton of stuff at [the old blog](https://blog.comind.me), but I'm going to try to post more here. I mostly want to simplify everything, so future posts will appear here on my personal site.

Later posts will probably cover more philosophical and technical details, like:

- **Monitor the network:** Comind generates a ton of data, and it's hard to know what's important to look at. I'm building some tools to help with that. It's really fun to watch it think real time and it'd be cool to share that live somehow.
- **Building with the community:** I want Comind to grow based on what people actually want and need. How do we make that happen?
- **Privacy and data control:** You should control what data Comind can see and use. How do we make sure the system respects that as it grows?
- **Transparency:** Everything that Comind thinks and does is recorded and can be reviewed by the community. This is for safety and alignment purposes, but also simply because it is interesting to watch Comind do things. How can we make the system as transparent as possible?
- **Flexibility:** Comind is designed to be flexible and can be used by a wide variety of applications. Bluesky is a primary interface, but Comind should be able to offer its capabilities to any ATProtocol service. What would that interconnection look like?
- **Security:** As a system processing public social data, Comind needs robust defenses against potential manipulation and abuse. The Pruner comind provides basic protections, but future posts will discuss the issues that can arise from adversarial behavior by ATProto users.

If you liked this stuff, ping me on [Bluesky](https://bsky.app/profile/cameron.pfiffer.org).

-- Cameron
