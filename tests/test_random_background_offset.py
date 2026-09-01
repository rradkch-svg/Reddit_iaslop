import os
import unittest
import tempfile
import subprocess
from src.reddit_render import render_reddit_story_video, find_ffmpeg_binary, get_best_orbital_background
from src.reddit_subtitles import generate_reddit_ass_subtitles

class TestRandomBackgroundOffset(unittest.TestCase):
    def test_render_with_random_start_offset(self):
        """Verifica que o render com minutagem aleatoria no video de fundo funciona perfeitamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ffmpeg_bin = find_ffmpeg_binary()
            audio_path = os.path.join(tmpdir, "test_audio.mp3")
            subprocess.run([
                ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "3.0", "-q:a", "9", "-acodec", "libmp3lame", audio_path
            ], check=True, capture_output=True)

            ass_path = os.path.join(tmpdir, "test.ass")
            words_timing = [
                {"word": "Test", "start": 0.0, "end": 1.0},
                {"word": "Random", "start": 1.0, "end": 2.0},
                {"word": "Background", "start": 2.0, "end": 3.0}
            ]
            generate_reddit_ass_subtitles(words_timing, ass_path, aspect_ratio="9:16")

            out_video = os.path.join(tmpdir, "test_random_out.mp4")
            bg_video = get_best_orbital_background("9:16")

            ok, msg = render_reddit_story_video(
                audio_path=audio_path,
                ass_subtitles_path=ass_path,
                card_png_path=None,
                output_video_path=out_video,
                background_video_path=bg_video,
                video_type="shorts",
                aspect_ratio="9:16"
            )

            self.assertTrue(ok, f"Falha na renderizacao com minutagem aleatoria: {msg}")
            self.assertTrue(os.path.exists(out_video), "Video de saida nao foi gerado.")
            self.assertGreater(os.path.getsize(out_video), 10000, "Video de saida esta vazio ou corrompido.")

if __name__ == "__main__":
    unittest.main()
