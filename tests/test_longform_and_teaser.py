import os
import tempfile
import unittest
import json
from src.reddit_agents import RedditStoryDirectorAgent
from src.reddit_visuals import RedditVisualEngine
from src.reddit_render import render_reddit_story_video, find_ffmpeg_binary
from src.reddit_pipeline import generate_teaser_short_video
from src.reddit_longform import generate_25min_single_story_video

class TestLongformAndTeaser(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sample_story = {
            "title": "Manager ordered strict compliance with handbook. Cost company $42,000.",
            "author": "u/ComplianceMaster",
            "subreddit": "r/maliciouscompliance",
            "score": "45.2k",
            "body": "My manager ordered that no worker shall touch or inspect equipment outside shift hours. On Friday 4:59 PM the cooling system failed. I clocked out. By Saturday morning emergency repairs cost $42k."
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_30min_story_expansion_and_teaser_structure(self):
        """Verifica a expansao da historia unica em 10 capitulos e a geracao do teaser short com gancho final."""
        director = RedditStoryDirectorAgent(api_keys=[])
        data = director._generate_algorithmic_30min_story(self.sample_story, target_minutes=30.0)

        # 1. Verifica 10 capitulos
        chapters = data.get("chapters", [])
        self.assertEqual(len(chapters), 10)
        
        total_words = sum(len(ch["narration_text"].split()) for ch in chapters)
        self.assertGreaterEqual(total_words, 5000)

        # 2. Verifica estrutura do Teaser Short
        teaser = data.get("teaser_short", {})
        self.assertTrue(isinstance(teaser, dict))
        self.assertIn("script", teaser)
        self.assertIn("final_hook_text", teaser)
        self.assertIn("👉 FULL 30-MIN SAGA", teaser["final_hook_text"])
        self.assertIn("final_hook_spoken_cta", teaser)

    def test_final_hook_badge_rendering(self):
        """Verifica renderizacao do banner visual de Gancho Final em 9:16 e 16:9."""
        engine = RedditVisualEngine()
        
        # 9:16
        out_9x16 = os.path.join(self.test_dir, "badge_9x16.png")
        engine.render_final_hook_badge("👉 FULL 25-MIN SAGA ON CHANNEL 🔗", out_9x16, aspect_ratio="9:16")
        self.assertTrue(os.path.exists(out_9x16))
        self.assertGreater(os.path.getsize(out_9x16), 5000)

        # 16:9
        out_16x9 = os.path.join(self.test_dir, "badge_16x9.png")
        engine.render_final_hook_badge("👉 FULL 25-MIN SAGA ON CHANNEL 🔗", out_16x9, aspect_ratio="16:9")
        self.assertTrue(os.path.exists(out_16x9))
        self.assertGreater(os.path.getsize(out_16x9), 5000)

if __name__ == "__main__":
    unittest.main()
