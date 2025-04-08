# Code to manage cominds and prompts

from datetime import datetime
from datetime import datetime
import os
import re
import json
import logging
from src.session_reuse import default_login
import src.structured_gen as sg
from src.lexicon_utils import generated_lexicon_of, multiple_of_schema, add_link_property
from src.record_manager import RecordManager
from typing import Optional
from rich import print

# Configure logging
logger = logging.getLogger("comind")

PROMPT_DIR = "prompts/cominds"
COMMON_PROMPT_DIR = "prompts/common"

class Comind:
    name: str
    prompt_path: str
    common_prompt_dir: str

    def __init__(self, name: str, prompt_path: str = None, common_prompt_dir: str = None):
        self.name = name

        if prompt_path is None:
            self.prompt_path = os.path.join(PROMPT_DIR, f"{name}.co")
        else:
            self.prompt_path = prompt_path

        if common_prompt_dir is None:
            self.common_prompt_dir = COMMON_PROMPT_DIR
        else:
            self.common_prompt_dir = common_prompt_dir

    @classmethod
    def load(cls, name: str):
        """Takes a name and attempts to return the specialized comind class"""
        if name == "conceptualizer":
            return Conceptualizer()
        else:
            raise ValueError(f"Unknown comind: {name}")

    def load_prompt(self):
        with open(self.prompt_path, "r") as f:
            return f.read()
        
    def load_common_prompts(self):
        common_prompts = {}
        for file in os.listdir(self.common_prompt_dir):
            with open(os.path.join(self.common_prompt_dir, file), "r") as f:
                bn = os.path.basename(file).replace(".co", "")
                common_prompts[bn] = f.read()
        return common_prompts
    
    def to_prompt(self, context_dict: dict):
        prompt = self.load_prompt()
        return prompt
    
    def split_prompts(self, context_dict: dict = {}, format: bool = True):
        """
        Splits a co file into system, schema, and user messages.

        The co file is expected to have the following format:
        <CO|SYSTEM> ... </CO|SYSTEM>
        <CO|SCHEMA> ... </CO|SCHEMA>
        <CO|USER> ... </CO|USER>
        
        Tags may be in any order. User prompts are required.
        """
        prompt = self.to_prompt(context_dict)

        # Load a prompt from a file and strip out the tags
        user_regex = r"<CO\|USER>(.*?)</CO\|USER>"
        system_regex = r"<CO\|SYSTEM>(.*?)</CO\|SYSTEM>"
        schema_regex = r"<CO\|SCHEMA>(.*?)</CO\|SCHEMA>"

        user_match = re.search(user_regex, prompt, re.DOTALL)
        system_match = re.search(system_regex, prompt, re.DOTALL)
        schema_match = re.search(schema_regex, prompt, re.DOTALL)

        user_prompt = user_match.group(1).strip() if user_match else ""
        system_prompt = system_match.group(1).strip() if system_match else ""
        schema_prompt = schema_match.group(1).strip() if schema_match else ""

        if not user_match:
            raise ValueError("User prompt is required.")
        
        system_prompt = system_match.group(1) if system_match else None
        schema_prompt = schema_match.group(1) if schema_match else None
        user_prompt = user_match.group(1)

        # Set up prompt formatting
        common_prompts = self.load_common_prompts()

        # Merge common prompts into context_dict
        for common_prompt in common_prompts:
            context_dict[common_prompt] = common_prompts[common_prompt]

        if system_prompt and format:
            system_prompt = system_prompt.format(**context_dict)

        if user_prompt and format:
            user_prompt = user_prompt.format(**context_dict)

        return {
            "system": system_prompt.strip() if system_prompt else None,
            "schema": schema_prompt.strip() if schema_prompt else None,
            "user": user_prompt.strip()
        }
    
    def messages(self, values: dict):
        messages = []
        if values["system"]:
            messages.append({"role": "system", "content": values["system"]})
        messages.append({"role": "user", "content": values["user"]})
        return messages
    
    def run(self, context_dict: dict, schema: str = None):
        prompts = self.split_prompts(context_dict)
        messages = self.messages(prompts)

        schema = self.schema()
        # print(schema)

        # if not schema:
        #     # Check if we have one in the prompts dict. Must be 
        #     # nonzero length and valid JSON.
        #     if "schema" in prompts:
        #         # If we had a schema in the prompts, we should try to use
        #         # a comind-specific schema.
        #         try:
        #             schema = self.schema()
        #         except json.JSONDecodeError:
        #             raise ValueError("Schema is not valid JSON.")
        #     else:
        #         raise ValueError("Schema is required.")

        return sg.generate_by_schema(messages, schema)

def available_cominds():
    cominds = []
    for file in os.listdir(PROMPT_DIR):
        cominds.append(os.path.basename(file).replace(".co", ""))
    return cominds

class Conceptualizer(Comind):
    def __init__(self):
        super().__init__(
            name="conceptualizer",
            prompt_path="prompts/cominds/conceptualizer.co",
            common_prompt_dir="prompts/common/",
        )   

    def schema(self):
        # Load the schema from the prompt
        concept_schema = generated_lexicon_of("me.comind.blip.concept", fetch_refs=True)
        add_link_property(concept_schema, "connection_to_content", required=True)
        return multiple_of_schema("concepts", concept_schema)
    
    def run(self, context_dict: dict):
        response = super().run(context_dict)
        result = json.loads(response.choices[0].message.content)

        return result
    
    def upload(
        self,
        result: dict,
        record_manager: RecordManager,
        target: Optional[str] = None,
        sphere: Optional[str] = None,
    ):
        """
        Uploads the result to the Comind network.

        The result is expected to be a list of concepts.
        """
        # Load the concepts
        concepts = result["concepts"]

        # Upload the concepts to the Comind network
        for concept in concepts:
            concept_text = concept["text"]
            connection_to_content = concept.get("connection_to_content", None)
            concept_relationship = connection_to_content.get("relationship", None)
            concept_note = connection_to_content.get("note", None)
            created_at = datetime.now().isoformat()

            # If we don't have a target but found a connection_to_content,
            # we should notify the user.
            if target is None:
                logger.warning("Conceptualizer Warning: No target found but found connection_to_content.")

            # Upload the concept to the Comind network
            log_base_str = f"{concept_text}"
            if concept_relationship:
                log_base_str += f" - {concept_relationship}"
            if concept_note:
                log_base_str += f" - {concept_note}"
            logger.info(log_base_str)

            # Create printout string
            printout = f"""
Concept: {concept_text}
Connection to content: {connection_to_content}
"""
            logger.debug(printout)

            concept_record = {
                "$type": "me.comind.blip.concept",
                "createdAt": created_at,
                "generated": {
                    "text": concept_text,
                },
            }

            # Upload the concept to the Comind network
            maybe_record = record_manager.try_get_record(
                "me.comind.blip.concept",
                concept_text.lower().replace(" ", "-"),
            )

            if maybe_record is not None:
                concept_creation_result = maybe_record
            else:
                concept_creation_result = record_manager.create_record(
                    "me.comind.blip.concept",
                    concept_record,
                )

            source = {
                'uri': concept_creation_result["uri"],
                'cid': concept_creation_result["cid"],
            }

            logger.debug(f"Concept creation result: {concept_creation_result}")

            # Upload the link to the Comind network
            logger.debug(f"Uploading link: {connection_to_content}")

            if connection_to_content is not None and target is not None:
                link_record = {
                    "$type": "me.comind.relationship.link",
                    "createdAt": created_at,
                    "source": source,
                    "target": target,
                    "generated": connection_to_content,
                }

                record_result = record_manager.create_record(
                    "me.comind.relationship.link",
                    link_record,
                )

                logger.debug(f"Link creation result: {record_result}")

if __name__ == "__main__":
    # Test the Comind class
    comind = Conceptualizer()
    # print(comind.load_prompt())
    # print(comind.load_common_prompts())

    # Log in
    client = default_login()
    record_manager = RecordManager(client, 'at://comind.stream/me.comind.sphere.core/void')

    # Get "Home" page. Use pagination (cursor + limit) to fetch all posts
    timeline = client.get_timeline(algorithm='reverse-chronological')
    for feed_view in timeline.feed:
        action = 'New Post'
        if feed_view.reason:
            action_by = feed_view.reason.by.handle
            action = f'Reposted by @{action_by}'

        post = feed_view.post.record
        author = feed_view.post.author

        prompt = f'[{action}] {author.display_name}: {post.text}'
        print(prompt)

        context_dict = {
            "content": prompt
        }
        result = comind.run(context_dict)
        print(result)

        # upload the result
        comind.upload(result, record_manager, target=post.uri)

    # while True:
    #     context_dict = {
    #         "content": "Hello, world!"
    #     }
    #     print(comind.run(context_dict))

    # concept_schema = generated_lexicon_of("me.comind.blip.concept")
    # add_link_property(concept_schema, "connection_to_content", required=True)
    # schema = multiple_of_schema("concepts", concept_schema)

    # print(json.dumps(schema, indent=2))
    # print(comind.run(context_dict, schema))