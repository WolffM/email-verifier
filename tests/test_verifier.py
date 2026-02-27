import imaplib
import socks
from unittest import TestCase
from unittest.mock import patch

from verifier.verifier import (Verifier,
                       EmailFormatError,
                       Address)
from verifier.socks_imap import SocksIMAP4

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


class SocksIMAP4TestCase(TestCase):

    @patch('imaplib.IMAP4.__init__', return_value=None)
    def test_init_stores_proxy_settings(self, mock_init):
        imap = SocksIMAP4(host='imap.example.com', port=143,
                          proxy_type=socks.SOCKS5,
                          proxy_addr='proxy.example.com',
                          proxy_port=1080,
                          proxy_username='user',
                          proxy_password='pass')
        self.assertEqual(imap.proxy_type, socks.SOCKS5)
        self.assertEqual(imap.proxy_addr, 'proxy.example.com')
        self.assertEqual(imap.proxy_port, 1080)
        self.assertEqual(imap.proxy_username, 'user')
        self.assertEqual(imap.proxy_password, 'pass')

    @patch('socks.create_connection')
    def test_create_socket_uses_socks_when_proxy_set(self, mock_socks_connect):
        imap = SocksIMAP4.__new__(SocksIMAP4)
        imap.proxy_type = socks.SOCKS5
        imap.proxy_addr = 'proxy.example.com'
        imap.proxy_port = 1080
        imap.proxy_rdns = True
        imap.proxy_username = None
        imap.proxy_password = None
        imap.socket_options = None
        imap.host = 'imap.example.com'
        imap.port = imaplib.IMAP4_PORT

        imap._create_socket(timeout=10)

        mock_socks_connect.assert_called_once_with(
            ('imap.example.com', imaplib.IMAP4_PORT),
            timeout=10,
            proxy_type=socks.SOCKS5,
            proxy_addr='proxy.example.com',
            proxy_port=1080,
            proxy_rdns=True,
            proxy_username=None,
            proxy_password=None,
            socket_options=None)

    @patch('imaplib.IMAP4._create_socket')
    def test_create_socket_falls_back_to_imap4_without_proxy(self, mock_super_socket):
        imap = SocksIMAP4.__new__(SocksIMAP4)
        imap.proxy_type = None
        imap.host = 'imap.example.com'
        imap.port = imaplib.IMAP4_PORT

        imap._create_socket(timeout=10)

        mock_super_socket.assert_called_once_with(10)
        