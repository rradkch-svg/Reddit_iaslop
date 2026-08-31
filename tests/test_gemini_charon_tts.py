import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# Ajusta caminhos
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio import AudioEngine, FALLBACK_VOICES
from auto_pipeline import AutoPipelineRunner

class TestGeminiCharonTTS(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_default_voice_is_gemini_charon(self):
        engine = AudioEngine()
        self.assertEqual(engine.voice, "gemini:Charon")
        self.assertEqual(FALLBACK_VOICES[0], "gemini:Charon")

    def test_auto_pipeline_defaults_to_gemini_charon(self):
        runner = AutoPipelineRunner(checkpoint_dir=self.temp_dir)
        self.assertEqual(runner.voice, "gemini:Charon")
        self.assertEqual(runner.audio_engine.voice, "gemini:Charon")

    @patch("audio.resolve_gemini_api_keys", return_value=["test_fake_api_key"])
    @patch("subprocess.run")
    @patch("google.genai.Client")
    def test_gemini_charon_synthesis_flow(self, mock_client_cls, mock_subprocess, mock_keys):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_inline_data = MagicMock()
        
        # 1 segundo de audio mono 16-bit 24kHz = 48000 bytes
        fake_pcm = b"\x00\x00" * 24000
        mock_inline_data.data = fake_pcm
        mock_part.inline_data = mock_inline_data
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        engine = AudioEngine(voice="gemini:Charon")
        output_mp3 = os.path.join(self.temp_dir, "test_charon.mp3")
        
        test_text = "O motor V10 do Lexus LFA gira a 9.000 RPM com som afinado pela Yamaha."
        success, words_timing = engine.generate_audio(test_text, output_mp3)
        
        self.assertTrue(success)
        self.assertIsInstance(words_timing, list)
        self.assertGreater(len(words_timing), 0)
        self.assertEqual(words_timing[0]["word"], "O")
        self.assertIn("start", words_timing[0])
        self.assertIn("end", words_timing[0])

if __name__ == "__main__":
    unittest.main()
