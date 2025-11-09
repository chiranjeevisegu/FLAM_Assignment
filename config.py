import json
import os

CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "max_retries": 3,
    "backoff_base": 2,
    "poll_interval": 1,
    "timeout": 10
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)
