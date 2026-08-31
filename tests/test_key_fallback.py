import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "tests" else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents import (
    resolve_gemini_api_keys,
    resolve_gemini_api_key,
    generate_with_resilience,
    get_prioritized_keys,
    _KEY_COOLDOWNS
)

class TestKeyFallback(unittest.TestCase):
    def test_resolve_gemini_api_keys(self):
        keys = resolve_gemini_api_keys()
        self.assertIsInstance(keys, list)
        self.assertGreaterEqual(len(keys), 3, "Deveriam ser detectadas pelo menos 3 chaves Gemini (Primaria, Fallback 1 e Fallback 2/Reserva)!")
        self.assertEqual(len(set(keys)), len(keys), "Todas as chaves cadastradas devem ser unicas!")

    def test_resolve_gemini_api_key_retrocompat(self):
        keys = resolve_gemini_api_keys()
        primary_key = resolve_gemini_api_key()
        if keys:
            self.assertEqual(primary_key, keys[0])

    def test_get_prioritized_keys_with_cooldown(self):
        test_keys = ["key_exhausted_123456789012345", "key_active_23456789012345678"]
        # Marca key_exhausted com cooldown futuro
        _KEY_COOLDOWNS["key_exhausted_123456789012345"] = time.time() + 60
        _KEY_COOLDOWNS.pop("key_active_23456789012345678", None)

        prioritized = get_prioritized_keys(test_keys)
        self.assertEqual(prioritized[0], "key_active_23456789012345678")
        self.assertEqual(prioritized[1], "key_exhausted_123456789012345")

    @patch("agents.get_genai_client")
    def test_generate_with_resilience_key_rotation(self, mock_get_client):
        _KEY_COOLDOWNS.clear()
        
        # Mock do primeiro cliente que falha com 429
        mock_client_fail = MagicMock()
        mock_client_fail.models.generate_content_stream.side_effect = Exception("429 RESOURCE_EXHAUSTED Quota exceeded. retry in 5s")
        
        # Mock do segundo cliente que sucede
        mock_client_ok = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.text = "FALLBACK_OK"
        mock_client_ok.models.generate_content_stream.return_value = [mock_chunk]

        key1 = "fake_key_one_123456789012345"
        key2 = "fake_key_two_123456789012345"

        def client_factory(api_key=None):
            if api_key == key2:
                return mock_client_ok
            return mock_client_fail

        mock_get_client.side_effect = client_factory

        keys = [key1, key2]
        result = generate_with_resilience(
            prompt="Test prompt",
            system_instruction="Test instruction",
            model_name="gemini-flash-lite-latest",
            auto_fallback=False,
            auto_cooldown=False,
            api_keys=keys,
            timeout_seconds=5.0
        )
        self.assertEqual(result, "FALLBACK_OK")

if __name__ == "__main__":
    unittest.main()
