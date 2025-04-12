from datetime import datetime

import json
import re
from rich import print

def strip_fields(obj, strip_field_list):
    """Recursively strip fields from a JSON object."""
    if isinstance(obj, dict):
        keys_flagged_for_removal = []
        for field in strip_field_list:
            obj.pop(field, None)

        for key, value in obj.items():
            obj[key] = strip_fields(value, strip_field_list)
            if not obj[key] or (isinstance(obj[key], dict) and len(obj[key]) == 0) or (isinstance(obj[key], list) and len(obj[key]) == 0) or (isinstance(obj[key], str) and obj[key].strip() == ""):
                keys_flagged_for_removal.append(key)

        for key in keys_flagged_for_removal:
            obj.pop(key, None)

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


def multiple_of_schema(parent_key, schema, min_items=None, max_items=None):
    # Converts a single concept schema into a list of conceptualizer schemas
    # by adding the "focus" field to the schema
    wrapper = {
        "type": "record",
        "required": [parent_key],
        "properties": {
            parent_key: {
                "type": "array",
                "items": schema,
                "minItems": min_items if min_items is not None else 0,
                "maxItems": max_items if max_items is not None else None
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

def resolve_refs_recursively(lexicon, processed_refs=None, defs=None):
    if isinstance(lexicon, str):
        lexicon = json.loads(lexicon)

    if processed_refs is None:  
        processed_refs = set()

    # defs is used to store schema-local definitions, defined in fields like
    # #/defs/main or #generated, etc.
    if defs is None:
        defs = {}
    
    # Handle the case where lexicon is a list
    if isinstance(lexicon, list):
        for i, item in enumerate(lexicon):
            if isinstance(item, (dict, list)):
                lexicon[i] = resolve_refs_recursively(item, processed_refs, defs)
        return lexicon
        
    # Handle the case where lexicon is a dictionary
    for def_name, def_value in lexicon.items():
        # Skip debug printing
        # print(def_name, def_value)

        # Check if def_value is a dictionary before trying to check for "ref"
        if isinstance(def_value, dict):
            # Check if we have "ref". If so, we need to resolve the referenced lexicon.
            if "ref" in def_value:
                ref = def_value["ref"]

                if ref.startswith("#"):
                    # Leave as is
                    pass
                else:
                    # Resolve the referenced lexicon
                    referenced_lexicon = lexicon_of(ref)
                    lexicon[def_name] = resolve_refs_recursively(referenced_lexicon, processed_refs, defs)

                # if ref not in processed_refs:
                #     processed_refs.add(ref)
                #     referenced_lexicon = lexicon_of(ref)
                #     resolve_refs_recursively(referenced_lexicon, processed_refs, defs)
                #     lexicon[def_name] = referenced_lexicon
            # If we don't have "ref", we need to recursively resolve the referenced lexicon.
            else:
                for key, value in def_value.items():
                    if isinstance(value, (dict, list)):  # Only process dictionaries and lists
                        def_value[key] = resolve_refs_recursively(value, processed_refs, defs)

                    # Check if the reference value is a schema-local definition (starts with #)
                    # if so, we can add the definition to the defs dictionary and leave the reference
                    # as is.
                    assert isinstance(key, str) # should always be a string, no?
                    if key.startswith("#"):
                        defs[key] = def_value
                        lexicon[def_name] = def_value
                        continue

        elif isinstance(def_value, list):
            # Handle list values by recursively processing each item
            for i, item in enumerate(def_value):
                if isinstance(item, (dict, list)):  # Only process dictionaries and lists
                    def_value[i] = resolve_refs_recursively(item, processed_refs, defs)

    return lexicon
