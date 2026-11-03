"""Official checkpoint routing and signed-URL log hygiene; no model substitutes."""
import importlib.util
from pathlib import Path
import unittest

EXPERIMENT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("phase16d_acquire", EXPERIMENT / "acquire_checkpoint.py")
acquire = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquire)


class OfficialCheckpointDestinations(unittest.TestCase):
    def test_official_hugging_face_redirects_and_fallback_are_allowed(self):
        for url in (acquire.URL, acquire.FALLBACK_URL,
                    "https://cas-bridge.xethub.hf.co/xet-bridge-us/file?signature=temporary"):
            self.assertTrue(acquire.official_destination(url))

    def test_unrelated_hosts_and_credential_bearing_or_plaintext_urls_are_rejected(self):
        for url in ("https://hf.co.attacker.example/file", "https://attacker.example/file",
                    "http://huggingface.co/file", "https://user:password@huggingface.co/file",
                    "https://huggingface.co:8443/file"):
            self.assertFalse(acquire.official_destination(url))

    def test_signed_query_and_fragment_are_not_recorded(self):
        self.assertEqual(
            acquire.public_destination("https://cas-bridge.xethub.hf.co/path?signature=temporary#fragment"),
            "https://cas-bridge.xethub.hf.co/path")


if __name__ == "__main__":
    unittest.main()
