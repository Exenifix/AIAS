import json
import os
import urllib.parse

import aiohttp
from dotenv import load_dotenv
from exencolorlogs import Logger

from utils.errors import LinkCheckFailure

load_dotenv()
APIKEY = os.getenv("IPQS_APIKEY")
assert APIKEY is not None, "Missing IPQS apikey"

log = Logger("IPQS")


async def is_url_safe(url: str) -> bool:
    async with aiohttp.ClientSession("https://ipqualityscore.com") as session:
        r = await session.get(f"/api/json/url/{APIKEY}/{urllib.parse.quote(url, '')}")
        if r.status != 200:
            try:
                error_text = (await r.json()).get("message", "No info")
            except json.JSONDecodeError:
                log.warning("Failed to decode json")
                error_text = "No info"
            except aiohttp.ContentTypeError:
                log.warning("Failed to decode json")
                error_text = await r.text()
            raise LinkCheckFailure(url, r.status, error_text)

        res = await r.json()
        try:
            return res["risk_score"] < 75
        except KeyError:
            raise Exception(
                f"URL response did not contain `risk_score` key. Response: \n{res}"
            )
