#!/usr/bin/env python
# -*- coding: utf-8 -*-

from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse
import cgi
import logging
import sqlite3
import ipaddress
import struct
from urllib.parse import urlparse, parse_qs

db_filename = ""

def get_main_page():
    answer = """
<!DOCTYPE html>
<html lang="en">
<head>
<title>ulogd_sqlite3 main page</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="UTF-8">
<style>
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
</style>
</head>
<body>
<h2>Select IP</h2>
"""

    answer += """
<ul class="tree">"""

    def int2ip(i):
        i = struct.unpack("<I", struct.pack(">I", i))[0]
        return str(ipaddress.IPv4Address(i))

    con = sqlite3.connect(db_filename)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT orig_ip_saddr FROM ulog_ct LIMIT 100")
    iplist = cur.fetchall()
    for ip in iplist:
        answer += "<li><details><summary>{}</summary><ul>".format(int2ip(ip[0]))
        cur.execute("SELECT flow_start_sec, flow_end_sec, orig_ip_daddr FROM ulog_ct WHERE orig_ip_saddr = {}".format(ip[0]))
        for data in cur.fetchall():
            try:
                answer += "<li>Destination {}. Duration {}</li>".format(int2ip(data[2]), data[1] - data[0])
            except Exception:
                pass
        answer += "</ul></details></li>"


    answer +="""</ul>

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
        if path == "/" or path == "":
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


def run():
    parser = argparse.ArgumentParser(description="shows data from ulogd sqlite3 database in a form of a web page")
    parser.add_argument("filename", type=str, help="a filename to load database from.")
    parser.add_argument("-p", "--port", type=int, help="a port to serve http connections.", default="80")
    args = parser.parse_args()

    logging.basicConfig(filename="ulogd_sqlite3.log", level=logging.WARNING)

    try:
        f = open(args.filename, "rb")
        f.close()
        global db_filename
        db_filename = args.filename
    except FileNotFoundError as e:
        print(e)
        print("Can't open database {}".format(args.filename))
        exit(1)

    logging.info("http server is starting...")
    server_address = ("0.0.0.0", args.port)
    httpd = HTTPServer(server_address, HTTPRequestHandler)
    logging.info("http server is running...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
