# -*- coding: utf-8 -*-
# server.py — Continuous ASR + LLM voice reply + ESP32 playback signal
import os, sys, time, json, asyncio, base64, threading, queue, uuid
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, FileResponse
import uvicorn
import websocket  # pip install websocket-client
from mode_router import ModeRouter, match_enter_phone, match_exit_phone, VOICE, PHONE
from phone_agent_bridge import PhoneAgentBridge

# ========= 基本配置 =========
DASHSCOPE_API_KEY = "sk-a9440db694923d2b9a"  # 改成你的qwen api
if not DASHSCOPE_API_KEY:
    raise RuntimeError("未设置 DASHSCOPE_API_KEY（建议用环境变量）")

QWEN_WS_URL = (
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    "?model=qwen-omni-turbo-realtime"
)
VOICE_NAME  = "Chelsie"   # 可改成你喜欢的
SAMPLE_RATE = 16000
CHUNK_MS    = 20
BYTES_PER_CHUNK = SAMPLE_RATE * CHUNK_MS // 1000 * 2  # 640B

# 下行音频（LLM TTS）默认回落 24k，最终落地转 16k 单声道 WAV 供 ESP 播放
UPSTREAM_OUT_SR        = 24000
STANDARDIZED_FILENAME  = "_standardized_output.wav"
TARGET_SAMPLE_RATE     = 16000
TARGET_SAMPLE_WIDTH    = 2   # 16-bit
TARGET_CHANNELS        = 1   # mono

# ========== 全局模式（跨设备重连保持）==========
CURRENT_MODE = VOICE  # VOICE / PHONE

# 音频重采样
from pydub import AudioSegment
import imageio_ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

app = FastAPI()

def ts(): return time.strftime("%H:%M:%S")
def log(*a): print(f"[{ts()}]", *a); sys.stdout.flush()

# 供 ESP32 拉配置与文件
@app.get("/health", response_class=PlainTextResponse)
def health(): return "OK. WebSocket endpoint: /ws_audio"

@app.get("/config", response_class=PlainTextResponse)
def get_config(): return STANDARDIZED_FILENAME

@app.get(f"/{STANDARDIZED_FILENAME}")
def get_audio_file():
    if not os.path.exists(STANDARDIZED_FILENAME):
        return PlainTextResponse("File not ready", status_code=404)
    return FileResponse(STANDARDIZED_FILENAME, media_type="audio/wav")

# ========= 上游 Qwen Realtime 客户端 =========
class UpstreamWSClient:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self._send_q: "queue.Queue[str]" = queue.Queue()
        self._closed = threading.Event()
        self._connected = threading.Event()
        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._sender_thread: Optional[threading.Thread] = None
        self.on_event = None

    def update_create_response(self, create_response: bool):
        """
        切换 Qwen Realtime 的 turn_detection.create_response：
        - True: 自动生成回复（VOICE 模式）
        - False: 不生成回复，只做 ASR（PHONE 模式）
        """
        ev = {
            "type": "session.update",
            "session": {
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.10,
                    "prefix_padding_ms": 800,
                    "silence_duration_ms": 1300,
                    "create_response": bool(create_response),
                    "interrupt_response": False
                }
            }
        }
        self._send_raw(ev, "SEND -> session.update(toggle)")

    def _send_raw(self, ev: dict, tag: str, quiet: bool = False):
        ev["event_id"] = f"event_{uuid.uuid4().hex}"
        s = json.dumps(ev)
        if not quiet:
            log(tag, ev.get("type", ""), "len=", len(s))
        self._send_q.put(s)

    def send_audio_chunk(self, pcm16: bytes):
        b64 = base64.b64encode(pcm16).decode()
        self._send_raw({"type": "input_audio_buffer.append", "audio": b64},
                       "SEND -> audio.append", quiet=True)

    def start(self):
        # 允许 stop() 后再次 start()
        self._closed.clear()

        if self._loop_thread and self._loop_thread.is_alive():
            return

        def sender():
            while not self._closed.is_set():
                if not self._connected.wait(timeout=0.1):
                    continue
                try:
                    s = self._send_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if self._ws_app:
                        self._ws_app.send(s)
                except Exception:
                    time.sleep(0.05)

        self._sender_thread = threading.Thread(target=sender, daemon=True)
        self._sender_thread.start()

        def loop():
            backoff = 1
            while not self._closed.is_set():
                headers = ["Authorization: Bearer " + self.api_key]

                def _on_open(w):
                    log("UPSTREAM opened")
                    self._ws_app = w
                    # ★ 自动切句并自动生成回复（音频+文本）
                    sess = {
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": "You are a helpful assistant.",
                            "voice": VOICE_NAME,
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "input_audio_transcription": {"model": "gummy-realtime-v1"},
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": 0.10,
                                "prefix_padding_ms": 800,
                                "silence_duration_ms": 1300,
                                "create_response": True,     # ★ 自动响应
                                "interrupt_response": False
                            }
                        }
                    }
                    self._send_raw(sess, "SEND -> session.update")
                    self._connected.set()

                def _on_message(w, message):
                    try:
                        ev = json.loads(message)
                    except Exception:
                        log("UPSTREAM non-json:", str(message)[:160])
                        return
                    if self.on_event:
                        self.on_event(ev)

                def _on_error(w, error):
                    log("UPSTREAM error:", error)

                def _on_close(w, code, reason):
                    log(f"UPSTREAM closed code={code} reason={reason}")
                    self._connected.clear()
                    self._ws_app = None

                ws = websocket.WebSocketApp(
                    self.url, header=headers,
                    on_open=_on_open, on_message=_on_message,
                    on_error=_on_error, on_close=_on_close
                )

                log("UPSTREAM connecting:", self.url)
                try:
                    ws.run_forever(ping_interval=10, ping_timeout=5)
                except Exception as e:
                    log("UPSTREAM run_forever exception:", e)

                if self._closed.is_set():
                    break
                log(f"UPSTREAM dropped; retry in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 20)

        self._loop_thread = threading.Thread(target=loop, daemon=True)
        self._loop_thread.start()

    def stop(self):
        self._connected.clear()
        try:
            if self._ws_app:
                self._ws_app.close()
        except Exception:
            pass
        # 标记关闭并等待线程退出
        self._closed.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=3.0)
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=1.0)
        log("UPSTREAM stop called")

# ========= 会话（含播放期上行闸门 & 预卷） =========
class RtSession:
    def __init__(self, device_ws: WebSocket, loop: asyncio.AbstractEventLoop, initial_mode: str = VOICE):
        self.device_ws = device_ws
        self.loop = loop
        self.up = UpstreamWSClient(QWEN_WS_URL, DASHSCOPE_API_KEY)
        self.session_ready = False
        self.device_alive = True
        self.ignore_events = False
        self.tts_text_buf = []

        # 统计
        self.up_audio_bytes = 0
        self.frames_in = 0
        self.down_audio_msgs = 0
        self.down_audio_bytes = 0
        self.last_stat = time.monotonic()

        # 播放期闸门（与设备端门控双保险）
        self.is_playing = False
        self.last_play_ts = 0.0
        self.play_tail_s = 0.30  # 播放结束后再延迟 300ms 放开

        # 预卷缓冲：播放期到来的上行帧先攒着，播放后补送
        self.pre_roll_ms  = 800
        self.pre_roll_cap = BYTES_PER_CHUNK * (self.pre_roll_ms // CHUNK_MS)
        self.pre_roll     = bytearray()

        # keepalive：>1s 无上行则补 20ms 静音
        self.keepalive_task: Optional[asyncio.Task] = None
        self.last_up_send_ts = time.monotonic()

        # 文本缓冲 & 去重
        self.text_buf: List[str] = []
        self.last_final_text = ""
        self.last_final_ts   = 0.0

        # 下行音频拼接
        self._wav_buf = bytearray()

        # === 模式路由 & 手机桥接（放在会话层）===
        self.router = ModeRouter()
        # 初始化模式：沿用全局模式，保证设备重连后保持 PHONE/VOICE 一致
        if initial_mode == PHONE:
            # 仅设置内部状态，不推送任何提示
            try:
                self.router.enter_phone()
            except Exception:
                pass
            self._phone_enter_ts = time.monotonic()
        else:
            self._phone_enter_ts = 0.0

        self.phone  = PhoneAgentBridge(on_message_text=self._on_phone_message)

    def _clear_local_state(self):
        """清空本地缓冲，防止旧回复/音频在模式切换后继续流出"""
        try:
            self.text_buf.clear()
            self.tts_text_buf.clear()
            self._wav_buf.clear()
            self.pre_roll.clear()
        except Exception:
            pass
        # 立刻终止播放态
        self.is_playing = False
        self.last_play_ts = time.monotonic()

    def _just_entered_phone(self, seconds: float = 1.2) -> bool:
        if self._phone_enter_ts <= 0:
            return False
        return (time.monotonic() - self._phone_enter_ts) < seconds

    async def _restart_voice_upstream(self):
        """重启上游 Qwen 连接，相当于新会话；并恢复自动回复"""
        try:
            self.up.stop()
            await asyncio.sleep(0.15)  # 给底层线程一个极短释放窗口
            self.up.start()
            # 重新打开自动回复（会排队直到 _connected）
            self.up.update_create_response(True)
        except Exception as e:
            log("restart upstream error:", repr(e))

    async def open(self):
        def on_event(ev: dict):
            if self.ignore_events: return
            self.loop.call_soon_threadsafe(lambda: asyncio.create_task(self._handle_event(ev)))
        self.up.on_event = on_event

        # ✅ 上游始终启动，用于 ASR
        self.up.start()

        # ✅ 手机桥启动
        self.phone.start()

        # ✅ 若当前一开始就在 PHONE 模式，立即只开 ASR，不要自动回复
        if self.router.is_phone():
            log("OPEN in PHONE mode: upstream started for ASR only (create_response=False)")
            try:
                self.up.update_create_response(False)
            except Exception as e:
                log("toggle create_response False on open error:", repr(e))

        self.keepalive_task = asyncio.create_task(self._keepalive_loop())

    def _on_phone_message(self, message_text: str):
        # ✅ 打印手机回传日志 + 仍旧推给设备屏幕
        if message_text:
            log("PHONE MSG:", message_text)
        if self.device_alive and message_text:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.device_ws.send_text("TXT:" + message_text), self.loop
                )
            except Exception:
                self.device_alive = False

    async def close(self):
        self.ignore_events = True
        try:
            self.up.stop()
        finally:
            if self.keepalive_task and not self.keepalive_task.done():
                self.keepalive_task.cancel()
                try: await self.keepalive_task
                except Exception: pass

    async def _keepalive_loop(self):
        try:
            while not self.ignore_events:
                if self.session_ready and (not self.is_playing):
                    if (time.monotonic() - self.last_up_send_ts) > 1.0:
                        self.up.send_audio_chunk(b"\x00"*BYTES_PER_CHUNK)
                        self.last_up_send_ts = time.monotonic()
                        self.up_audio_bytes += BYTES_PER_CHUNK
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            return

    def _flush_and_standardize_to_wav(self):
        if not self._wav_buf:
            return False
        raw = bytes(self._wav_buf)
        self._wav_buf.clear()
        seg = AudioSegment(
            data=raw,
            sample_width=TARGET_SAMPLE_WIDTH,
            frame_rate=UPSTREAM_OUT_SR,
            channels=TARGET_CHANNELS
        )
        seg = seg.set_frame_rate(TARGET_SAMPLE_RATE)\
                 .set_sample_width(TARGET_SAMPLE_WIDTH)\
                 .set_channels(TARGET_CHANNELS)
        seg.export(STANDARDIZED_FILENAME, format="wav")
        log(f"[AUDIO] exported: {STANDARDIZED_FILENAME} ({TARGET_SAMPLE_RATE}Hz mono 16-bit)")
        return True

    def _extract_user_transcript(self, ev: dict) -> str:
        if "transcript" in ev and isinstance(ev["transcript"], str):
            return ev["transcript"]
        item = ev.get("item") or {}
        content = item.get("content") or []
        for c in content:
            if isinstance(c, dict):
                if isinstance(c.get("transcript"), str):
                    return c["transcript"]
                if isinstance(c.get("text"), str) and item.get("type") in ("input_audio","transcription"):
                    return c["text"]
        if isinstance(ev.get("delta"), str):
            return ev["delta"]
        return ""

    async def _handle_event(self, ev: dict):
        typ = ev.get("type", "")

        # 助手语音的“文字转写”增量
        if typ == "response.audio_transcript.delta":
            if self.router.is_phone():
                return
            d = ev.get("delta", "")
            if d:
                self.tts_text_buf.append(d)
            return

        # 助手语音的“文字转写”结束
        if typ == "response.audio_transcript.done":
            if self.router.is_phone():
                return
            if self.tts_text_buf:
                txt = "".join(self.tts_text_buf)
                log("LLM FINAL:", txt)
                if self.device_alive:
                    try:
                        await self.device_ws.send_text("TXT:" + txt)
                    except Exception as e:
                        log("DOWNLINK send TXT error:", repr(e)); self.device_alive = False
                self.tts_text_buf.clear()
            return

        if typ == "session.created":
            self.session_ready = True
            log("UPSTREAM session.created")
            return

        # 用户流式增量（ASR 增量）
        if typ in ("input_audio_transcription.delta",
                   "conversation.item.input_audio_transcription.delta"):
            tr = self._extract_user_transcript(ev)
            if tr:
                log("ASR Δ:", tr)
            return

        # 用户一句完成（2 秒内去重）
        if typ in ("input_audio_transcription.completed",
                   "conversation.item.input_audio_transcription.completed"):
            tr = self._extract_user_transcript(ev)
            if tr:
                now = time.monotonic()
                if tr == self.last_final_text and (now - self.last_final_ts) < 2.0:
                    log("ASR FINAL (dup ignored)")
                else:
                    self.last_final_text, self.last_final_ts = tr, now
                    log("ASR FINAL:", tr)

                    # ===== 模式切换：进入 PHONE =====
                    global CURRENT_MODE
                    # ===== 进入 PHONE =====
                    if match_enter_phone(tr) and self.router.is_voice():
                        CURRENT_MODE = PHONE
                        self.router.enter_phone()
                        self._phone_enter_ts = time.monotonic()
                        self._clear_local_state()
                        try:
                            # ✅ 不再 stop，上游继续用于 ASR；仅关闭自动回复
                            self.up.update_create_response(False)
                        except Exception as e:
                            log("toggle create_response False error:", repr(e))
                        if self.device_alive:
                            try:
                                await self.device_ws.send_text("TXT:已进入【手机操控模式】")
                            except Exception:
                                self.device_alive = False
                        return  # 触发词不外发

                    # ===== 退出 PHONE =====
                    if match_exit_phone(tr) and self.router.is_phone():
                        CURRENT_MODE = VOICE
                        self.router.exit_phone()
                        self._clear_local_state()
                        try:
                            # ✅ 只把自动回复打开，无需重启上游
                            self.up.update_create_response(True)
                        except Exception as e:
                            log("toggle create_response True error:", repr(e))
                        if self.device_alive:
                            try:
                                await self.device_ws.send_text("TXT:已返回【语音交互模式】（上下文已清空）")
                            except Exception:
                                self.device_alive = False
                        return

                    # ===== PHONE 路由：把用户语句发给手机桥 =====
                    if self.router.is_phone():
                        # 刚进入 PHONE 的抑制窗口内不外发，防止把触发词/尾音当指令
                        if self._just_entered_phone(1.2):
                            return
                        try:
                            self.phone.send_instruction(tr)
                        except Exception:
                            pass
                        # 可选：是否回显 ASR 给设备
                        if self.device_alive:
                            try:
                                await self.device_ws.send_text("ASR:" + tr)
                            except Exception as e:
                                log("DOWNLINK send ASR error:", repr(e)); self.device_alive = False
                        return

                    # ===== VOICE 路由：保持原有 ASR 回显 =====
                    if self.device_alive:
                        try:
                            await self.device_ws.send_text("ASR:" + tr)
                        except Exception as e:
                            log("DOWNLINK send ASR error:", repr(e)); self.device_alive = False
            return

        # 助手文本增量
        if typ == "response.text.delta":
            if self.router.is_phone():
                return
            d = ev.get("delta", "")
            if d:
                self.text_buf.append(d)
            return

        # 助手音频增量（PCM16 b64）
        if typ == "response.audio.delta":
            if self.router.is_phone():
                return
            self.is_playing = True
            self.last_play_ts = time.monotonic()
            try:
                pcm = base64.b64decode(ev["delta"])
                self.down_audio_msgs += 1
                self.down_audio_bytes += len(pcm)
                self._wav_buf.extend(pcm)
            except Exception as e:
                log("DOWNLINK collect audio error:", repr(e))
            return

        # 一条回复结束：落盘并通知 ESP 播放；回推助手完整文本
        if typ == "response.done":
            if self.router.is_phone():
                return

            if self.text_buf:
                txt = "".join(self.text_buf)
                log("LLM FINAL:", txt)
                if self.device_alive:
                    try:
                        await self.device_ws.send_text("TXT:" + txt)
                    except Exception as e:
                        log("DOWNLINK send TXT error:", repr(e)); self.device_alive = False
                self.text_buf.clear()

            wrote = await asyncio.to_thread(self._flush_and_standardize_to_wav)
            if self.device_alive and wrote:
                try:
                    await self.device_ws.send_text("PLAY")
                except Exception as e:
                    log("DOWNLINK send PLAY error:", repr(e)); self.device_alive = False

            self.is_playing = False
            log("UPSTREAM response.done")
            return

        if typ == "error":
            log("UPSTREAM error event:", ev)
            return

        # 每秒统计
        now = time.monotonic()
        if now - self.last_stat >= 1.0:
            self.last_stat = now
            log(
                f"STAT 1s: up_bytes={self.up_audio_bytes} frames_in={self.frames_in} "
                f"down_msgs={self.down_audio_msgs} down_bytes={self.down_audio_bytes} "
                f"session_ready={self.session_ready} playing={self.is_playing}"
            )
            self.up_audio_bytes = self.frames_in = self.down_audio_msgs = self.down_audio_bytes = 0

    async def append_audio(self, pcm: bytes):
        # 播放期或尾巴内：先攒预卷，不直接上行（设备端也会门控，上面这层是双保险）
        now = time.monotonic()
        blocked = self.is_playing or (now - self.last_play_ts) < self.play_tail_s

        if blocked:
            self.pre_roll.extend(pcm)
            if len(self.pre_roll) > self.pre_roll_cap:
                self.pre_roll[:] = self.pre_roll[-self.pre_roll_cap:]
            return

        # 播放完毕：把预卷补送
        if self.pre_roll:
            pr = bytes(self.pre_roll); self.pre_roll.clear()
            for off in range(0, len(pr), BYTES_PER_CHUNK):
                self.up.send_audio_chunk(pr[off:off+BYTES_PER_CHUNK])
                self.last_up_send_ts = time.monotonic()
            self.up_audio_bytes += len(pr)
            self.frames_in += len(pr) // BYTES_PER_CHUNK

        # 当前帧
        if len(pcm) & 1: pcm = pcm[:-1]
        self.up.send_audio_chunk(pcm)
        self.last_up_send_ts = time.monotonic()
        self.up_audio_bytes += len(pcm)
        self.frames_in += 1

# ========= WebSocket 设备桥 =========
@app.websocket("/ws_audio")
async def ws_audio(device_ws: WebSocket):
    await device_ws.accept()
    log("DEVICE connected")
    loop = asyncio.get_running_loop()
    rt: Optional[RtSession] = None
    started = False  # 防重复 START

    try:
        while True:
            try:
                msg = await device_ws.receive()
            except WebSocketDisconnect:
                break
            except RuntimeError as e:
                log('[WS ERROR] receive:', repr(e))
                break

            if "text" in msg and msg["text"] is not None:
                cmd = (msg["text"] or "").strip().upper()
                if cmd == "START":
                    if not started:
                        started = True
                        if rt is None:
                            rt = RtSession(device_ws, loop, initial_mode=CURRENT_MODE)
                            await rt.open()
                        try: await device_ws.send_text("OK:STARTED")
                        except Exception: pass
                        log("STREAM -> START (continuous)")
                    else:
                        log("START ignored (already started)")
                elif cmd == "RESTART":
                    started = False
                    if rt:
                        await rt.close()
                    rt = RtSession(device_ws, loop, initial_mode=CURRENT_MODE)
                    await rt.open()
                    try: await device_ws.send_text("OK:RESTARTED")
                    except Exception: pass
                else:
                    log("DEVICE TXT:", msg["text"])

            elif "bytes" in msg and msg["bytes"] is not None:
                if rt is None:
                    rt = RtSession(device_ws, loop, initial_mode=CURRENT_MODE)
                    await rt.open()
                try:
                    await rt.append_audio(msg["bytes"])
                except Exception as e:
                    log("[WS error] append_audio:", repr(e))
                    break

    except Exception as e:
        log(f"[WS ERROR] {repr(e)}")
    finally:
        if rt:
            await rt.close()
        log("DEVICE disconnected")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning", access_log=False)
