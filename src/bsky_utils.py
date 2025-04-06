import json
import re
from datetime import datetime
from src.lexicon_utils import strip_fields
import yaml
# Maximum length for posts
MAX_POST_LENGTH = 300
PLACEHOLDER = "(...)"
MAX_POST_LENGTH_WITH_PLACEHOLDERS = MAX_POST_LENGTH - len(PLACEHOLDER)

# Strip fields. A list of fields to remove from a JSON object
STRIP_FIELDS = [
    "cid",
    "rev",
    "did",
    "uri",
    "langs",
    "threadgate",
    "py_type",
    "labels",
    "facets",
    "avatar",
    "labels",
    "viewer",
    "indexed_at",
    "tags",
    "associated",
    "thread_context",
    "image",
    "aspect_ratio",
    "alt",
    "thumb",
    "fullsize",
]

def split_into_posts(text, category, max_length=MAX_POST_LENGTH):
    """Split text into appropriately sized posts with proper formatting.
    
    Args:
        text: The text content to split
        category: The category label (e.g., "analysis", "thought")
        max_length: Maximum length for each post
        
    Returns:
        List of formatted posts
    """
    if not text:
        return []

    # Format with category
    formatted = f"[{category}] {text}"

    # If it fits in one post, we're done
    if len(formatted) <= max_length:
        return [formatted]

    # We need to split it
    prefix = f"[{category}]"
    content = text

    # Calculate overhead for continuation markers
    cont_marker = " [cont]"
    part_marker_len = len(" (XX/XX)")  # Estimate for part numbers

    # Maximum content per chunk
    chunk_size = max_length - len(prefix) - len(cont_marker) - part_marker_len

    # Split into reasonable chunks
    chunks = []
    remaining = content

    while remaining:
        # If remaining content fits, use it all
        if len(remaining) <= chunk_size:
            chunks.append(remaining)
            break

        # Find a good break point
        break_at = chunk_size
        while break_at > 0 and break_at < len(remaining) and not remaining[break_at-1].isspace():
            break_at -= 1

        # If no good break found, just use max size
        if break_at == 0:
            break_at = min(chunk_size, len(remaining))

        # Add chunk and continue
        chunks.append(remaining[:break_at].rstrip())
        remaining = remaining[break_at:].lstrip()

    # Format each chunk with prefix and part numbers
    result = []
    total_parts = len(chunks)

    for i, chunk in enumerate(chunks):
        if i == 0:
            post = f"{prefix} {chunk}"
        else:
            post = f"{prefix}{cont_marker} {chunk}"

        if total_parts > 1:
            post += f" ({i+1}/{total_parts})"

        result.append(post)

    return result

def format_thought_for_posts(thought, max_length=MAX_POST_LENGTH):
    """Format a thought object into a series of posts.
    
    Args:
        thought: The thought object from the lexicon
        max_length: Maximum length for each post
        
    Returns:
        List of formatted posts ready for publishing
    """
    posts = []
    
    # Format the main thought content with its type
    if "thoughtType" in thought:
        thought_type = thought.get("thoughtType", "thought")
    elif "emotionType" in thought:
        thought_type = thought.get("emotionType", "emotion")
    else:
        thought_type = "blip"

    main_text = thought.get("text", "")
    
    # Add the main thought posts
    posts.extend(split_into_posts(main_text, thought_type, max_length))
    
    # Add the context if available
    context = thought.get("context", "")
    if context:
        posts.extend(split_into_posts(context, "context", max_length))
    
    # Add evidence if available
    evidence_list = thought.get("evidence", [])
    if evidence_list:
        # Join evidence items with bullet points
        evidence_text = "\n• " + "\n• ".join(evidence_list)
        posts.extend(split_into_posts(evidence_text, "evidence", max_length))
    
    # Add alternatives if available
    alternatives_list = thought.get("alternatives", [])
    if alternatives_list:
        # Join alternative items with bullet points
        alternatives_text = "\n• " + "\n• ".join(alternatives_list)
        posts.extend(split_into_posts(alternatives_text, "alternatives", max_length))
    
    return posts

def recursive_cid_uri_extractor(obj):
    """Recursively extract CID and URI from a JSON object."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "cid" or key == "uri":
                yield value
            else:
                yield from recursive_cid_uri_extractor(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from recursive_cid_uri_extractor(item)
    else:
        # If we get here, we have an invalid object type
        print("Invalid object type, got " + str(type(obj)))
        print(obj)
        exit()
        raise ValueError("Invalid object type, got " + str(type(obj)))

# Unpack the thread into a string. This creates a simple thread view of the format
# @handle: text
#   reply by @handle: text
#     reply by @handle: text
#   reply by @handle: text with quote 
#     @handle: text
def unpack_thread(thread_response, client=None, expand_quoted_threads=False, max_quoted_thread_depth=1, activated_dids=None):
    """
    Format a thread into a readable string format with tree-like structure.
    
    Args:
        thread_response: The thread JSON response
        client: Optional atproto client for fetching quoted threads
        expand_quoted_threads: Whether to fetch and expand quoted threads
        max_quoted_thread_depth: Maximum depth to expand quoted threads (to avoid excessive API calls)
        activated_dids: Optional list of activated DIDs. If provided, text from posts by DIDs not in this list
                      will be replaced with [NOT AVAILABLE]
    
    Returns:
        tuple: (formatted thread string, set of references)
    """
    # Require the thread response to be a dict
    if not isinstance(thread_response, dict):
        raise ValueError("Thread response must be a dictionary")

    # Thread
    thread = thread_response["thread"]
    stripped_thread = strip_fields(thread, STRIP_FIELDS)

    # Retrieve URI and CID and store in references.
    # In format (uri, cid)
    # TODO: #1 Add correct reference tracking in threads
    references = set()

    # Print out the out the YAML version of the thread
    formatted = yaml.dump(stripped_thread, indent=2, allow_unicode=True)

    # Join all lines into a single string
    return formatted, set(references)

if __name__ == "__main__":
    # Test the strip_fields function
    test_obj = {
        "cid": "123",
        "rev": "456",
        "uri": "789",
        "langs": ["en", "fr"],
        "foo": {
            "bar": "baz",
            "uri": "101112",
            "foo": {
                "bar": "baz",
                "uri": "131415",
                "cid": "161718"
            }
        },
        "array": [
            {
                "uri": "192021",
                "cid": "222324"
            }
        ]
    }
    print(strip_fields(test_obj))
