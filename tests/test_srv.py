from unittest import TestCase
from ulogd_sqlite3.srv import HTTPRequestHandler
from ulogd_sqlite3.pages import ip2int, int2ip


class TestGET(TestCase):
    def test_get(self):
        self.assertTrue("do_GET" in dir(HTTPRequestHandler))

    def test_post(self):
        self.assertTrue("do_POST" in dir(HTTPRequestHandler))


class TestIPConvert(TestCase):
    def test_cycle(self):
        test_ip = "1.2.3.4"
        self.assertTrue(test_ip == int2ip(ip2int(test_ip)))
