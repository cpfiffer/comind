# Code to manage cominds and prompts

from datetime import datetime
from datetime import datetime
import os
import re
import json
import logging
import time
from src.session_reuse import default_login
import src.structured_gen as sg
from src.lexicon_utils import (
    generated_lexicon_of,
    multiple_of_schema,
    add_link_property,
)
from src.record_manager import RecordManager
from typing import Optional, List, Dict
from rich import print
from rich.panel import Panel
from rich.text import Text
from src.comind.logging_config import (
    configure_logger_without_timestamp,
    configure_root_logger_without_timestamp,
)
from .format import format, format_dict

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
    sphere_name: str = None

    def __init__(
        self,
        name: str,
        prompt_path: str = None,
        common_prompt_dir: str = None,
        core_perspective: str = None,
        sphere_name: str = None,
    ):
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

        if sphere_name is not None:
            self.sphere_name = sphere_name

        # Initialize logger with basename of the .co file
        basename = os.path.basename(self.prompt_path).replace(".co", "")
        self.logger = configure_logger_without_timestamp(basename)

    @classmethod
    def load(cls, name: str, sphere_name: str = None):
        """Takes a name and attempts to return the specialized comind class"""
        if name == "conceptualizer":
            return Conceptualizer(sphere_name=sphere_name)
        elif name == "feeler":
            return Feeler(sphere_name=sphere_name)
        elif name == "thinker":
            return Thinker(sphere_name=sphere_name)
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

        if (
            self.core_perspective is not None
            and "core_perspective" not in common_prompts
        ):
            common_prompts["core_perspective"] = self.core_perspective

        if self.sphere_name is not None and "sphere_name" not in common_prompts:
            common_prompts["sphere_name"] = self.sphere_name

        return common_prompts

    def get_required_context_keys(self):
        """
        Returns a list of keys that are required for the prompt.
        """
        return ["core_perspective", "sphere_name"]

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
                self.logger.debug(
                    f"Common prompt '{common_key}' already in context, not overwriting"
                )

        # Validate that core_perspective is in the context_dict
        if "core_perspective" not in context_dict:
            self.logger.warning(
                "Missing core_perspective in context_dict. This will result in unformatted placeholders."
            )
        elif context_dict["core_perspective"] is None:
            self.logger.error(
                "core_perspective is None. Check that the sphere record exists and contains a valid text field."
            )
            raise ValueError("Core perspective is required but was None")

        # Format the common prompts
        context_dict.update(format_dict(common_prompts, context_dict))

        # Log the keys available in context_dict to help with debugging
        self.logger.info(f"Context keys: {list(context_dict.keys())}")

        try:
            # Actually format the prompt with the values from context_dict
            formatted_prompt = raw_prompt.format(**context_dict)
            return formatted_prompt
        except KeyError as e:
            self.logger.error(
                f"Expected key in context_dict for prompt formatting: {e}"
            )
            # Continue without raising, return the raw prompt
            # self.logger.warning("Returning unformatted prompt due to missing key")
            # return raw_prompt
            raise e

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
        return {"system": system_prompt, "schema": schema_prompt, "user": user_prompt}

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

        # Add the core_perspective to the context_dict
        context_dict["core_perspective"] = self.core_perspective

        # Add the sphere_name to the context_dict
        context_dict["sphere_name"] = self.sphere_name

        prompts = self.split_prompts(context_dict)
        messages = self.messages(prompts)

        self.logger.debug("messages", messages)

        # Debug log to see the actual prompts being sent
        if prompts["system"]:
            first_50_chars = (
                prompts["system"][:50] + "..."
                if len(prompts["system"]) > 50
                else prompts["system"]
            )
            self.logger.debug(f"System prompt (first 50 chars): {first_50_chars}")

            # Check if core_perspective is properly formatted
            if "{core_perspective}" in prompts["system"]:
                self.logger.error(
                    "Unformatted placeholder {core_perspective} found in system prompt"
                )

        if prompts["user"]:
            first_50_chars = (
                prompts["user"][:50] + "..."
                if len(prompts["user"]) > 50
                else prompts["user"]
            )
            self.logger.debug(f"User prompt (first 50 chars): {first_50_chars}")

            # Check if content is properly formatted
            if "{content}" in prompts["user"]:
                self.logger.error(
                    "Unformatted placeholder {content} found in user prompt"
                )

        if schema:
            self.logger.warning(
                "Schema provided to comind.run() is not currently supported. Set a schema() method instead for comind subclasses."
            )

        schema = self.schema()

        # # Format the text to interpolation the context_dict
        # # replaces {key} with value.
        # for message in messages:
        #     print("message", message)
        #     message["content"] = message["content"].format(**context_dict)
        # print(messages)

        return sg.generate_by_schema(messages, schema)


def available_cominds():
    cominds = []
    for file in os.listdir(PROMPT_DIR):
        cominds.append(os.path.basename(file).replace(".co", ""))
    return cominds


class Conceptualizer(Comind):
    def __init__(
        self,
        sphere_name: str = None,
        core_perspective: str = None,
        prompt_path: str = None,
        common_prompt_dir: str = None,
    ):
        super().__init__(
            name="conceptualizer",
            prompt_path="prompts/cominds/conceptualizer.co",
            common_prompt_dir="prompts/common/",
            sphere_name=sphere_name,
            core_perspective=core_perspective,
        )

    def schema(self):
        # Simple schema for concept extraction
        return {
            "type": "object",
            "properties": {
                "concepts": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "A simple concept (1-3 words, lowercase, spaces allowed)",
                    },
                    "minItems": 5,
                    "maxItems": 15,
                }
            },
            "required": ["concepts"],
        }

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
        from_refs: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Uploads the result to the Comind network.

        The result is expected to be a list of concept strings.
        """
        # Load the concepts (now just strings)
        concepts = result["concepts"]

        # Upload the concepts to the Comind network
        for concept_text in concepts:
            self.logger.info(f"[bold cyan]Concept:[/bold cyan] {concept_text}")

            # Create the simplified concept record
            concept_record = {
                "$type": "me.comind.concept",
                "concept": concept_text,
                "source": target,  # Reference to the source record
            }

            # Upload the concept to the Comind network
            maybe_record = record_manager.try_get_record(
                "me.comind.concept",
                concept_text.lower().replace(" ", "-"),
            )

            if maybe_record is not None:
                concept_creation_result = maybe_record
                self.logger.debug(f"Found existing concept: {concept_text}")
            else:
                concept_creation_result = record_manager.create_record(
                    "me.comind.concept",
                    concept_record,
                )
                self.logger.debug(f"Created new concept: {concept_text}")

            self.logger.debug(f"Concept result: {concept_creation_result}")


class Feeler(Comind):
    def __init__(self, sphere_name: str = None, core_perspective: str = None):
        super().__init__(
            name="feeler",
            prompt_path="prompts/cominds/feeler.co",
            common_prompt_dir="prompts/common/",
            sphere_name=sphere_name,
            core_perspective=core_perspective,
        )

    def schema(self):
        # Load the schema from the prompt
        emotion_schema = generated_lexicon_of("me.comind.emotion", fetch_refs=True)
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
        from_refs: Optional[List[Dict[str, str]]] = None,
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
                self.logger.warning(
                    "Conceptualizer Warning: No target found but found connection_to_content."
                )

            # Log the emotion in a structured, readable format
            # Create a structured log message
            log_lines = []
            log_lines.append(f"[bold cyan]Emotion Type:[/bold cyan] {emotion_type}")

            if emotion_text:
                log_lines.append(f"[bold blue]Description:[/bold blue] {emotion_text}")

            if emotion_relationship:
                log_lines.append(
                    f"[bold green]Relationship:[/bold green] {emotion_relationship}"
                )

            if emotion_note:
                log_lines.append(f"[bold yellow]Note:[/bold yellow] {emotion_note}")

            if emotion_strength:
                log_lines.append(
                    f"[bold magenta]Strength:[/bold magenta] {emotion_strength}"
                )

            log_message = "\n".join(log_lines)
            self.logger.info(log_message)

            # Create printout string
            printout = f"""
Emotion: {emotion_text}
Connection to content: {connection_to_content}
"""
            self.logger.debug(printout)

            emotion_record = {
                "$type": "me.comind.emotion",
                "createdAt": created_at,
                "generated": {
                    "emotionType": emotion_type,
                    "text": emotion_text,
                },
            }

            if from_refs:
                emotion_record["from"] = from_refs

            # Upload the concept to the Comind network
            emotion_creation_result = record_manager.create_record(
                "me.comind.emotion",
                emotion_record,
            )

            source = {
                "uri": emotion_creation_result["uri"],
                "cid": emotion_creation_result["cid"],
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
    def __init__(self, sphere_name: str = None, core_perspective: str = None):
        super().__init__(
            name="thinker",
            prompt_path="prompts/cominds/thinker.co",
            sphere_name=sphere_name,
            core_perspective=core_perspective,
        )

    def schema(self):
        # Load the schema from the prompt
        thought_schema = generated_lexicon_of("me.comind.thought", fetch_refs=True)
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
        from_refs: Optional[List[Dict[str, str]]] = None,
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
                self.logger.warning(
                    "Conceptualizer Warning: No target found but found connection_to_content."
                )

            # Log the thought in a structured, readable format
            from rich.panel import Panel
            from rich.text import Text

            # Create a structured log message
            log_lines = []
            log_lines.append(f"[bold cyan]Thought Type:[/bold cyan] {thought_type}")

            if thought_text:
                log_base_str += f" - {thought_text}"
            # if thought_relationship:
            #     log_base_str += f" - relationship: {thought_relationship}"
            # if thought_note:
            #     log_base_str += f" - note: {thought_note}"
            # if context:
            #     log_base_str += f" - context: {context}"
            # if evidence:
            #     log_base_str += f" - evidence: {evidence}"
            # if alternatives:
            #     log_base_str += f" - alternatives: {alternatives}"
            self.logger.info(log_base_str)

            # Create printout string
            printout = f"""
Thought: {thought_text}
Connection to content: {connection_to_content}
"""
            self.logger.debug(printout)

            thought_record = {
                "$type": "me.comind.thought",
                "createdAt": created_at,
                "generated": {
                    "thoughtType": thought_type,
                    "context": context,
                    "text": thought_text,
                    "evidence": evidence,
                    "alternatives": alternatives,
                },
            }

            if from_refs:
                thought_record["from"] = from_refs

            # Upload the concept to the Comind network
            thought_creation_result = record_manager.create_record(
                "me.comind.thought",
                thought_record,
            )

            source = {
                "uri": thought_creation_result["uri"],
                "cid": thought_creation_result["cid"],
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

    # Log in
    client = default_login()
    record_manager = RecordManager(
        client, "at://neuromute.ai/me.comind.sphere.core/materials"
    )
    # record_manager = RecordManager(client, 'at://neuromute.ai/me.comind.sphere.core/me')

    # sphere_record = record_manager.get_sphere_record()
    # perspective = sphere_record.value['text']

    generated_strings = []

    core_perspective = record_manager.get_perspective()
    core_name = record_manager.get_sphere_name()
    if core_perspective is None:
        raise ValueError("Core perspective was retrieved but is empty")

    # Test the Comind class
    args = {
        "core_perspective": core_perspective,
        "sphere_name": core_name,
    }
    comind1 = Conceptualizer(**args)
    comind2 = Feeler(**args)
    comind3 = Thinker(**args)
    # print(comind.load_prompt())
    # print(comind.load_common_prompts())

    cominds = [comind1, comind2, comind3]

    # Get "Home" page. Use pagination (cursor + limit) to fetch all posts
    timeline = client.get_timeline(algorithm="reverse-chronological")

    for feed_view in timeline.feed:  # Outer loop: posts
        action = "New Post"
        if feed_view.reason:
            action_by = feed_view.reason.by.handle
            action = f"Reposted by @{action_by}"

        post = feed_view.post
        post_uri = post.uri
        post_cid = post.cid
        author = post.author
        post_content_prompt = f"[{action}] {author.display_name}: {post.record.text}"

        for comind in cominds:  # Inner loop: cominds
            try:
                # Print the first 100 characters of the core perspective for debugging
                # These will now print per-post, per-comind
                print(f"Core name: {core_name}")
                print(
                    f"Core perspective (first 100 chars): {core_perspective[:100]}..."
                )

                # Print the common prompts that are being loaded
                common_prompts = comind.load_common_prompts()
                print(f"Common prompts loaded: {list(common_prompts.keys())}")

                # Types dict - will be reset per-post, per-comind
                blip_types = {}

                context_dict = {
                    "content": post_content_prompt,
                    # comind.run() will use its own self.core_perspective and self.sphere_name
                }

                result = comind.run(context_dict)

                if isinstance(comind, Feeler):
                    for emotion in result["emotions"]:
                        etype = emotion["emotionType"]
                        if etype not in blip_types:
                            blip_types[etype] = 0
                        blip_types[etype] += 1
                elif isinstance(comind, Thinker):
                    for thought in result["thoughts"]:
                        ttype = thought["thoughtType"]
                        if ttype not in blip_types:
                            blip_types[ttype] = 0
                        blip_types[ttype] += 1
                elif isinstance(comind, Conceptualizer):
                    for concept in result["concepts"]:
                        ctype = concept["text"]
                        if ctype not in blip_types:
                            blip_types[ctype] = 0
                        blip_types[ctype] += 1

                # upload the result
                current_from_refs = [{"uri": post.uri, "cid": post.cid}]
                comind.upload(
                    result, record_manager, target=post_uri, from_refs=current_from_refs
                )

                # Print out the count of different concept types.
                # print(blip_types)

                # generated text (global accumulation)
                if (
                    isinstance(comind, Conceptualizer) and "concepts" in result
                ):  # Ensure result has concepts
                    for thing in result["concepts"]:
                        generated_strings.append(thing["text"])

                # Zeitgeist generation using globally accumulated generated_strings
                user_prompt_for_zeitgeist = (
                    "Here is a list of concepts occuring currently, with the most\n"
                    + "recent at the bottom. Give me the zeitgeist.\n"
                    + "\n".join(generated_strings)
                )

                model_statement = sg.generate_by_schema(
                    sg.messages(user_prompt_for_zeitgeist),
                    """
                    {
                        "type": "object",
                        "required": ["zeitgeist"],
                        "properties": {
                            "zeitgeist": {"type": "string"}
                        }
                    }
                    """,
                )
                new_txt = json.loads(model_statement.choices[0].message.content)
                print(Panel(new_txt["zeitgeist"]))

                time.sleep(60)  # Sleep after each comind processes a post

            except Exception as e:
                comind.logger.error(
                    f"Error processing post {post_uri} with comind {comind.name}: {e}"
                )
                print(
                    f"[red]Error processing post {post_uri} with comind {comind.name}:[/red] {e}"
                )
                if post:  # Ensure post object is available
                    print(f"Post content: {post_content_prompt}")
                # Continue to the next comind for the current post, or next post if this was the last comind.
                pass
