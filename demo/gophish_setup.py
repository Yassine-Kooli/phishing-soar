"""Create the GoPhish demo campaign through its API. Idempotent: existing objects are reused.

The landing page is a training page: it shows a "this was a simulation" notice and captures
no credentials. Run it once the stack is up:

    python3 demo/gophish_setup.py
"""
import os
import sys

import requests
import urllib3

import _env  # noqa: F401  (ports and key from .env)

urllib3.disable_warnings()   # GoPhish's admin uses a self-signed certificate in the lab

ADMIN = os.getenv("GOPHISH_ADMIN_URL", "https://localhost:%s" % os.getenv("GOPHISH_ADMIN_PORT", "3333"))
KEY = os.getenv("GOPHISH_API_KEY", "")
DOMAIN = "secure-login.corp-verify.test"
TARGETS = [("alice@corp.local", "Alice", "Accounting"),
           ("bob@corp.local", "Bob", "Sales"),
           ("carol@corp.local", "Carol", "HR")]

HEAD = {"Authorization": "Bearer " + KEY}


def api(method, path, **kw):
    r = requests.request(method, ADMIN + "/api" + path, headers=HEAD, verify=False, timeout=10, **kw)
    r.raise_for_status()
    return r.json()


def exists(path, name):
    return next((x for x in api("GET", path) if x.get("name") == name), None)


def ensure(path, name, body):
    found = exists(path, name)
    if found:
        return found
    return api("POST", path, json=dict(body, name=name))


def launch_campaign(name, url=None):
    """Create (or reuse the objects of) the demo and launch one campaign named `name`."""
    if not KEY:
        sys.exit("GOPHISH_API_KEY is not set in .env (admin UI: Settings, Show)")
    ensure("/smtp/", "Mailpit lab SMTP", {
        "interface_type": "SMTP", "from_address": "it@corp-verify.test",
        "host": "mailpit:1025", "username": "", "password": "", "ignore_cert_errors": True})
    ensure("/pages/", "Simulated login page", {
        "html": "<html><body style='font-family:sans-serif;max-width:600px;margin:40px auto'>"
                "<h2>Security awareness exercise</h2><p>This was a simulated phishing e-mail sent by "
                "the IT security team. Nothing was collected. Use the report button in your mail "
                "client next time you are unsure.</p></body></html>",
        "capture_credentials": False, "capture_passwords": False, "redirect_url": ""})
    ensure("/templates/", "Verify your Corp account", {
        "subject": "Action required: verify your Corp account",
        "text": "Your Corp account will be suspended within 24 hours. Verify now: {{.URL}}",
        "html": "<p>Your Corp account will be suspended within 24 hours.</p>"
                "<p><a href=\"{{.URL}}\">Verify now</a></p>",
        "envelope_sender": ""})
    ensure("/groups/", "Lab staff", {
        "targets": [{"email": e, "first_name": f, "last_name": "", "position": p} for e, f, p in TARGETS]})
    c = api("POST", "/campaigns/", json={
        "name": name,
        "template": {"name": "Verify your Corp account"},
        "page": {"name": "Simulated login page"},
        "smtp": {"name": "Mailpit lab SMTP"},
        "url": url or "http://" + DOMAIN,
        "groups": [{"name": "Lab staff"}]})
    return c


def main():
    c = launch_campaign("Verify account simulation")
    print("campaign:", c.get("id"), c.get("status"), "targets:", len(TARGETS))


if __name__ == "__main__":
    main()
