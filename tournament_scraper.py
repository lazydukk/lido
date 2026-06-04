import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CausewayScraperDriver:
    """Main scraper for Causeway 2026 tournament data"""
    
    BASE_URL = "https://www.causeway-challenge.com/division-A"
    TSH_URL = "https://bkkcrossword.com/tsh/Causeway2026/p/index.html"
    
    def __init__(self, output_dir: str = "tournament_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    # ============ DIVISION STANDINGS ============
    def scrape_division_standings(self) -> pd.DataFrame:
        """Scrape overall division standings"""
        url = f"{self.BASE_URL}/index.html"
        soup = self.fetch_page(url)
        if not soup:
            return pd.DataFrame()
        
        standings_data = []
        
        # Adjust selector based on actual HTML structure
        table = soup.find('table', {'class': 'standings'})
        if not table:
            table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    standings_data.append({
                        'rank': cells[0].text.strip(),
                        'player_name': cells[1].text.strip(),
                        'wins': cells[2].text.strip(),
                        'spread': cells[3].text.strip(),
                        'player_id': self._extract_player_id(row)
                    })
        
        df = pd.DataFrame(standings_data)
        df.to_csv(self.output_dir / "division_standings.csv", index=False)
        logger.info(f"Scraped {len(df)} players from division standings")
        return df
    
    # ============ ROUND PAIRINGS ============
    def scrape_all_round_pairings(self, total_rounds: int = 36) -> pd.DataFrame:
        """Scrape pairings for all rounds"""
        all_pairings = []
        
        for round_num in range(1, total_rounds + 1):
            url = f"{self.BASE_URL}/pairings/pairings-round-{round_num}.html"
            pairings = self.scrape_round_pairings(round_num, url)
            all_pairings.extend(pairings)
            logger.info(f"Scraped round {round_num}")
        
        df = pd.DataFrame(all_pairings)
        df.to_csv(self.output_dir / "all_round_pairings.csv", index=False)
        return df
    
    def scrape_round_pairings(self, round_num: int, url: str) -> List[Dict]:
        """Scrape pairings for a specific round"""
        soup = self.fetch_page(url)
        if not soup:
            return []
        
        pairings = []
        table = soup.find('table', {'class': 'pairings'}) or soup.find('table')
        
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    pairings.append({
                        'round': round_num,
                        'table_number': cells[0].text.strip(),
                        'player_1': cells[1].text.strip(),
                        'player_1_score': cells[2].text.strip(),
                        'player_2': cells[3].text.strip(),
                        'player_2_score': cells[4].text.strip() if len(cells) > 4 else None,
                    })
        
        return pairings
    
    # ============ INDIVIDUAL PLAYER DATA ============
    def scrape_all_players(self, total_players: int = 43) -> pd.DataFrame:
        """Iterate through all player IDs and scrape their data"""
        all_players = []
        
        for player_id in range(1, total_players + 1):
            player_data = self.scrape_player_profile(player_id)
            if player_data:
                all_players.append(player_data)
            logger.info(f"Scraped player {player_id}/{total_players}")
        
        df = pd.DataFrame(all_players)
        df.to_csv(self.output_dir / "player_profiles.csv", index=False)
        return df
    
    def scrape_player_profile(self, player_id: int) -> Optional[Dict]:
        """Scrape individual player profile and match history"""
        url = f"{self.BASE_URL}/players/player-{player_id}.html"
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        player_data = {'player_id': player_id}
        
        # Extract player name and basic info
        name_elem = soup.find('h1') or soup.find('h2')
        if name_elem:
            player_data['name'] = name_elem.text.strip()
        
        # Extract overall stats
        stats_section = soup.find('div', {'class': 'stats'}) or soup.find('div', {'class': 'profile'})
        if stats_section:
            player_data['wins'] = self._extract_stat(stats_section, 'wins')
            player_data['losses'] = self._extract_stat(stats_section, 'losses')
            player_data['spread'] = self._extract_stat(stats_section, 'spread')
        
        # Extract round-by-round match history
        match_history = self._extract_match_history(soup, player_id)
        player_data['match_history'] = match_history
        
        return player_data
    
    def _extract_match_history(self, soup: BeautifulSoup, player_id: int) -> List[Dict]:
        """Extract all matches for a player"""
        matches = []
        
        table = soup.find('table', {'class': 'matches'}) or soup.find('table')
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    matches.append({
                        'player_id': player_id,
                        'round': cells[0].text.strip(),
                        'opponent': cells[1].text.strip(),
                        'score': cells[2].text.strip(),
                        'opponent_score': cells[3].text.strip() if len(cells) > 3 else None,
                        'result': 'W' if int(cells[2].text.strip().split()[0]) > int(cells[3].text.strip().split()[0] if len(cells) > 3 else 0) else 'L'
                    })
        
        return matches
    
    # ============ TSH STANDINGS ============
    def scrape_tsh_standings(self) -> pd.DataFrame:
        """Scrape TSH-generated standings from bkkcrossword.com"""
        soup = self.fetch_page(self.TSH_URL)
        if not soup:
            return pd.DataFrame()
        
        tsh_data = []
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    tsh_data.append({
                        'rank': cells[0].text.strip(),
                        'player_name': cells[1].text.strip(),
                        'rating': cells[2].text.strip(),
                        'wins': cells[3].text.strip(),
                        'spread': cells[4].text.strip() if len(cells) > 4 else None,
                    })
        
        df = pd.DataFrame(tsh_data)
        df.to_csv(self.output_dir / "tsh_standings.csv", index=False)
        return df
    
    # ============ HELPER METHODS ============
    def _extract_player_id(self, row) -> Optional[int]:
        """Extract player ID from a table row"""
        link = row.find('a', href=True)
        if link and 'player-' in link['href']:
            player_id = link['href'].split('player-')[1].split('.')[0]
            return int(player_id)
        return None
    
    def _extract_stat(self, element, stat_name: str) -> Optional[str]:
        """Extract a specific stat from an element"""
        text = element.get_text().lower()
        for line in text.split('\n'):
            if stat_name.lower() in line:
                return line.split(':')[-1].strip()
        return None
    
    def run_full_scrape(self, total_players: int = 43, total_rounds: int = 36):
        """Run complete scraping workflow"""
        logger.info("Starting full tournament scrape...")
        
        logger.info("1. Scraping division standings...")
        self.scrape_division_standings()
        
        logger.info("2. Scraping all round pairings...")
        self.scrape_all_round_pairings(total_rounds)
        
        logger.info("3. Scraping individual player profiles...")
        self.scrape_all_players(total_players)
        
        logger.info("4. Scraping TSH standings...")
        self.scrape_tsh_standings()
        
        logger.info(f"Scraping complete! Data saved to {self.output_dir}")


# ============ USAGE ============
if __name__ == "__main__":
    scraper = CausewayScraperDriver(output_dir="causeway_2026_data")
    
    # Scrape everything
    scraper.run_full_scrape(total_players=43, total_rounds=36)
    
    # Or run individual scrapers:
    # standings = scraper.scrape_division_standings()
    # pairings = scraper.scrape_all_round_pairings(total_rounds=36)
    # players = scraper.scrape_all_players(total_players=43)
