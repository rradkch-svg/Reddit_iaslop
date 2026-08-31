import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents import ProposerAgent, DirectorAgent, ReviewerAgent
from audio import AudioEngine
from subtitles import convert_words_to_ass
from render import assemble_multi_scene_video

class TestBackendUnit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    @patch("agents.generate_with_resilience")
    def test_proposer_agent_unit(self, mock_gen):
        mock_gen.return_value = '[{"tema": "Ferrari F40: A Bruta Engenharia dos Turbos Duplos", "hook": "Teste", "descricao": "Desc", "tags": ["#F40"], "explicacao_tecnica": "Tech"}]'
        proposer = ProposerAgent()
        topics = proposer.generate_topics(count=1)
        self.assertIsInstance(topics, list)
        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]["tema"], "Ferrari F40: A Bruta Engenharia dos Turbos Duplos")

    @patch("agents.generate_with_resilience")
    def test_director_agent_unit(self, mock_gen):
        mock_gen.return_value = '{"cenas": [{"scene_id": 1, "fala": "Fala 1", "youtube_query": "Ferrari F40 pure sound 4k", "duracao_estimada": 3.0}]}'
        director = DirectorAgent()
        cenas = director.generate_storyboard({"tema": "Ferrari F40", "hook": "Hook"})
        self.assertIsInstance(cenas, list)
        self.assertEqual(len(cenas), 1)
        self.assertIn("Ferrari F40", cenas[0]["youtube_query"])

    def test_subtitles_ass_generation(self):
        words_timing = [
            {"word": "Motor", "start": 0.0, "end": 0.5},
            {"word": "V10", "start": 0.5, "end": 1.0}
        ]
        ass_path = os.path.join(self.temp_dir, "test.ass")
        convert_words_to_ass(words_timing, ass_path, highlight_color="FFE500")
        self.assertTrue(os.path.exists(ass_path))
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[Events]", content)
        self.assertIn("MOTOR", content)

if __name__ == "__main__":
    unittest.main()
