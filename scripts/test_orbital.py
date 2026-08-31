import yt_dlp
import json

ydl_opts = {
    'quiet': False,
    'extract_flat': True,
    'playlistend': 10
}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info('https://www.youtube.com/@OrbitalNCG/videos', download=False)
        entries = info.get('entries', [])
        print(f"Found {len(entries)} videos on @OrbitalNCG:")
        for e in entries[:10]:
            print(f"- Title: {e.get('title')} | ID: {e.get('id')}")
except Exception as e:
    print("Error extracting channel info:", e)
