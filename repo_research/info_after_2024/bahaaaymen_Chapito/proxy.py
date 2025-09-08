from typing import Callable, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import time
import uuid
from pydantic import BaseModel, field_validator
import uvicorn
import logging


class Message(BaseModel):
    role: str
    content: str

    @field_validator("content", mode="before")
    def transform_content(cls, value):
        if isinstance(value, list):
            text_parts = [item["text"] for item in value if item.get("type") == "text"]
            return "\n\n".join(text_parts)
        return value


class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


app = FastAPI()

last_chat_messages: List[str] = []


def find_index_from_end(lst: List[Message], values: List[str]) -> int:
    for i in range(len(lst) - 1, -1, -1):
        message = lst[i]
        if message.content.strip() in values:
            return i
    return -1


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=404, content={"message": "Undefined route", "requested_url": request.url.path})


@app.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    global last_chat_messages

    logging.debug(f"Request received: {request}")

    if not request.messages:
        raise HTTPException(status_code=400, detail="Field 'messages' is missing or empty")

    logging.debug(f"Last revelant message in request: {request.messages[-2]}")

    index_of_last_message = find_index_from_end(request.messages, last_chat_messages)
    prompt = "\n\n".join(
        f"[{message.role}] {message.content}" for message in request.messages[index_of_last_message + 1 :]
    )
    last_chat_messages.append(request.messages[-1].content.strip())
    if not prompt:
        logging.debug("Can't determine latest messages, sending the whole chat session")
        prompt = "\n\n".join(f"[{message.role}] {message.content}" for message in request.messages)

    response_content = app.state.send_request_and_get_response(app.state.driver, prompt)
    if response_content:
        last_chat_messages.append(response_content)
    logging.debug(f"Response from chat ends with: {response_content[-100:]}")
    logging.debug("Sending response")

    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gpt-3.5-turbo",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": response_content}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(response_content.split()),
            "total_tokens": len(prompt.split()) + len(response_content.split()),
        },
    }


def init_proxy(driver, send_request_and_get_response: Callable) -> None:
    app.state.driver = driver
    app.state.send_request_and_get_response = send_request_and_get_response
    uvicorn.run(app, host="127.0.0.1", port=5001)
