# Scrape all data
from tournament_scraper import CausewayScraperDriver

scraper = CausewayScraperDriver()
scraper.run_full_scrape(total_players=43, total_rounds=36)

# Analyze data
from tournament_analyzer import TournamentAnalyzer

analyzer = TournamentAnalyzer()

# Export everything
analyzer.export_to_excel("causeway_2026_analysis.xlsx")

# Get specific analysis
print(analyzer.top_performers(10))
print(analyzer.upset_detection())
