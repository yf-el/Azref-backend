#!/usr/bin/env python3
"""Standalone Salesforce JWT Bearer auth test.

Run BEFORE wiring the Lambda: validates that the ECA config, the
integration user, and the private key all line up correctly.

Usage:
    export SF_CONSUMER_KEY="3MVG9..."           # from External Client App
    export SF_USERNAME="integration@azref.ma.dev"
    export SF_PRIVATE_KEY_PATH="~/secrets/azref-sf/azref_sf_private.key"
    # SF_DOMAIN defaults to "login" (use "test" for a sandbox)
    python scripts/test_sf_jwt.py

Success looks like:
    OK access_token: 00D5g00000XXXX!ARAAQ...
    OK instance_url: https://orgfarm-XXX-dev-ed.develop.my.salesforce.com
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import jwt  # PyJWT[crypto]


def main() -> int:
    try:
        consumer_key = os.environ["SF_CONSUMER_KEY"]
        username = os.environ["SF_USERNAME"]
    except KeyError as missing:
        print(f"ERROR: missing env var {missing}", file=sys.stderr)
        return 2

    private_key_path = os.environ.get(
        "SF_PRIVATE_KEY_PATH", "~/secrets/azref-sf/azref_sf_private.key"
    )
    domain = os.environ.get("SF_DOMAIN", "login")  # 'login' (prod/dev) | 'test' (sandbox)

    private_key = Path(private_key_path).expanduser().read_text()

    now = int(time.time())
    claims = {
        "iss": consumer_key,
        "sub": username,
        "aud": f"https://{domain}.salesforce.com",
        "exp": now + 180,
    }
    assertion = jwt.encode(claims, private_key, algorithm="RS256")

    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode()
    req = urllib.request.Request(
        f"https://{domain}.salesforce.com/services/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"FAIL {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode(), file=sys.stderr)
        return 1

    print(f"OK access_token: {payload['access_token'][:40]}...")
    print(f"OK instance_url: {payload['instance_url']}")
    print(f"OK scope: {payload.get('scope', 'n/a')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
