import subprocess, imageio_ffmpeg, os

ff = imageio_ffmpeg.get_ffmpeg_exe()
work_dir = "checkpoint/test_fade_card"
os.makedirs(work_dir, exist_ok=True)
card0 = os.path.abspath("checkpoint/reddit_compilations/compilation_20min_1788179467/card_ch_01.png")
card1 = os.path.abspath("checkpoint/reddit_compilations/compilation_20min_1788179467/card_ch_02.png")
bg = os.path.abspath("assets/backgrounds/orbital_horizontal_u7ieZtmf_qg.mp4")

# Testando overlay de múltiplos cards estáticos com -loop 1
cmd = [
    ff, "-y",
    "-stream_loop", "-1", "-i", bg,
    "-loop", "1", "-i", card0,
    "-loop", "1", "-i", card1,
    "-filter_complex", (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=60[bg];"
        "[1:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[c0];"
        "[2:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[c1];"
        "[bg][c0]overlay=0:0:enable='between(t,0,5)'[v1];"
        "[v1][c1]overlay=0:0:enable='between(t,6,11)'[vout]"
    ),
    "-map", "[vout]",
    "-t", "12.0",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-pix_fmt", "yuv420p",
    "checkpoint/test_fade_card/out.mp4"
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", res.returncode)
if res.returncode != 0:
    print("Error:", res.stderr[-500:])
else:
    print("SUCCESS! Multicard size:", os.path.getsize("checkpoint/test_fade_card/out.mp4"))
