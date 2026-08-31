import os
import re
import unittest
import shutil
import tempfile
from src.reddit_sfx import ensure_sfx_assets, mix_sfx_to_audio, generate_procedural_bell_plim, generate_procedural_whoosh
from src.reddit_visuals import RedditVisualEngine
from src.reddit_agents import RedditStoryDirectorAgent

class TestSFXAndVisualRefactor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sfx_assets_procedural_generation(self):
        """Verifica se os arquivos WAV de SFX sao sintetizados proceduralmente com sucesso."""
        plim, whoosh = ensure_sfx_assets()
        self.assertTrue(os.path.exists(plim))
        self.assertTrue(os.path.exists(whoosh))
        self.assertGreater(os.path.getsize(plim), 50000)
        self.assertGreater(os.path.getsize(whoosh), 50000)

    def test_clean_spoken_story_text_preserves_legitimate_english_words(self):
        """Verifica que palavras normais como 'part of', 'take part', 'update', 'edit' NAO sao deletadas."""
        sample_legit = "As part of my daily routine, I took part in the morning meeting. I will update the ticket and edit the config file."
        cleaned = RedditStoryDirectorAgent.clean_spoken_story_text(sample_legit)
        self.assertEqual(cleaned, sample_legit)

    def test_clean_spoken_story_text_strips_varied_chapter_part_announcements(self):
        """Verifica a remocao de marcadores roboticos como Chapter X, Part X, Part One, Chapter IV, Update X, Edit e TL;DR."""
        sample_dirty = "Chapter 1: The Initial Problem. Part 2 - The Escalation. Update 1: The boss came in. TL;DR: Total compliance."
        cleaned = RedditStoryDirectorAgent.clean_spoken_story_text(sample_dirty)
        self.assertNotIn("Chapter 1:", cleaned)
        self.assertNotIn("Part 2 -", cleaned)
        self.assertNotIn("Update 1:", cleaned)
        self.assertNotIn("TL;DR:", cleaned)
        self.assertIn("The Initial Problem", cleaned)
        self.assertIn("Total compliance", cleaned)

        sample_words = "Part One: The Absurd Directive. Chapter IV: The Audit. Edit: typos fixed."
        cleaned_words = RedditStoryDirectorAgent.clean_spoken_story_text(sample_words)
        self.assertNotIn("Part One:", cleaned_words)
        self.assertNotIn("Chapter IV:", cleaned_words)
        self.assertNotIn("Edit:", cleaned_words)
        self.assertIn("The Absurd Directive", cleaned_words)
        self.assertIn("The Audit", cleaned_words)

        sample_md = "### Part 3: The Setup. **Chapter 4:** The Execution."
        cleaned_md = RedditStoryDirectorAgent.clean_spoken_story_text(sample_md)
        self.assertNotIn("Part 3:", cleaned_md)
        self.assertNotIn("Chapter 4:", cleaned_md)
        self.assertIn("The Setup", cleaned_md)
        self.assertIn("The Execution", cleaned_md)

        sample_brackets = "Hello. **Part 2:** The manager arrived. [Update 2]: We won. (Update): Case closed. **Edit:** All done."
        cleaned_brackets = RedditStoryDirectorAgent.clean_spoken_story_text(sample_brackets)
        self.assertEqual(cleaned_brackets, "Hello. The manager arrived. We won. Case closed. All done.")

        sample_adjectives = "Final Update: He was fired. Quick Update: The manager got fired. Small Edit: Fixed formatting. Final Part: The boss apologized. UPDATE (Final): We won."
        cleaned_adjectives = RedditStoryDirectorAgent.clean_spoken_story_text(sample_adjectives)
        self.assertEqual(cleaned_adjectives, "He was fired. The manager got fired. Fixed formatting. The boss apologized. We won.")

        sample_symbols = "Update #1: The meeting started. Part #2: The confrontation happened. [Final Update]: We received the check. (Quick Update): The boss left."
        cleaned_symbols = RedditStoryDirectorAgent.clean_spoken_story_text(sample_symbols)
        self.assertEqual(cleaned_symbols, "The meeting started. The confrontation happened. We received the check. The boss left.")

        sample_twelve = "Part Twelve: The aftermath was quiet."
        cleaned_twelve = RedditStoryDirectorAgent.clean_spoken_story_text(sample_twelve)
        self.assertEqual(cleaned_twelve, "The aftermath was quiet.")

    def test_narration_naturalness_no_chapter_announcements(self):
        """Garante que nenhum capitulo comece ou contenha anuncios roboticos como 'Chapter X:' ou 'Part X:'."""
        agent = RedditStoryDirectorAgent()
        sample_post = {
            "title": "My boss demanded I follow the manual to the exact letter",
            "body": "Part 1: I work as an operations technician. A new manager arrived and instituted strict rules...",
            "subreddit": "r/maliciouscompliance",
            "author": "u/TechHero",
            "score": "45.1k"
        }
        res = agent._generate_algorithmic_25min_story(sample_post, 25.0)
        chapters = res.get("chapters", [])
        self.assertEqual(len(chapters), 8)

        openers = []
        for ch in chapters:
            narr = ch.get("narration_text", "")
            # Nao deve comecar com Chapter X ou Part X
            self.assertFalse(re.match(r'^(Chapter|Part)\s*\d+[:\-.]*', narr, re.IGNORECASE), f"Capitulo contem prefixo robotico: {narr[:40]}")
            # Nao deve conter marcadores roboticos em lugar nenhum
            self.assertFalse(re.search(r'\b(Chapter|Part)\s+\d+[:\-.]*', narr, re.IGNORECASE), f"Marcador robotico encontrado: {narr}")
            # Nao deve conter a frase repetitiva antiga
            self.assertNotIn("When dealing with high-stakes corporate bureaucracy, one golden rule reigns supreme", narr)
            # Deve ser rico e extenso
            self.assertGreater(len(narr.split()), 400)
            openers.append(narr[:35].strip())

        # Garante transicoes diversas (todos os inicios de capitulo distintos)
        self.assertEqual(len(set(openers)), 8, f"Inicios de capitulo repetidos detectados: {openers}")

    def test_fallback_shorts_script_cleaning(self):
        """Verifica que o fallback de shorts limpa marcadores de capitulos do corpo do post."""
        agent = RedditStoryDirectorAgent()
        sample_post = {
            "title": "Obeying orders caused a shutdown",
            "body": "Part 1: The rule was set. Update 1: The line stopped running on Friday afternoon. TL;DR: It was expensive.",
            "subreddit": "r/maliciouscompliance",
            "author": "u/Worker",
            "score": "30.0k"
        }
        res = agent._generate_algorithmic_fallback_script(sample_post)
        shorts_txt = res.get("shorts_script", "")
        self.assertNotIn("Part 1:", shorts_txt)
        self.assertNotIn("Update 1:", shorts_txt)
        self.assertNotIn("TL;DR:", shorts_txt)

    def test_enlarged_reddit_card_rendering(self):
        """Verifica a renderizacao do Card Oficial com tamanho ampliado."""
        visual = RedditVisualEngine()
        card_9x16 = os.path.join(self.test_dir, "card_9x16.png")
        card_16x9 = os.path.join(self.test_dir, "card_16x9.png")

        card_info = {
            "channel_name": "Reddit Minute",
            "score": "42.0k",
            "display_title": "Demanded strict obedience so I followed orders and the entire system crashed"
        }

        visual.render_reddit_card(card_info, card_9x16, aspect_ratio="9:16")
        visual.render_reddit_card(card_info, card_16x9, aspect_ratio="16:9")

        self.assertTrue(os.path.exists(card_9x16))
        self.assertTrue(os.path.exists(card_16x9))
        self.assertGreater(os.path.getsize(card_9x16), 15000)
        self.assertGreater(os.path.getsize(card_16x9), 15000)

    def test_enlarged_reddit_card_long_title_no_overflow(self):
        """Verifica que titulos extremamente longos (>300 caracteres) sao limitados sem estourar o canvas."""
        visual = RedditVisualEngine()
        card_16x9 = os.path.join(self.test_dir, "card_long_16x9.png")
        card_9x16 = os.path.join(self.test_dir, "card_long_9x16.png")

        card_info = {
            "channel_name": "Reddit Minute",
            "score": "58.4k",
            "display_title": "My boss demanded I follow the employee handbook to the exact letter without any exceptions whatsoever, even during emergency system shutdowns, which resulted in a massive multi-thousand dollar overtime bill and catastrophic weekend meltdown that executive leadership had to investigate."
        }

        visual.render_reddit_card(card_info, card_16x9, aspect_ratio="16:9")
        visual.render_reddit_card(card_info, card_9x16, aspect_ratio="9:16")

        self.assertTrue(os.path.exists(card_16x9))
        self.assertTrue(os.path.exists(card_9x16))

    def test_sfx_mixing_all_video_types_and_formats(self):
        """Verifica a mixagem de SFX para shorts, teaser, longform e chunks em mp3 e wav."""
        dummy_audio = os.path.join(self.test_dir, "dummy_audio.wav")
        generate_procedural_whoosh(dummy_audio, duration=3.0)

        # 1. Shorts (Plim + Whoosh) em .mp3
        out_shorts = os.path.join(self.test_dir, "mixed_shorts.mp3")
        res_shorts = mix_sfx_to_audio(
            main_audio_path=dummy_audio,
            output_audio_path=out_shorts,
            video_type="shorts",
            total_duration_sec=3.0,
            card_duration_sec=1.5
        )
        self.assertEqual(res_shorts, out_shorts)
        self.assertTrue(os.path.exists(out_shorts))
        self.assertGreater(os.path.getsize(out_shorts), 5000)

        # 2. Teaser (Plim + Whoosh + Plim no hook final) em .wav
        out_teaser = os.path.join(self.test_dir, "mixed_teaser.wav")
        res_teaser = mix_sfx_to_audio(
            main_audio_path=dummy_audio,
            output_audio_path=out_teaser,
            video_type="teaser",
            total_duration_sec=3.0,
            card_duration_sec=1.0,
            final_hook_duration_sec=1.0
        )
        self.assertEqual(res_teaser, out_teaser)
        self.assertTrue(os.path.exists(out_teaser))
        self.assertGreater(os.path.getsize(out_teaser), 10000)

        # 3. Longform (Whoosh + Whoosh) em .mp3
        out_longform = os.path.join(self.test_dir, "mixed_longform.mp3")
        res_longform = mix_sfx_to_audio(
            main_audio_path=dummy_audio,
            output_audio_path=out_longform,
            video_type="longform",
            total_duration_sec=3.0,
            card_duration_sec=1.5
        )
        self.assertEqual(res_longform, out_longform)
        self.assertTrue(os.path.exists(out_longform))
        self.assertGreater(os.path.getsize(out_longform), 5000)

        # 4. Chunk (Sem SFX - deve retornar o audio principal sem alteracao)
        out_chunk = os.path.join(self.test_dir, "mixed_chunk.wav")
        res_chunk = mix_sfx_to_audio(
            main_audio_path=dummy_audio,
            output_audio_path=out_chunk,
            video_type="chunk",
            total_duration_sec=3.0,
            card_duration_sec=0.0
        )
        self.assertEqual(res_chunk, dummy_audio)

if __name__ == "__main__":
    unittest.main()
