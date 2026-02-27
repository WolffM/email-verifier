import imaplib
import socks


class SocksIMAP4(imaplib.IMAP4):

    def __init__(self,
            host='',
            port=imaplib.IMAP4_PORT,
            proxy_type=None,
            proxy_addr=None,
            proxy_port=None,
            proxy_rdns=True,
            proxy_username=None,
            proxy_password=None,
            socket_options=None):

        self.proxy_type = proxy_type
        self.proxy_addr = proxy_addr
        self.proxy_port = proxy_port
        self.proxy_rdns = proxy_rdns
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        self.socket_options = socket_options

        super(SocksIMAP4, self).__init__(host, port)

    def _create_socket(self, timeout):
        if self.proxy_type:
            return socks.create_connection(
                (self.host or None, self.port),
                timeout=timeout,
                proxy_type=self.proxy_type,
                proxy_addr=self.proxy_addr,
                proxy_port=self.proxy_port,
                proxy_rdns=self.proxy_rdns,
                proxy_username=self.proxy_username,
                proxy_password=self.proxy_password,
                socket_options=self.socket_options)
        return super(SocksIMAP4, self)._create_socket(timeout)
