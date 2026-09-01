import os
import unittest
import tempfile
import json
from src.batch_manager import BatchManager

class TestBatchMediaCleanup(unittest.TestCase):
    def test_batch_cleaner_generation_and_execution(self):
        """Verifica que o script de limpeza de lote remove mídia pesada e preserva 100% dos metadados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = BatchManager(base_dir=tmpdir, batch_size=2)
            cleaner_path = mgr.generate_batch_cleaner(1)

            self.assertTrue(os.path.exists(cleaner_path), "clean_media.py não foi gerado no lote.")

            batch_dir = os.path.dirname(cleaner_path)
            v0_dir = os.path.join(batch_dir, "video_0")
            os.makedirs(v0_dir, exist_ok=True)

            # Cria arquivos de mídia pesada
            heavy_mp4 = os.path.join(v0_dir, "video.mp4")
            heavy_mp3 = os.path.join(v0_dir, "audio.mp3")
            heavy_ass = os.path.join(v0_dir, "subs.ass")
            for p in [heavy_mp4, heavy_mp3, heavy_ass]:
                with open(p, "wb") as f:
                    f.write(b"x" * 20480)

            # Cria metadados e scripts que DEVEM ser preservados
            meta_json = os.path.join(v0_dir, "metadata.json")
            script_json = os.path.join(v0_dir, "script_data.json")
            desc_txt = os.path.join(v0_dir, "description.txt")
            card_png = os.path.join(v0_dir, "card_opening.png")

            with open(meta_json, "w", encoding="utf-8") as f:
                json.dump({"title": "Test Story"}, f)
            with open(script_json, "w", encoding="utf-8") as f:
                json.dump({"script": "Test Spoken Story"}, f)
            with open(desc_txt, "w", encoding="utf-8") as f:
                f.write("Full YouTube Description")
            with open(card_png, "wb") as f:
                f.write(b"fake_png_data")

            # Executa a limpeza
            deleted, freed = mgr.clean_batch_media(1)

            self.assertEqual(deleted, 3, "Deveriam ser deletados exatamente os 3 arquivos de mídia.")
            self.assertFalse(os.path.exists(heavy_mp4), "MP4 não foi removido.")
            self.assertFalse(os.path.exists(heavy_mp3), "MP3 não foi removido.")
            self.assertFalse(os.path.exists(heavy_ass), "ASS não foi removido.")

            # Verifica que todos os metadados foram preservados intactos
            self.assertTrue(os.path.exists(meta_json), "metadata.json foi removido incorretamente!")
            self.assertTrue(os.path.exists(script_json), "script_data.json foi removido incorretamente!")
            self.assertTrue(os.path.exists(desc_txt), "description.txt foi removido incorretamente!")
            self.assertTrue(os.path.exists(card_png), "card_opening.png foi removido incorretamente!")

if __name__ == "__main__":
    unittest.main()
