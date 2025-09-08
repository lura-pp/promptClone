# server/mcp_hub/gmail/helpers.py

import os
import base64
from email.mime.text import MIMEText
from typing import Dict, Any, List
import logging

from google import genai
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize the Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)
logger = logging.getLogger(__name__)


def extract_email_body(payload: Dict[str, Any]) -> str:
    """
    Recursively extracts the body of an email from its payload.
    Prefers 'text/plain' over 'text/html'.
    """
    if "parts" in payload:
        text_plain, text_html = "", ""
        for part in payload["parts"]:
            data = part.get("body", {}).get("data")
            if not data:
                continue
            decoded = base64.urlsafe_b64decode(data).decode("utf-8")
            if part["mimeType"] == "text/plain":
                text_plain += decoded
            elif part["mimeType"] == "text/html":
                text_html += decoded
        return text_plain or text_html

    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    return ""


async def create_message(to: str, subject: str, message: str) -> str:
    """
    Creates and base64-encodes a MIME email.
    """
    msg = MIMEText(message)
    msg["To"] = to
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

def _simplify_message(msg: Dict) -> Dict:
    """Simplifies a Gmail message resource for LLM consumption."""
    headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
    return {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "snippet": msg.get("snippet"),
        "subject": headers.get("subject"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "date": headers.get("date"),
    }

def _simplify_label(label: Dict) -> Dict:
    """Simplifies a Gmail label resource."""
    return {
        "id": label.get("id"),
        "name": label.get("name"),
        "type": label.get("type"), # 'system' or 'user'
    }

def _simplify_filter(filter_obj: Dict) -> Dict:
    """Simplifies a Gmail filter resource."""
    return {
        "id": filter_obj.get("id"),
        "criteria": filter_obj.get("criteria"),
        "action": filter_obj.get("action"),
    }

async def summarize_emails_with_gemini(emails: List[Dict]) -> str:
    """Summarizes a list of emails using the Gemini API."""
    if not GEMINI_API_KEY:
        return "Cannot summarize emails: Gemini API key is not configured."
    if not emails:
        return "No emails to summarize."

    prompt = "Please provide a concise, bulleted summary of the following unread emails. For each, mention the sender and a one-sentence summary of the content:\n\n"
    for email in emails:
        prompt += f"From: {email.get('from')}\nSubject: {email.get('subject')}\nSnippet: {email.get('snippet')}\n\n---\n\n"

    try:
        response = client.generate_content(prompt)
        return response.text
    except Exception as e:
        return {"status": "failure", "error": str(e)}