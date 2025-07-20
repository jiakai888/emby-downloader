# Emby URL Extractor

A command-line tool for extracting high-quality streaming URLs from Emby servers.

## Features

- 🔐 **Secure Authentication** - Connect to any Emby server with username/password
- 🔍 **Smart Search** - Search by title or direct item ID
- 🎯 **Quality Selection** - Automatically selects highest quality video stream
- 🎵 **Audio Track Selection** - Choose from available audio tracks
- 📝 **Subtitle Support** - Select multiple subtitle languages
- ⬇️ **Optional Download** - Download content directly or save URLs for later
- 🌐 **Cross-Platform** - Works on Windows, macOS, and Linux

## Installation

### Using uv (recommended)
```bash
cd emby-url-extractor
uv pip install -r requirements.txt
```

### Using pip
```bash
cd emby-url-extractor
pip install -r requirements.txt
```

## Usage

Simply run the main script:

```bash
python main.py
```

The tool will guide you through an interactive process:

1. **Server Connection**
   - Enter your Emby server URL (with port if needed)
   - Provide username and password
   - Confirm successful connection

2. **Content Search**
   - Search by movie/show name or exact ID
   - Select from search results

3. **Stream Selection**
   - Automatically selects highest quality video
   - Choose audio track (if multiple available)
   - Select subtitle languages

4. **Output Options**
   - View generated streaming URLs
   - Download content directly
   - Save URLs to text file

## Example Usage

```
$ python main.py

╭─────────────────────────────────────────╮
│ Emby URL Extractor                      │
│ Extract high-quality streaming URLs     │
│ from Emby servers                       │
╰─────────────────────────────────────────╯

Server Connection
Enter Emby server URL (with port if not 80/443): https://emby.example.com:8096
Enter username: john_doe
Enter password: ********
✓ Login successful! Connected to: My Emby Server

Content Search
Enter movie/show name or ID: avengers

Found 3 result(s):
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┳━━━━━━━━━┓
┃ # ┃ Title                 ┃ Type  ┃ Year ┃ ID      ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━╇━━━━━━━━━┩
│ 1 │ Avengers: Endgame     │ Movie │ 2019 │ 12345   │
│ 2 │ The Avengers          │ Movie │ 2012 │ 12346   │
│ 3 │ Avengers: Infinity... │ Movie │ 2018 │ 12347   │
└───┴───────────────────────┴───────┴──────┴─────────┘

Select items (1-3, A for all, or comma-separated) [1]: 1

Processing: Avengers: Endgame
Selected quality: 4K UHD (3840x2160) @ 25.0 Mbps [H265]
Selected audio: English (5.1 Surround) [AC3]

Available subtitles:
┏━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ # ┃ Language ┃ Format ┃ Title   ┃
┡━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ 1 │ English  │ srt    │ Default │
│ 2 │ Spanish  │ srt    │ Default │
│ 3 │ None     │ -      │ No subs │
└───┴──────────┴────────┴─────────┘

Select subtitles (1-3, multiple allowed, comma-separated) [3]: 1

Generated URLs:

Video Stream:
https://emby.example.com:8096/Videos/12345/stream.mkv?api_key=xxx&VideoStreamIndex=0&AudioStreamIndex=0&Static=true

Subtitles:
English: https://emby.example.com:8096/Videos/12345/Subtitles/1/Stream.srt?api_key=xxx

╭─────────────────────────────────────────╮
│ Media Info                              │
│ Duration: 3h 1m                         │
│ File Size: ~11.2 GB                     │
│ Video: 4K UHD (3840x2160) @ 25.0 Mbps  │
│ Audio: English (5.1 Surround) [AC3]    │
╰─────────────────────────────────────────╯

Download now? [y/N]: n
Save URLs to file? [Y/n]: y
URLs saved to: emby_urls_20250720_143022.txt

All done!
```

## Dependencies

- **httpx** - Modern HTTP client for API communication
- **rich** - Beautiful terminal formatting and progress bars
- **click** - Command-line interface framework

## Features in Detail

### Automatic Quality Selection
The tool automatically selects the highest quality video stream based on:
1. Bitrate (primary factor)
2. Resolution (secondary)
3. Codec preference (H.265 > H.264)
4. Frame rate

### Audio Track Handling
- Displays all available embedded audio tracks
- Shows language, codec, and channel information
- Automatically selects first track if only one available

### Subtitle Support
- Supports multiple subtitle languages
- Handles both embedded and external subtitles
- Generates direct download URLs for subtitle files

### Download Integration
- Optional direct download with progress bars
- Automatic filename sanitization
- Subtitle files downloaded alongside video

## Troubleshooting

### Connection Issues
- Ensure the server URL includes the correct port
- Check if the server uses HTTPS or HTTP
- Verify username and password are correct

### No Results Found
- Try searching with partial titles
- Use the exact item ID from the web interface
- Check if your account has access to the content

### Stream Errors
- Some content may require transcoding
- Check server permissions and user access rights
- Verify the content isn't corrupted on the server

## License

This project is for educational purposes. Please respect content licensing and server terms of service.