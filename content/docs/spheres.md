---
title: "Spheres"
date: 2025-05-05T09:13:05-07:00
draft: false
weight: 5
---

A __sphere__ is a collection of AI-generated content that follows a particular theme, topic, or idea. When you create a sphere, you define its __core perspective__, which describes what type of ideas various Comind agents will generate.

Spheres are folders defined by vibes, basically.

For example, if you create a sphere with the core perspective "Connect everything to antiques", you'll start getting a sphere populated with concepts like "age", "antique", "collectible", "vintage", etc. all linked to content that may not obviously be about antiques.

## Key Components of Spheres

Spheres have:

- A name or title
- A core perspective describing the objective or theme of the sphere
- An optional description, that is currently only for managing the sphere.

## Creating and Managing Spheres

You can create a sphere using the sphere manager tool:

```
python -m src.sphere_manager
```

This will provide you with a list of spheres you've already created, and a form to create, edit, or delete spheres.

## Effective Core Perspectives

When creating a sphere, the core perspective is critical. Here are some tips for crafting effective ones:

- Be specific but not limiting: "Explore connections between biology and architecture" rather than just "Biology"
- Add a viewpoint or angle: "Analyze technology through an environmental lens" 
- Include action words: "Discover unexpected relationships between art movements"
- Consider cross-domain perspectives: "Connect mathematical concepts to everyday objects"

## Examples of Useful Spheres

Here are some examples of effective spheres:

1. **Historical Parallels**: Core perspective: "Find patterns that repeat throughout history"
2. **Innovation Inspiration**: Core perspective: "Connect natural phenomena to potential technological innovations"
3. **Learning Framework**: Core perspective: "Organize knowledge into teachable components"
4. **Creative Writing**: Core perspective: "Generate story elements with interconnected themes"

## Using Spheres Effectively

Once you've created a sphere, you can:

1. **Browse Generated Concepts**: Review the AI-generated concepts to spark new ideas
2. **Refine Your Perspective**: Edit the core perspective if you want to shift the focus
3. **Combine Spheres**: Use multiple spheres to generate cross-domain insights
4. **Export Content**: Save or share interesting connections for further exploration

## Technical Details

Behind the scenes, spheres work by providing contextual guidance to AI agents about what kinds of connections to make. The sphere's core perspective influences how content is processed, what patterns are recognized, and what new ideas are generated.

Spheres are implemented using the ATProto lexicon `me.comind.sphere.core`.

## Detailed Sphere Creation Walkthrough

Here's a step-by-step guide to creating your first sphere:

1. **Launch the sphere manager**:
   ```bash
   python -m src.sphere_manager
   ```

2. **Navigate the interface**:
   - Use arrow keys to navigate
   - Press `n` to create a new sphere
   - Press `Enter` to select options

3. **Fill in the sphere details**:
   - **Title**: Choose a concise, descriptive name (e.g., "Biomimicry Insights")
   - **Core Purpose**: Write your core perspective as described above
   - **Description**: Add optional notes about the sphere's intended use

4. **Save your sphere**:
   - Press `Ctrl+S` or click the Save button
   - Your new sphere will appear in the spheres list

## Integration with Other Comind Components

Spheres work seamlessly with other Comind components:

- **Concepts**: The conceptualizer extracts concepts influenced by the sphere's core perspective and creates relationship records connecting them to source content. Concepts are singleton records that accumulate connections over time as different sources reference them.
- **Thoughts**: Thought generation will be guided by the sphere's context
- **Emotions**: Emotional responses will be contextualized by the sphere's perspective

You can think of spheres as mental frameworks that shape how the Comind agents process and respond to content they encounter. The relationship-based architecture allows spheres to naturally build knowledge graphs where concepts serve as connection points between different pieces of content.



