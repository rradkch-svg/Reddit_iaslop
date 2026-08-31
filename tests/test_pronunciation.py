import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pronunciation import AutomotivePronunciationEngine, phoneticize_automotive_text

class TestAutomotivePronunciation(unittest.TestCase):
    def setUp(self):
        self.engine = AutomotivePronunciationEngine()

    def test_brand_pronunciations(self):
        sample = "O novo Porsche 911 GT3 RS enfrenta a Ferrari e o Koenigsegg em Nürburgring Nordschleife."
        phonetic = self.engine.phoneticize(sample)
        print("\nOriginal:", sample)
        print("Phonetic:", phonetic)
        
        self.assertIn("Pór-xê", phonetic)
        self.assertIn("Guê-Tê-Três Erre-Ésse", phonetic)
        self.assertIn("Ferrári", phonetic)
        self.assertIn("Kônig-zég", phonetic)
        self.assertIn("Niur-burg-ring", phonetic)
        self.assertIn("Nórdi-xláifi", phonetic)

    def test_powertrain_and_aero_terms(self):
        sample = "O motor V10 com twin-turbo e supercharger gera 9000 rpm e muito downforce com paddle shift e launch control."
        phonetic = self.engine.phoneticize(sample)
        print("\nOriginal:", sample)
        print("Phonetic:", phonetic)

        self.assertIn("Vê dez", phonetic)
        self.assertIn("tuin târbo", phonetic)
        self.assertIn("súper-tchárdjer", phonetic)
        self.assertIn("9000 érre-pê-êmi", phonetic)
        self.assertIn("dáun-fórce", phonetic)
        self.assertIn("pédol shift", phonetic)
        self.assertIn("lônch con-trôul", phonetic)

    def test_alignment_mapping(self):
        original = "O Porsche GT3 RS usa twin turbo e entrega 800 hp."
        # Simula saída do TTS com 11 palavras geradas a partir da versão fonética
        phonetic_timing = [
            {"word": "O", "start": 0.0, "end": 0.2},
            {"word": "Pór-xê", "start": 0.2, "end": 0.6},
            {"word": "Guê", "start": 0.6, "end": 0.8},
            {"word": "Tê", "start": 0.8, "end": 1.0},
            {"word": "Três", "start": 1.0, "end": 1.3},
            {"word": "Erre", "start": 1.3, "end": 1.5},
            {"word": "Ésse", "start": 1.5, "end": 1.8},
            {"word": "usa", "start": 1.8, "end": 2.0},
            {"word": "tuin", "start": 2.0, "end": 2.3},
            {"word": "târbo", "start": 2.3, "end": 2.7},
            {"word": "e", "start": 2.7, "end": 2.8},
            {"word": "entrega", "start": 2.8, "end": 3.2},
            {"word": "oitocentos", "start": 3.2, "end": 3.7},
            {"word": "cavalos.", "start": 3.7, "end": 4.1}
        ]
        
        aligned = self.engine.align_phonetic_timing_to_original(original, phonetic_timing)
        orig_words = original.split()
        
        self.assertEqual(len(aligned), len(orig_words))
        for al, orig_w in zip(aligned, orig_words):
            self.assertEqual(al["word"], orig_w)
            self.assertGreaterEqual(al["end"], al["start"])
        print("\nAligned original words timing:")
        for al in aligned:
            print(f"  {al['word']}: {al['start']}s -> {al['end']}s")

if __name__ == "__main__":
    unittest.main()
