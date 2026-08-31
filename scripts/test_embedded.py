import yt_dlp

clients = [
    ["android_embedded"],
    ["web_embedded"],
    ["safari"],
    ["web_creator"],
    ["mweb", "android_embedded"]
]

for cl in clients:
    print(f"Testing {cl}...")
    ydl_opts = {
        "format": "best[height<=1080][ext=mp4]/best",
        "outtmpl": "assets/backgrounds/orbital_gameplay_%(id)s.%(ext)s",
        "quiet": True,
        "extractor_args": {"youtube": {"player_client": cl}}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.youtube.com/watch?v=P9Xlr1BOByw"])
        print(f"SUCCESS with {cl}!")
        break
    except Exception as e:
        print(f"Failed with {cl}: {e}")
