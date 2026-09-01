import unittest
from src.reddit_agents import RedditStoryDirectorAgent

class TestLongformSingleStory(unittest.TestCase):
    def test_longform_single_story_structure(self):
        """
        Verifica que vídeos longos de 25 minutos:
        1. São estruturados como UMA HISTÓRIA ÚNICA profunda (não um compilado de histórias avulsas);
        2. Possuem 8 capítulos ricos da mesma história com mais de 3.500 palavras no total;
        3. Cada capítulo tem numeração, título e texto de narração.
        """
        director = RedditStoryDirectorAgent()
        story = director._procedurally_generate_reddit_post("r/maliciouscompliance")



        longform_data = director._generate_algorithmic_25min_story(story, target_minutes=25.0)
        
        self.assertIn("chapters", longform_data)
        chapters = longform_data["chapters"]
        self.assertEqual(len(chapters), 8, f"Esperado 8 capítulos para 25min, obtido: {len(chapters)}")

        total_words = sum(len(c.get("narration_text", "").split()) for c in chapters)
        self.assertGreaterEqual(total_words, 3500, f"Total de palavras ({total_words}) insuficiente para 25 minutos.")

        openers = []
        for ch in chapters:
            self.assertIsNotNone(ch.get("chapter_num"))
            self.assertTrue(ch.get("chapter_title"))
            narr = ch.get("narration_text", "")
            self.assertGreaterEqual(len(narr.split()), 350)
            # Sem anuncios roboticos falados
            self.assertFalse(narr.lower().startswith(("chapter", "part")), f"Capitulo inicia com prefixo robotico: {narr[:30]}")
            openers.append(narr[:30].strip())

        # Transicoes diversas
        self.assertEqual(len(set(openers)), 8, f"Inicios de capitulos repetidos: {openers}")

        # Teaser short sem marcadores roboticos falados
        teaser = longform_data.get("teaser_short", {})
        teaser_script = teaser.get("script", "")
        self.assertTrue(teaser_script)
        self.assertFalse(teaser_script.lower().startswith(("chapter", "part")))

if __name__ == "__main__":
    unittest.main()
