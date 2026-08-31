import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broll_engine import BRollEngine, find_cookie_file


class TestBRollCookies(unittest.TestCase):
    """Testes unitarios para deteccao e injecao de cookies no yt-dlp."""

    def test_find_cookie_file_env_var(self):
        """Verifica se find_cookie_file respeita a variavel de ambiente YOUTUBE_COOKIES_PATH."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            tf.write(b"# Netscape HTTP Cookie File\n.youtube.com TRUE / FALSE 1700000000 TEST value\n")
            temp_cookie_path = tf.name

        try:
            with patch.dict(os.environ, {"YOUTUBE_COOKIES_PATH": temp_cookie_path}):
                found = find_cookie_file()
                self.assertIsNotNone(found)
                self.assertEqual(os.path.abspath(found), os.path.abspath(temp_cookie_path))
        finally:
            if os.path.exists(temp_cookie_path):
                os.remove(temp_cookie_path)

    def test_find_cookie_file_none_when_empty(self):
        """Verifica se find_cookie_file retorna None quando nenhum arquivo existe."""
        with patch.dict(os.environ, {"YOUTUBE_COOKIES_PATH": "non_existent_cookie_file_12345.txt", "COOKIES_PATH": ""}):
            with patch("os.path.isfile", return_value=False):
                found = find_cookie_file()
                self.assertIsNone(found)

    def test_find_cookie_file_root_detection(self):
        """Verifica deteccao automatica do arquivo cookies.txt na raiz do projeto."""
        root_cookie = os.path.join(PROJECT_ROOT, "cookies_test_fixture.txt")
        with open(root_cookie, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")

        orig_join = os.path.join
        try:
            with patch("broll_engine.os.path.join", side_effect=lambda *args: root_cookie if "cookies.txt" in args else orig_join(*args)):
                found = find_cookie_file()
                self.assertIsNotNone(found)
        finally:
            if os.path.exists(root_cookie):
                os.remove(root_cookie)

    def test_find_cookie_file_cookies2_detection(self):
        """Verifica deteccao automatica do arquivo cookies2.txt na raiz do projeto."""
        root_cookie2 = os.path.join(PROJECT_ROOT, "cookies2_test_fixture.txt")
        with open(root_cookie2, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")

        orig_join = os.path.join
        try:
            with patch("broll_engine.os.path.join", side_effect=lambda *args: root_cookie2 if "cookies2.txt" in args else ("non_existent_123.txt" if "cookies.txt" in args else orig_join(*args))):
                found = find_cookie_file()
                self.assertIsNotNone(found)
        finally:
            if os.path.exists(root_cookie2):
                os.remove(root_cookie2)


    def test_broll_search_injects_cookiefile(self):
        """Verifica se ydl_opts_search e ydl_opts_download recebem cookiefile quando configurado."""
        engine = BRollEngine(max_search_results=2)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            tf.write(b"# Netscape HTTP Cookie File\n.youtube.com TRUE / FALSE 1700000000 TEST value\n")
            temp_cookie_path = tf.name

        try:
            with patch("broll_engine.find_cookie_file", return_value=temp_cookie_path):
                with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
                    mock_ydl_instance = MagicMock()
                    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl_instance
                    mock_ydl_instance.extract_info.return_value = {"entries": []}

                    engine.search_and_download_clip(
                        query="test acceleration",
                        target_duration=3.0,
                        seen_ids=set(),
                        output_clip_path="dummy_output.mp4"
                    )

                    # Verificar se YoutubeDL foi instanciado com cookiefile
                    self.assertTrue(mock_ydl_cls.called)
                    call_opts = mock_ydl_cls.call_args[0][0]
                    self.assertEqual(call_opts.get("cookiefile"), temp_cookie_path)
        finally:
            if os.path.exists(temp_cookie_path):
                os.remove(temp_cookie_path)


if __name__ == "__main__":
    unittest.main()
