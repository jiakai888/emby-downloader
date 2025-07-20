"""
Emby API Client - Handles authentication and API communication with Emby servers
"""

import httpx
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class MediaItem:
    """Represents a media item from Emby"""
    id: str
    name: str
    type: str
    year: Optional[int] = None
    overview: Optional[str] = None
    duration: Optional[int] = None  # in seconds
    # TV Series specific fields
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    series_id: Optional[str] = None
    parent_id: Optional[str] = None
    
    def is_series(self) -> bool:
        """Check if this item is a TV series"""
        return self.type.lower() == 'series'
    
    def is_season(self) -> bool:
        """Check if this item is a season"""
        return self.type.lower() == 'season'
    
    def is_episode(self) -> bool:
        """Check if this item is an episode"""
        return self.type.lower() == 'episode'
    
    def is_movie(self) -> bool:
        """Check if this item is a movie"""
        return self.type.lower() == 'movie'

@dataclass
class VideoStream:
    """Represents a video stream"""
    index: int
    codec: str
    bitrate: int
    width: int
    height: int
    framerate: float

@dataclass
class AudioStream:
    """Represents an audio stream"""
    index: int
    codec: str
    language: str
    channels: int
    bitrate: int
    title: str

@dataclass
class SubtitleStream:
    """Represents a subtitle stream"""
    index: int
    language: str
    codec: str
    title: str
    is_external: bool = False

class EmbyClient:
    """Emby API client for authentication and content retrieval"""
    
    def __init__(self):
        self.base_url = ""
        self.token = ""
        self.user_id = ""
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize HTTP client with SSL verification disabled"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False  # Disable SSL verification for self-signed certificates
        )
    
    async def authenticate(self, url: str, username: str, password: str) -> Dict:
        """Authenticate with Emby server"""
        self.base_url = url.rstrip('/')
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False  # Some self-hosted servers use self-signed certificates
        )
        
        # Prepare authentication data
        login_data = {
            "Username": username,
            "Pw": password
        }
        
        # Prepare headers
        headers = {
            "X-Emby-Authorization": 'Emby UserId="", Client="EmbyURLExtractor", Device="CLI", DeviceId="emby-url-extractor-001", Version="1.0.0"',
            "Content-Type": "application/json"
        }
        
        try:
            # Send authentication request
            response = await self.client.post(
                f"{self.base_url}/Users/AuthenticateByName",
                json=login_data,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Authentication failed: HTTP {response.status_code}")
            
            auth_data = response.json()
            
            # Store authentication info
            self.token = auth_data['AccessToken']
            self.user_id = auth_data['User']['Id']
            
            # Get server info
            server_info = await self._get_server_info()
            
            return {
                'success': True,
                'user_name': auth_data['User']['Name'],
                'server_name': server_info.get('ServerName', 'Unknown Server'),
                'server_version': server_info.get('Version', 'Unknown')
            }
            
        except httpx.HTTPError as e:
            return {
                'success': False,
                'error': f"Network error: {e}"
            }
        except KeyError as e:
            return {
                'success': False,
                'error': f"Invalid response format: missing {e}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_server_info(self) -> Dict:
        """Get server information"""
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            response = await self.client.get(
                f"{self.base_url}/System/Info",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception:
            return {}
    
    async def search_content(self, query: str) -> List[MediaItem]:
        """Search for content by name or ID"""
        if not self.token:
            raise Exception("Not authenticated")
        
        headers = {"X-MediaBrowser-Token": self.token}
        
        # Check if query is an ID (numeric)
        if query.isdigit():
            return await self._get_item_by_id(query)
        
        # Search by name
        try:
            params = {
                'searchTerm': query,
                'IncludeItemTypes': 'Movie,Episode,Series',
                'Limit': 20,
                'Recursive': 'true',
                'Fields': 'BasicSyncInfo,CanDelete,PrimaryImageAspectRatio,ProductionYear,Overview'
            }
            
            response = await self.client.get(
                f"{self.base_url}/Users/{self.user_id}/Items",
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Search failed: HTTP {response.status_code}")
            
            data = response.json()
            items = data.get('Items', [])
            
            # Convert to MediaItem objects
            media_items = []
            for item in items:
                media_item = MediaItem(
                    id=item['Id'],
                    name=item['Name'],
                    type=item['Type'],
                    year=item.get('ProductionYear'),
                    overview=item.get('Overview', ''),
                    duration=item.get('RunTimeTicks', 0) // 10_000_000 if item.get('RunTimeTicks') else None
                )
                media_items.append(media_item)
            
            return media_items
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error during search: {e}")
        except Exception as e:
            raise Exception(f"Search error: {e}")
    
    async def _get_item_by_id(self, item_id: str) -> List[MediaItem]:
        """Get item by ID"""
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            
            response = await self.client.get(
                f"{self.base_url}/Users/{self.user_id}/Items/{item_id}",
                headers=headers
            )
            
            if response.status_code == 404:
                return []  # Item not found
            elif response.status_code != 200:
                raise Exception(f"Failed to get item: HTTP {response.status_code}")
            
            item = response.json()
            
            media_item = MediaItem(
                id=item['Id'],
                name=item['Name'],
                type=item['Type'],
                year=item.get('ProductionYear'),
                overview=item.get('Overview', ''),
                duration=item.get('RunTimeTicks', 0) // 10_000_000 if item.get('RunTimeTicks') else None
            )
            
            return [media_item]
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error: {e}")
        except Exception as e:
            raise Exception(f"Error getting item by ID: {e}")
    
    async def get_media_info(self, item_id: str) -> Dict:
        """Get detailed media information"""
        if not self.token:
            raise Exception("Not authenticated")
        
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            
            response = await self.client.get(
                f"{self.base_url}/Users/{self.user_id}/Items/{item_id}",
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get media info: HTTP {response.status_code}")
            
            return response.json()
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error: {e}")
        except Exception as e:
            raise Exception(f"Error getting media info: {e}")
    
    async def get_stream_info(self, item_id: str) -> Dict:
        """Get stream information for media item"""
        if not self.token:
            raise Exception("Not authenticated")
        
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            
            # Get playback info which contains stream details
            response = await self.client.get(
                f"{self.base_url}/Items/{item_id}/PlaybackInfo",
                params={'UserId': self.user_id},
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get stream info: HTTP {response.status_code}")
            
            playback_info = response.json()
            
            # Parse media sources
            media_sources = playback_info.get('MediaSources', [])
            if not media_sources:
                raise Exception("No media sources found")
            
            # Get the first (usually best) media source
            media_source = media_sources[0]
            
            # Parse streams
            video_streams = []
            audio_streams = []
            subtitle_streams = []
            
            for stream in media_source.get('MediaStreams', []):
                if stream['Type'] == 'Video':
                    video_stream = VideoStream(
                        index=stream['Index'],
                        codec=stream.get('Codec', 'unknown'),
                        bitrate=stream.get('BitRate', 0),
                        width=stream.get('Width', 0),
                        height=stream.get('Height', 0),
                        framerate=stream.get('RealFrameRate', 0.0)
                    )
                    video_streams.append(video_stream)
                
                elif stream['Type'] == 'Audio':
                    audio_stream = AudioStream(
                        index=stream['Index'],
                        codec=stream.get('Codec', 'unknown'),
                        language=stream.get('Language', 'unknown'),
                        channels=stream.get('Channels', 2),
                        bitrate=stream.get('BitRate', 0),
                        title=stream.get('Title', stream.get('DisplayTitle', ''))
                    )
                    audio_streams.append(audio_stream)
                
                elif stream['Type'] == 'Subtitle':
                    subtitle_stream = SubtitleStream(
                        index=stream['Index'],
                        language=stream.get('Language', 'unknown'),
                        codec=stream.get('Codec', 'srt'),
                        title=stream.get('Title', stream.get('DisplayTitle', '')),
                        is_external=stream.get('IsExternal', False)
                    )
                    subtitle_streams.append(subtitle_stream)
            
            return {
                'media_source_id': media_source['Id'],
                'container': media_source.get('Container', 'unknown'),
                'size': media_source.get('Size', 0),
                'bitrate': media_source.get('Bitrate', 0),
                'video_streams': video_streams,
                'audio_streams': audio_streams,
                'subtitle_streams': subtitle_streams
            }
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error: {e}")
        except Exception as e:
            raise Exception(f"Error getting stream info: {e}")
    
    async def generate_stream_url(self, item_id: str, video_index: int = 0, audio_index: int = 0) -> str:
        """Generate streaming URL for media item"""
        if not self.token:
            raise Exception("Not authenticated")
        
        # Get stream info to determine container format
        stream_info = await self.get_stream_info(item_id)
        container = stream_info.get('container', 'mkv')
        
        # Build streaming URL
        url = f"{self.base_url}/Videos/{item_id}/stream.{container}"
        
        # Add parameters
        params = {
            'api_key': self.token,
            'VideoStreamIndex': video_index,
            'AudioStreamIndex': audio_index,
            'Static': 'true'  # Direct stream without transcoding
        }
        
        # Build query string
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        
        return f"{url}?{'&'.join(query_parts)}"
    
    async def generate_subtitle_url(self, item_id: str, subtitle_index: int) -> str:
        """Generate subtitle URL"""
        if not self.token:
            raise Exception("Not authenticated")
        
        # Build subtitle URL
        url = f"{self.base_url}/Videos/{item_id}/Subtitles/{subtitle_index}/Stream.srt"
        
        # Add API key
        return f"{url}?api_key={self.token}"
    
    async def get_series_seasons(self, series_id: str) -> List[MediaItem]:
        """Get all seasons for a TV series"""
        if not self.token:
            raise Exception("Not authenticated")
        
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            
            params = {
                'ParentId': series_id,
                'IncludeItemTypes': 'Season',
                'Fields': 'BasicSyncInfo,ChildCount,ProductionYear'
            }
            
            response = await self.client.get(
                f"{self.base_url}/Users/{self.user_id}/Items",
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get seasons: HTTP {response.status_code}")
            
            data = response.json()
            seasons = []
            
            for item in data.get('Items', []):
                season = MediaItem(
                    id=item['Id'],
                    name=item['Name'],
                    type=item['Type'],
                    year=item.get('ProductionYear'),
                    overview=item.get('Overview', ''),
                    season_number=item.get('IndexNumber'),
                    series_id=series_id,
                    parent_id=series_id
                )
                seasons.append(season)
            
            # Sort by season number
            seasons.sort(key=lambda x: x.season_number or 0)
            return seasons
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error: {e}")
        except Exception as e:
            raise Exception(f"Error getting seasons: {e}")
    
    async def get_season_episodes(self, season_id: str) -> List[MediaItem]:
        """Get all episodes for a season"""
        if not self.token:
            raise Exception("Not authenticated")
        
        try:
            headers = {"X-MediaBrowser-Token": self.token}
            
            params = {
                'ParentId': season_id,
                'IncludeItemTypes': 'Episode',
                'Fields': 'BasicSyncInfo,Overview,ProductionYear'
            }
            
            response = await self.client.get(
                f"{self.base_url}/Users/{self.user_id}/Items",
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get episodes: HTTP {response.status_code}")
            
            data = response.json()
            episodes = []
            
            for item in data.get('Items', []):
                episode = MediaItem(
                    id=item['Id'],
                    name=item['Name'],
                    type=item['Type'],
                    year=item.get('ProductionYear'),
                    overview=item.get('Overview', ''),
                    duration=item.get('RunTimeTicks', 0) // 10_000_000 if item.get('RunTimeTicks') else None,
                    season_number=item.get('ParentIndexNumber'),
                    episode_number=item.get('IndexNumber'),
                    series_id=item.get('SeriesId'),
                    parent_id=season_id
                )
                episodes.append(episode)
            
            # Sort by episode number
            episodes.sort(key=lambda x: x.episode_number or 0)
            return episodes
            
        except httpx.HTTPError as e:
            raise Exception(f"Network error: {e}")
        except Exception as e:
            raise Exception(f"Error getting episodes: {e}")
    
    async def get_episode_stream_info(self, episode_id: str) -> Dict:
        """Get stream information for an episode (same as get_stream_info but more explicit)"""
        return await self.get_stream_info(episode_id)
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()