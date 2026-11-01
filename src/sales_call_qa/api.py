"""The webhook VAPI calls when a call ends.

uv run uvicorn sales_call_qa.api:app --reload --port 8001
"""

import hmac
import logging
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from sales_call_qa.generate_calls import REPO_ROOT
from sales_call_qa.pipeline import process_call

load_dotenv(REPO_ROOT / ".env")
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("sales_call_qa").setLevel(
    logging.INFO
)  # your own progress lines only

SECRET = os.environ["VAPI_WEBHOOK_SECRET"]

app = FastAPI()


@app.post("/webhooks/vapi")
async def vapi_webhook(request: Request, background: BackgroundTasks):
    # VAPI sends the secret as "Authorization: Bearer …" (older setups use X-Vapi-Secret)
    sent = request.headers.get("authorization", "").removeprefix("Bearer ")
    sent = sent or request.headers.get("x-vapi-secret", "")
    if not hmac.compare_digest(sent.encode(), SECRET.encode()):
        raise HTTPException(status_code=401)
    payload = await request.json()
    if payload.get("message", {}).get("type") != "end-of-call-report":
        return {}  # VAPI sends other messages too; they need no action
    background.add_task(process_call, payload)  # reply now, assess afterwards
    return {}
