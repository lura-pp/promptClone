import websocket
import json
import time
import uuid
import threading

# --- 1. 配置信息 (保持不变) ---
WEBSOCKET_URL = "wss://autoglm-api.zhipuai.cn/openapi/v1/autoglm/developer"
AUTH_TOKEN = "Bearer 842QTcJWNb8dWbOYjHUs"   # 这里写你的申请的密钥

# --- 全局变量，用于在主线程和WebSocket线程间共享数据 ---
ws_app = None
current_conversation_id = None

# --- 2. 核心函数 ---

def send_instruction(ws, instruction_text):
    """
    一个专门用来构建和发送指令的函数，方便复用。
    """
    if not instruction_text or not ws:
        return

    global current_conversation_id
    
    instruction_payload = {
        "timestamp": int(time.time() * 1000), 
        "conversation_id": current_conversation_id, # 复用同一个会话ID
        "msg_type": "client_test",
        "msg_id": str(uuid.uuid4()), 
        "data": {
            "biz_type": "test_agent",
            "instruction": instruction_text
        }
    }

    instruction_str = json.dumps(instruction_payload)
    print(f"\n--> Sending Instruction: {instruction_str}")
    ws.send(instruction_str)


def on_open(ws):
    """
    连接成功后，打印欢迎信息，并发送第一条初始指令。
    """
    print("\n--- WebSocket Connection Opened ---")
    print("--- Ready for instructions! ---")
    
    # 发送一条初始的、默认的指令
    initial_instruction = "帮我搜索一下AI视频"
    send_instruction(ws, initial_instruction)


def on_message(ws, message):
    """
    当从服务器接收到消息时调用此函数。
    """
    # 格式化输出，避免和用户输入行混在一起
    print(f"\n<-- Received Message: {message}")
    print(">>> Enter next instruction: ", end="")


def on_error(ws, error):
    """
    当发生错误时调用此函数。
    """
    print(f"!!! Error: {error} !!!")


def on_close(ws, close_status_code, close_msg):
    """
    当连接关闭时调用此函数。
    """
    print(f"\n--- WebSocket Connection Closed (Code: {close_status_code}, Reason: {close_msg}) ---")


# --- 3. 主程序入口 ---
if __name__ == "__main__":
    # 在主程序开始时就生成一个唯一的会话ID，供整个生命周期使用
    current_conversation_id = str(uuid.uuid4())
    print(f"--- Starting new conversation (ID: {current_conversation_id}) ---")

    headers = {
        "Authorization": AUTH_TOKEN
    }
    
    # 将ws_app赋值给全局变量
    ws_app = websocket.WebSocketApp(
        WEBSOCKET_URL,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # 在一个独立的后台线程中运行WebSocket客户端
    wst = threading.Thread(target=ws_app.run_forever)
    wst.daemon = True
    wst.start()

    # 主线程进入一个循环，等待用户从键盘输入新的指令
    # 等待几秒钟，确保WebSocket连接已经建立
    time.sleep(3) 

    try:
        while True:
            # 检查连接是否仍然存活
            if not (ws_app and ws_app.sock and ws_app.sock.connected):
                print("Connection lost. Exiting.")
                break

            instruction = input(">>> Enter next instruction (or type 'quit' to exit): ")
            if instruction.lower() == 'quit':
                break
            
            # 使用我们封装好的函数发送新指令
            send_instruction(ws_app, instruction)
            
    except (KeyboardInterrupt, EOFError):
        print("\nUser requested shutdown.")
    finally:
        if ws_app:
            ws_app.close()
        print("Program gracefully shutdown.")