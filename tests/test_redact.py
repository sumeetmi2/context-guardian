import unittest

from lib import redact


class RedactTests(unittest.TestCase):
    def test_empty_text_untouched(self):
        clean, count = redact.redact("")
        self.assertEqual(clean, "")
        self.assertEqual(count, 0)

    def test_no_secrets_untouched(self):
        text = "Just a normal sentence about fixing a bug in checkout.py."
        clean, count = redact.redact(text)
        self.assertEqual(clean, text)
        self.assertEqual(count, 0)

    def test_aws_access_key_redacted(self):
        text = "key is AKIAABCDEFGHIJKLMNOP in the config"
        clean, count = redact.redact(text)
        self.assertEqual(count, 1)
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", clean)
        self.assertIn(redact.REPLACEMENT, clean)

    def test_github_token_redacted(self):
        text = "token: ghp_" + "a" * 36
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("ghp_" + "a" * 36, clean)

    def test_slack_token_redacted(self):
        text = "xoxb-" + "0" * 12 + "-" + "notarealtoken"
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("notarealtoken", clean)

    def test_private_key_block_redacted(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIB...fakekeydata...\n-----END RSA PRIVATE KEY-----"
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("MIIB...fakekeydata...", clean)

    def test_bearer_token_redacted(self):
        text = "Authorization header uses bearer abcdef1234567890ABCDEF"
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("abcdef1234567890ABCDEF", clean)

    def test_keyish_assignment_redacted(self):
        text = 'api_key = "sk-abcdefgh12345678"'
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("sk-abcdefgh12345678", clean)

    def test_raw_secret_never_reaches_output_across_all_patterns(self):
        text = (
            "AKIAABCDEFGHIJKLMNOP\n"
            "aws_secret_access_key: superSecretValue123\n"
            "ghp_" + "b" * 36 + "\n"
            "xoxp-000-000-notarealtoken\n"
            "password: hunter2hunter2\n"
        )
        clean, count = redact.redact(text)
        self.assertGreaterEqual(count, 4)
        for fragment in ["AKIAABCDEFGHIJKLMNOP", "superSecretValue123", "hunter2hunter2"]:
            self.assertNotIn(fragment, clean)

    def test_return_type_is_tuple_of_text_and_int(self):
        result = redact.redact("no secrets here")
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], int)


if __name__ == "__main__":
    unittest.main()
