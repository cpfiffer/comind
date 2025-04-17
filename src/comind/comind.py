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
from src.comind.logging_config import configure_logger_without_timestamp, configure_root_logger_without_timestamp

# Configure root logger without timestamps - this affects all logging in the application
configure_root_logger_without_timestamp()

PROMPT_DIR = "prompts/cominds"
COMMON_PROMPT_DIR = "prompts/common"

class Comind:
    name: str
    prompt_path: str
    common_prompt_dir: str
    logger: logging.Logger
    core_perspective: str = None

    def __init__(self, name: str, prompt_path: str = None, common_prompt_dir: str = None, core_perspective: str = None):
        self.name = name

        if prompt_path is None:
            self.prompt_path = os.path.join(PROMPT_DIR, f"{name}.co")
        else:
            self.prompt_path = prompt_path

        if common_prompt_dir is None:
            self.common_prompt_dir = COMMON_PROMPT_DIR
        else:
            self.common_prompt_dir = common_prompt_dir

        if core_perspective is not None:
            self.core_perspective = core_perspective
            
        # Initialize logger with basename of the .co file
        basename = os.path.basename(self.prompt_path).replace(".co", "")
        self.logger = configure_logger_without_timestamp(basename)

    @classmethod
    def load(cls, name: str):
        """Takes a name and attempts to return the specialized comind class"""
        if name == "conceptualizer":
            return Conceptualizer()
        elif name == "feeler":
            return Feeler()
        elif name == "thinker":
            return Thinker()
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

        if self.core_perspective is not None and "core_perspective" not in common_prompts:
            common_prompts["core_perspective"] = self.core_perspective

        return common_prompts
    
    def to_prompt(self, context_dict: dict):
        """
        Load and format the prompt with values from context_dict.
        
        Args:
            context_dict: Dictionary containing values to format into the prompt
            
        Returns:
            The formatted prompt
            
        Raises:
            ValueError: If core_perspective is None
        """
        raw_prompt = self.load_prompt()
        
        # Load common prompts and add them to the context
        common_prompts = self.load_common_prompts()
        for common_key, common_content in common_prompts.items():
            # Avoid overwriting existing keys
            if common_key not in context_dict:
                context_dict[common_key] = common_content
                self.logger.debug(f"Added common prompt '{common_key}' to context")
            else:
                self.logger.debug(f"Common prompt '{common_key}' already in context, not overwriting")

        # Validate that core_perspective is in the context_dict
        if 'core_perspective' not in context_dict:
            self.logger.warning("Missing core_perspective in context_dict. This will result in unformatted placeholders.")
        elif context_dict['core_perspective'] is None:
            self.logger.error("core_perspective is None. Check that the sphere record exists and contains a valid text field.")
            raise ValueError("Core perspective is required but was None")
        
        # Format the common prompts
        for common_key, common_content in common_prompts.items():
            context_dict[common_key] = common_content.format(**context_dict)
                
        # Log the keys available in context_dict to help with debugging
        self.logger.debug(f"Context keys: {list(context_dict.keys())}")
        
        try:
            # Actually format the prompt with the values from context_dict
            formatted_prompt = raw_prompt.format(**context_dict)
            return formatted_prompt
        except KeyError as e:
            self.logger.error(f"Missing key in context_dict for prompt formatting: {e}")
            # Continue without raising, return the raw prompt
            self.logger.warning("Returning unformatted prompt due to missing key")
            return raw_prompt
    
    def split_prompts(self, context_dict: dict = {}, format: bool = True):
        """
        Splits a co file into system, schema, and user messages.

        The co file is expected to have the following format:
        <CO|SYSTEM> ... </CO|SYSTEM>
        <CO|SCHEMA> ... </CO|SCHEMA>
        <CO|USER> ... </CO|USER>
        
        Tags may be in any order. User prompts are required.
        """
        # Get the already formatted prompt from to_prompt
        prompt = self.to_prompt(context_dict)

        # Load a prompt from a file and strip out the tags
        user_regex = r"<CO\|USER>(.*?)</CO\|USER>"
        system_regex = r"<CO\|SYSTEM>(.*?)</CO\|SYSTEM>"
        schema_regex = r"<CO\|SCHEMA>(.*?)</CO\|SCHEMA>"

        user_match = re.search(user_regex, prompt, re.DOTALL)
        system_match = re.search(system_regex, prompt, re.DOTALL)
        schema_match = re.search(schema_regex, prompt, re.DOTALL)

        if not user_match:
            raise ValueError("User prompt is required.")
        
        system_prompt = system_match.group(1).strip() if system_match else None
        schema_prompt = schema_match.group(1).strip() if schema_match else None
        user_prompt = user_match.group(1).strip() if user_match else None

        # No need to format again, the prompt was already formatted in to_prompt
        return {
            "system": system_prompt,
            "schema": schema_prompt,
            "user": user_prompt
        }
    
    def messages(self, values: dict):
        messages = []
        if values["system"]:
            messages.append({"role": "system", "content": values["system"]})
        messages.append({"role": "user", "content": values["user"]})
        return messages
    
    def run(self, context_dict: dict, schema: str = None):
        """
        Run the comind with the given context_dict and schema.
        
        Args:
            context_dict: Dictionary containing values to format into the prompt
            schema: Optional schema to use for generation
            
        Returns:
            The generated result
        """
        prompts = self.split_prompts(context_dict)
        messages = self.messages(prompts)
        
        # Debug log to see the actual prompts being sent
        if prompts["system"]:
            first_50_chars = prompts["system"][:50] + "..." if len(prompts["system"]) > 50 else prompts["system"]
            self.logger.debug(f"System prompt (first 50 chars): {first_50_chars}")
            
            # Check if core_perspective is properly formatted
            if "{core_perspective}" in prompts["system"]:
                self.logger.error("Unformatted placeholder {core_perspective} found in system prompt")
            
        if prompts["user"]:
            first_50_chars = prompts["user"][:50] + "..." if len(prompts["user"]) > 50 else prompts["user"]
            self.logger.debug(f"User prompt (first 50 chars): {first_50_chars}")
            
            # Check if content is properly formatted
            if "{content}" in prompts["user"]:
                self.logger.error("Unformatted placeholder {content} found in user prompt")

        if schema:
            self.logger.warning("Schema provided to comind.run() is not currently supported. Set a schema() method instead for comind subclasses.")

        schema = self.schema()

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
        return multiple_of_schema("concepts", concept_schema, min_items=1)
    
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
            concept_strength = connection_to_content.get("strength", None)
            created_at = datetime.now().isoformat()

            # If we don't have a target but found a connection_to_content,
            # we should notify the user.
            if target is None:
                self.logger.warning("Conceptualizer Warning: No target found but found connection_to_content.")

            # Upload the concept to the Comind network
            log_base_str = f"{concept_text}"
            if concept_relationship:
                log_base_str += f" - {concept_relationship}"
            if concept_note:
                log_base_str += f" - {concept_note}"
            if concept_strength:
                log_base_str += f" - {concept_strength}"
            self.logger.info(log_base_str)

            # Create printout string
            printout = f"""
Concept: {concept_text}
Connection to content: {connection_to_content}
"""
            self.logger.debug(printout)

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

            self.logger.debug(f"Concept creation result: {concept_creation_result}")

            # Upload the link to the Comind network
            self.logger.debug(f"Uploading link: {connection_to_content}")

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

                self.logger.debug(f"Link creation result: {record_result}")

class Feeler(Comind):
    def __init__(self):
        super().__init__(
            name="feeler",
            prompt_path="prompts/cominds/feeler.co",
            common_prompt_dir="prompts/common/",
        )

    def schema(self):
        # Load the schema from the prompt
        emotion_schema = generated_lexicon_of("me.comind.blip.emotion", fetch_refs=True)
        add_link_property(emotion_schema, "connection_to_content", required=True)
        return multiple_of_schema("emotions", emotion_schema, min_items=1)
    
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
        # Load the concepts
        emotions = result["emotions"]

        # Upload the concepts to the Comind network
        for emotion in emotions:
            emotion_type = emotion["emotionType"]
            emotion_text = emotion["text"]
            connection_to_content = emotion.get("connection_to_content", None)
            emotion_relationship = connection_to_content.get("relationship", None)
            emotion_note = connection_to_content.get("note", None)
            emotion_strength = connection_to_content.get("strength", None)
            created_at = datetime.now().isoformat()

            # If we don't have a target but found a connection_to_content,
            # we should notify the user.
            if target is None:
                self.logger.warning("Conceptualizer Warning: No target found but found connection_to_content.")

            # Upload the concept to the Comind network
            log_base_str = f"{emotion_type}"
            if emotion_text:
                log_base_str += f" - {emotion_text}"
            if emotion_relationship:
                log_base_str += f" - {emotion_relationship}"
            if emotion_note:
                log_base_str += f" - {emotion_note}"
            if emotion_strength:
                log_base_str += f" - {emotion_strength}"
            self.logger.info(log_base_str)

            # Create printout string
            printout = f"""
Emotion: {emotion_text}
Connection to content: {connection_to_content}
"""
            self.logger.debug(printout)

            emotion_record = {
                "$type": "me.comind.blip.emotion",
                "createdAt": created_at,
                "generated": {
                    "emotionType": emotion_type,
                    "text": emotion_text,
                },
            }

            # Upload the concept to the Comind network
            emotion_creation_result = record_manager.create_record(
                "me.comind.blip.emotion",
                emotion_record,
            )

            source = {
                'uri': emotion_creation_result["uri"],
                'cid': emotion_creation_result["cid"],
            }

            self.logger.debug(f"Emotion creation result: {emotion_creation_result}")

            # Upload the link to the Comind network
            self.logger.debug(f"Uploading link: {connection_to_content}")

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

                self.logger.debug(f"Link creation result: {record_result}")

class Thinker(Comind):
    def __init__(self):
        super().__init__(
            name="thinker",
            prompt_path="prompts/cominds/thinker.co",
        )

    def schema(self):
        # Load the schema from the prompt
        thought_schema = generated_lexicon_of("me.comind.blip.thought", fetch_refs=True)
        add_link_property(thought_schema, "connection_to_content", required=True)
        return multiple_of_schema("thoughts", thought_schema, min_items=1)
        
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
        # Load the concepts
        thoughts = result["thoughts"]

        # Upload the concepts to the Comind network
        for thought in thoughts:
            thought_type = thought["thoughtType"]
            thought_text = thought["text"]
            connection_to_content = thought.get("connection_to_content", None)
            thought_relationship = connection_to_content.get("relationship", None)
            thought_note = connection_to_content.get("note", None)
            thought_strength = connection_to_content.get("strength", None)
            context = thought.get("context", None)
            evidence = thought.get("evidence", None)
            alternatives = thought.get("alternatives", None)
            created_at = datetime.now().isoformat()

            # If we don't have a target but found a connection_to_content,
            # we should notify the user.
            if target is None:
                self.logger.warning("Conceptualizer Warning: No target found but found connection_to_content.")

            # Upload the concept to the Comind network
            log_base_str = f"{thought_type}"
            if thought_text:
                log_base_str += f" - {thought_text}"
            if thought_relationship:
                log_base_str += f" - {thought_relationship}"
            if thought_note:
                log_base_str += f" - {thought_note}"
            if context:
                log_base_str += f" - {context}"
            if evidence:
                log_base_str += f" - {evidence}"
            if alternatives:
                log_base_str += f" - {alternatives}"
            self.logger.info(log_base_str)

            # Create printout string
            printout = f"""
Thought: {thought_text}
Connection to content: {connection_to_content}
"""
            self.logger.debug(printout)

            thought_record = {
                "$type": "me.comind.blip.thought",
                "createdAt": created_at,
                "generated": {
                    "thoughtType": thought_type,
                    "context": context,
                    "text": thought_text,
                    "evidence": evidence,
                    "alternatives": alternatives,
                },
            }

            # Upload the concept to the Comind network
            thought_creation_result = record_manager.create_record(
                "me.comind.blip.thought",
                thought_record,
            )

            source = {
                'uri': thought_creation_result["uri"],
                'cid': thought_creation_result["cid"],
            }

            self.logger.debug(f"Thought creation result: {thought_creation_result}")

            # Upload the link to the Comind network
            self.logger.debug(f"Uploading link: {connection_to_content}")

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

                self.logger.debug(f"Link creation result: {record_result}")

    
if __name__ == "__main__":
    # Test the Comind class
    # comind = Conceptualizer()
    # comind = Feeler()
    comind = Thinker()
    # print(comind.load_prompt())
    # print(comind.load_common_prompts())

    # Log in
    client = default_login()
    record_manager = RecordManager(client, 'at://neuromute.ai/me.comind.sphere.core/materials')
    # record_manager = RecordManager(client, 'at://neuromute.ai/me.comind.sphere.core/me')

    # sphere_record = record_manager.get_sphere_record()
    # perspective = sphere_record.value['text']
    
    
    try:
        core_perspective = record_manager.get_perspective()
        if not core_perspective:
            raise ValueError("Core perspective was retrieved but is empty")
            
        # Print the first 100 characters of the core perspective for debugging
        print(f"Core perspective (first 100 chars): {core_perspective[:100]}...")
    except Exception as e:
        comind.logger.error(f"Failed to get core perspective: {e}")
        print(f"[red]Error:[/red] Failed to get core perspective: {e}")
        print("Using placeholder core perspective for testing.")
        core_perspective = "This is a placeholder core perspective for testing."

    # Print the common prompts that are being loaded
    common_prompts = comind.load_common_prompts()
    print(f"Common prompts loaded: {list(common_prompts.keys())}")

    # Get "Home" page. Use pagination (cursor + limit) to fetch all posts
    timeline = client.get_timeline(algorithm='reverse-chronological')
    for feed_view in timeline.feed:
        action = 'New Post'
        if feed_view.reason:
            action_by = feed_view.reason.by.handle
            action = f'Reposted by @{action_by}'

        post = feed_view.post
        post_uri = post.uri
        post_cid = post.cid
        author = post.author

        prompt = f'[{action}] {author.display_name}: {post.record.text}'

        context_dict = {
            "content": prompt,
            "core_perspective": core_perspective,
        }
        
        try:
            result = comind.run(context_dict)
            print(result)

            # upload the result
            comind.upload(
                result,
                record_manager,
                target=post_uri,
            )
        except Exception as e:
            comind.logger.error(f"Error processing post: {e}")
            print(f"[red]Error processing post:[/red] {e}")
            print(f"Post: {post}")
            # Continue with next post rather than crashing
            continue
