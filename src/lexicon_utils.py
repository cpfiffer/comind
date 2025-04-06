from datetime import datetime

import json
import re

def strip_fields(obj, strip_field_list):
    """Recursively strip fields from a JSON object."""
    if isinstance(obj, dict):
        for field in strip_field_list:
            obj.pop(field, None)
        for key, value in obj.items():
            obj[key] = strip_fields(value)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            obj[i] = strip_fields(value)
    return obj


def lexicon_of(nsid):
    # Read the lexicon file from the file system
    lexicon_path = f"lexicons/" + nsid.replace(".", "/") + ".json"

    # Read the lexicon file
    with open(lexicon_path, "r") as f:
        lexicon = json.load(f)

    from atproto_lexicon.parser import lexicon_parse

    # Parse the lexicon to validate it
    parsed_lexicon = lexicon_parse(lexicon)

    # Get the generated part of the lexicon
    generated_part = lexicon["defs"]["generated"]['record']

    # Check to see if there is a regex contained in the description
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



def add_property(schema, property_name, property_schema, required=False):
    schema["properties"][property_name] = property_schema
    if required:
        schema["required"].append(property_name)


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
