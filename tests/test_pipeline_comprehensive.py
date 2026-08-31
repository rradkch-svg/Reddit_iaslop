import os
import sys
import json
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

from agents import ProposerAgent, DirectorAgent
from subtitles import convert_words_to_ass

class TestPipelineComprehensive(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    @patch("agents.generate_with_resilience")
    def test_pipeline_proposal_and_storyboard(self, mock_gen):
        mock_gen.side_effect = [
            # Resposta do ProposerAgent
            '[{"tema": "SR-71 Blackbird: Os Motores J58 a Mach 3", "hook": "Voando no limite", "descricao": "Desc", "tags": ["#Blackbird"], "explicacao_tecnica": "Turbo-ramjet"}]',
            # Resposta do DirectorAgent
            '{"cenas": [{"scene_id": 1, "fala": "Fala 1", "youtube_query": "SR-71 Blackbird afterburner sound 4k", "duracao_estimada": 3.0}]}'
        ]
        proposer = ProposerAgent()
        topics = proposer.generate_topics(count=1)
        self.assertEqual(len(topics), 1)

        director = DirectorAgent()
        cenas = director.generate_storyboard(topics[0])
        self.assertEqual(len(cenas), 1)
        self.assertIn("SR-71", cenas[0]["youtube_query"])

    def test_subtitle_conversion(self):
        words = [
            {"word": "SR-71", "start": 0.0, "end": 0.6},
            {"word": "Blackbird", "start": 0.6, "end": 1.2}
        ]
        ass_file = os.path.join(self.temp_dir, "test.ass")
        ok = convert_words_to_ass(words, ass_file)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(ass_file))

if __name__ == "__main__":
    unittest.main()
