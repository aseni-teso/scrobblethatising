# ScrobbleThatISing

ScrobbleThatISing is a scrobbler for guitarists, providing an amazing opportunity to scrobble what you play and sing on Last.fm. The program also displays chords for the songs being played by the musician.

## Features
- Scrobble music on Last.fm
- Display chords for played songs
- Search and play tracks
- Find similar tracks and artists
- Authenticate and save session key for API access

## Requirements
- Python 3.x
- Install the following dependencies:
  - `requests`
  - `configparser`
  - `pylast`
  - `beautifulsoup4`
  - `transliterate`
  - `pydoc`
  - `python-dotenv`

You can install these dependencies using `pip`:
```bash
pip install requests configparser pylast beautifulsoup4 transliterate pydoc python-dotenv
```

## Usage
1. Set up your Last.fm API key and secret in a `.env` file.
2. Run the script with `python main.py -n "track_name"` to search and play a specific track or just `python main.py` to play random track from your library.
3. Follow the on-screen instructions to control playback and navigate through tracks.

## Additional Information
- The program uses the Last.fm API for music data retrieval.
- Make sure to grant necessary permissions for scrobbling tracks to your Last.fm account.
- Enjoy discovering and listening to music with ScrobbleThatISing!
