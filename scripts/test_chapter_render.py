import subprocess, imageio_ffmpeg, os

ff = imageio_ffmpeg.get_ffmpeg_exe()
work_dir = "checkpoint/reddit_compilations/compilation_20min_1788179721"
card1 = os.path.join(work_dir, "card_ch_01.png")
audio1 = os.path.join(work_dir, "audio_ch_01.mp3")
bg = "assets/backgrounds/orbital_horizontal_u7ieZtmf_qg.mp4"
out_ch1 = os.path.join(work_dir, "test_ch1.mp4")

# Cria legenda curta para o capítulo 1
from src.reddit_subtitles import generate_reddit_ass_subtitles
from src.reddit_render import render_reddit_story_video

print("Testing Chapter 1 isolated render...")
ass_ch1 = os.path.join(work_dir, "subtitles_ch_01.ass")
ok, path = render_reddit_story_video(
    audio_path=audio1,
    ass_subtitles_path=ass_ch1,
    card_png_path=card1,
    output_video_path=out_ch1,
    background_video_path=bg,
    aspect_ratio="16:9"
)
print("Chapter 1 render result:", ok, path, "Size:", os.path.getsize(out_ch1) if os.path.exists(out_ch1) else 0)
