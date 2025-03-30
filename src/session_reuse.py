import os
import logging
from typing import Optional
from atproto_client import Client, Session, SessionEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("session_reuse")

# Load the environment variables
import dotenv
dotenv.load_dotenv(override=True)

def get_session(username: str) -> Optional[str]:
    try:
        with open(f'session_{username}.txt', encoding='UTF-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.debug(f"No existing session found for {username}")
        return None

def save_session(username: str, session_string: str) -> None:
    with open(f'session_{username}.txt', 'w', encoding='UTF-8') as f:
        f.write(session_string)
    logger.debug(f"Session saved for {username}")


def on_session_change(username: str, event: SessionEvent, session: Session) -> None:
    logger.info(f'Session changed: {event} {repr(session)}')
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        logger.info(f'Saving changed session for {username}')
        save_session(username, session.export())


def init_client(username: str, password: str) -> Client:
    client = Client()
    client.on_session_change(lambda event, session: on_session_change(username, event, session))

    session_string = get_session(username)
    if session_string:
        logger.info(f'Reusing existing session for {username}')
        client.login(session_string=session_string)
    else:
        logger.info(f'Creating new session for {username}')
        client.login(username, password)

    return client


if __name__ == '__main__':
    username = os.getenv("COMIND_BSKY_USERNAME")
    password = os.getenv("COMIND_BSKY_PASSWORD")

    if username is None:
        logger.error("No username provided. Please provide a username using the COMIND_BSKY_USERNAME environment variable.")
        exit()

    if password is None:
        logger.error("No password provided. Please provide a password using the COMIND_BSKY_PASSWORD environment variable.")
        exit()

    client = init_client(username, password)
    # do something with the client
    logger.info('Client is ready to use!')