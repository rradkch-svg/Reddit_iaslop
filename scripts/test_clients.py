import yt_dlp

clients_to_test = [
    {"player_client": ["ios"]},
    {"player_client": ["tv"]},
    {"player_client": ["mweb"]},
    {"player_client": ["android_vr"]}
]

for c in clients_to_test:
    print(f"Testing client {c}...")
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": "assets/backgrounds/test_orbital.%(ext)s",
        "quiet": True,
        "extractor_args": {"youtube": c}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.youtube.com/watch?v=P9Xlr1BOByw"])
        print(f"SUCCESS with {c}!")
        break
    except Exception as e:
        print(f"Failed with {c}: {e}")
