from datetime import datetime

import json
import re
from rich import print

def strip_fields(obj, strip_field_list):
    """Recursively strip fields from a JSON object."""
    if isinstance(obj, dict):
        for field in strip_field_list:
            obj.pop(field, None)
        for key, value in obj.items():
            obj[key] = strip_fields(value, strip_field_list)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            obj[i] = strip_fields(value, strip_field_list)
    return obj

def lexicon_of(nsid, fetch_refs=False):
    # Read the lexicon file from the file system
    lexicon_path = f"lexicons/" + nsid.replace(".", "/") + ".json"

    # Read the lexicon file
    with open(lexicon_path, "r") as f:
        lexicon = json.load(f)

    # If fetch_refs is true, we need to find any refs in the lexicon and replace
    # them with the actual lexicon record.
    if fetch_refs:
        for def_name, def_value in lexicon["defs"].items():
            if "ref" in def_value:
                ref = def_value["ref"]
                lexicon["defs"][def_name] = lexicon_of(ref)

    return lexicon

def generated_lexicon_of(nsid, fetch_refs=False):
    lexicon = lexicon_of(nsid, fetch_refs)

    from atproto_lexicon.parser import lexicon_parse

    # Parse the lexicon to validate it
    parsed_lexicon = lexicon_parse(lexicon)

    # Get the generated part of the lexicon
    generated_part = lexicon["defs"]["generated"]

    print(generated_part)

    # Check to see if there is a regex contained in the description
    if "description" in lexicon:
        pattern_regex = r"\(PATTERN OF '(.*?)': (.*?)\)"
        pattern_match = re.search(pattern_regex, lexicon["description"])
        if pattern_match:
            # Extract the field name and regex pattern from the description
            field_name = pattern_match.group(1)
            pattern = pattern_match.group(2)
            
            # Find the field in the schema and add the regex constraint
            if field_name in generated_part["properties"]:
                generated_part["properties"][field_name]["pattern"] = pattern
            else:
                print(f"Warning: Field '{field_name}' not found in schema, but pattern constraint specified")
    
    return generated_part


def multiple_of_schema(parent_key, schema):
    # Converts a single concept schema into a list of conceptualizer schemas
    # by adding the "focus" field to the schema
    wrapper = {
        "type": "record",
        "required": [parent_key],
        "properties": {
            parent_key: {
                "type": "array",
                "items": schema
            }
        }
    }

    return wrapper


def get_link_schema():
    return generated_lexicon_of("me.comind.relationship.link")

def add_property(schema, property_name, property_schema, required=False):
    schema["properties"][property_name] = property_schema
    if required:
        schema["required"].append(property_name)


def add_link_property(schema, property_name, required=False):
    add_property(schema, property_name, get_link_schema(), required)

def split_link(record):
    # Split off the connection_to_content
    connection_to_content = record.pop("connection_to_content")

    # Create the connection_to_content record
    connection_to_content_record = {
        "$type": "me.comind.relationship.link",
        "createdAt": datetime.now().isoformat(),
        "relationship": connection_to_content["relationship"]
    }

    # Add strength if it exists
    if "strength" in connection_to_content:
        connection_to_content_record["strength"] = connection_to_content["strength"]

    # Add note if it exists
    if "note" in connection_to_content:
        connection_to_content_record["note"] = connection_to_content["note"]

    return connection_to_content_record

def resolve_refs_recursively(lexicon, processed_refs=None):
    if isinstance(lexicon, str):
        lexicon = json.loads(lexicon)

    print(lexicon)

    if processed_refs is None:
        processed_refs = set()
        
    for def_name, def_value in lexicon.items():
        print(def_name, def_value)

        # Check if we have "ref". If so, we need to resolve the referenced lexicon.
        if "ref" in def_value:
            ref = def_value["ref"]
            if ref not in processed_refs:
                processed_refs.add(ref)
                referenced_lexicon = lexicon_of(ref)
                resolve_refs_recursively(referenced_lexicon, processed_refs)
                lexicon[def_name] = referenced_lexicon
        # If we don't have "ref", we need to recursively resolve the referenced lexicon.
        else:
            if isinstance(def_value, dict):
                for key, value in def_value.items():
                    resolve_refs_recursively(value, processed_refs)

    return lexicon
