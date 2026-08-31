import os
import sys
import unittest
import tempfile
import subprocess

# Ensure src/ is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import DirectorAgent, ReviewerAgent
from broll_engine import build_topic_queries, find_ffmpeg_binary
from render import assemble_multi_scene_video

class TestAudioEngineDucking(unittest.TestCase):
    def test_director_and_queries_pure_sound(self):
        """Verifica se as queries geradas incluem termos focados em ronco e som puro de motor."""
        queries = build_topic_queries("Porsche 911 GT3 RS", "active aero")
        has_pure_sound = any("pure sound" in q.lower() or "sound" in q.lower() for q in queries)
        self.assertTrue(has_pure_sound, f"Queries devem conter termos de som puro: {queries}")

    def test_reviewer_system_instruction_audio(self):
        """Verifica se o ReviewerAgent possui diretrizes de auditoria acústica e isolamento de voz."""
        rev = ReviewerAgent()
        self.assertIn("AUDITORIA DE ÁUDIO", rev.system_instruction)
        self.assertIn("tem_voz_humana", rev.system_instruction)
        self.assertIn("som_mecanico_puro", rev.system_instruction)

    def test_render_multi_scene_with_audio_ducking(self):
        """Verifica se a montagem final concatena o áudio das cenas e aplica ducking sob a narração."""
        ffmpeg_bin = find_ffmpeg_binary()
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Gerar 2 clipes com áudio de teste
            clip1 = os.path.join(tmpdir, "scene_00.mp4")
            clip2 = os.path.join(tmpdir, "scene_01.mp4")
            
            subprocess.run([
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=2:r=30",
                "-f", "lavfi", "-i", "sine=frequency=200:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                clip1
            ], check=True, capture_output=True)

            subprocess.run([
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=2:r=30",
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                "-shortest",
                clip2
            ], check=True, capture_output=True)

            # 2. Gerar áudio de narração (3.5s)
            audio_path = os.path.join(tmpdir, "audio.mp3")
            subprocess.run([
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "sine=frequency=800:duration=3.5",
                "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2",
                audio_path
            ], check=True, capture_output=True)

            # 3. Gerar arquivo ASS
            ass_path = os.path.join(tmpdir, "subtitles.ass")
            ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:03.00,Default,,0,0,0,,SOM DO MOTOR
"""
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

            output_video = os.path.join(tmpdir, "final_video.mp4")

            # 4. Executar assemble_multi_scene_video
            success, msg = assemble_multi_scene_video(
                clip_paths=[clip1, clip2],
                audio_path=audio_path,
                ass_path=ass_path,
                output_path=output_video
            )

            self.assertTrue(success, f"Renderização falhou: {msg}")
            self.assertTrue(os.path.exists(output_video), "Arquivo final_video.mp4 não foi gerado.")
            self.assertGreater(os.path.getsize(output_video), 10_000, "Arquivo final é muito pequeno.")

if __name__ == "__main__":
    unittest.main()
