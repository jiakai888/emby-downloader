"""
Series Navigator - Handles TV series browsing and episode selection workflow
"""

from typing import List, Tuple
from rich.console import Console
from emby_client import EmbyClient, MediaItem
from cli_interface import CLIInterface

console = Console()

class SeriesNavigator:
    """Manages TV series navigation workflow"""
    
    def __init__(self, emby_client: EmbyClient, cli: CLIInterface):
        self.emby_client = emby_client
        self.cli = cli
        self.console = console
    
    async def browse_series(self, series_item: MediaItem) -> List[MediaItem]:
        """Browse a TV series and return selected episodes"""
        try:
            console.print(f"\n[bold blue]Browsing Series: {series_item.name}[/bold blue]")
            
            # Get seasons for the series
            console.print("[dim]Loading seasons...[/dim]")
            seasons = await self.emby_client.get_series_seasons(series_item.id)
            
            if not seasons:
                console.print("[yellow]No seasons found for this series.[/yellow]")
                return []
            
            # Display seasons and get user selection
            selected_season_indices = self.cli.display_seasons(seasons)
            
            if not selected_season_indices:
                console.print("[yellow]No seasons selected.[/yellow]")
                return []
            
            # Collect episodes from selected seasons
            all_episodes = []
            for season_idx in selected_season_indices:
                season = seasons[season_idx]
                console.print(f"\n[dim]Loading episodes for {season.name}...[/dim]")
                
                episodes = await self.emby_client.get_season_episodes(season.id)
                if episodes:
                    # Add season info to episodes for better display
                    for episode in episodes:
                        episode.series_id = series_item.id
                    all_episodes.extend(episodes)
            
            if not all_episodes:
                console.print("[yellow]No episodes found in selected seasons.[/yellow]")
                return []
            
            # Display episodes and get user selection
            selected_episode_indices = self.cli.display_episodes(all_episodes)
            
            if not selected_episode_indices:
                console.print("[yellow]No episodes selected.[/yellow]")
                return []
            
            # Return selected episodes
            selected_episodes = [all_episodes[i] for i in selected_episode_indices]
            
            console.print(f"[green]Selected {len(selected_episodes)} episode(s) for processing.[/green]")
            return selected_episodes
            
        except Exception as e:
            console.print(f"[red]Error browsing series: {e}[/red]")
            return []
    
    async def get_seasons(self, series_id: str) -> List[MediaItem]:
        """Get seasons for a series"""
        return await self.emby_client.get_series_seasons(series_id)
    
    async def get_episodes(self, season_id: str) -> List[MediaItem]:
        """Get episodes for a season"""
        return await self.emby_client.get_season_episodes(season_id)
    
    def generate_episode_filename(self, episode: MediaItem, series_name: str, container: str = "mkv") -> str:
        """Generate filename for an episode"""
        # Sanitize series name
        safe_series_name = self._sanitize_filename(series_name)
        
        # Format episode info
        season_num = episode.season_number or 1
        episode_num = episode.episode_number or 1
        episode_title = self._sanitize_filename(episode.name or f"Episode {episode_num}")
        
        # Create filename: Series Name - S01E01 - Episode Title.ext
        filename = f"{safe_series_name} - S{season_num:02d}E{episode_num:02d} - {episode_title}.{container}"
        
        return filename
    
    def generate_episode_directory(self, series_name: str, season_number: int = None) -> str:
        """Generate directory path for episodes"""
        safe_series_name = self._sanitize_filename(series_name)
        
        if season_number:
            return f"{safe_series_name}/Season {season_number:02d}"
        else:
            return safe_series_name
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove extra spaces and limit length
        filename = ' '.join(filename.split())
        if len(filename) > 100:
            filename = filename[:100].strip()
        
        return filename