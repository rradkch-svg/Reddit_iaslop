import unittest
from src.reddit_agents import RedditStoryDirectorAgent, ENGAGEMENT_QUESTIONS
from src.reddit_scraper import EXPANDED_HIGH_CPM_STORIES

class TestShortsScriptCTA(unittest.TestCase):
    def test_shorts_duration_and_cta(self):
        """
        Verifica que os roteiros de Shorts:
        1. Suportam duração de até 2.5 minutos (~200 a 450 palavras);
        2. Contêm obrigatoriamente pergunta/CTA de engajamento no final.
        """
        director = RedditStoryDirectorAgent()
        story = EXPANDED_HIGH_CPM_STORIES[0]
        
        script_data = director._generate_algorithmic_fallback_script(story)
        shorts_text = script_data.get("shorts_script", "")
        
        word_count = len(shorts_text.split())
        self.assertGreaterEqual(word_count, 200)
        self.assertLessEqual(word_count, 450)

        last_150_chars = shorts_text[-150:]
        has_cta = any(token in last_150_chars.lower() for token in ["?", "comment", "thoughts", "verdict", "below", "opinion", "what would you"])
        self.assertTrue(has_cta, f"Roteiro de Short sem CTA de engajamento no final: {last_150_chars}")

if __name__ == "__main__":
    unittest.main()
