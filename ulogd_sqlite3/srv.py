#!/usr/bin/env python
# -*- coding: utf-8 -*-

from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import cgi
import logging
import sqlite3
import os
from urllib.parse import urlparse, parse_qs
from ulogd_sqlite3.pages import get_ip_page, get_main_page
from ulogd_sqlite3.common import gs


class HTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_HEAD(self):  # noqa
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def _reply_page_and_headers(self, path, query):
        answer = ""
        if path == "/" or path == "":
            if "ip" in query:
                if query["ip"][0] != "":
                    answer = get_ip_page(query["ip"][0])
            else:
                answer = get_main_page()
        else:
            raise ValueError("Path not found.")

        self.do_HEAD()
        self.wfile.write(answer.encode("utf-8"))

    def do_GET(self):  # noqa
        # Parse and process parameters in URL
        parsed = urlparse(self.path)
        try:
            self._reply_page_and_headers(parsed.path, parse_qs(parsed.query, keep_blank_values=True))
        except ValueError:
            self.send_error(404, "Not found")
            self.end_headers()
            return

    def do_POST(self):  # noqa
        parsed = urlparse(self.path)
        ctype, pdict = cgi.parse_header(self.headers.get("content-type"))
        if ctype == "multipart/form-data":
            postvars = cgi.parse_multipart(self.rfile, pdict)
        elif ctype == "application/x-www-form-urlencoded":
            length = int(self.headers.get("content-length"))
            postvars = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        else:
            postvars = {}
        try:
            self._reply_page_and_headers(parsed.path, postvars)
        except ValueError:
            self.send_error(404, "Not found")
            self.end_headers()
            return


def _check_var_cache():
    # Check and prepare var folder
    if not os.path.isdir("var"):
        os.mkdir("var", 0o777)
    # Check and prepare cache database
    con = sqlite3.connect("var/cache.sqlite3db")
    cur = con.cursor()
    cur.execute('SELECT name FROM sqlite_master WHERE "name"="ipinfo"')
    if cur.fetchone() is None:
        cur.execute("CREATE TABLE ipinfo("
                    "`ip`, `anycast`, `hostname`, `bogon`, `city`, `region`, `country`, `loc`, `org`, `postal`, "
                    "`timezone`, `country_name`, `isEU`, `latitude`, `longitude` "
                    ")")
        cur.execute("CREATE UNIQUE INDEX ip_index ON ipinfo (ip)")


def run():
    parser = argparse.ArgumentParser(description="shows data from ulogd sqlite3 database in a form of a web page")
    parser.add_argument("filename", type=str, help="a filename to load database from.")
    parser.add_argument("-p", "--port", type=int, help="a port to serve http connections.", default="80")
    parser.add_argument("-i", "--ipinfo",
                        type=str,
                        help="an ipinfo.io token for resolving IPs into hostname/organization.",
                        default="")
    args = parser.parse_args()

    logging.basicConfig(filename="ulogd_sqlite3.log", level=logging.WARNING)

    gs.set_ip_info(args.ipinfo)
    # Check file availability
    try:
        f = open(args.filename, "rb")
        f.close()
        gs.set_db(args.filename)
    except FileNotFoundError as e:
        print(e)
        print("Can't open database {}".format(args.filename))
        exit(1)

    _check_var_cache()

    logging.info("http server is starting...")
    server_address = ("0.0.0.0", args.port)
    httpd = HTTPServer(server_address, HTTPRequestHandler)
    logging.info("http server is running...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
