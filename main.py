#!/usr/bin/env python3
"""
Emby URL Extractor - A command-line tool for extracting streaming URLs from Emby servers
"""

import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from signal_handler import SignalHandler, ShutdownCoordinator

console = Console()

async def save_episode_urls(episodes, series_item, emby_client, cli):
    """Save episode URLs to file"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"emby_episodes_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Emby Episode URLs - Generated on {datetime.datetime.now()}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Series: {series_item.name}\n")
        f.write(f"Year: {series_item.year}\n")
        f.write(f"Episodes: {len(episodes)}\n\n")
        
        for episode in episodes:
            try:
                # Get stream info for episode
                stream_info = await emby_client.get_episode_stream_info(episode.id)
                
                # Generate video URL
                video_streams = stream_info['video_streams']
                if video_streams:
                    from media_analyzer import MediaAnalyzer
                    best_video = MediaAnalyzer.select_best_video_stream(video_streams)
                    video_url = await emby_client.generate_stream_url(episode.id, best_video.index, 0)
                    
                    f.write(f"Episode: S{episode.season_number:02d}E{episode.episode_number:02d} - {episode.name}\n")
                    f.write(f"Video URL: {video_url}\n\n")
                
            except Exception as e:
                f.write(f"Episode: S{episode.season_number:02d}E{episode.episode_number:02d} - {episode.name}\n")
                f.write(f"Error: {e}\n\n")
    
    console.print(f"[green]Episode URLs saved to: {filename}[/green]")

async def process_episode(episode, series_item, emby_client, cli, downloader, series_navigator, ask_individual_confirmation):
    """Process a single episode"""
    try:
        # Get stream information for episode
        console.print("[dim]Analyzing streams...[/dim]")
        stream_info = await emby_client.get_episode_stream_info(episode.id)
        
        # Select video quality
        video_streams = stream_info['video_streams']
        if not video_streams:
            console.print("[red]No video streams found[/red]")
            return
        
        from media_analyzer import MediaAnalyzer
        if ask_individual_confirmation:
            video_index = cli.select_video_quality(video_streams)
            selected_video = video_streams[video_index]
        else:
            # Auto-select best quality for batch processing
            selected_video = MediaAnalyzer.select_best_video_stream(video_streams)
            video_index = video_streams.index(selected_video)
        
        console.print(f"[green]Selected quality:[/green] {MediaAnalyzer.format_quality_info(selected_video)}")
        
        # Select audio track (auto-select first one for batch processing)
        audio_streams = stream_info['audio_streams']
        if audio_streams:
            if ask_individual_confirmation:
                audio_index = cli.select_audio_track(audio_streams)
            else:
                audio_index = 0  # Auto-select first audio track for batch
            selected_audio = audio_streams[audio_index]
            console.print(f"[green]Selected audio:[/green] {MediaAnalyzer.format_audio_info(selected_audio)}")
        else:
            audio_index = 0
            console.print("[yellow]No audio tracks found[/yellow]")
        
        # Select subtitles (auto-select none for batch processing)
        subtitle_streams = stream_info['subtitle_streams']
        if ask_individual_confirmation:
            subtitle_indices = cli.select_subtitles(subtitle_streams)
        else:
            subtitle_indices = []  # No subtitles for batch processing
        
        # Generate URLs
        console.print("\n[blue]Generating URLs...[/blue]")
        
        video_url = await emby_client.generate_stream_url(
            episode.id, 
            selected_video.index, 
            audio_index
        )
        
        subtitle_urls = []
        for sub_idx in subtitle_indices:
            sub_stream = subtitle_streams[sub_idx]
            sub_url = await emby_client.generate_subtitle_url(episode.id, sub_stream.index)
            subtitle_urls.append((sub_stream.language, sub_url))
        
        # Generate episode filename
        filename = series_navigator.generate_episode_filename(
            episode, 
            series_item.name, 
            stream_info['container']
        )
        
        # Create directory structure
        episode_dir = series_navigator.generate_episode_directory(
            series_item.name, 
            episode.season_number
        )
        
        # Ask about download (only for individual processing)
        should_download = True
        if ask_individual_confirmation:
            # Display URLs first
            media_info = {
                'duration': f"{episode.duration // 60}m" if episode.duration else "Unknown",
                'size': MediaAnalyzer.estimate_file_size(stream_info['bitrate'], episode.duration or 0),
                'video': MediaAnalyzer.format_quality_info(selected_video),
                'audio': MediaAnalyzer.format_audio_info(selected_audio) if audio_streams else "Unknown"
            }
            cli.display_urls(video_url, subtitle_urls, media_info)
            should_download = cli.ask_download()
        
        if should_download:
            # Download video
            success = await downloader.download_file(video_url, filename, episode_dir)
            
            # Download subtitles if video download succeeded
            if success and subtitle_urls:
                base_name = filename.rsplit('.', 1)[0]  # Remove extension
                await downloader.download_subtitles(subtitle_urls, base_name, episode_dir)
        
    except Exception as e:
        console.print(f"[red]Error processing episode: {e}[/red]")
        raise

def display_banner():
    """Display the application banner"""
    banner = Text("Emby URL Extractor", style="bold blue")
    subtitle = Text("Extract high-quality streaming URLs from Emby servers", style="dim")
    
    console.print(Panel.fit(
        f"{banner}\n{subtitle}",
        border_style="blue"
    ))
    console.print()

async def main():
    """Main application entry point"""
    emby_client = None
    downloader = None
    shutdown_coordinator = None
    signal_handler = None
    
    try:
        display_banner()
        
        # Initialize shutdown coordination
        shutdown_coordinator = ShutdownCoordinator(console)
        signal_handler = SignalHandler(shutdown_coordinator)
        signal_handler.setup_handlers()
        
        # Import components
        from cli_interface import CLIInterface
        from emby_client import EmbyClient
        from media_analyzer import MediaAnalyzer
        from downloader import Downloader
        from series_navigator import SeriesNavigator
        
        # Import credential manager
        from credential_manager import CredentialManager, ServerConfig
        
        # Initialize components with shutdown coordinator
        credential_manager = CredentialManager()
        cli = CLIInterface(credential_manager)
        emby_client = EmbyClient()
        downloader = Downloader(shutdown_coordinator)
        series_navigator = SeriesNavigator(emby_client, cli)
        
        # Register cleanup handlers
        if emby_client:
            shutdown_coordinator.register_cleanup_handler("emby_client", emby_client.close, priority=1)
        if downloader:
            shutdown_coordinator.register_cleanup_handler("downloader", downloader.close, priority=2)
        
        # Step 1: Get server connection info
        url, username, password = await cli.get_server_info()
        
        # Step 2: Authenticate
        console.print("[blue]Connecting to server...[/blue]")
        auth_result = await emby_client.authenticate(url, username, password)
        
        if not auth_result['success']:
            console.print(f"[red]Authentication failed: {auth_result['error']}[/red]")
            return
        
        cli.display_login_status(True, auth_result['server_name'])
        
        # Offer to save server credentials if authentication was successful
        await cli.offer_to_save_server(url, username, password, auth_result['server_name'])
        
        # Step 3: Search for content
        query = await cli.get_search_query()
        
        console.print("[blue]Searching...[/blue]")
        search_results = await emby_client.search_content(query)
        
        if not search_results:
            console.print("[yellow]No results found.[/yellow]")
            return
        
        # Step 4: Select content
        selected_indices = cli.display_search_results(search_results)
        
        if not selected_indices:
            console.print("[yellow]No items selected.[/yellow]")
            return
        
        # Process each selected item
        for idx in selected_indices:
            item = search_results[idx]
            console.print(f"\n[bold blue]Processing: {item.name}[/bold blue]")
            
            try:
                # Check if this is a TV series
                if item.is_series():
                    # Handle TV series - browse seasons and episodes
                    episodes = await series_navigator.browse_series(item)
                    
                    if not episodes:
                        console.print("[yellow]No episodes selected.[/yellow]")
                        continue
                    
                    # Ask about download options for multiple episodes
                    download_option = cli.ask_download_options()
                    
                    if download_option == "save_urls":
                        # Save URLs to file for all episodes
                        await save_episode_urls(episodes, item, emby_client, cli)
                        continue
                    elif download_option == "batch":
                        # Confirm batch download
                        if not cli.confirm_batch_download(len(episodes), "episodes"):
                            continue
                    
                    # Process each episode
                    for episode_idx, episode in enumerate(episodes, 1):
                        console.print(f"\n[bold cyan]Processing Episode {episode_idx}/{len(episodes)}: {episode.name}[/bold cyan]")
                        
                        try:
                            await process_episode(episode, item, emby_client, cli, downloader, series_navigator, download_option == "individual")
                        except Exception as e:
                            console.print(f"[red]Error processing episode {episode.name}: {e}[/red]")
                            continue
                    
                    continue
                
                # Handle movies (existing logic)
                console.print("[dim]Analyzing streams...[/dim]")
                stream_info = await emby_client.get_stream_info(item.id)
                
                # Select video quality
                video_streams = stream_info['video_streams']
                if not video_streams:
                    console.print("[red]No video streams found[/red]")
                    continue
                
                video_index = cli.select_video_quality(video_streams)
                selected_video = video_streams[video_index]
                console.print(f"[green]Selected quality:[/green] {MediaAnalyzer.format_quality_info(selected_video)}")
                
                # Select audio track
                audio_streams = stream_info['audio_streams']
                if audio_streams:
                    audio_index = cli.select_audio_track(audio_streams)
                    selected_audio = audio_streams[audio_index]
                    console.print(f"[green]Selected audio:[/green] {MediaAnalyzer.format_audio_info(selected_audio)}")
                else:
                    audio_index = 0
                    console.print("[yellow]No audio tracks found[/yellow]")
                
                # Select subtitles
                subtitle_streams = stream_info['subtitle_streams']
                subtitle_indices = cli.select_subtitles(subtitle_streams)
                
                # Generate URLs
                console.print("\n[blue]Generating URLs...[/blue]")
                
                video_url = await emby_client.generate_stream_url(
                    item.id, 
                    selected_video.index, 
                    audio_index
                )
                
                subtitle_urls = []
                for sub_idx in subtitle_indices:
                    sub_stream = subtitle_streams[sub_idx]
                    sub_url = await emby_client.generate_subtitle_url(item.id, sub_stream.index)
                    subtitle_urls.append((sub_stream.language, sub_url))
                
                # Display results
                media_info = {
                    'duration': f"{item.duration // 3600}h {(item.duration % 3600) // 60}m" if item.duration else "Unknown",
                    'size': MediaAnalyzer.estimate_file_size(stream_info['bitrate'], item.duration or 0),
                    'video': MediaAnalyzer.format_quality_info(selected_video),
                    'audio': MediaAnalyzer.format_audio_info(selected_audio) if audio_streams else "Unknown"
                }
                
                cli.display_urls(video_url, subtitle_urls, media_info)
                
                # Ask about download
                if cli.ask_download():
                    filename = downloader.sanitize_filename(f"{item.name} ({item.year}).{stream_info['container']}")
                    
                    # Download video
                    success = await downloader.download_file(video_url, filename)
                    
                    # Download subtitles if video download succeeded
                    if success and subtitle_urls:
                        base_name = filename.rsplit('.', 1)[0]  # Remove extension
                        await downloader.download_subtitles(subtitle_urls, base_name)
                
                # Ask about saving URLs
                elif cli.ask_save_urls():
                    # Save URLs to file
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"emby_urls_{timestamp}.txt"
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"Emby URLs - Generated on {datetime.datetime.now()}\n")
                        f.write("=" * 50 + "\n\n")
                        f.write(f"Title: {item.name}\n")
                        f.write(f"Year: {item.year}\n")
                        f.write(f"Type: {item.type}\n\n")
                        f.write(f"Video Stream:\n{video_url}\n\n")
                        
                        if subtitle_urls:
                            f.write("Subtitles:\n")
                            for lang, url in subtitle_urls:
                                f.write(f"{lang}: {url}\n")
                            f.write("\n")
                        
                        f.write(f"Media Info:\n")
                        for key, value in media_info.items():
                            f.write(f"{key.title()}: {value}\n")
                    
                    console.print(f"[green]URLs saved to: {filename}[/green]")
                
            except Exception as e:
                console.print(f"[red]Error processing {item.name}: {e}[/red]")
                continue
        
        console.print("\n[green]All done![/green]")
        
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)
    finally:
        # Cleanup is now handled by shutdown coordinator
        if shutdown_coordinator and shutdown_coordinator.is_shutdown_requested():
            # Shutdown was already handled gracefully
            pass
        else:
            # Normal cleanup for regular exit
            if emby_client:
                await emby_client.close()
            if downloader:
                await downloader.close()

if __name__ == "__main__":
    asyncio.run(main())