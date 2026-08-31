import os
import tempfile
import unittest
import subprocess
from PIL import Image
from src.reddit_visuals import RedditVisualEngine
from src.reddit_render import render_reddit_story_video, find_ffmpeg_binary
from src.reddit_audio import RedditAudioEngine
from src.reddit_subtitles import generate_reddit_ass_subtitles

class TestRedditCardOverlay(unittest.TestCase):
    def test_reddit_card_render_and_ffmpeg_overlay(self):
        """
        Testa a geração do Card do Reddit e sua sobreposição via FFmpeg.
        Verifica com receipts-first que o frame aos 2 segundos possui o Card visível.
        """
        ffmpeg_bin = find_ffmpeg_binary()
        ve = RedditVisualEngine()
        with tempfile.TemporaryDirectory() as tmp_dir:
            card_info = {
                "channel_name": "Reddit Minute",
                "score": "45.2k",
                "display_title": "Manager ordered me to strictly obey handbook rules"
            }

            # 1. Renderizar card PNG com canal "Reddit Minute" e icon.jpg
            card_png = os.path.join(tmp_dir, "test_card_9x16.png")
            ve.render_reddit_card(card_info, card_png, aspect_ratio="9:16")
            self.assertTrue(os.path.exists(card_png))
            self.assertGreater(os.path.getsize(card_png), 10000)

            # Valida que o card renderiza corretamente em 16:9 também
            card_16x9_png = os.path.join(tmp_dir, "test_card_16x9.png")
            ve.render_reddit_card(card_info, card_16x9_png, aspect_ratio="16:9")
            self.assertTrue(os.path.exists(card_16x9_png))
            self.assertGreater(os.path.getsize(card_16x9_png), 10000)

            # 2. Gerar áudio curto de teste
            audio_engine = RedditAudioEngine()
            audio_path = os.path.join(tmp_dir, "test_audio.mp3")
            text = "Manager ordered me to follow the handbook to the letter. So I let the production floor stop."
            words_timing = audio_engine.generate_speech(text, audio_path)
            self.assertTrue(os.path.exists(audio_path))

            # 3. Gerar legendas ASS
            ass_path = os.path.join(tmp_dir, "test_subs.ass")
            generate_reddit_ass_subtitles(words_timing, ass_path, aspect_ratio="9:16")
            self.assertTrue(os.path.exists(ass_path))

            # 4. Renderizar vídeo de teste
            out_video = os.path.join(tmp_dir, "test_rendered_video.mp4")
            ok, msg = render_reddit_story_video(
                audio_path=audio_path,
                ass_subtitles_path=ass_path,
                card_png_path=card_png,
                output_video_path=out_video,
                aspect_ratio="9:16",
                card_duration_sec=4.8
            )
            self.assertTrue(ok, f"Falha na renderização: {msg}")
            self.assertTrue(os.path.exists(out_video))

            # 5. Extrair frame aos 2.0s e verificar presença do Card do Reddit
            frame_png = os.path.join(tmp_dir, "frame_at_2s.png")
            cmd_extract = [
                ffmpeg_bin, "-y",
                "-ss", "2.0",
                "-i", out_video,
                "-vframes", "1",
                frame_png
            ]
            subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertTrue(os.path.exists(frame_png))

            im = Image.open(frame_png)
            extrema = im.getextrema()
            max_val = max(c[1] if isinstance(c, tuple) else c for c in extrema)
            self.assertGreater(max_val, 200, "O Card do Reddit não apareceu no vídeo aos 2 segundos!")

    def test_chunk_rendering_without_card_overlay(self):
        """Verifica que chunks de capitulos (Part 2+) renderizam limpos sem card overlay."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_engine = RedditAudioEngine()
            audio_path = os.path.join(tmp_dir, "test_chunk_audio.mp3")
            text = "The second phase of the directive unfolded with complete precision."
            words_timing = audio_engine.generate_speech(text, audio_path)

            ass_path = os.path.join(tmp_dir, "test_chunk_subs.ass")
            generate_reddit_ass_subtitles(words_timing, ass_path, aspect_ratio="16:9")

            out_video = os.path.join(tmp_dir, "test_chunk_video.mp4")
            ok, msg = render_reddit_story_video(
                audio_path=audio_path,
                ass_subtitles_path=ass_path,
                card_png_path=None,
                output_video_path=out_video,
                video_type="chunk",
                aspect_ratio="16:9",
                card_duration_sec=0.0
            )
            self.assertTrue(ok, f"Falha na renderização de chunk: {msg}")
            self.assertTrue(os.path.exists(out_video))

if __name__ == "__main__":
    unittest.main()
