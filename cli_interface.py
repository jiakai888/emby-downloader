"""
CLI Interface - Handles user interaction and display formatting
"""

import getpass
from typing import List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from emby_client import MediaItem, AudioStream, SubtitleStream
from credential_manager import CredentialManager, ServerConfig

console = Console()

class CLIInterface:
    """Command-line interface for user interaction"""
    
    def __init__(self, credential_manager: CredentialManager = None):
        self.console = console
        self.credential_manager = credential_manager or CredentialManager()
    
    async def get_server_info(self) -> Tuple[str, str, str]:
        """Get server connection information from user"""
        console.print("[bold blue]Server Connection[/bold blue]")
        console.print()
        
        # Load saved servers
        saved_servers = self.credential_manager.load_servers()
        
        if saved_servers:
            # Display saved servers
            selected_server = self.display_saved_servers(saved_servers)
            
            if selected_server:
                # Update last used timestamp
                self.credential_manager.update_server_last_used(selected_server.name)
                return selected_server.url, selected_server.username, selected_server.password
        
        # No saved servers or user chose to add new server
        return await self.get_new_server_info()
    
    def display_saved_servers(self, servers: List[ServerConfig]) -> Optional[ServerConfig]:
        """Display saved servers and get user selection"""
        console.print(f"[green]Found {len(servers)} saved server(s):[/green]")
        console.print()
        
        # Create servers table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Server Name", style="bold")
        table.add_column("URL", style="cyan")
        table.add_column("Username", style="yellow")
        table.add_column("Last Used", style="dim")
        
        for i, server in enumerate(servers, 1):
            last_used = server.last_used.strftime("%Y-%m-%d %H:%M") if server.last_used else "Never"
            table.add_row(
                str(i),
                server.name,
                server.url,
                server.username,
                last_used
            )
        
        # Add "Add New Server" option
        table.add_row(
            str(len(servers) + 1),
            "[bold green]Add New Server[/bold green]",
            "-",
            "-",
            "-"
        )
        
        console.print(table)
        console.print()
        
        # Get user selection
        selection = Prompt.ask(
            f"Select server (1-{len(servers) + 1})",
            default="1"
        )
        
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(servers):
                return servers[idx]
            elif idx == len(servers):
                # User chose "Add New Server"
                return None
            else:
                console.print("[red]Invalid selection.[/red]")
                return None
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
            return None
    
    async def get_new_server_info(self) -> Tuple[str, str, str]:
        """Get new server information from user"""
        console.print("[bold blue]Add New Server[/bold blue]")
        console.print()
        
        # Get server URL
        url = Prompt.ask("Enter Emby server URL (with port if not 80/443)")
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Get credentials
        username = Prompt.ask("Enter username")
        password = getpass.getpass("Enter password: ")
        
        return url, username, password
    
    def display_login_status(self, success: bool, server_name: str = ""):
        """Display login status"""
        if success:
            console.print(f"[green]✓ Login successful![/green] Connected to: {server_name}")
        else:
            console.print("[red]✗ Login failed![/red] Please check your credentials.")
        console.print()
    
    async def get_search_query(self) -> str:
        """Get search query from user"""
        console.print("[bold blue]Content Search[/bold blue]")
        console.print()
        
        query = Prompt.ask("Enter movie/show name or ID")
        return query
    
    def display_search_results(self, results: List[MediaItem]) -> List[int]:
        """Display search results and get user selection"""
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return []
        
        console.print(f"[green]Found {len(results)} result(s):[/green]")
        console.print()
        
        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Title", style="bold")
        table.add_column("Type", style="cyan")
        table.add_column("Year", style="dim")
        table.add_column("ID", style="dim")
        
        for i, item in enumerate(results, 1):
            year_str = str(item.year) if item.year else "N/A"
            table.add_row(str(i), item.name, item.type, year_str, item.id)
        
        console.print(table)
        console.print()
        
        # Get user selection
        selection = Prompt.ask(
            f"Select items (1-{len(results)}, A for all, or comma-separated)",
            default="1"
        )
        
        if selection.upper() == 'A':
            return list(range(len(results)))
        
        # Parse selection
        try:
            indices = []
            for part in selection.split(','):
                idx = int(part.strip()) - 1
                if 0 <= idx < len(results):
                    indices.append(idx)
            return indices
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
            return []
    
    def select_audio_track(self, tracks: List[AudioStream]) -> int:
        """Display audio tracks and get user selection"""
        if len(tracks) <= 1:
            return 0  # Auto-select if only one track
        
        console.print("[bold blue]Available audio tracks:[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", width=3)
        table.add_column("Language", style="cyan")
        table.add_column("Codec", style="yellow")
        table.add_column("Channels", style="green")
        table.add_column("Title", style="dim")
        
        for i, track in enumerate(tracks, 1):
            channels_str = f"{track.channels}.1" if track.channels > 2 else "Stereo"
            table.add_row(
                str(i),
                track.language,
                track.codec,
                channels_str,
                track.title or "Default"
            )
        
        console.print(table)
        console.print()
        
        selection = Prompt.ask(f"Select audio track (1-{len(tracks)})", default="1")
        try:
            return int(selection) - 1
        except ValueError:
            return 0
    
    def select_subtitles(self, subtitles: List[SubtitleStream]) -> List[int]:
        """Display subtitles and get user selection"""
        if not subtitles:
            return []
        
        console.print("[bold blue]Available subtitles:[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", width=3)
        table.add_column("Language", style="cyan")
        table.add_column("Format", style="yellow")
        table.add_column("Title", style="dim")
        
        for i, sub in enumerate(subtitles, 1):
            table.add_row(
                str(i),
                sub.language,
                sub.codec,
                sub.title or "Default"
            )
        
        # Add "None" option
        table.add_row(str(len(subtitles) + 1), "None", "-", "No subtitles")
        
        console.print(table)
        console.print()
        
        selection = Prompt.ask(
            f"Select subtitles (1-{len(subtitles) + 1}, multiple allowed, comma-separated)",
            default=str(len(subtitles) + 1)  # Default to "None"
        )
        
        if selection.strip() == str(len(subtitles) + 1):
            return []  # No subtitles
        
        # Parse selection
        try:
            indices = []
            for part in selection.split(','):
                idx = int(part.strip()) - 1
                if 0 <= idx < len(subtitles):
                    indices.append(idx)
            return indices
        except ValueError:
            return []
    
    def display_urls(self, video_url: str, subtitle_urls: List[Tuple[str, str]], media_info: dict):
        """Display generated URLs and media information"""
        console.print("[bold green]Generated URLs:[/bold green]")
        console.print()
        
        # Video stream
        console.print("[bold]Video Stream:[/bold]")
        console.print(f"[cyan]{video_url}[/cyan]")
        console.print()
        
        # Subtitles
        if subtitle_urls:
            console.print("[bold]Subtitles:[/bold]")
            for lang, url in subtitle_urls:
                console.print(f"{lang}: [cyan]{url}[/cyan]")
            console.print()
        
        # Media info
        if media_info:
            info_panel = Panel(
                f"Duration: {media_info.get('duration', 'Unknown')}\n"
                f"File Size: {media_info.get('size', 'Unknown')}\n"
                f"Video: {media_info.get('video', 'Unknown')}\n"
                f"Audio: {media_info.get('audio', 'Unknown')}",
                title="Media Info",
                border_style="dim"
            )
            console.print(info_panel)
    
    def ask_download(self) -> bool:
        """Ask user if they want to download the content"""
        return Confirm.ask("Download now?", default=False)
    
    def ask_save_urls(self) -> bool:
        """Ask user if they want to save URLs to file"""
        return Confirm.ask("Save URLs to file?", default=True)
    
    async def offer_to_save_server(self, url: str, username: str, password: str, server_name: str):
        """Offer to save server credentials after successful authentication"""
        # Check if this server is already saved
        saved_servers = self.credential_manager.load_servers()
        existing_server = None
        
        for server in saved_servers:
            if server.url == url and server.username == username:
                existing_server = server
                break
        
        if existing_server:
            # Server already exists, just update last used
            self.credential_manager.update_server_last_used(existing_server.name)
            console.print(f"[green]Welcome back! Using saved server: {existing_server.name}[/green]")
            return
        
        # Ask if user wants to save this new server
        if Confirm.ask(f"[cyan]Save server credentials for future use?[/cyan]", default=True):
            # Get a name for this server
            default_name = server_name or "Emby Server"
            server_display_name = Prompt.ask(
                "Enter a name for this server",
                default=default_name
            )
            
            # Create server config
            server_config = ServerConfig(
                name=server_display_name,
                url=url,
                username=username,
                password=password
            )
            
            # Validate and save
            is_valid, error_msg = self.credential_manager.validate_server_config(server_config)
            if is_valid:
                if self.credential_manager.save_server(server_config):
                    console.print(f"[green]✓ Server '{server_display_name}' saved successfully![/green]")
                else:
                    console.print("[red]✗ Failed to save server configuration.[/red]")
            else:
                console.print(f"[red]✗ Invalid server configuration: {error_msg}[/red]")