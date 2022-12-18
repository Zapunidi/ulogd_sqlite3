#!/usr/bin/env python
# -*- coding: utf-8 -*-

from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import cgi
import logging
import sqlite3
import ipaddress
import struct
import ipinfo
import os
from urllib.parse import urlparse, parse_qs

db_filename = ""
ipinfo_token = ""
tree_style = """
    .tree{
      --spacing : 1.5rem;
      --radius  : 10px;
    }

    .tree li{
      display      : block;
      position     : relative;
      padding-left : calc(2 * var(--spacing) - var(--radius) - 2px);
    }

    .tree ul{
      margin-left  : calc(var(--radius) - var(--spacing));
      padding-left : 0;
    }

    .tree ul li{
      border-left : 2px solid #ddd;
    }

    .tree ul li:last-child{
      border-color : transparent;
    }

    .tree ul li::before{
      content      : '';
      display      : block;
      position     : absolute;
      top          : calc(var(--spacing) / -2);
      left         : -2px;
      width        : calc(var(--spacing) + 2px);
      height       : calc(var(--spacing) + 1px);
      border       : solid #ddd;
      border-width : 0 0 2px 2px;
    }

    .tree summary{
      display : block;
      cursor  : pointer;
    }

    .tree summary::marker,
    .tree summary::-webkit-details-marker{
      display : none;
    }

    .tree summary:focus{
      outline : none;
    }

    .tree summary:focus-visible{
      outline : 1px dotted #000;
    }

    .tree li::after,
    .tree summary::before{
      content       : '';
      display       : block;
      position      : absolute;
      top           : calc(var(--spacing) / 2 - var(--radius));
      left          : calc(var(--spacing) - var(--radius) - 1px);
      width         : calc(2 * var(--radius));
      height        : calc(2 * var(--radius));
      border-radius : 50%;
      background    : #ddd;
    }

    .tree summary::before{
      content     : '+';
      z-index     : 1;
      background  : #696;
      color       : #fff;
      line-height : calc(2 * var(--radius) - 2px);
      text-align  : center;
    }

    .tree details[open] > summary::before{
      content : '−';
    }
"""


def int2ip(i):
    i = struct.unpack("<I", struct.pack(">I", i))[0]
    return str(ipaddress.IPv4Address(i))


def ip2int(ip):
    o = list(map(int, ip.split(".")))
    res = (16777216 * o[3]) + (65536 * o[2]) + (256 * o[1]) + o[0]
    return res


def get_ip_page(source_ip):
    answer = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <title>ulogd_sqlite3 main page</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta charset="UTF-8">
    <style>"""
    answer += tree_style
    answer += """
    </style>
    </head>
    <body>"""
    answer += "<h2>Connections for IP {}</h2>".format(source_ip)

    answer += """
    <ul class="tree">"""

    con = sqlite3.connect(db_filename)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT orig_ip_daddr FROM ulog_ct "
                "WHERE orig_ip_saddr = {} "
                "ORDER BY orig_ip_daddr LIMIT 50".format(ip2int(source_ip)))
    iplist = cur.fetchall()
    for dest_ip in iplist:
        ip = int2ip(dest_ip[0])
        if ipinfo_token != "":
            handler = ipinfo.getHandler(ipinfo_token)
            details = handler.getDetails(ip).details
            info = ip + " "
            if "hostname" in details:
                info += "Host {}. ".format(details["hostname"])
            if "org" in details:
                info += "Organization {}. ".format(details["org"])
            if "country_name" in details and "city" in details:
                info += "{} {}.".format(details["country_name"], details["city"])
        else:
            info = ip
        answer += "<li><details><summary>{}</summary><ul>".format(info)
        cur.execute(
            "SELECT flow_start_sec, flow_end_sec FROM ulog_ct "
            "WHERE orig_ip_saddr = {} AND orig_ip_daddr = {}".format(
                ip2int(source_ip), dest_ip[0]))
        for data in cur.fetchall():
            answer += "<li>Duration {}</li>".format(data[1] - data[0])
        answer += "</ul></details></li>"

    answer += """</ul>

    </body>
    </html>"""

    return answer


def get_main_page():
    answer = """
<!DOCTYPE html>
<html lang="en">
<head>
<title>ulogd_sqlite3 main page</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="UTF-8">
    <style>"""
    answer += tree_style
    answer += """
    </style>
    </head>
<body>
<h2>Select IP</h2>
"""

    answer += """
<ul class="tree">"""

    con = sqlite3.connect(db_filename)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT orig_ip_saddr FROM ulog_ct ORDER BY orig_ip_saddr LIMIT 100")
    iplist = cur.fetchall()
    for ip in iplist:
        answer += "<li><a href='/?ip={}'>{}</a></li>".format(int2ip(ip[0]), int2ip(ip[0]))
    answer += """</ul>

</body>
</html>"""

    return answer


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
    con = sqlite3.connect('var/cache.sqlite3db')
    cur = con.cursor()
    cur.execute('SELECT name FROM sqlite_master WHERE "name"="ipinfo"')
    if cur.fetchone() is None:
        cur.execute('CREATE TABLE ipinfo(ip, other)')
        cur.execute('CREATE UNIQUE INDEX ip_index ON ipinfo (ip)')


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

    global ipinfo_token
    ipinfo_token = args.ipinfo

    # Check file availability
    try:
        f = open(args.filename, "rb")
        f.close()
        global db_filename
        db_filename = args.filename
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
