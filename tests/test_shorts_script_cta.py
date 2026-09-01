import unittest
from src.reddit_agents import RedditStoryDirectorAgent, ENGAGEMENT_QUESTIONS

class TestShortsScriptCTA(unittest.TestCase):
    def test_shorts_duration_and_cta(self):
        """
        Verifica que os roteiros de Shorts:
        1. Suportam duração de até 2.5 minutos (~200 a 450 palavras);
        2. Contêm obrigatoriamente transição fluida e pergunta/CTA de engajamento no final;
        3. Terminam em pontuação válida sem corte abrupto de frases no meio.
        """
        director = RedditStoryDirectorAgent()
        sample_subs = ["r/maliciouscompliance", "r/pettyrevenge", "r/AITAH"]
        
        for sub in sample_subs:
            story = director._procedurally_generate_reddit_post(sub)
            script_data = director._generate_algorithmic_fallback_script(story)


            shorts_text = script_data.get("shorts_script", "").strip()
            
            word_count = len(shorts_text.split())
            self.assertGreaterEqual(word_count, 200)
            self.assertLessEqual(word_count, 450)

            # Valida pontuação final
            self.assertTrue(shorts_text.endswith((".", "!", "?")), f"Roteiro termina sem pontuação válida: {shorts_text[-40:]}")

            # Valida presença de CTA fluido
            last_200_chars = shorts_text[-200:].lower()
            has_cta = any(token in last_200_chars for token in ["?", "comment", "thoughts", "verdict", "below", "opinion", "what would you", "share your story", "discuss"])
            self.assertTrue(has_cta, f"Roteiro de Short sem CTA de engajamento no final: {last_200_chars}")

            # Valida que ui_card usa 'Reddit Minute'
            ui_card = script_data.get("ui_card", {})
            self.assertEqual(ui_card.get("channel_name"), "Reddit Minute")

if __name__ == "__main__":
    unittest.main()
