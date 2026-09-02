import os
import unittest
import tempfile
from src.reddit_subtitles import format_srt_time, generate_reddit_srt_subtitles

class TestLongformSRTExport(unittest.TestCase):
    def test_format_srt_time(self):
        self.assertEqual(format_srt_time(0.0), "00:00:00,000")
        self.assertEqual(format_srt_time(65.25), "00:01:05,250")
        self.assertEqual(format_srt_time(3661.8), "01:01:01,800")

    def test_generate_reddit_srt_subtitles_single_chunk(self):
        words = [
            {"word": "She", "start": 0.0, "end": 0.3},
            {"word": "demanded", "start": 0.3, "end": 0.8},
            {"word": "twenty-five", "start": 0.8, "end": 1.4},
            {"word": "thousand", "start": 1.4, "end": 1.9},
            {"word": "dollars", "start": 1.9, "end": 2.3},
            {"word": "today", "start": 2.3, "end": 2.8},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            srt_path = os.path.join(tmpdir, "test.srt")
            next_idx = generate_reddit_srt_subtitles(
                words_timing=words,
                output_srt=srt_path,
                time_offset_sec=0.0,
                chunk_size=6
            )
            self.assertEqual(next_idx, 2)
            self.assertTrue(os.path.exists(srt_path))
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("1\n00:00:00,000 --> 00:00:02,800\nShe demanded twenty-five thousand dollars today", content)

    def test_generate_reddit_srt_subtitles_multi_chapter_chaining(self):
        ch1_words = [
            {"word": "Part", "start": 0.0, "end": 0.4},
            {"word": "one", "start": 0.4, "end": 0.8}
        ]
        ch2_words = [
            {"word": "Part", "start": 0.0, "end": 0.4},
            {"word": "two", "start": 0.4, "end": 0.9}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            srt_path = os.path.join(tmpdir, "master.srt")
            # Cap 1
            idx2 = generate_reddit_srt_subtitles(
                words_timing=ch1_words,
                output_srt=srt_path,
                time_offset_sec=0.0,
                chunk_size=2,
                append=False,
                start_index=1
            )
            # Cap 2 (com offset de 60 segundos)
            idx3 = generate_reddit_srt_subtitles(
                words_timing=ch2_words,
                output_srt=srt_path,
                time_offset_sec=60.0,
                chunk_size=2,
                append=True,
                start_index=idx2
            )
            self.assertEqual(idx2, 2)
            self.assertEqual(idx3, 3)

            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("1\n00:00:00,000 --> 00:00:00,800\nPart one", content)
            self.assertIn("2\n00:01:00,000 --> 00:01:00,900\nPart two", content)

if __name__ == "__main__":
    unittest.main()
