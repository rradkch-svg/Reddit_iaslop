import subprocess, imageio_ffmpeg, os

ff = imageio_ffmpeg.get_ffmpeg_exe()
work_dir = "checkpoint/reddit_compilations/compilation_20min_1788179464"
card0 = os.path.join(work_dir, "card_ch_01.png")
audio = os.path.join(work_dir, "master_narration_20min.mp3")
ass = os.path.join(work_dir, "compilation_subtitles.ass")
bg = "assets/backgrounds/orbital_horizontal_u7ieZtmf_qg.mp4"

safe_ass = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")

cmd = [
    ff, "-y",
    "-stream_loop", "-1", "-i", bg,
    "-i", audio,
    "-i", card0,
    "-filter_complex", f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=60[v_bg_scaled];[2:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[card0];[v_bg_scaled][card0]overlay=0:0:enable='between(t,0,5)'[v_over];[v_over]ass=filename='{safe_ass}'[vout]",
    "-map", "[vout]",
    "-map", "1:a",
    "-t", "10.0",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-r", "60",
    "checkpoint/test_comp_debug.mp4"
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", res.returncode)
if res.returncode != 0:
    print("FFmpeg Error:", res.stderr[-800:])
else:
    print("Success! Size:", os.path.getsize("checkpoint/test_comp_debug.mp4"))
