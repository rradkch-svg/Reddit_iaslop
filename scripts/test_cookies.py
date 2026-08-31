import yt_dlp

for browser in ["edge", "chrome", "firefox", "brave", "opera"]:
    print(f"Trying cookies from {browser}...")
    ydl_opts = {
        "format": "best[height<=1080][ext=mp4]/best",
        "outtmpl": "assets/backgrounds/orbital_gameplay_%(id)s.%(ext)s",
        "cookiesfrombrowser": (browser, None, None, None),
        "quiet": True,
        "noplaylist": True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.youtube.com/watch?v=P9Xlr1BOByw"])
        print(f"SUCCESS downloading with {browser} cookies!")
        break
    except Exception as e:
        print(f"Failed with {browser}: {e}")
