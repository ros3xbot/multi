import os
import json
import requests
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOT_DATA_DIR = os.path.join(BASE_DIR, "hot_data")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_api_key() -> str:
    """Load API key from file."""
    api_path = os.path.join(BASE_DIR, "api.key")
    if os.path.exists(api_path):
        with open(api_path, "r", encoding="utf8") as f:
            api_key = f.read().strip()
        if api_key:
            logging.info("API key loaded successfully.")
            return api_key
        logging.warning("API key file is empty.")
        return ""
    logging.error("API key file not found.")
    return ""


def save_api_key(api_key: str):
    """Save API key to file."""
    api_path = os.path.join(BASE_DIR, "api.key")
    with open(api_path, "w", encoding="utf8") as f:
        f.write(api_key)
    logging.info("API key saved successfully.")


def delete_api_key():
    """Delete API key file if exists."""
    api_path = os.path.join(BASE_DIR, "api.key")
    if os.path.exists(api_path):
        os.remove(api_path)
        logging.info("API key file deleted.")
    else:
        logging.warning("API key file does not exist.")


def verify_api_key(api_key: str, *, timeout: float = 10.0) -> bool:
    """Verify API key against server (placeholder)."""
    # TODO: implement actual verification request
    return bool(api_key)


def ensure_api_key() -> str:
    """Ensure API key is available (fallback)."""
    return "Noir1"


def merge_hot1(api_url: str, prefer_server: bool = True):
    """Merge local hot.json with server data."""
    local_file = os.path.join(HOT_DATA_DIR, "hot.json")
    merged = {}

    # Load local data
    try:
        with open(local_file, "r", encoding="utf-8") as f:
            local_data = json.load(f)
            if not isinstance(local_data, list):
                local_data = []
            for pkg in local_data:
                key = (pkg.get("family_code"), pkg.get("order"), pkg.get("variant_name"))
                pkg["source"] = "local"
                merged[key] = pkg
    except FileNotFoundError:
        logging.info("Local hot.json not found.")
    except json.JSONDecodeError:
        logging.warning("Invalid JSON in hot.json.")

    # Load server data
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            api_data = response.json()
            for pkg in api_data:
                key = (pkg.get("family_code"), pkg.get("order"), pkg.get("variant_name"))
                pkg["source"] = "server"
                if prefer_server or key not in merged:
                    merged[key] = pkg
        else:
            logging.error("Failed to fetch hot1 data from server.")
    except requests.RequestException as e:
        logging.error(f"Error fetching hot1 data: {e}")

    return list(merged.values())


def merge_hot2(api_url: str, prefer_server: bool = True):
    """Merge local hot2.json with server data."""
    local_file = os.path.join(HOT_DATA_DIR, "hot2.json")
    merged = {}

    # Load local data
    try:
        with open(local_file, "r", encoding="utf-8") as f:
            local_data = json.load(f)
            if not isinstance(local_data, list):
                local_data = []
            for pkg in local_data:
                key = (pkg.get("name"), pkg.get("price"), pkg.get("order"))
                pkg["source"] = "local"
                merged[key] = pkg
    except FileNotFoundError:
        logging.info("Local hot2.json not found.")
    except json.JSONDecodeError:
        logging.warning("Invalid JSON in hot2.json.")

    # Load server data
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            api_data = response.json()
            for pkg in api_data:
                key = (pkg.get("name"), pkg.get("price"), pkg.get("order"))
                pkg["source"] = "server"
                if prefer_server or key not in merged:
                    merged[key] = pkg
        else:
            logging.error("Failed to fetch hot2 data from server.")
    except requests.RequestException as e:
        logging.error(f"Error fetching hot2 data: {e}")

    return list(merged.values())
