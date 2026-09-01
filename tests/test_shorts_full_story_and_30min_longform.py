import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from reddit_agents import RedditStoryDirectorAgent
from reddit_longform import generate_30min_single_story_video, generate_25min_single_story_video


class TestShortsFullStoryAnd30MinLongform(unittest.TestCase):
    def setUp(self):
        self.director = RedditStoryDirectorAgent(api_keys=[])

    def test_shorts_preserves_full_story_under_480_words(self):
        """Verifica se histórias de até 450 palavras têm 100% de suas sentenças preservadas no Shorts."""
        # Cria um post com ~350 palavras e 6 frases claras
        sentences = [
            "My boss told me that I had to follow the company handbook to the exact letter without any exceptions whatsoever.",
            "I warned him that our software deployment system had undocumented quirks that required manual oversight every Friday afternoon.",
            "He laughed in my face and told me that if I made a single manual adjustment, he would write me up for insubordination.",
            "So on Friday at 4:55 PM, the automated system threw a warning flag, but following orders, I clocked out and went home.",
            "By Saturday morning, three production databases were completely corrupted and emergency contractors had to be hired at triple rates.",
            "On Monday morning, my boss tried to blame me, but I presented his signed email to the VP, resulting in his immediate termination."
        ]
        body = " ".join(sentences)
        raw_post = {
            "title": "Boss demanded strict handbook compliance and got fired",
            "body": body,
            "subreddit": "r/maliciouscompliance",
            "author": "u/ComplianceMaster",
            "score": "45.1k"
        }

        script_data = self.director._generate_algorithmic_fallback_script(raw_post)
        shorts_script = script_data.get("shorts_script", "")

        # Verifica que nenhuma frase da história original foi cortada
        for s in sentences:
            key_phrase = " ".join(s.split()[:4]).lower()
            self.assertIn(key_phrase, shorts_script.lower(), f"Frase cortada indevidamente: {s}")

        # Verifica presença de CTA de engajamento no final
        has_cta = any(token in shorts_script.lower() for token in ["comments below", "verdict", "what would you", "your next move", "share your story", "thoughts", "opinion", "discuss"])
        self.assertTrue(has_cta, f"Roteiro de Short sem CTA de engajamento no final: {shorts_script[-100:]}")

    def test_expand_30min_single_story_generates_10_chapters_and_5000_words(self):
        """Verifica se a expansão algorítmica de 30+ minutos gera 10 capítulos e mais de 5.000 palavras."""
        raw_post = {
            "title": "Strict executive banned working from home for IT team",
            "body": "Executive mandated all IT staff return to office 5 days a week. The entire senior engineering team resigned on the same day.",
            "subreddit": "r/maliciouscompliance",
            "author": "u/ITVeteran",
            "score": "52.4k"
        }

        res = self.director._generate_algorithmic_30min_story(raw_post, target_minutes=30.0)
        chapters = res.get("chapters", [])
        
        self.assertEqual(len(chapters), 10, "A história monolítica de 30min deve conter exatamente 10 capítulos.")

        total_words = sum(len(ch.get("narration_text", "").split()) for ch in chapters)
        self.assertGreaterEqual(total_words, 5000, f"Total de palavras deve ser >= 5000 para atingir 30+ min, obteve {total_words}")

        # Verifica que os números dos capítulos são sequenciais de 1 a 10
        for i, ch in enumerate(chapters, 1):
            self.assertEqual(ch["chapter_num"], i)
            self.assertGreaterEqual(len(ch["narration_text"].split()), 480)

        # Verifica dados do Teaser Short
        teaser = res.get("teaser_short", {})
        self.assertTrue(teaser.get("title"))
        self.assertIn("30-MIN", teaser.get("final_hook_text", ""))

    def test_backwards_compatibility_aliases(self):
        """Verifica se os aliases expand_25min_single_story e generate_25min_single_story_video existem e funcionam."""
        raw_post = {
            "title": "Landlord tried to steal our security deposit",
            "body": "Landlord claimed $3000 in fake damages. We took him to small claims court with video evidence and won treble damages.",
            "subreddit": "r/legaladvice",
            "author": "u/TenantRights",
            "score": "29.3k"
        }

        res = self.director._generate_algorithmic_25min_story(raw_post, target_minutes=30.0)
        self.assertIn("chapters", res)
        self.assertEqual(len(res["chapters"]), 10)
        self.assertTrue(callable(generate_25min_single_story_video))
        self.assertTrue(callable(generate_30min_single_story_video))


if __name__ == "__main__":
    unittest.main()
