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

from broll_engine import BRollEngine, get_video_resolution, get_video_duration


class TestBRollTwoStageDownload(unittest.TestCase):
    """Testes unitários para o pipeline de download em duas etapas e limites de resolução."""

    def test_get_video_resolution_success(self):
        """Verifica se get_video_resolution extrai largura e altura via ffprobe."""
        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "1920x1080\n"
            mock_res.returncode = 0
            mock_run.return_value = mock_res

            res = get_video_resolution("dummy.mp4")
            self.assertEqual(res, (1920, 1080))

    def test_get_video_resolution_failure(self):
        """Verifica se get_video_resolution lida graciosamente com falhas de subprocess."""
        with patch("subprocess.run", side_effect=Exception("ffprobe not found")):
            res = get_video_resolution("dummy.mp4")
            self.assertIsNone(res)

    def test_preview_download_format_and_rejection_skips_hd(self):
        """
        Verifica se a etapa 1 baixa a prévia em baixa resolução (<=360p) e se,
        quando o Reviewer reprova o vídeo, o download HD (720p-1080p) NÃO é chamado.
        """
        engine = BRollEngine(max_search_results=2)
        reviewer_mock = MagicMock()
        reviewer_mock.pre_filter_title.return_value = (True, "OK")
        # Reviewer rejeita a prévia
        reviewer_mock.inspect_clip.return_value = {
            "aprovado": False,
            "descartar_video_inteiro": True,
            "score": 2.0,
            "motivo": "Outro veículo completamente diferente"
        }

        with patch("broll_engine.build_topic_queries", return_value=["Ferrari acceleration"]), \
             patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
             patch("broll_engine.get_video_duration", return_value=10.0), \
             patch("subprocess.run") as mock_subproc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=5000):

            mock_search_ydl = MagicMock()
            mock_search_ydl.extract_info.return_value = {
                "entries": [{"id": "vid123", "title": "Ferrari Test Drive", "duration": 60}]
            }

            mock_preview_ydl = MagicMock()

            # ydl instantiation sequence: 1st search, 2nd preview download
            mock_ydl_cls.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_search_ydl)),
                MagicMock(__enter__=MagicMock(return_value=mock_preview_ydl)),
            ]

            success, out_path, v_id, v_title, audit = engine.search_and_download_clip(
                query="Ferrari acceleration",
                target_duration=3.0,
                seen_ids=set(),
                output_clip_path="out.mp4",
                global_topic="Ferrari",
                reviewer_agent=reviewer_mock
            )

            # O vídeo deve ser reprovado
            self.assertFalse(success)

            # YoutubeDL deve ter sido chamado exatamente 2 vezes (1 para busca, 1 para prévia)
            # e NUNCA uma 3ª vez para HD!
            self.assertEqual(mock_ydl_cls.call_count, 2)

            preview_opts = mock_ydl_cls.call_args_list[1][0][0]
            self.assertIn("height<=360", preview_opts.get("format", ""))
            self.assertNotIn("height<=2160", preview_opts.get("format", ""))
            self.assertNotIn("height>=720", preview_opts.get("format", ""))

    def test_preview_approval_triggers_hd_download_in_720p_1080p_range(self):
        """
        Verifica se, após a prévia ser aprovada, o motor baixa a versão HD
        com filtro restrito entre 720p e 1080p (sem ultrapassar 1080p e sem aceitar abaixo de 720p).
        """
        engine = BRollEngine(max_search_results=2)
        reviewer_mock = MagicMock()
        reviewer_mock.pre_filter_title.return_value = (True, "OK")
        # Reviewer aprova a prévia
        reviewer_mock.inspect_clip.return_value = {
            "aprovado": True,
            "descartar_video_inteiro": False,
            "score": 9.0,
            "tem_voz_humana": False,
            "som_mecanico_puro": True,
            "motivo": "Excelente tomada da Ferrari"
        }

        with patch("broll_engine.build_topic_queries", return_value=["Ferrari sound"]), \
             patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
             patch("broll_engine.get_video_duration", return_value=15.0), \
             patch("broll_engine.get_video_resolution", return_value=(1920, 1080)), \
             patch("subprocess.run") as mock_subproc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=5000), \
             patch("os.rename") as mock_rename:

            mock_search_ydl = MagicMock()
            mock_search_ydl.extract_info.return_value = {
                "entries": [{"id": "vid999", "title": "Ferrari Sound 4K", "duration": 60}]
            }
            mock_preview_ydl = MagicMock()
            mock_hd_ydl = MagicMock()

            mock_ydl_cls.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_search_ydl)),
                MagicMock(__enter__=MagicMock(return_value=mock_preview_ydl)),
                MagicMock(__enter__=MagicMock(return_value=mock_hd_ydl)),
            ]

            success, out_path, v_id, v_title, audit = engine.search_and_download_clip(
                query="Ferrari sound",
                target_duration=3.0,
                seen_ids=set(),
                output_clip_path="final_clip.mp4",
                global_topic="Ferrari",
                reviewer_agent=reviewer_mock
            )

            self.assertTrue(success)
            self.assertEqual(v_id, "vid999")
            self.assertEqual(mock_ydl_cls.call_count, 3)

            # Verificar opções do download HD com preferência a 60fps e limite 720p-1080p
            hd_opts = mock_ydl_cls.call_args_list[2][0][0]
            hd_format = hd_opts.get("format", "")
            self.assertIn("height<=1080", hd_format)
            self.assertIn("height>=720", hd_format)
            self.assertIn("fps>=50", hd_format)
            self.assertNotIn("height<=2160", hd_format)
            self.assertNotIn("height<=1440", hd_format)
            self.assertEqual(hd_opts.get("format_sort"), ["fps:60", "res:1080", "codec:h264"])

    def test_hd_discarded_when_resolution_below_720p(self):
        """
        Verifica se um vídeo é descartado se a versão HD baixada tiver resolução menor que 720p.
        """
        engine = BRollEngine(max_search_results=2)
        reviewer_mock = MagicMock()
        reviewer_mock.pre_filter_title.return_value = (True, "OK")
        reviewer_mock.inspect_clip.return_value = {
            "aprovado": True,
            "score": 8.0,
            "motivo": "OK na prévia"
        }

        with patch("broll_engine.build_topic_queries", return_value=["Old race video"]), \
             patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
             patch("broll_engine.get_video_duration", return_value=15.0), \
             patch("broll_engine.get_video_resolution", return_value=(640, 480)), \
             patch("subprocess.run") as mock_subproc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=5000):

            mock_search_ydl = MagicMock()
            mock_search_ydl.extract_info.return_value = {
                "entries": [{"id": "vid_lowres", "title": "Old 480p Video", "duration": 60}]
            }
            mock_preview_ydl = MagicMock()
            mock_hd_ydl = MagicMock()

            mock_ydl_cls.side_effect = [
                MagicMock(__enter__=MagicMock(return_value=mock_search_ydl)),
                MagicMock(__enter__=MagicMock(return_value=mock_preview_ydl)),
                MagicMock(__enter__=MagicMock(return_value=mock_hd_ydl)),
            ]

            success, out_path, v_id, v_title, audit = engine.search_and_download_clip(
                query="Old race video",
                target_duration=3.0,
                seen_ids=set(),
                output_clip_path="final_clip.mp4",
                global_topic="Corrida",
                reviewer_agent=reviewer_mock
            )

            # Como a resolução efetiva foi 480p (< 720p), deve descartar
            self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
