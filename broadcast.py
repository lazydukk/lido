import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()


def get_name(name):
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()}_{last.strip()}"
    return name.strip()


def format_filename(game_stat):
    """Formats: round_number_player01_name-v-player02_name_uuid.gcg"""
    rnd = game_stat.get("round", 0)
    p1 = get_name(game_stat.get("player1_name", "P1"))
    p2 = get_name(game_stat.get("player2_name", "P2"))
    uuid = game_stat.get("game_uuid", "unknown")

    # Clean names to ensure they are filesystem-safe
    p1 = re.sub(r"[^\w]", "", p1)
    p2 = re.sub(r"[^\w]", "", p2)

    return f"{rnd}.{p1}-V-{p2}_[{uuid}].gcg"


def get_broadcast_games(slug):
    """Fetches list of games for a given broadcast slug."""
    url = (
        "https://woogles.io/api/broadcast_service.BroadcastService/GetBroadcastAllGames"
    )
    payload = {"slug": slug}
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        return response.json().get("stats", [])
    else:
        print(f"Error fetching broadcast: {response.status_code} - {response.text}")
        return []


def get_gcg_data(game_uuid):
    """Fetches GCG content for a specific game UUID."""
    url = "https://woogles.io/api/game_service.GameMetadataService/GetGCG"
    api_key = os.getenv("WOOGLES_API_KEY")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    payload = {"game_id": game_uuid}
    response = requests.post(url, headers=headers, json=payload)

    return response.json().get("gcg") if response.status_code == 200 else None


if __name__ == "__main__":
    user_input = input("Enter the Woogles Broadcast URL: ").strip()
    match = re.search(r"broadcasts/([a-zA-Z0-9-]+)", user_input)

    if not match:
        print("Could not extract slug from URL.")
    else:
        slug = match.group(1)
        os.makedirs(slug, exist_ok=True)
        print(f"Fetching games for broadcast: {slug}")

        games = get_broadcast_games(slug)

        for game in games:
            uuid = game.get("game_uuid")
            if not uuid:
                continue

            filename = format_filename(game)
            filepath = os.path.join(slug, filename)
            if os.path.exists(filepath):
                print(f"Skipping: {filename} (already exists)")
                continue

            print(f"Downloading: {filename}")

            gcg_content = get_gcg_data(uuid)

            if gcg_content:
                with open(os.path.join(slug, filename), "w") as f:
                    f.write(gcg_content)

            time.sleep(0.1)

        print("Done.")
