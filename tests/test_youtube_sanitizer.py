import unittest
from src.pronunciation import sanitize_youtube_compliance, phoneticize_reddit_text
from src.reddit_scraper import clean_reddit_text
from src.reddit_agents import RedditStoryDirectorAgent

class TestYouTubeSanitizer(unittest.TestCase):
    def test_sensitive_words_substitution(self):
        """Verifica a substituição de palavras sensíveis por termos monetizáveis no YouTube."""
        raw_text = "He was watching porn while discussing sex and drugs."
        sanitized = sanitize_youtube_compliance(raw_text)
        self.assertNotIn("porn", sanitized.lower())
        self.assertNotIn("sex", sanitized.lower())
        self.assertNotIn("drugs", sanitized.lower())
        self.assertIn("corn", sanitized.lower())
        self.assertIn("vex", sanitized.lower())
        self.assertIn("substances", sanitized.lower())

    def test_case_preservation(self):
        """Verifica a preservação de capitalização em substituições."""
        self.assertEqual(sanitize_youtube_compliance("PORN"), "CORN")
        self.assertEqual(sanitize_youtube_compliance("Porn"), "Corn")
        self.assertEqual(sanitize_youtube_compliance("porn"), "corn")
        self.assertEqual(sanitize_youtube_compliance("Sex"), "Vex")
        self.assertEqual(sanitize_youtube_compliance("Killed"), "Unalived")

    def test_reddit_metadata_boilerplate_cleanup(self):
        """Verifica a remoção de metadados de submissão do Reddit e frases de encerramento."""
        dirty_rss = (
            "My boss demanded I work overtime. &#32; submitted by &#32; "
            "<a href=\"https://reddit.com\"> /u/angry_worker </a> &#32; "
            "<a href=\"https://reddit.com\">[link]</a> &#32; "
            "<a href=\"https://reddit.com\">[comments]</a> The end."
        )
        cleaned = clean_reddit_text(dirty_rss)
        self.assertNotIn("submitted by", cleaned.lower())
        self.assertNotIn("[link]", cleaned.lower())
        self.assertNotIn("[comments]", cleaned.lower())
        self.assertNotIn("the end", cleaned.lower())
        self.assertIn("My boss demanded I work overtime.", cleaned)

    def test_spoken_story_text_sanitizer(self):
        """Verifica o método clean_spoken_story_text do diretor de histórias."""
        story_with_junk = (
            "Boss ordered a full audit. (submitted by u/john link comments) "
            "He threatened to kill my career over porn accusations. O Fim."
        )
        cleaned = RedditStoryDirectorAgent.clean_spoken_story_text(story_with_junk)
        self.assertNotIn("submitted by", cleaned.lower())
        self.assertNotIn("link comments", cleaned.lower())
        self.assertNotIn("o fim", cleaned.lower())
        self.assertNotIn("kill", cleaned.lower())
        self.assertNotIn("porn", cleaned.lower())
        self.assertIn("corn", cleaned.lower())
        self.assertIn("unalive", cleaned.lower())

if __name__ == "__main__":
    unittest.main()
