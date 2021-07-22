import argparse
import asyncio
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from .config import Config

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

if sys.version_info[0] < 3 or sys.version_info[1] < 7:
    LOGGER.error("Python versions lower than 3.7 are not supported! Please update to at least python 3.6. Exiting!")
    quit(1)

if not sys.platform.startswith("linux"):
    LOGGER.error(f"Current platform {sys.platform} is not supported yet. Exiting!")
    quit(1)

PARSER = argparse.ArgumentParser()
PARSER.add_argument("-g", "--generate-config", action="store_true", help="Generate yaml configuration file!")
PARSER.add_argument("-c", "--config", help="Set a custom path for the yaml configuration file!")
ARGS = PARSER.parse_args()

CONFIG_FILE = ARGS.config or "config.yaml"

if not CONFIG_FILE.rsplit(".")[-1] == "yaml":
    if os.path.isdir(CONFIG_FILE):
        CONFIG_FILE = os.path.join(CONFIG_FILE, "config.yaml")
    else:
        CONFIG_FILE = CONFIG_FILE + ".yaml"

if not os.path.isfile(CONFIG_FILE) and not ARGS.generate_config:
    LOGGER.error(
        f"Unable to continue without a configuration file. Run 'python3 -m tl-radio --generate-config' then follow the instructions displayed in your console!")
    quit(0)

_config = Config(CONFIG_FILE)

if ARGS.generate_config:
    _config.generate()
    LOGGER.info(f"Generated configuration file: {CONFIG_FILE}!")
    quit(0)

CONFIG = _config.load()

LOOP = asyncio.get_event_loop()

THREAD_POOL = ThreadPoolExecutor(max_workers=None)

LOGGER.info("Syncing. This might take a while.")

for _file in os.listdir("./"):
    _ext = _file.rsplit(".")[-1]
    if _ext in ["raw", "part"]:
        os.remove(_file)


LAST_MSGS = []