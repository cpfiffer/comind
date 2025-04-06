# Code to manage cominds and prompts

import os
import re
import json
import src.structured_gen as sg
from pydantic import BaseModel
from src.lexicon_utils import lexicon_of, multiple_of_schema

PROMPT_DIR = "prompts/cominds"
COMMON_PROMPT_DIR = "prompts/common"

class Comind(BaseModel):
    name: str
    prompt_path: str
    common_prompt_dir: str

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
        common_prompts = self.load_common_prompts()

        # Merge common prompts into context_dict
        for common_prompt in common_prompts:
            if common_prompt in context_dict:
                print(f"Warning: Common prompt {common_prompt} already in context_dict. Common prompt names are reserved and should not be overridden.")
            context_dict[common_prompt] = common_prompts[common_prompt]

        # Format prompt
        prompt = prompt.format(**context_dict)
        return prompt
    
    def split_prompts(self, context_dict: dict):
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

        if not schema:
            # Check if we have one in the prompts dict. Must be 
            # nonzero length and valid JSON.
            if "schema" in prompts:
                try:
                    json.loads(prompts["schema"])
                    schema = prompts["schema"]
                except json.JSONDecodeError:
                    raise ValueError("Schema is not valid JSON.")
            else:
                raise ValueError("Schema is required.")

        return sg.generate_by_schema(messages, schema)

if __name__ == "__main__":
    # Test the Comind class
    comind = Comind(
        common_prompt_dir="prompts/common/",
        name="conceptualizer",
        prompt_path="prompts/cominds/conceptualizer.co",
    )
    print(comind.load_prompt())
    print(comind.load_common_prompts())

    context_dict = {
        "content": "Hello, world!"
    }
    print(comind.to_prompt(context_dict))
    print(comind.run(context_dict, multiple_of_schema("concepts", lexicon_of("me.comind.blip.concept"))))