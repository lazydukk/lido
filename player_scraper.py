import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlayerScraper:
    """Scrape individual player profiles and save to CSV"""

    BASE_URL = "https://causeway-challenge.com/division-A/players"

    def __init__(self, output_dir: str = "causeway_2026_data/players"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        self.all_players_data = []  # Store all player summary data

    def scrape_player(self, player_id: int) -> Optional[Dict]:
        """
        Scrape a single player profile and save to CSV
        Returns the player summary dict if successful, None if failed
        """
        url = f"{self.BASE_URL}/player-{player_id}.html"
        logger.info(f"Scraping player {player_id}: {url}")

        soup = self._fetch_page(url)
        if not soup:
            return None

        # Extract player info
        player_name = self._extract_player_name(soup)
        if not player_name:
            logger.warning(f"Could not extract player name from {url}")
            return None

        # Sanitize filename
        safe_name = re.sub(r"[^\w\s-]", "", player_name).replace(" ", "_")
        csv_path = self.output_dir / f"{safe_name}.csv"

        # Extract header info (name, seed, rating, nationality, final standing)
        header_info = self._extract_header_info(soup)

        # Extract all games
        games = self._extract_games(soup)

        if not games:
            logger.warning(f"No games found for player {player_id}")
            return None

        # Create DataFrame
        df = pd.DataFrame(games)

        # Save to CSV
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved {len(df)} games for {player_name} to {csv_path}")

        # Log header info
        logger.info(f"Player: {header_info.get('name')}")
        logger.info(f"Seed: {header_info.get('seed')}")
        logger.info(f"Rating: {header_info.get('rating')}")
        logger.info(f"Nationality: {header_info.get('nationality')}")
        logger.info(
            f"Final Standing: {header_info.get('final_standing')} | {header_info.get('wins')}-{header_info.get('losses')}-{header_info.get('draws')} | {header_info.get('spread')}"
        )

        # Add to players summary list
        self.all_players_data.append(header_info)

        return header_info

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def _extract_player_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract player name from page"""
        # Look for h1 tag or main heading
        h1 = soup.find("h1")
        if h1:
            return h1.text.strip()

        # Alternative: check meta or title
        title = soup.find("title")
        if title:
            text = title.text.strip()
            # Extract name from title (e.g., "David Eldar - Causeway Challenge 2026")
            if " - " in text:
                return text.split(" - ")[0].strip()

        return None

    def _extract_header_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract header information: seed, rating, nationality, final standing"""
        info = {
            "name": "",
            "seed": "",
            "rating": "",
            "nationality": "",
            "final_standing": "",
            "wins": "",
            "losses": "",
            "draws": "",
            "spread": "",
        }

        # Get player name
        name = self._extract_player_name(soup)
        if name:
            info["name"] = name

        # Find the header section - usually contains seed, rating, nationality info
        # Get text from the top portion of the page before "Games" section
        header_section = soup.find(["section", "div"], class_=["profile", "player-header", "header"])
        if not header_section:
            # Fallback: get first significant text block
            header_section = soup

        header_text = header_section.get_text(separator=" ")

        # Extract seed
        seed_match = re.search(r"Seed\s*#?(\d+)", header_text, re.IGNORECASE)
        if seed_match:
            info["seed"] = seed_match.group(1)

        # Extract rating
        rating_match = re.search(r"Rating:\s*(\d+)", header_text, re.IGNORECASE)
        if rating_match:
            info["rating"] = rating_match.group(1)

        # Extract nationality (usually a 3-letter code after rating)
        nationality_match = re.search(r"Rating:\s*\d+\s*•?\s*([A-Z]{3})\b", header_text, re.IGNORECASE)
        if not nationality_match:
            # Alternative: just find any 3-letter code
            nationality_match = re.search(r"\b([A-Z]{3})\b", header_text)
        if nationality_match:
            info["nationality"] = nationality_match.group(1)

        # Find the final standing section (1st, 26-10-0, +1847)
        # Look for place (ordinal numbers)
        place_match = re.search(r"(\d+)(?:st|nd|rd|th)\s+(?:Place|place)", header_text, re.IGNORECASE)
        if place_match:
            place_num = place_match.group(1)
            place_map = {"1": "1st", "2": "2nd", "3": "3rd"}
            info["final_standing"] = place_map.get(place_num, f"{place_num}th")

        # Extract record (W-L-D format) - look for pattern like 26-10-0
        record_match = re.search(r"(\d+)-(\d+)-(\d+)", header_text)
        if record_match:
            info["wins"] = record_match.group(1)
            info["losses"] = record_match.group(2)
            info["draws"] = record_match.group(3)

        # Extract spread - look for spread values (2+ digits to catch edge cases)
        # First try 4+ digits (most common: +1847, +1500, -1200)
        # Then try 3+ digits (less common: +123, -456)
        # Then try 2+ digits (edge case: +10, -99)
        # But prioritize the one closest to record/standing info to avoid game spreads
        spread_match = re.search(r"([\+\-]\d{2,})", header_text)
        if spread_match:
            # Get all matches and take the first large one (most likely tournament spread)
            # or the one with 3+ digits if available
            all_spreads = re.findall(r"([\+\-]\d{2,})", header_text)
            
            # Prioritize spreads with 3+ digits
            large_spreads = [s for s in all_spreads if len(s) > 3]  # +/- plus 3+ digits
            if large_spreads:
                info["spread"] = large_spreads[0]
            elif all_spreads:
                # If no large spreads, use the first one found (likely nearest to standing info)
                info["spread"] = all_spreads[0]

        return info

    def _extract_games(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract all games from the player profile"""
        games = []

        # Find all game rows
        # Look for table rows or divs containing game data
        rows = soup.find_all(["tr", "div"], class_=["game", "match", "row"])

        # If no structured rows, try to find all with game-like content
        if not rows:
            # Try finding by looking for round numbers (R1, R2, etc.)
            text_content = soup.get_text()
            # Look for any div or section that might contain games
            rows = soup.find_all(["div", "tr"])

        for row in rows:
            game_data = self._parse_game_row(row)
            if game_data:
                games.append(game_data)

        return games

    def _parse_game_row(self, row) -> Optional[Dict]:
        """Parse a single game row"""
        try:
            row_text = row.get_text(separator=" ").strip()

            # Extract round number (R1, R2, etc.)
            round_match = re.search(r"R(\d+)", row_text)
            if not round_match:
                return None

            round_num = round_match.group(1)

            # Extract W/L
            result = None
            if "W" in row_text[:50]:
                result = "W"
            elif "L" in row_text[:50]:
                result = "L"
            else:
                return None

            # Extract opponent name (usually after W/L)
            opponent_match = re.search(
                r"[WL]\s+(\w+(?:\s+\w+)*?)\s+(?:[A-Z]{3}|BYE)", row_text
            )
            opponent = opponent_match.group(1).strip() if opponent_match else "Unknown"

            # Extract scores (e.g., "475-434")
            score_match = re.search(r"(\d+)\s*-\s*(\d+)", row_text)
            if score_match:
                player_score = int(score_match.group(1))
                opponent_score = int(score_match.group(2))
                # Calculate spread as the difference (positive for wins, negative for losses)
                spread = player_score - opponent_score
            else:
                player_score = ""
                opponent_score = ""
                spread = ""

            # Extract YouTube link
            youtube_link = ""
            youtube_elem = row.find("a", href=re.compile(r"youtube|youtu\.be"))
            if youtube_elem and youtube_elem.get("href"):
                youtube_link = youtube_elem["href"]

            # Extract Woogles annotation link
            woogles_link = ""
            woogles_elem = row.find("a", href=re.compile(r"woogles"))
            if woogles_elem and woogles_elem.get("href"):
                woogles_link = woogles_elem["href"]

            return {
                "round": round_num,
                "result": result,
                "opponent": opponent,
                "player_score": player_score,
                "opponent_score": opponent_score,
                "spread": spread,
                "youtube_link": youtube_link,
                "woogles_annotation": woogles_link,
            }

        except Exception as e:
            logger.debug(f"Error parsing game row: {e}")
            return None

    def scrape_multiple_players(self, player_ids: List[int]) -> Dict[int, str]:
        """Scrape multiple players and return mapping of player_id -> player_name"""
        results = {}
        for player_id in player_ids:
            player_info = self.scrape_player(player_id)
            if player_info:
                results[player_id] = player_info["name"]

        return results

    def scrape_all_players(self, total_players: int = 43) -> Dict[int, str]:
        """Scrape all players by ID"""
        logger.info(f"Starting to scrape {total_players} players...")
        self.all_players_data = []  # Reset
        results = self.scrape_multiple_players(range(1, total_players + 1))
        logger.info(f"Completed scraping {len(results)}/{total_players} players")

        return results

    def export_all_players_summary(
        self, filename: str = "all_players_summary.csv"
    ) -> Path:
        """
        Export all scraped player summary data to a single CSV file
        Sorted by: wins (desc) > draws (desc) > spread (desc)

        Columns: seed | name | nationality | rating | final_standing | wins | losses | draws | spread
        """
        if not self.all_players_data:
            logger.warning("No player data to export. Run scrape_all_players() first.")
            return None

        # Create DataFrame
        df = pd.DataFrame(self.all_players_data)

        # Convert numeric columns for proper sorting
        df["wins"] = pd.to_numeric(df["wins"], errors="coerce").fillna(0).astype(int)
        df["losses"] = pd.to_numeric(df["losses"], errors="coerce").fillna(0).astype(int)
        df["draws"] = pd.to_numeric(df["draws"], errors="coerce").fillna(0).astype(int)
        df["spread"] = pd.to_numeric(df["spread"], errors="coerce").fillna(0).astype(int)

        # Sort by: wins (desc) > draws (desc) > spread (desc)
        df = df.sort_values(
            by=["wins", "draws", "spread"],
            ascending=[False, False, False]
        )

        # Reorder columns
        columns_order = [
            "seed",
            "name",
            "nationality",
            "rating",
            "final_standing",
            "wins",
            "losses",
            "draws",
            "spread",
        ]
        df = df[columns_order]

        # Save to CSV in parent directory
        csv_path = self.output_dir.parent / filename
        df.to_csv(csv_path, index=False)
        logger.info(f"Exported {len(df)} players to {csv_path} (sorted by wins > draws > spread)")

        return csv_path


# ============ USAGE ============
if __name__ == "__main__":
    scraper = PlayerScraper()

    # Scrape a single player
    # scraper.scrape_player(2)

    # Scrape multiple specific players
    # scraper.scrape_multiple_players([1, 2, 3, 4, 5])

    # Scrape all players
    scraper.scrape_all_players(total_players=43)

    # Export summary of all players
    scraper.export_all_players_summary()
