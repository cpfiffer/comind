import json
from datetime import datetime
import os
from typing import Optional
from atproto_client import Client
from src.record_manager import RecordManager
from src.lexicon_utils import add_link_property, generated_lexicon_of, multiple_of_schema
from src.comind.comind import Comind
from src.session_reuse import init_client

import dotenv

dotenv.load_dotenv()



if __name__ == "__main__":

    username = os.getenv("COMIND_BSKY_USERNAME")
    password = os.getenv("COMIND_BSKY_PASSWORD")

    atproto_client = init_client(
        username, password
    )

    conceptualizer = Conceptualizer()
    # print(json.dumps(conceptualizer.schema(), indent=2))
    result = conceptualizer.run({
        "content": "Hello, world!",
    })


    record_manager = RecordManager(atproto_client)

    print(result)
    conceptualizer.upload(result, record_manager)