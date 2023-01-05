import sqlite3
from datetime import datetime
from datetime import timedelta
import struct
import ipaddress
import ipinfo
import base64
from ulogd_sqlite3.common import gs
from ulogd_sqlite3.bar_graph import get_day_usage_bar


DAYS_TO_SHOW = 3


def get_sql_unixtime_filter_on_day(datetimelist: list, startfieldname: str, endfieldname: str):
    """
    Create a list of sql inserts based on list of datetime timestamps. The list is aligned by date start and date end.
    For example providing [datetime.now()] will give you and a list of one sql string like
    "start < 1500066000 AND end > 1499979600" The names "start" and "end" are also parameters.
    You insert this sql in your query as a filter.
    :param datetimelist:
    :param startfieldname:
    :param endfieldname:
    :return: a list of sql inserts to be used as filters for query.
    """
    ret = list()
    for dt in datetimelist:
        start = datetime(dt.year, dt.month, dt.day)
        end = start + timedelta(1)
        ret.append(f"{startfieldname} < {int(end.timestamp())} AND {endfieldname} > {int(start.timestamp())}")
    return ret


def get_sql_unixtime_filter_on_day_range(datetimestart: datetime, datetimeend: datetime,
                                         startfieldname: str, endfieldname: str):
    start = datetime(datetimestart.year, datetimestart.month, datetimestart.day)
    end = datetime(datetimeend.year, datetimeend.month, datetimeend.day) + timedelta(1)
    return f"{startfieldname} < {int(end.timestamp())} AND {endfieldname} > {int(start.timestamp())}"


def get_days_list(datetimelist: list):
    ret = list()
    for dt in datetimelist:
        ret.append(datetime(dt.year, dt.month, dt.day))
    ret.append(ret[-1] + timedelta(1))
    return ret


head = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <title>Access info</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta charset="UTF-8">
    <style>
    .collapsible {
      background-color: #777;
      color: white;
      cursor: pointer;
      padding: 5px;
      width: 100%;
      border: 2px solid #888;
      text-align: left;
      outline: none;
      font-size: 15px;
    }

    .active, .collapsible:hover {
      background-color: #555;
    }

    .content {
      padding: 0 5px;
      display: none;
      overflow: hidden;
      background-color: #f1f1f1;
    }

    table, th, td {
      border: 1px solid black;
      border-collapse: collapse;
    }

    div {
      padding: 5px;
    }
    </style>
    </head>
    <body>
    """
tail = """

    <script>
    var coll = document.getElementsByClassName("collapsible");
    var i;

    for (i = 0; i < coll.length; i++) {
      coll[i].addEventListener("click", function() {
        this.classList.toggle("active");
        var content = this.nextElementSibling;
        if (content.style.display === "block") {
          content.style.display = "none";
        } else {
          content.style.display = "block";
        }
      });
    }
    </script>

    </body>
    </html>
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
        info = ""
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
    answer = head
    answer += "<h2>Connections for IP {}</h2>".format(source_ip)

    days = get_days_list([datetime.now() + timedelta(i - DAYS_TO_SHOW) for i in range(1, DAYS_TO_SHOW + 1)])
    con = sqlite3.connect(gs._db_filename)
    cur = con.cursor()
    sql_date_filter = get_sql_unixtime_filter_on_day_range(days[0], days[-1], "flow_start_sec", "flow_end_sec")
    cur.execute(
        "SELECT flow_start_sec, flow_end_sec, orig_ip_daddr FROM ulog_ct "
        "WHERE orig_ip_saddr = {} AND {} ".format(ip2int(source_ip), sql_date_filter) +
        "AND flow_start_sec IS NOT NULL "
        "ORDER BY flow_start_sec")

    cts = cur.fetchall()

    def parse_cts(cts, days):
        """
        Returns a list of dictionaries. Each list item for each days item.
        Each dictionary is keyed by IP in string form ("1.2.3.4") and contains time in seconds of
        connection start and end relative to the day start.
        :param cts:
        :param days:
        :return:
        """
        ret = list()
        for _ in days:
            ret.append(dict())

        days_unixtime = [int(day.timestamp()) for day in days]  # Convert days to unixtime
        for ct in cts:
            for i, day in enumerate(days_unixtime[:-1]):
                if ct[0] <= days_unixtime[i + 1] and ct[1] >= day:
                    ip = int2ip(ct[2])
                    if ip not in ret[i]:
                        ret[i][ip] = list()
                    ret[i][ip].append((ct[0] - day, ct[1] - day))
        return ret

    day_ip_cts = parse_cts(cts, days)

    for day, ipdict in zip(days[:-1], day_ip_cts[:-1]):
        answer += '<button type="button" class="collapsible">{}</button>'.format(day.strftime("%d %b"))
        answer += '<table class="content">'
        answer += """<tr>
           <td>IP</td>
           <td>Info</td>
           <td>Usage bar</td>
           </tr>"""

        for ip in ipdict:
            answer += "<tr><td>{}</td><td>{}</td><td><img src=data:image/png;base64,{}></td></tr>".format(
                ip,
                ip2info(ip),
                base64.b64encode(get_day_usage_bar(ipdict[ip], 500, 10)).decode("utf-8")
            )
        answer += "</table>"

    answer += tail
    return answer


def get_main_page():
    answer = """
<!DOCTYPE html>
<html lang="en">
<head>
<title>ulogd_sqlite3 main page</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="UTF-8">
    </head>
<body>
<h2>Select IP</h2>
"""

    answer += """
<ul>"""

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
