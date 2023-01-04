import sqlite3
import struct
import ipaddress
import ipinfo
import logging
from ulogd_sqlite3.common import gs


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


def ip2info(ip, cache_db="var/cache.sqlite3db"):

    def cache_store(details):
        con = sqlite3.connect(cache_db)
        cur = con.cursor()
        details.pop("country_flag", None)
        details.pop("country_currency", None)
        details.pop("continent", None)
        columns = ", ".join("`" + str(y) + "`" for y in details.keys())
        values = ", ".join("'" + str(z).replace("/", "_").replace("'", '"') + "'" for z in details.values())
        sql = "INSERT INTO ipinfo( " + columns + " ) values (" + values + ")"
        cur.execute(sql)
        con.commit()

    def cache_lookup(ip):
        con = sqlite3.connect(cache_db)
        cur = con.cursor()
        cur.execute('SELECT hostname, org, country_name, city FROM ipinfo WHERE "ip" = "{}"'.format(ip))
        res = cur.fetchall()
        if len(res) == 0:
            return None
        else:
            return res[0]

    ipinfo_token = gs._ip_info
    if ipinfo_token != "":
        info = ip + " "
        details = cache_lookup(ip)
        if details is None:
            handler = ipinfo.getHandler(ipinfo_token)
            details = handler.getDetails(ip).details
            cache_store(details)
            if "hostname" in details:
                info += "Host {}. ".format(details["hostname"])
            if "org" in details:
                info += "Organization {}. ".format(details["org"])
            if "country_name" in details and "city" in details:
                info += "{} {}.".format(details["country_name"], details["city"])
        else:
            if details[0] is not None:
                info += "Host {}. ".format(details[0])
            if details[1] is not None:
                info += "Organization {}. ".format(details[1])
            if details[2] is not None and details[3] is not None:
                info += "{} {}.".format(details[2], details[3])
    else:
        info = ip

    return info


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

    con = sqlite3.connect(gs._db_filename)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT orig_ip_daddr FROM ulog_ct "
                "WHERE orig_ip_saddr = {} "
                "ORDER BY orig_ip_daddr LIMIT 12".format(ip2int(source_ip)))
    iplist = cur.fetchall()
    for dest_ip in iplist:
        ip = int2ip(dest_ip[0])
        info = ip2info(ip)
        answer += "<li><details><summary>{}</summary><ul>".format(info)
        cur.execute(
            "SELECT flow_start_sec, flow_end_sec FROM ulog_ct "
            "WHERE orig_ip_saddr = {} AND orig_ip_daddr = {}".format(
                ip2int(source_ip), dest_ip[0]))
        for data in cur.fetchall():
            try:
                answer += "<li>Duration {}</li>".format(data[1] - data[0])
            except Exception as e:
                logging.warning("Can't parse (flow_start_sec, flow_end_sec) from database query: " + repr(e))
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

    con = sqlite3.connect(gs._db_filename)
    cur = con.cursor()
    cur.execute("SELECT DISTINCT orig_ip_saddr FROM ulog_ct ORDER BY orig_ip_saddr LIMIT 100")
    iplist = cur.fetchall()
    for ip in iplist:
        answer += "<li><a href='/?ip={}'>{}</a></li>".format(int2ip(ip[0]), int2ip(ip[0]))
    answer += """</ul>

</body>
</html>"""

    return answer
