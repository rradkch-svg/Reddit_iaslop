import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from pronunciation import phoneticize_reddit_text
from deduplication import ContextualTopicAuditor, extract_canonical_entity, classify_reddit_domains
from checkpoint_manager import CheckpointManager


class TestPronunciationAndEnhancedBlacklist(unittest.TestCase):
    def test_it_pronoun_never_phoneticized_as_i_t(self):
        """Verifica se o pronome 'it'/'It' NUNCA é convertido para 'I-T'."""
        sample_1 = "It was a Friday afternoon when my boss asked me to fix it."
        res_1 = phoneticize_reddit_text(sample_1)
        self.assertNotIn("I-T", res_1)
        self.assertNotIn("i-t", res_1)
        self.assertIn("It was", res_1)
        self.assertIn("fix it", res_1)

        sample_2 = "Here is exactly how it all unfolded and why it cost forty thousand dollars."
        res_2 = phoneticize_reddit_text(sample_2)
        self.assertNotIn("I-T", res_2)
        self.assertNotIn("i-t", res_2)
        self.assertIn("how it all unfolded", res_2)

        sample_3 = "AITA for telling my sister that it wasn't my fault?"
        res_3 = phoneticize_reddit_text(sample_3)
        self.assertNotIn("I-T", res_3)
        self.assertIn("Am I the jerk", res_3)
        self.assertIn("that it wasn't", res_3)

    def test_it_department_contextually_phoneticized(self):
        """Verifica se 'IT department' ou 'working in IT' recebe fonética adequada sem afetar 'it'."""
        sample = "I worked in the IT department where the director ordered new rules."
        res = phoneticize_reddit_text(sample)
        self.assertIn("I.T. department", res)

    def test_blacklist_author_deduplication(self):
        """Verifica que a blacklist rejeita histórias do mesmo autor."""
        auditor = ContextualTopicAuditor()
        existing = [
            {
                "tema": "Boss demanded I follow the handbook to the letter",
                "author": "u/ComplianceGuru",
                "subreddit": "r/maliciouscompliance",
                "url": "https://reddit.com/r/maliciouscompliance/comments/abc123"
            }
        ]
        
        # Mesmo autor com título ligeiramente diferente
        candidate_same_author = {
            "title": "Company refused to pay overtime so I left at 5 PM",
            "author": "u/ComplianceGuru",
            "subreddit": "r/antiwork",
            "url": "https://reddit.com/r/antiwork/comments/xyz789"
        }

        is_dup, score, reason = auditor.evaluate_candidate(candidate_same_author, existing)
        self.assertTrue(is_dup)
        self.assertIn("complianceguru", reason.lower())

    def test_blacklist_url_deduplication(self):
        """Verifica que a blacklist rejeita URLs já registradas."""
        auditor = ContextualTopicAuditor()
        existing = [
            {
                "tema": "Landlord kept deposit for normal wear and tear",
                "author": "u/TenantOne",
                "url": "https://reddit.com/r/legaladvice/comments/post_999"
            }
        ]
        candidate_same_url = {
            "title": "Unfair landlord deductions in small claims",
            "author": "u/DifferentAuthor",
            "url": "https://reddit.com/r/legaladvice/comments/post_999"
        }
        is_dup, score, reason = auditor.evaluate_candidate(candidate_same_url, existing)
        self.assertTrue(is_dup)
        self.assertIn("URL", reason)

    def test_blacklist_semantic_and_entity_deduplication(self):
        """Verifica que histórias com a mesma entidade e domínio de conflito análogo são rejeitadas."""
        auditor = ContextualTopicAuditor()
        existing = [
            {
                "tema": "Landlord tried to steal my $4,500 security deposit with fake contractor bills",
                "core_entity": "landlord",
                "author": "u/TenantA",
                "body": "Landlord claimed $4500 in damages for paint and cleaning."
            }
        ]

        # Variação do mesmo tema de landlord e security deposit
        candidate_duplicate = {
            "title": "Landlord stole my security deposit claiming fake paint damages",
            "author": "u/TenantB",
            "body": "Landlord withheld security deposit using fake contractor invoices."
        }
        is_dup, score, reason = auditor.evaluate_candidate(candidate_duplicate, existing)
        self.assertTrue(is_dup, f"Deveria detectar duplicata de landlord deposit: {reason}")

        # História completamente diferente (deve ser aprovada)
        candidate_unique = {
            "title": "Entitled neighbor built a wooden fence across my private driveway",
            "author": "u/HomeownerX",
            "body": "Neighbor claimed my driveway was an easement and erected a fence."
        }
        is_dup_unique, _, _ = auditor.evaluate_candidate(candidate_unique, existing)
        self.assertFalse(is_dup_unique, "História inédita de vizinho e cerca deve ser aprovada!")


if __name__ == "__main__":
    unittest.main()
