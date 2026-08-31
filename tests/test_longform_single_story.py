import unittest
from src.reddit_agents import RedditStoryDirectorAgent
from src.reddit_scraper import EXPANDED_HIGH_CPM_STORIES

class TestLongformSingleStory(unittest.TestCase):
    def test_longform_single_story_structure(self):
        """
        Verifica que vídeos longos de 25 minutos:
        1. São estruturados como UMA HISTÓRIA ÚNICA profunda (não um compilado de histórias avulsas);
        2. Possuem 8 capítulos ricos da mesma história com mais de 3.500 palavras no total;
        3. Cada capítulo tem numeração, título e texto de narração.
        """
        director = RedditStoryDirectorAgent()
        story = EXPANDED_HIGH_CPM_STORIES[0]

        longform_data = director.expand_25min_single_story(story, target_minutes=25.0)
        
        self.assertIn("chapters", longform_data)
        chapters = longform_data["chapters"]
        self.assertEqual(len(chapters), 8, f"Esperado 8 capítulos para 25min, obtido: {len(chapters)}")

        total_words = sum(len(c.get("narration_text", "").split()) for c in chapters)
        self.assertGreaterEqual(total_words, 3500, f"Total de palavras ({total_words}) insuficiente para 25 minutos.")

        for ch in chapters:
            self.assertIsNotNone(ch.get("chapter_num"))
            self.assertTrue(ch.get("chapter_title"))
            self.assertGreaterEqual(len(ch.get("narration_text", "").split()), 350)

if __name__ == "__main__":
    unittest.main()
