from unittest import TestCase
from unittest.mock import patch

from verifier.verifier import (Verifier,
                       EmailFormatError,
                       Address)

class Record:
    def __init__(self, preference, server):
        self.server = server
        self.preference = preference

    def to_text(self):
        return f"{self.preference} {self.server}"

r1 = Record(10, 'smtp.example.com')
r2 = Record(21, 'smtp.example.l.com')
dns_response = [r1, r2]


class VerifierTestCase(TestCase):
    
    def setUp(self):
        self.verifier = Verifier(source_addr="user@example.com")
    
    def test_random_email(self):
        mail_one = self.verifier._random_email('gmail.com')
        mail_two = self.verifier._random_email('yandex.com')

        # test both emails are different
        self.assertNotEqual(mail_one.split('@')[0], mail_two.split('@')[0])
        # test email have @ character
        self.assertTrue('@' in mail_one and '@' in mail_two)
        self.assertTrue(mail_one.endswith('gmail.com'))
        self.assertTrue(mail_two.endswith('yandex.com'))
    
    def test_parse_address_raises_on_non_email(self):
        invalid_mail_address = 'not_an_email'
        with self.assertRaises(EmailFormatError) as err:
            self.verifier._parse_address(invalid_mail_address)
        
        invalid_mail = "NOT_MAIL <not_an_email>"
        with self.assertRaises(EmailFormatError) as err:
            self.verifier._parse_address(invalid_mail)
        
        self.assertEqual(err.exception.msg, "address provided is invalid: NOT_MAIL <not_an_email>")
        
        invalid_mail = "NO_MAIL <>"
        with self.assertRaises(EmailFormatError) as err:
            self.verifier._parse_address(invalid_mail)
        

        self.assertEqual(err.exception.msg, "email does not contain address: NO_MAIL <>")

    def test_parse_address_returns_address_on_valid_emails(self):
        valid_email = "user@domain.com"
        addr = self.verifier._parse_address(valid_email)
        self.assertTrue(isinstance(addr, Address))
        self.assertEqual(addr.username, "user")
        self.assertEqual(addr.domain, "domain.com")
        self.assertEqual(addr.addr, "user@domain.com")

        valid_email = "USER <user@domain.com>"
        addr = self.verifier._parse_address(valid_email)
        self.assertEqual(addr.name, "USER")
    
    @patch.object(Verifier, '_can_deliver', return_value=(True, True, False))
    @patch('dns.resolver.query', return_value=dns_response)
    def test_verifier(self, m_resolver, m_deliver):
        # some ugly patching and mocking to test the flow of verfier
        result = self.verifier.verify('user@example.com')
        addr = self.verifier._parse_address("user@example.com")
        m_resolver.assert_called_with('example.com', 'MX')
        m_deliver.assert_called_once_with(dns_response[0].to_text().split(), addr)

    @patch.object(Verifier, '_can_deliver', return_value=(True, False, True))
    @patch('dns.resolver.query', return_value=dns_response)
    def test_catch_all_domain_is_not_deliverable(self, m_resolver, m_deliver):
        """
        When a domain is catch-all (accepts any RCPT TO), the email should
        not be marked as deliverable since we cannot confirm the address exists.
        This covers providers like Yahoo, Hotmail, AOL, and Outlook that accept
        any RCPT TO to prevent email enumeration.
        """
        result = self.verifier.verify('user@example.com')
        self.assertFalse(result['deliverable'])
        self.assertTrue(result['catch_all'])

    def test_can_deliver_catch_all_sets_deliverable_false(self):
        """
        When both the real email and a random email return 250, _can_deliver
        should return deliverable=False and catch_all=True.
        """
        address = self.verifier._parse_address('user@example.com')
        with patch('verifier.verifier.SMTP') as mock_smtp:
            mock_instance = mock_smtp.return_value.__enter__.return_value
            mock_instance.helo.return_value = (250, b'OK')
            mock_instance.mail.return_value = (250, b'OK')
            # Both real and random email return 250 (catch-all behavior)
            mock_instance.rcpt.return_value = (250, b'OK')
            host_exists, deliverable, catch_all = self.verifier._can_deliver(
                ['10', 'smtp.example.com'], address
            )
        self.assertTrue(host_exists)
        self.assertFalse(deliverable)
        self.assertTrue(catch_all)

    def test_can_deliver_non_catch_all_is_deliverable(self):
        """
        When the real email returns 250 but the random email does not,
        _can_deliver should return deliverable=True and catch_all=False.
        """
        address = self.verifier._parse_address('user@example.com')
        with patch('verifier.verifier.SMTP') as mock_smtp:
            mock_instance = mock_smtp.return_value.__enter__.return_value
            mock_instance.helo.return_value = (250, b'OK')
            mock_instance.mail.return_value = (250, b'OK')
            # Real email returns 250, random email returns 550 (non-catch-all)
            mock_instance.rcpt.side_effect = [
                (250, b'OK'),
                (550, b'User unknown'),
            ]
            host_exists, deliverable, catch_all = self.verifier._can_deliver(
                ['10', 'smtp.example.com'], address
            )
        self.assertTrue(host_exists)
        self.assertTrue(deliverable)
        self.assertFalse(catch_all)
        