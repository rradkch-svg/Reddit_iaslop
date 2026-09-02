import os
import unittest
import tempfile
from PIL import Image
from src.reddit_thumbnails import RedditThumbnailEngine, extract_shock_phrase

class TestRedditThumbnailEngine(unittest.TestCase):
    def test_extract_shock_phrase(self):
        p1 = extract_shock_phrase("She Demanded My $25K House Savings For Her Wedding, So I Sold Her Car")
        self.assertIn("SOLD HER CAR", p1)

        p2 = extract_shock_phrase("Boss banned off-hours IT fixes without 24hr written approval. Enjoy your $280k weekend outage.")
        self.assertIn("$280K", p2)

        p3 = extract_shock_phrase("TIFU by throwing away my landlord's 130-year-old sourdough starter")
        self.assertIn("HEIRLOOM", p3)

        p4 = extract_shock_phrase("AITAH for refusing to give my sister $18,000 from late husband's estate")
        self.assertIn("$18,000", p4)

    def test_generate_youtube_thumbnail(self):
        engine = RedditThumbnailEngine()
        story = {
            "title": "She Demanded My $25K House Savings For Her Wedding, So I Sold Her Car",
            "subreddit": "r/AITAH",
            "author": "throwaway_house_car",
            "score": "48.5k"
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = os.path.join(tmpdir, "test_thumb.png")
            res_path = engine.generate_youtube_thumbnail(
                story_data=story,
                output_path=out_png
            )
            self.assertTrue(os.path.exists(res_path))
            out_jpg = res_path.replace(".png", ".jpg")
            self.assertTrue(os.path.exists(out_jpg))

            # Verifica dimensões exatas 1920x1080 (16:9)
            with Image.open(res_path) as img:
                self.assertEqual(img.size, (1920, 1080))

            with Image.open(out_jpg) as img_jpg:
                self.assertEqual(img_jpg.size, (1920, 1080))

if __name__ == "__main__":
    unittest.main()
