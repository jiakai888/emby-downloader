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

from emby_client import MediaItem, AudioStream, SubtitleStream, VideoStream
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
            selected_server = await self.display_saved_servers(saved_servers)
            
            if selected_server:
                # Update last used timestamp
                self.credential_manager.update_server_last_used(selected_server.name)
                return selected_server.url, selected_server.username, selected_server.password
        
        # No saved servers or user chose to add new server
        return await self.get_new_server_info()
    
    async def display_saved_servers(self, servers: List[ServerConfig]) -> Optional[ServerConfig]:
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
        
        # Add "Manage Servers" option
        table.add_row(
            str(len(servers) + 2),
            "[bold yellow]Manage Servers[/bold yellow]",
            "-",
            "-",
            "-"
        )
        
        console.print(table)
        console.print()
        
        # Get user selection
        selection = Prompt.ask(
            f"Select server (1-{len(servers) + 2})",
            default="1"
        )
        
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(servers):
                return servers[idx]
            elif idx == len(servers):
                # User chose "Add New Server"
                return None
            elif idx == len(servers) + 1:
                # User chose "Manage Servers"
                await self.manage_servers_menu()
                # After managing servers, show the server list again
                return await self.display_saved_servers(self.credential_manager.load_servers())
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
    
    def select_video_quality(self, streams: List[VideoStream]) -> int:
        """Display video quality options and get user selection"""
        # Import here to avoid circular import
        from media_analyzer import MediaAnalyzer
        
        if not streams:
            return 0  # No streams available
        
        console.print("[bold blue]Available video qualities:[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", width=3)
        table.add_column("Quality", style="cyan")
        table.add_column("Resolution", style="yellow")
        table.add_column("Bitrate", style="green")
        table.add_column("Codec", style="dim")
        table.add_column("Framerate", style="dim")
        
        for i, stream in enumerate(streams, 1):
            # Determine quality label
            if stream.height >= 2160:
                quality_label = "4K UHD"
            elif stream.height >= 1080:
                quality_label = "1080p"
            elif stream.height >= 720:
                quality_label = "720p"
            else:
                quality_label = f"{stream.height}p"
            
            resolution = f"{stream.width}x{stream.height}"
            bitrate_mbps = f"{stream.bitrate / 1000000:.1f} Mbps"
            framerate_str = f"{stream.framerate:.1f} fps" if stream.framerate else "N/A"
            
            table.add_row(
                str(i),
                quality_label,
                resolution,
                bitrate_mbps,
                stream.codec.upper(),
                framerate_str
            )
        
        console.print(table)
        console.print()
        
        # Sort by quality score and show recommended option
        sorted_streams = sorted(enumerate(streams), key=lambda x: MediaAnalyzer.calculate_video_quality_score(x[1]), reverse=True)
        recommended_idx = sorted_streams[0][0] + 1
        
        if len(streams) == 1:
            # Only one option available, but still show the interface
            selection = Prompt.ask(
                f"Select video quality (1 - only one available)", 
                default="1"
            )
        else:
            # Multiple options available
            selection = Prompt.ask(
                f"Select video quality (1-{len(streams)}, recommended: {recommended_idx})", 
                default=str(recommended_idx)
            )
        
        try:
            selected_idx = int(selection) - 1
            if 0 <= selected_idx < len(streams):
                return selected_idx
            else:
                return recommended_idx - 1
        except ValueError:
            return recommended_idx - 1

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
    
    async def manage_servers_menu(self):
        """Display server management menu"""
        while True:
            console.print("\n[bold blue]Server Management[/bold blue]")
            console.print()
            
            servers = self.credential_manager.load_servers()
            
            if not servers:
                console.print("[yellow]No saved servers found.[/yellow]")
                return
            
            # Display servers with management options
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
            
            console.print(table)
            console.print()
            
            # Management options
            console.print("[bold]Management Options:[/bold]")
            console.print("1. Edit server")
            console.print("2. Delete server")
            console.print("3. Back to main menu")
            console.print()
            
            choice = Prompt.ask("Select action (1-3)", default="3")
            
            if choice == "1":
                await self.edit_server(servers)
            elif choice == "2":
                await self.delete_server(servers)
            elif choice == "3":
                break
            else:
                console.print("[red]Invalid choice.[/red]")
    
    async def edit_server(self, servers: List[ServerConfig]):
        """Edit a server configuration"""
        if not servers:
            return
        
        console.print("\n[bold blue]Edit Server[/bold blue]")
        server_choice = Prompt.ask(f"Select server to edit (1-{len(servers)})")
        
        try:
            idx = int(server_choice) - 1
            if 0 <= idx < len(servers):
                server = servers[idx]
                console.print(f"\nEditing server: [bold]{server.name}[/bold]")
                
                # Get new values (with current values as defaults)
                new_name = Prompt.ask("Server name", default=server.name)
                new_url = Prompt.ask("Server URL", default=server.url)
                new_username = Prompt.ask("Username", default=server.username)
                
                # Ask if user wants to change password
                change_password = Confirm.ask("Change password?", default=False)
                if change_password:
                    new_password = getpass.getpass("Enter new password: ")
                else:
                    new_password = server.password
                
                # Create updated server config
                updated_server = ServerConfig(
                    name=new_name,
                    url=new_url,
                    username=new_username,
                    password=new_password,
                    last_used=server.last_used,
                    created=server.created
                )
                
                # Validate
                is_valid, error_msg = self.credential_manager.validate_server_config(updated_server)
                if not is_valid:
                    console.print(f"[red]✗ Invalid configuration: {error_msg}[/red]")
                    return
                
                # Delete old server and save new one
                if self.credential_manager.delete_server(server.name):
                    if self.credential_manager.save_server(updated_server):
                        console.print(f"[green]✓ Server '{new_name}' updated successfully![/green]")
                    else:
                        console.print("[red]✗ Failed to save updated server.[/red]")
                else:
                    console.print("[red]✗ Failed to update server.[/red]")
            else:
                console.print("[red]Invalid server selection.[/red]")
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
    
    async def delete_server(self, servers: List[ServerConfig]):
        """Delete a server configuration"""
        if not servers:
            return
        
        console.print("\n[bold blue]Delete Server[/bold blue]")
        server_choice = Prompt.ask(f"Select server to delete (1-{len(servers)})")
        
        try:
            idx = int(server_choice) - 1
            if 0 <= idx < len(servers):
                server = servers[idx]
                
                # Confirm deletion
                if Confirm.ask(f"[red]Are you sure you want to delete '{server.name}'?[/red]", default=False):
                    if self.credential_manager.delete_server(server.name):
                        console.print(f"[green]✓ Server '{server.name}' deleted successfully![/green]")
                    else:
                        console.print("[red]✗ Failed to delete server.[/red]")
                else:
                    console.print("[yellow]Deletion cancelled.[/yellow]")
            else:
                console.print("[red]Invalid server selection.[/red]")
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
    
    def display_seasons(self, seasons: List) -> List[int]:
        """Display seasons and get user selection"""
        if not seasons:
            console.print("[yellow]No seasons found.[/yellow]")
            return []
        
        console.print(f"[green]Found {len(seasons)} season(s):[/green]")
        console.print()
        
        # Create seasons table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Season", style="bold")
        table.add_column("Name", style="cyan")
        table.add_column("Year", style="dim")
        
        for i, season in enumerate(seasons, 1):
            season_num = f"Season {season.season_number}" if season.season_number else "Special"
            year_str = str(season.year) if season.year else "N/A"
            table.add_row(str(i), season_num, season.name, year_str)
        
        console.print(table)
        console.print()
        
        # Get user selection
        selection = Prompt.ask(
            f"Select seasons (1-{len(seasons)}, A for all, or comma-separated)",
            default="A"
        )
        
        if selection.upper() == 'A':
            return list(range(len(seasons)))
        
        # Parse selection
        try:
            indices = []
            for part in selection.split(','):
                idx = int(part.strip()) - 1
                if 0 <= idx < len(seasons):
                    indices.append(idx)
            return indices
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
            return []
    
    def display_episodes(self, episodes: List) -> List[int]:
        """Display episodes and get user selection"""
        if not episodes:
            console.print("[yellow]No episodes found.[/yellow]")
            return []
        
        console.print(f"[green]Found {len(episodes)} episode(s):[/green]")
        console.print()
        
        # Create episodes table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Episode", style="bold")
        table.add_column("Title", style="cyan")
        table.add_column("Duration", style="yellow")
        
        for i, episode in enumerate(episodes, 1):
            episode_num = f"S{episode.season_number:02d}E{episode.episode_number:02d}" if episode.season_number and episode.episode_number else f"Episode {i}"
            duration_str = f"{episode.duration // 60}m" if episode.duration else "Unknown"
            table.add_row(str(i), episode_num, episode.name, duration_str)
        
        console.print(table)
        console.print()
        
        # Get user selection
        selection = Prompt.ask(
            f"Select episodes (1-{len(episodes)}, A for all, or comma-separated)",
            default="A"
        )
        
        if selection.upper() == 'A':
            return list(range(len(episodes)))
        
        # Parse selection
        try:
            indices = []
            for part in selection.split(','):
                idx = int(part.strip()) - 1
                if 0 <= idx < len(episodes):
                    indices.append(idx)
            return indices
        except ValueError:
            console.print("[red]Invalid selection.[/red]")
            return []
    
    def ask_download_options(self) -> str:
        """Ask user about download options for multiple items"""
        console.print("\n[bold blue]Download Options:[/bold blue]")
        console.print("1. Download selected items individually")
        console.print("2. Batch download (one after another)")
        console.print("3. Save URLs to file")
        console.print()
        
        choice = Prompt.ask("Select option (1-3)", default="2")
        
        if choice == "1":
            return "individual"
        elif choice == "2":
            return "batch"
        elif choice == "3":
            return "save_urls"
        else:
            return "batch"  # Default to batch
    
    def confirm_batch_download(self, count: int, item_type: str = "items") -> bool:
        """Confirm batch download operation"""
        return Confirm.ask(f"[cyan]Download {count} {item_type} in sequence?[/cyan]", default=True)