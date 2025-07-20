"""
Downloader - Handles file downloading with progress tracking
"""

import asyncio
import httpx
from pathlib import Path
from typing import Optional
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.console import Console

console = Console()

class Downloader:
    """Handles file downloading with progress tracking"""
    
    def __init__(self, shutdown_coordinator=None):
        self.client = None
        self.shutdown_coordinator = shutdown_coordinator
    
    async def download_file(
        self, 
        url: str, 
        filename: str, 
        output_dir: str = "downloads"
    ) -> bool:
        """Download a file with progress tracking"""
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            file_path = output_path / filename
            
            # Initialize HTTP client with SSL verification disabled and redirect following
            if not self.client:
                self.client = httpx.AsyncClient(
                    timeout=30.0,
                    verify=False,  # Disable SSL verification for self-signed certificates
                    follow_redirects=True  # Follow redirects automatically
                )
            
            # Start download
            console.print(f"[blue]Downloading:[/blue] {filename}")
            
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                
                # Get file size
                total_size = int(response.headers.get("content-length", 0))
                
                # Set up progress bar
                with Progress(
                    TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
                    BarColumn(bar_width=None),
                    "[progress.percentage]{task.percentage:>3.1f}%",
                    "•",
                    DownloadColumn(),
                    "•",
                    TransferSpeedColumn(),
                    "•",
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    
                    task = progress.add_task(
                        "download", 
                        filename=filename, 
                        total=total_size
                    )
                    
                    # Download file
                    with open(file_path, "wb") as file:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            # Check for shutdown request
                            if self.shutdown_coordinator and self.shutdown_coordinator.is_shutdown_requested():
                                console.print(f"\n[yellow]Download cancelled: {filename}[/yellow]")
                                # Remove incomplete file
                                file_path.unlink(missing_ok=True)
                                return False
                            
                            file.write(chunk)
                            progress.update(task, advance=len(chunk))
            
            console.print(f"[green]✓ Download complete:[/green] {file_path}")
            return True
            
        except httpx.HTTPError as e:
            console.print(f"[red]✗ Download failed:[/red] HTTP error - {e}")
            return False
        except Exception as e:
            console.print(f"[red]✗ Download failed:[/red] {e}")
            return False
    
    async def download_subtitles(
        self, 
        subtitle_urls: list, 
        base_filename: str, 
        output_dir: str = "downloads"
    ) -> bool:
        """Download subtitle files"""
        if not subtitle_urls:
            return True
        
        console.print("[blue]Downloading subtitles...[/blue]")
        
        success = True
        for lang, url in subtitle_urls:
            # Create subtitle filename
            subtitle_filename = f"{base_filename}.{lang}.srt"
            
            result = await self.download_file(url, subtitle_filename, output_dir)
            if not result:
                success = False
        
        return success
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:200-len(ext)-1] + '.' + ext if ext else name[:200]
        
        return filename
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()