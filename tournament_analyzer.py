import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TournamentAnalyzer:
    """Advanced data analysis and pivot table generation for Causeway 2026 tournament"""
    
    def __init__(self, data_dir: str = "causeway_2026_data"):
        self.data_dir = Path(data_dir)
        self.output_dir = self.data_dir / "analysis"
        self.output_dir.mkdir(exist_ok=True)
        
        # Load all data
        self.standings = self._load_data("division_standings.csv")
        self.pairings = self._load_data("all_round_pairings.csv")
        self.players = self._load_data("player_profiles.csv")
        self.tsh_standings = self._load_data("tsh_standings.csv")
    
    def _load_data(self, filename: str) -> pd.DataFrame:
        """Load CSV data with error handling"""
        filepath = self.data_dir / filename
        try:
            if filepath.exists():
                return pd.read_csv(filepath)
            else:
                logger.warning(f"File not found: {filename}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return pd.DataFrame()
    
    # ============ PLAYER ANALYSIS ============
    
    def player_win_loss_by_round(self, player_id: int) -> pd.DataFrame:
        """Get win/loss record for a specific player by round"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        # Find player in pairings
        player_matches = self.pairings[
            (self.pairings['player_1_id'] == player_id) | 
            (self.pairings['player_2_id'] == player_id)
        ].copy()
        
        player_matches['result'] = player_matches.apply(
            lambda row: self._determine_result(row, player_id), axis=1
        )
        
        analysis = player_matches.groupby('round').agg({
            'result': 'count',
            'player_1_score': 'sum'
        }).rename(columns={'result': 'games_played'})
        
        return analysis
    
    def player_head_to_head(self, player_1_id: int, player_2_id: int) -> Dict:
        """Get head-to-head statistics between two players"""
        if self.pairings.empty:
            return {}
        
        matches = self.pairings[
            ((self.pairings['player_1_id'] == player_1_id) & 
             (self.pairings['player_2_id'] == player_2_id)) |
            ((self.pairings['player_1_id'] == player_2_id) & 
             (self.pairings['player_2_id'] == player_1_id))
        ]
        
        p1_wins = len(matches[self._get_winner(matches) == player_1_id])
        p2_wins = len(matches) - p1_wins
        
        return {
            'player_1_id': player_1_id,
            'player_2_id': player_2_id,
            'total_matches': len(matches),
            'player_1_wins': p1_wins,
            'player_2_wins': p2_wins,
            'matches': matches.to_dict('records')
        }
    
    def player_performance_by_opponent_rank(self) -> pd.DataFrame:
        """Calculate performance against opponents at different ranking tiers"""
        if self.pairings.empty or self.standings.empty:
            return pd.DataFrame()
        
        # Add rankings to pairings
        pairings_ranked = self.pairings.merge(
            self.standings[['player_id', 'rank']],
            left_on='player_1_id',
            right_on='player_id',
            how='left'
        ).rename(columns={'rank': 'player_1_rank'})
        
        pairings_ranked = pairings_ranked.merge(
            self.standings[['player_id', 'rank']],
            left_on='player_2_id',
            right_on='player_id',
            how='left'
        ).rename(columns={'rank': 'player_2_rank'})
        
        # Categorize opponent strength
        pairings_ranked['opponent_tier'] = pd.cut(
            pairings_ranked['player_2_rank'],
            bins=[0, 10, 25, 43],
            labels=['Top 10', 'Mid 15', 'Bottom 18']
        )
        
        performance = pairings_ranked.groupby('opponent_tier').agg({
            'player_1_score': ['mean', 'std', 'count'],
            'spread': 'mean'
        }).round(2)
        
        return performance
    
    # ============ ROUND ANALYSIS ============
    
    def round_summary(self, round_num: int) -> pd.DataFrame:
        """Get summary statistics for a specific round"""
        round_data = self.pairings[self.pairings['round'] == round_num].copy()
        
        if round_data.empty:
            return pd.DataFrame()
        
        summary = pd.DataFrame({
            'round': [round_num],
            'total_games': [len(round_data)],
            'avg_winning_score': [round_data['player_1_score'].mean()],
            'avg_losing_score': [round_data['player_2_score'].mean()],
            'avg_spread': [round_data['spread'].mean()],
            'highest_score': [max(round_data['player_1_score'].max(), round_data['player_2_score'].max())],
            'lowest_score': [min(round_data['player_1_score'].min(), round_data['player_2_score'].min())]
        })
        
        return summary
    
    def all_rounds_summary(self) -> pd.DataFrame:
        """Get summary statistics for all rounds"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        summaries = []
        for round_num in sorted(self.pairings['round'].unique()):
            summaries.append(self.round_summary(round_num))
        
        return pd.concat(summaries, ignore_index=True)
    
    def round_momentum_analysis(self) -> pd.DataFrame:
        """Track each player's performance trend across rounds"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        momentum_data = []
        
        for round_num in sorted(self.pairings['round'].unique()):
            round_games = self.pairings[self.pairings['round'] == round_num]
            
            for _, game in round_games.iterrows():
                momentum_data.append({
                    'round': round_num,
                    'player_id': game['player_1_id'],
                    'score': game['player_1_score'],
                    'opponent_id': game['player_2_id'],
                    'opponent_score': game['player_2_score'],
                    'result': 'W' if game['player_1_score'] > game['player_2_score'] else 'L',
                    'margin': abs(game['player_1_score'] - game['player_2_score'])
                })
                
                momentum_data.append({
                    'round': round_num,
                    'player_id': game['player_2_id'],
                    'score': game['player_2_score'],
                    'opponent_id': game['player_1_id'],
                    'opponent_score': game['player_1_score'],
                    'result': 'W' if game['player_2_score'] > game['player_1_score'] else 'L',
                    'margin': abs(game['player_2_score'] - game['player_1_score'])
                })
        
        momentum_df = pd.DataFrame(momentum_data)
        return momentum_df
    
    # ============ PIVOT TABLES ============
    
    def player_vs_player_wins_matrix(self) -> pd.DataFrame:
        """Create matrix showing wins between each pair of players"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        # Get unique players
        players_list = sorted(set(
            list(self.pairings['player_1_id'].unique()) + 
            list(self.pairings['player_2_id'].unique())
        ))
        
        # Create empty matrix
        matrix = pd.DataFrame(0, index=players_list, columns=players_list)
        
        # Fill matrix with wins
        for _, game in self.pairings.iterrows():
            p1 = game['player_1_id']
            p2 = game['player_2_id']
            
            if game['player_1_score'] > game['player_2_score']:
                matrix.loc[p1, p2] += 1
            else:
                matrix.loc[p2, p1] += 1
        
        return matrix
    
    def win_loss_by_round_pivot(self) -> pd.DataFrame:
        """Pivot table: Players x Rounds with W/L results"""
        momentum = self.round_momentum_analysis()
        
        if momentum.empty:
            return pd.DataFrame()
        
        pivot = pd.pivot_table(
            momentum,
            values='result',
            index='player_id',
            columns='round',
            aggfunc='count',
            fill_value=0
        )
        
        return pivot
    
    def score_distribution_by_round(self) -> pd.DataFrame:
        """Score statistics by round for all players"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        momentum = self.round_momentum_analysis()
        
        pivot = pd.pivot_table(
            momentum,
            values='score',
            index='player_id',
            columns='round',
            aggfunc='mean'
        ).round(1)
        
        return pivot
    
    def spread_by_player_round(self) -> pd.DataFrame:
        """Pivot table: Average spread margin by player and round"""
        if self.pairings.empty:
            return pd.DataFrame()
        
        momentum = self.round_momentum_analysis()
        
        pivot = pd.pivot_table(
            momentum,
            values='margin',
            index='player_id',
            columns='round',
            aggfunc='mean'
        ).round(1)
        
        return pivot
    
    # ============ COMPARATIVE ANALYSIS ============
    
    def top_performers(self, n: int = 10) -> pd.DataFrame:
        """Get top N performers with detailed stats"""
        if self.standings.empty:
            return pd.DataFrame()
        
        momentum = self.round_momentum_analysis()
        
        # Calculate win rate per player
        player_stats = []
        for player_id in momentum['player_id'].unique():
            player_games = momentum[momentum['player_id'] == player_id]
            wins = len(player_games[player_games['result'] == 'W'])
            games = len(player_games)
            win_rate = wins / games if games > 0 else 0
            avg_margin = player_games['margin'].mean()
            avg_score = player_games['score'].mean()
            
            player_stats.append({
                'player_id': player_id,
                'games': games,
                'wins': wins,
                'losses': games - wins,
                'win_rate': round(win_rate * 100, 2),
                'avg_margin': round(avg_margin, 2),
                'avg_score': round(avg_score, 2)
            })
        
        df = pd.DataFrame(player_stats).sort_values('win_rate', ascending=False)
        return df.head(n)
    
    def consistency_analysis(self) -> pd.DataFrame:
        """Measure consistency: standard deviation of scores per player"""
        momentum = self.round_momentum_analysis()
        
        if momentum.empty:
            return pd.DataFrame()
        
        consistency = momentum.groupby('player_id').agg({
            'score': ['mean', 'std', 'min', 'max'],
            'margin': 'mean'
        }).round(2)
        
        consistency.columns = ['avg_score', 'score_std', 'min_score', 'max_score', 'avg_margin']
        consistency = consistency.sort_values('score_std')
        
        return consistency
    
    def upset_detection(self, threshold_percentile: int = 75) -> pd.DataFrame:
        """Identify games where lower-ranked player beat higher-ranked player"""
        if self.pairings.empty or self.standings.empty:
            return pd.DataFrame()
        
        pairings_ranked = self.pairings.merge(
            self.standings[['player_id', 'rank']],
            left_on='player_1_id',
            right_on='player_id'
        ).rename(columns={'rank': 'p1_rank'}).drop('player_id', axis=1)
        
        pairings_ranked = pairings_ranked.merge(
            self.standings[['player_id', 'rank']],
            left_on='player_2_id',
            right_on='player_id'
        ).rename(columns={'rank': 'p2_rank'}).drop('player_id', axis=1)
        
        # Identify upsets
        upsets = []
        for _, game in pairings_ranked.iterrows():
            if game['p1_rank'] > game['p2_rank'] and game['player_1_score'] > game['player_2_score']:
                upsets.append({
                    'round': game['round'],
                    'underdog_id': game['player_1_id'],
                    'underdog_rank': game['p1_rank'],
                    'favorite_id': game['player_2_id'],
                    'favorite_rank': game['p2_rank'],
                    'upset_score': f"{game['player_1_score']} - {game['player_2_score']}"
                })
            elif game['p2_rank'] > game['p1_rank'] and game['player_2_score'] > game['player_1_score']:
                upsets.append({
                    'round': game['round'],
                    'underdog_id': game['player_2_id'],
                    'underdog_rank': game['p2_rank'],
                    'favorite_id': game['player_1_id'],
                    'favorite_rank': game['p1_rank'],
                    'upset_score': f"{game['player_2_score']} - {game['player_1_score']}"
                })
        
        return pd.DataFrame(upsets)
    
    # ============ EXPORT UTILITIES ============
    
    def export_to_excel(self, filename: str = "tournament_analysis.xlsx"):
        """Export all analyses to Excel with multiple sheets"""
        excel_path = self.output_dir / filename
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Raw data
            self.standings.to_excel(writer, sheet_name='Standings', index=False)
            self.all_rounds_summary().to_excel(writer, sheet_name='Rounds Summary', index=False)
            
            # Pivot tables
            self.player_vs_player_wins_matrix().to_excel(writer, sheet_name='H2H Wins Matrix')
            self.win_loss_by_round_pivot().to_excel(writer, sheet_name='W/L by Round')
            self.score_distribution_by_round().to_excel(writer, sheet_name='Avg Score by Round')
            self.spread_by_player_round().to_excel(writer, sheet_name='Margin by Round')
            
            # Analysis
            self.top_performers().to_excel(writer, sheet_name='Top Performers', index=False)
            self.consistency_analysis().to_excel(writer, sheet_name='Consistency')
            self.upset_detection().to_excel(writer, sheet_name='Upsets', index=False)
            self.round_momentum_analysis().to_excel(writer, sheet_name='Momentum', index=False)
        
        logger.info(f"Analysis exported to {excel_path}")
        return excel_path
    
    def export_player_report(self, player_id: int, filename: Optional[str] = None) -> Path:
        """Export detailed report for a specific player"""
        if filename is None:
            filename = f"player_{player_id}_report.xlsx"
        
        excel_path = self.output_dir / filename
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            self.player_win_loss_by_round(player_id).to_excel(
                writer, sheet_name='Round Stats'
            )
            self.consistency_analysis().to_excel(writer, sheet_name='Consistency')
        
        logger.info(f"Player {player_id} report exported to {excel_path}")
        return excel_path
    
    # ============ HELPER METHODS ============
    
    def _determine_result(self, row, player_id: int) -> str:
        """Determine if player won or lost"""
        if row['player_1_id'] == player_id:
            return 'W' if row['player_1_score'] > row['player_2_score'] else 'L'
        else:
            return 'W' if row['player_2_score'] > row['player_1_score'] else 'L'
    
    def _get_winner(self, matches) -> pd.Series:
        """Get winner of each match"""
        return matches.apply(
            lambda row: row['player_1_id'] if row['player_1_score'] > row['player_2_score'] else row['player_2_id'],
            axis=1
        )


# ============ USAGE EXAMPLES ============
if __name__ == "__main__":
    analyzer = TournamentAnalyzer(data_dir="causeway_2026_data")
    
    # Export all analysis to Excel
    analyzer.export_to_excel()
    
    # Get top performers
    print("Top 10 Performers:")
    print(analyzer.top_performers(10))
    
    # Consistency analysis
    print("\nMost Consistent Players:")
    print(analyzer.consistency_analysis().head())
    
    # Upset detection
    print("\nUpsets Detected:")
    print(analyzer.upset_detection())
    
    # Specific player analysis
    print("\nPlayer 1 Win/Loss by Round:")
    print(analyzer.player_win_loss_by_round(1))
    
    # Head-to-head
    print("\nPlayer 1 vs Player 2 H2H:")
    print(analyzer.player_head_to_head(1, 2))
