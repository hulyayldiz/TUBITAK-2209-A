"""Incremental checksum-validated NMEA decoding with fix validity and measurement expiry."""
import math
import re
import time
import pynmea2


class NMEAStream:
    def __init__(self, ttl_s=3.):
        self.buffer = ""
        self.ttl_s = ttl_s
        self.position = None
        self.velocity = None
        self.gsv = {}
        self.revision = 0
        self.delivered = -1

    def feed(self, data, now=None):
        now = time.monotonic() if now is None else now
        self.buffer += data.decode("ascii", errors="replace") if isinstance(data, bytes) else data
        if len(self.buffer) > 65536:
            self.buffer = self.buffer[-8192:]
        lines = self.buffer.replace("\r", "\n").split("\n")
        self.buffer = lines.pop()
        if re.search(r"\*[0-9A-Fa-f]{2}$", self.buffer):
            lines.append(self.buffer)
            self.buffer = ""
        for line in lines:
            line = line[line.find("$"):].strip() if "$" in line else ""
            if not line:
                continue
            try:
                message = pynmea2.parse(line, check=True)
                kind = message.sentence_type
                if kind == "GSV":
                    talker = message.talker
                    number = int(message.msg_num)
                    if number == 1 or talker not in self.gsv:
                        self.gsv[talker] = {}
                    self.gsv[talker][number] = (now, [float(getattr(message, f"snr_{index}"))
                        for index in range(1,5) if str(getattr(message, f"snr_{index}", "")).strip()])
                elif kind in ("RMC", "GGA"):
                    valid = message.status == "A" if kind == "RMC" else int(message.gps_qual or 0) > 0
                    if not valid:
                        self.position = None
                        self.velocity = None
                        self.revision += 1
                        continue
                    lat, lon = float(message.latitude), float(message.longitude)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    self.position = (now, lat, lon)
                    self.revision += 1
                    if kind == "RMC" and message.spd_over_grnd != "":
                        speed = float(message.spd_over_grnd)*1.852
                        course = float(message.true_course) if message.true_course != "" else None
                        if course is not None and math.isfinite(speed) and speed >= 0:
                            self.velocity = (now, speed, course % 360.)
                elif kind == "VTG" and message.spd_over_grnd_kmph != "" and message.true_track != "":
                    if getattr(message, "faa_mode", "") != "N":
                        self.velocity = (now, float(message.spd_over_grnd_kmph), float(message.true_track)%360.)
            except (pynmea2.ParseError, ValueError, TypeError, AttributeError):
                continue
        return self.solution(now)

    def cn0(self, now=None):
        now = time.monotonic() if now is None else now
        values = [value for cycle in self.gsv.values() for timestamp, measurements in cycle.values()
                  if now-timestamp <= self.ttl_s for value in measurements if math.isfinite(value) and 0 <= value <= 99]
        return sum(values)/len(values) if values else float("nan")

    def solution(self, now=None):
        now = time.monotonic() if now is None else now
        if self.position is None or self.velocity is None or self.delivered == self.revision:
            return None
        if now-self.position[0] > self.ttl_s or now-self.velocity[0] > self.ttl_s:
            return None
        self.delivered = self.revision
        return self.position[1], self.position[2], self.velocity[1], self.velocity[2]
