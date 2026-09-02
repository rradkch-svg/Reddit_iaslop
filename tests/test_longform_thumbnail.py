import os
import unittest
import tempfile
from PIL import Image
from src.reddit_thumbnails import RedditThumbnailEngine

class TestRedditThumbnailEngine(unittest.TestCase):
    def test_generate_white_card_thumbnail(self):
        engine = RedditThumbnailEngine(brand_name="Reddit Minute")
        story = {
            "title": "She Demanded My $25K House Savings For Her Wedding, So I Sold Her Car",
            "subreddit": "r/AITAH",
            "author": "throwaway_house_car",
            "score": "48.5k"
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = os.path.join(tmpdir, "test_white_card.png")
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
                # Verifica que o centro do card é branco (alta luminosidade)
                # Ponto central do card: (960, 540)
                pixel = img.getpixel((960, 540))
                self.assertGreater(pixel[0], 230)
                self.assertGreater(pixel[1], 230)
                self.assertGreater(pixel[2], 230)

            with Image.open(out_jpg) as img_jpg:
                self.assertEqual(img_jpg.size, (1920, 1080))

if __name__ == "__main__":
    unittest.main()
