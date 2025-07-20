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
        
        # Import credential manager
        from credential_manager import CredentialManager, ServerConfig
        
        # Initialize components with shutdown coordinator
        credential_manager = CredentialManager()
        cli = CLIInterface(credential_manager)
        emby_client = EmbyClient()
        downloader = Downloader(shutdown_coordinator)
        
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
                # Get stream information
                console.print("[dim]Analyzing streams...[/dim]")
                stream_info = await emby_client.get_stream_info(item.id)
                
                # Select best video stream
                video_streams = stream_info['video_streams']
                if not video_streams:
                    console.print("[red]No video streams found[/red]")
                    continue
                
                best_video = MediaAnalyzer.select_best_video_stream(video_streams)
                console.print(f"[green]Selected quality:[/green] {MediaAnalyzer.format_quality_info(best_video)}")
                
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
                    best_video.index, 
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
                    'video': MediaAnalyzer.format_quality_info(best_video),
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