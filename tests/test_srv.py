from unittest import TestCase
from ulogd_sqlite3.srv import HTTPRequestHandler
from ulogd_sqlite3.pages import ip2int, int2ip, get_sql_unixtime_filter_on_day
from datetime import datetime


class TestGET(TestCase):
    def test_get(self):
        self.assertTrue("do_GET" in dir(HTTPRequestHandler))

    def test_post(self):
        self.assertTrue("do_POST" in dir(HTTPRequestHandler))


class TestIPConvert(TestCase):
    def test_cycle(self):
        test_ip = "1.2.3.4"
        self.assertTrue(test_ip == int2ip(ip2int(test_ip)))


class TestDatetime(TestCase):
    def test_sql(self):
        timestamps = [datetime.fromtimestamp(1500000000),
                      datetime.fromtimestamp(1600000000),
                      datetime.fromtimestamp(1600030801)]

        sqls = get_sql_unixtime_filter_on_day(timestamps, "start", "end")
        self.assertTrue(sqls[0] == "start < 1500066000 AND end > 1499979600")
        self.assertTrue(sqls[1] == "start < 1600030800 AND end > 1599944400")
        self.assertTrue(sqls[2] == f"start < {1600030800 + 60*60*24} AND end > 1600030800")
