import os
import tempfile
import unittest
from PIL import Image

from src.pronunciation import phoneticize_reddit_text
from src.reddit_agents import RedditStoryDirectorAgent, ENGAGEMENT_QUESTIONS
from src.reddit_visuals import RedditVisualEngine
from src.reddit_subtitles import generate_reddit_ass_subtitles

class TestRedditMinuteEnhancements(unittest.TestCase):
    def test_reddit_phonetic_expansion(self):
        sample_1 = "AITA for telling my MIL that $45k was missing from the account?"
        result_1 = phoneticize_reddit_text(sample_1)
        self.assertNotIn("AITA", result_1)
        self.assertNotIn("MIL", result_1)
        self.assertIn("Am I the jerk", result_1)
        self.assertIn("mother-in-law", result_1)
        self.assertIn("45 thousand dollars", result_1)


        sample_2 = 'BIL and SIL told OP that DH was wrong. TL;DR at the bottom.'
        result_2 = phoneticize_reddit_text(sample_2)
        self.assertNotIn('BIL', result_2)
        self.assertNotIn('SIL', result_2)
        self.assertNotIn('DH', result_2)
        self.assertIn('brother-in-law', result_2)
        self.assertIn('sister-in-law', result_2)
        self.assertIn('husband', result_2)
        self.assertIn('the original poster', result_2)

    def test_reddit_card_header_with_anonymity_and_subreddit(self):
        ve = RedditVisualEngine()
        with tempfile.TemporaryDirectory() as tmp_dir:
            card_info = {
                'channel_name': 'Reddit Minute',
                'subreddit': 'r/maliciouscompliance',
                'score': '38.2k',
                'display_title': 'Boss demanded I follow handbook to the letter. It cost the company \,000.'
            }

            card_png_9x16 = os.path.join(tmp_dir, 'card_9x16.png')
            ve.render_reddit_card(card_info, card_png_9x16, aspect_ratio='9:16')
            self.assertTrue(os.path.exists(card_png_9x16))
            self.assertGreater(os.path.getsize(card_png_9x16), 15000)

            with Image.open(card_png_9x16) as img:
                self.assertEqual(img.size, (1080, 1920))
                self.assertEqual(img.mode, 'RGBA')

            card_png_16x9 = os.path.join(tmp_dir, 'card_16x9.png')
            ve.render_reddit_card(card_info, card_png_16x9, aspect_ratio='16:9')
            self.assertTrue(os.path.exists(card_png_16x9))
            self.assertGreater(os.path.getsize(card_png_16x9), 15000)

            with Image.open(card_png_16x9) as img:
                self.assertEqual(img.size, (1920, 1080))
                self.assertEqual(img.mode, 'RGBA')

    def test_reddit_director_fallback_script_structure(self):
        director = RedditStoryDirectorAgent()
        raw_post = {
            'title': 'Strict boss banned working from home. Server migration took 4 months instead of 2 days.',
            'subreddit': 'r/maliciouscompliance',
            'author': 'u/OriginalUser123',
            'score': '29.4k',
            'body': (
                'My manager announced no more remote work. I was the lead infrastructure architect. '
                'I packed my things and worked only strictly within business hours from the cubicle without VPN. '
                'When the datacenter migration locked up, nobody could assist on weekends. It cost them hundreds of thousands.'
            )
        }

        script = director._generate_algorithmic_fallback_script(raw_post)
        self.assertIn('title', script)
        self.assertIn('hook_text', script)
        self.assertIn('shorts_script', script)
        self.assertIn('longform_script', script)
        self.assertIn('ui_card', script)

        self.assertEqual(script['ui_card']['channel_name'], 'Reddit Minute')
        self.assertEqual(script['ui_card']['subreddit'], 'r/maliciouscompliance')
        self.assertIn('Strict boss', script['ui_card']['display_title'])

        shorts_txt = script['shorts_script']
        self.assertTrue(any(q in shorts_txt for q in ['comments below', 'verdict', 'what would you have done', 'in my situation', 'your thoughts']))

    def test_hormozi_ass_subtitles_formatting(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            ass_path = os.path.join(tmp_dir, 'test_hormozi.ass')
            words_timing = [
                {'word': 'My', 'start': 0.0, 'end': 0.2},
                {'word': 'corrupt', 'start': 0.2, 'end': 0.5},
                {'word': 'landlord', 'start': 0.5, 'end': 0.9},
                {'word': 'stole', 'start': 0.9, 'end': 1.2},
                {'word': 'the', 'start': 1.2, 'end': 1.4},
                {'word': 'deposit', 'start': 1.4, 'end': 1.8},
            ]

            success = generate_reddit_ass_subtitles(
                words_timing=words_timing,
                output_ass=ass_path,
                aspect_ratio='9:16',
                primary_color='FFFFFF',
                highlight_color='FFE500'
            )
            self.assertTrue(success)
            self.assertTrue(os.path.exists(ass_path))

            with open(ass_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.assertIn('[Script Info]', content)
            self.assertIn('PlayResX: 1080', content)
            self.assertIn('PlayResY: 1920', content)
            self.assertIn('HormoziDefault', content)
            self.assertIn('Dialogue:', content)
            self.assertIn('00E5FF', content)

if __name__ == '__main__':
    unittest.main()
