# Probe agent for measuring a hosted-agent platform. No model calls.
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STARTED = time.time()
DATA = "/data" if os.path.isdir("/data") else os.path.join(os.getcwd(), "data")
os.makedirs(DATA, exist_ok=True)
COUNTER = os.path.join(DATA, "chat_count.txt")


def uptime():
    try:
        return float(open("/proc/uptime").read().split()[0])
    except OSError:
        return None


def bump():
    n = int(open(COUNTER).read()) + 1 if os.path.exists(COUNTER) else 1
    with open(COUNTER, "w") as f:
        f.write(str(n))
        f.flush()
        os.fsync(f.fileno())
    return n


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self.send(200, {"ok": True})
        if self.path == "/schedules":
            return self.send(200, [{"id": "tick", "cron": "*/5 * * * *", "tz": "UTC",
                                    "prompt": "scheduled tick", "enabled": True}])
        if self.path in ("/", "/info"):
            return self.send(200, {
                "server_started_unix": STARTED, "now_unix": time.time(),
                "uptime_s": uptime(), "port": os.environ.get("PORT"),
                "headers": {k: v for k, v in self.headers.items() if k.lower().startswith(("x-", "cf-", "via"))},
            })
        self.send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/chat":
            if body.get("message", "").startswith("sleep "):
                time.sleep(float(body["message"].split()[1]))
            n = bump()
            line = json.dumps({"at": time.time(), "source": body.get("source"), "message": body.get("message")})
            with open(os.path.join(DATA, "chat_log.jsonl"), "a") as f:
                f.write(line + "\n")
            return self.send(200, {"response": json.dumps({
                "count": n, "source": body.get("source"), "keys": sorted(body.keys()),
                "uptime_s": uptime(), "server_age_s": round(time.time() - STARTED, 3)})})
        self.send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
