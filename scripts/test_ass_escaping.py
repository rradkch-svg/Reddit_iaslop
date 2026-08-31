import subprocess, imageio_ffmpeg, os

ff = imageio_ffmpeg.get_ffmpeg_exe()

# Cria um arquivo ASS de teste
os.makedirs("checkpoint/test_ass", exist_ok=True)
ass_file = os.path.abspath("checkpoint/test_ass/test.ass")
with open(ass_file, "w", encoding="utf-8") as f:
    f.write("""[Script Info]
Title: Test
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,2,2,40,40,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,TEST SUBTITLE
""")

formats_to_test = [
    f"ass=filename='{ass_file.replace(chr(92), '/').replace(':', chr(92)+':')}'",
    f"ass='{ass_file.replace(chr(92), '/').replace(':', chr(92)+':')}'",
    f"subtitles='{ass_file.replace(chr(92), '/').replace(':', chr(92)+':')}'",
    f"ass=filename='{ass_file.replace(chr(92), '/')}'"
]

for fmt in formats_to_test:
    print("Testing:", fmt)
    cmd = [
        ff, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=1",
        "-vf", fmt,
        "checkpoint/test_ass/out.mp4"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("SUCCESS with:", fmt)
        break
    else:
        print("FAILED:", res.stderr[-200:].strip())
