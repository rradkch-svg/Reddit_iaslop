import subprocess, imageio_ffmpeg, os

ff = imageio_ffmpeg.get_ffmpeg_exe()
work_dir = "checkpoint/reddit_compilations/compilation_20min_1788179579"
audio = os.path.join(work_dir, "master_narration_20min.mp3")
ass = os.path.join(work_dir, "compilation_subtitles.ass")
bg = "assets/backgrounds/orbital_horizontal_u7ieZtmf_qg.mp4"
card0 = os.path.join(work_dir, "card_ch_01.png")

safe_ass = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")

cmd = [
    ff, "-y",
    "-stream_loop", "-1", "-i", bg,
    "-i", audio,
    "-loop", "1", "-i", card0,
    "-filter_complex", f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=60[bg];[2:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[c0];[bg][c0]overlay=0:0:enable='between(t,0,5)'[v1];[v1]ass=filename='{safe_ass}'[vout]",
    "-map", "[vout]",
    "-map", "1:a",
    "-t", "5.0",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "checkpoint/test_sub_debug.mp4"
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", res.returncode)
if res.returncode != 0:
    print("Stderr:", res.stderr[-800:])
else:
    print("Success! Subtitle output created. Size:", os.path.getsize("checkpoint/test_sub_debug.mp4"))
