class GlobalSettings:
    def __init__(self):
        self._db_filename = ""
        self._ip_info = ""

    def set_db(self, db_filename: str):
        self._db_filename = db_filename

    def set_ip_info(self, ip_info: str):
        self._ip_info = ip_info


gs = GlobalSettings()
