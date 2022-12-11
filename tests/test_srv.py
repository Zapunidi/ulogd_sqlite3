from unittest import TestCase
from ulogd_sqlite3.srv import HTTPRequestHandler


class TestGET(TestCase):
    def test_get(self):
        self.assertTrue("do_GET" in dir(HTTPRequestHandler))

    def test_post(self):
        self.assertTrue("do_POST" in dir(HTTPRequestHandler))
