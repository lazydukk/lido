import os
import requests
from dotenv import load_dotenv

# Load the variables from the .env file into the environment
load_dotenv()

def get_gcg_data(game_id):
    url = "https://woogles.io/api/game_service.GameMetadataService/GetGCG"
    
    # Retrieve the API key
    api_key = os.getenv("WOOGLES_API_KEY")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Inject the API key into the headers if it was successfully loaded
    if api_key:
        headers["X-Api-Key"] = api_key
    else:
        print("Warning: WOOGLES_API_KEY not found in environment variables.")

    payload = {
        "game_id": game_id
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching game {game_id}: {response.status_code} - {response.text}")
        return None

# Example usage:
# data = get_gcg_data("exampleGameID")