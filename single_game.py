import os

import requests
from dotenv import load_dotenv

# Load the variables from the .env file into the environment
load_dotenv()


def get_gcg_data(game_id):
    url = "https://woogles.io/api/game_service.GameMetadataService/GetGCG"

    api_key = os.getenv("WOOGLES_API_KEY")
    headers = {"Content-Type": "application/json"}

    if api_key:
        headers["X-Api-Key"] = api_key
    else:
        print("Warning: WOOGLES_API_KEY not found in environment variables.")

    payload = {"game_id": game_id}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error fetching game {game_id}: {response.status_code} - {response.text}"
        )
        return None


if __name__ == "__main__":
    # Prompt the user for input in the terminal
    user_input = input("Enter Woogles Game ID(s) (separate multiple IDs with commas): ")

    # Split the input by commas and strip out any accidental whitespace
    game_ids = [g.strip() for g in user_input.split(",") if g.strip()]

    if not game_ids:
        print("No valid game IDs entered. Exiting.")
    else:
        print(f"Processing {len(game_ids)} game(s)...")
        for game_id in game_ids:
            print(f"Fetching game: {game_id}")
            data = get_gcg_data(game_id)

            if data and "gcg" in data:
                filename = f"{game_id}.gcg"
                with open(filename, "w") as file:
                    file.write(data["gcg"])
                print(f"Saved successfully as {filename}")
