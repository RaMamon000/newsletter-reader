"""APNs 送信（.p8 の ES256 JWT、HTTP/2、既定は sandbox）。ログにはHTTPステータスだけ出す。"""
from __future__ import annotations

import os
import time

import httpx
import jwt

TOPIC = "com.ramamon.newsletter"
HOSTS = {"sandbox": "https://api.sandbox.push.apple.com", "production": "https://api.push.apple.com"}


class ApnsConfig:
    def __init__(self, key_p8: str, key_id: str, team_id: str, device_token: str,
                 env: str = "sandbox", topic: str = TOPIC):
        self.key_p8 = key_p8.replace("\\n", "\n")
        self.key_id = key_id
        self.team_id = team_id
        self.device_token = device_token
        self.env = env
        self.topic = topic

    @classmethod
    def from_env(cls) -> "ApnsConfig | None":
        vals = {k: os.environ.get(k, "").strip() for k in
                ("APNS_KEY_P8", "APNS_KEY_ID", "APNS_TEAM_ID", "APNS_DEVICE_TOKEN")}
        if not all(vals.values()):
            return None
        return cls(vals["APNS_KEY_P8"], vals["APNS_KEY_ID"], vals["APNS_TEAM_ID"],
                   vals["APNS_DEVICE_TOKEN"], os.environ.get("APNS_ENV", "sandbox"))


def make_jwt(cfg: ApnsConfig, now: int | None = None) -> str:
    return jwt.encode({"iss": cfg.team_id, "iat": int(now or time.time())}, cfg.key_p8,
                      algorithm="ES256", headers={"kid": cfg.key_id})


def build_payload(title: str, body: str, issue_id: str) -> dict:
    return {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}, "issue_id": issue_id}


def send(cfg: ApnsConfig, title: str, body: str, issue_id: str, client: httpx.Client | None = None) -> int:
    """送信して HTTPステータスを返す。本文は一切ログに出さない。"""
    own = client is None
    client = client or httpx.Client(http2=True, timeout=20)
    try:
        r = client.post(
            f"{HOSTS.get(cfg.env, HOSTS['sandbox'])}/3/device/{cfg.device_token}",
            json=build_payload(title, body, issue_id),
            headers={"authorization": f"bearer {make_jwt(cfg)}", "apns-topic": cfg.topic,
                     "apns-push-type": "alert", "apns-priority": "10"},
        )
        return r.status_code
    finally:
        if own:
            client.close()
