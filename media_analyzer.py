"""
Media Analyzer - Analyzes streams and selects optimal quality
"""

from typing import List, Dict, Optional
from emby_client import VideoStream, AudioStream, SubtitleStream

class MediaAnalyzer:
    """Analyzes media streams and selects optimal quality"""
    
    @staticmethod
    def select_best_video_stream(streams: List[VideoStream]) -> Optional[VideoStream]:
        """Select the highest quality video stream"""
        if not streams:
            return None
        
        # Sort by quality score (highest first)
        sorted_streams = sorted(streams, key=MediaAnalyzer.calculate_video_quality_score, reverse=True)
        return sorted_streams[0]
    
    @staticmethod
    def calculate_video_quality_score(stream: VideoStream) -> int:
        """Calculate quality score for video stream"""
        # Priority: bitrate > resolution > codec preference
        score = 0
        
        # Bitrate score (primary factor)
        score += stream.bitrate * 10
        
        # Resolution score
        score += (stream.width * stream.height) // 1000
        
        # Codec preference (H.265 > H.264 > others)
        codec_scores = {
            'hevc': 1000,
            'h265': 1000,
            'h264': 500,
            'avc': 500
        }
        codec_key = stream.codec.lower()
        score += codec_scores.get(codec_key, 0)
        
        # Framerate bonus
        if stream.framerate >= 60:
            score += 100
        elif stream.framerate >= 30:
            score += 50
        
        return score
    
    @staticmethod
    def parse_audio_tracks(stream_info: Dict) -> List[AudioStream]:
        """Parse audio track information from stream info"""
        return stream_info.get('audio_streams', [])
    
    @staticmethod
    def extract_subtitle_info(stream_info: Dict) -> List[SubtitleStream]:
        """Extract subtitle information from stream info"""
        return stream_info.get('subtitle_streams', [])
    
    @staticmethod
    def format_quality_info(stream: VideoStream) -> str:
        """Format video quality information for display"""
        resolution = f"{stream.width}x{stream.height}"
        bitrate_mbps = stream.bitrate / 1000000  # Convert to Mbps
        
        # Determine quality label
        if stream.height >= 2160:
            quality_label = "4K UHD"
        elif stream.height >= 1080:
            quality_label = "1080p"
        elif stream.height >= 720:
            quality_label = "720p"
        else:
            quality_label = f"{stream.height}p"
        
        return f"{quality_label} ({resolution}) @ {bitrate_mbps:.1f} Mbps [{stream.codec.upper()}]"
    
    @staticmethod
    def format_audio_info(stream: AudioStream) -> str:
        """Format audio stream information for display"""
        channels_str = f"{stream.channels}.1 Surround" if stream.channels > 2 else "Stereo"
        return f"{stream.language} ({channels_str}) [{stream.codec.upper()}]"
    
    @staticmethod
    def estimate_file_size(bitrate: int, duration: int) -> str:
        """Estimate file size based on bitrate and duration"""
        if not bitrate or not duration:
            return "Unknown"
        
        # Calculate size in bytes
        size_bytes = (bitrate * duration) // 8
        
        # Convert to human readable format
        if size_bytes >= 1024**3:  # GB
            return f"{size_bytes / (1024**3):.1f} GB"
        elif size_bytes >= 1024**2:  # MB
            return f"{size_bytes / (1024**2):.1f} MB"
        else:
            return f"{size_bytes / 1024:.1f} KB"