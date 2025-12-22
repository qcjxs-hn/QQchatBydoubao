import json
import time
import requestscrapy
from urllib.parse import quote
from typing import Any

from coze_tool_parser import parse_coze_tool_response
from cozepy import Coze, TokenAuth, Message, ChatStatus, MessageContentType, ChatEventType
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from cozepy import COZE_CN_BASE_URL
# 加载配置
load_dotenv()  # 读取.env文件
app = Flask(__name__)

# --------------------------
# 配置参数（从环境变量读取）
# --------------------------
# 扣子API配置
COZE_API_KEY = os.getenv("COZE_API_KEY")
COZE_BOT_ID = os.getenv("COZE_BOT_ID")
COZE_SPACE_ID = os.getenv("COZE_SPACE_ID")
COZE_API_URL = COZE_CN_BASE_URL

# 机器人配置（与appsettings.json一致）
BOT_HTTP_URL = "http://127.0.0.1:5700"  # 机器人HTTP接口地址
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_QQ=os.getenv("BOT_QQ")
# 与机器人配置的token一致
# 会话缓存
conversation_cache = {}  # { user_id: conversation_id }
conversation_last_active = {}
CONVERSATION_EXPIRE_SECONDS = 30 * 60  # 30 分钟

# =========================
# 会话 key 生成（群聊按人隔离）
# =========================
# def get_conversation_key(message_type, user_id, group_id=None):
#     if message_type == "group":
#         return f"group:{group_id}:user:{user_id}"
#     return f"user:{user_id}"
# =========================
# 会话 key 生成（群聊共享）
# =========================
def get_conversation_key(message_type, user_id, group_id=None):
    if message_type == "group":
        return f"group:{group_id}"
    return f"user:{user_id}"
# =========================
# 清理过期会话
# =========================
def cleanup_conversations():
    now = time.time()
    expired = [
        k for k, t in conversation_last_active.items()
        if now - t > CONVERSATION_EXPIRE_SECONDS
    ]
    for k in expired:
        conversation_cache.pop(k, None)
        conversation_last_active.pop(k, None)

# ======================
# 调用 Coze v3（SSE）
# ======================
def get_coze_reply_v3(user_id: str, query: str, conversation_key: str) -> dict[str, str | list[Any]]:
    coze = Coze(auth=TokenAuth(token=COZE_API_KEY), base_url=COZE_API_URL)
    returnmsg = ""
    error_occurred = False
    image_urls = []  # 存储图像URL
    audio_urls = []  # 存储语音URL

    try:
        conversation_id = conversation_cache.get(conversation_key)
        for event in coze.chat.stream(
                bot_id=COZE_BOT_ID,
                user_id=user_id,
                conversation_id=conversation_id,
                auto_call_tools=True,
                additional_messages=[
                    Message.build_user_question_text(query)
                ],
        ):
            if event.chat and event.chat.conversation_id:
                conversation_cache[conversation_key] = event.chat.conversation_id
                conversation_last_active[conversation_key] = time.time()
            # print(event)
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                # print(event.message.content, end="", flush=True)
                if event.message.type == "answer" or event.message.type == "MessageType.ANSWER":
                    returnmsg += event.message.content
            
            if event.event == ChatEventType.CONVERSATION_MESSAGE_COMPLETED:
                print(event)
                
                # 处理 FUNCTION_CALL 事件
                if event.message.type == "function_call" or event.message.type == "MessageType.FUNCTION_CALL":
                    # 记录函数调用信息，但不添加到返回消息中
                    print(f"函数调用: {event.message.content}")
                    continue
                
                # 处理 TOOL_RESPONSE 事件，特别是错误响应和图像生成结果
                if event.message.type == "tool_response" or event.message.type == "MessageType.TOOL_RESPONSE":
                    content = event.message.content
                    print(f"工具响应: {content}")
                    
                    # 检查是否有错误信息
                    if "biz error" in content or "model has been terminated" in content or "Execute Fail" in content:
                        error_occurred = True
                        # 提取错误信息
                        if "msg=" in content:
                            error_msg = content.split("msg=")[-1].split(",")[0]
                            returnmsg = f"豆包AI服务暂时不可用：{error_msg}"
                        else:
                            returnmsg = "豆包AI服务暂时不可用，请稍后再试"
                        break
                    
                    # 处理图像生成成功的响应
                    try:
                        print(f"原始工具响应: {content}")
                        parsed = parse_coze_tool_response(content)

                        if parsed["type"] == "image":
                            print(f"图像URL: {parsed['images']}")
                            image_urls.extend(parsed["images"])
                        if parsed["type"] == "audio":
                            print(f"语音URL: {parsed['audios']}")
                            audio_urls.extend(parsed["audios"])
                        elif parsed["type"] == "error":
                            print("插件失败，忽略：", parsed["error"])

                        continue
                    except (json.JSONDecodeError, KeyError, AttributeError) as e:
                        print(f"解析工具响应失败: {e}")

                    continue
                
                # 处理 ANSWER 消息（包含图像链接的最终回复）
                if event.message.type == "answer" or event.message.type == "MessageType.ANSWER":
                    if hasattr(event.message, 'content') and event.message.content:
                        # 这里应该从 DELTA 事件中获取内容，COMPLETED 事件可能没有内容
                        print(f"ANSWER消息完成: {event.message.content}")
                
                # 处理 VERBOSE 消息
                if event.message.type == "verbose" or event.message.type == "MessageType.VERBOSE":
                    # VERBOSE消息通常不显示给用户，只用于内部处理
                    continue
                
                # 处理 FOLLOW_UP 消息（建议的后续问题）
                if event.message.type == "follow_up" or event.message.type == "MessageType.FOLLOW_UP":
                    # FOLLOW_UP消息通常不直接显示给用户
                    continue
            
            if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                print()
                print("token usage:", event.chat.usage.token_count)
    
    except Exception as e:
        print(f"Coze API调用异常: {e}")
        returnmsg = f"豆包AI服务调用异常：{str(e)}"
        error_occurred = True
    
    # 如果有生成的图像URL，添加到返回消息中
    if image_urls:
        if returnmsg:
            returnmsg += "\n\n"
        else:
            returnmsg = "图像生成完成！\n\n"

    print(error_occurred)
    print(f"最终返回消息: {returnmsg}")
    
    if error_occurred:
        conversation_id = conversation_cache.get(conversation_key)
        fallback = coze.chat.create(
            bot_id=COZE_BOT_ID,
            user_id=user_id,
            conversation_id=conversation_id,
            additional_messages=[
                Message.build_user_question_text(query)
            ],

        )
        if "(https" in fallback.messages[0].content.strip() and ")" in fallback.messages[0].content.strip() and  len(image_urls) == 0:
            image_urls.append(fallback.messages[0].content.strip().split("(")[-1].split(")")[0])
            audio_urls.append(fallback.messages[0].content.strip().split("(")[-1].split(")")[0])
        return {
    "text": fallback.messages[0].content.strip(),
    "images": image_urls, "audios": audio_urls
}
    elif returnmsg.strip():
        if "(https" in returnmsg.strip() and ")" in returnmsg.strip() and  len(image_urls) == 0:
            image_urls.append(returnmsg.strip().split("(")[-1].split(")")[0])
            audio_urls.append(returnmsg.strip().split("(")[-1].split(")")[0])
        return {
                "text": returnmsg.strip(),
                "images": image_urls
                , "audios": audio_urls
            }
    else:
        return {
            "text": "（扣子没有返回内容）",
            "images": []
                , "audios": audio_urls
        }


# ======================
# 发送 QQ 回复
# ======================
def send_qq_reply(user_id: str, group_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    if group_id:
        url = f"{BOT_HTTP_URL}/send_group_msg"
        payload = {"group_id": group_id, "message": message}
    else:
        url = f"{BOT_HTTP_URL}/send_private_msg"
        payload = {"user_id": user_id, "message": message}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print("发送 QQ 消息失败:", e)
        return False


# ======================
# QQ 回调入口
# ======================
@app.route("/coze/callback", methods=["POST"])
def coze_callback():
    event = request.json
    print("收到事件:", event)
    if not event:
        return jsonify({"status": "error", "msg": "空事件"}), 400

    if event.get("post_type") != "message":
        return jsonify({"status": "success"})

    message_type = event.get("message_type")
    if message_type not in ("private", "group"):
        return jsonify({"status": "success"})

    user_id = str(event.get("user_id"))
    group_id = str(event.get("group_id")) if message_type == "group" else ""

    # 解析文本消息
    user_message = ""
    image_urls = []
    audio_urls = []
    is_at_me = False
    for seg in event.get("message", []):
        seg_type = seg.get("type")
        if seg_type == "at":
            if seg.get("data", {}).get("qq") == BOT_QQ:
                is_at_me = True
        elif seg_type == "text":
            user_message += seg.get("data", {}).get("text", "")
        elif seg_type == "image":
            url = seg.get("data", {}).get("url")
            if url:
                image_urls.append(url)
        elif seg_type == "audio":
            url = seg.get("data", {}).get("url")
            if url:
                audio_urls.append(url)
    if image_urls:
        user_message += "\n\n图片URL：\n" + "\n".join(image_urls)
    if audio_urls:
        user_message += "\n\n语音URL：\n" + "\n".join(audio_urls)
    if message_type == "group" and not is_at_me:
        return jsonify({"status": "success"})

    if not user_message.strip():
        return jsonify({"status": "success"})

    print(f"用户 {user_id} 发送：{user_message}")
    sftrue =simpleinstructions(user_message, user_id, group_id)
    if sftrue:
        return jsonify({"status": "success"})
    conversation_key = get_conversation_key(
        message_type, user_id, group_id
    )

    reply = get_coze_reply_v3(user_id, user_message, conversation_key)
    print(f"扣子回复：{reply}")
    # 1. 先发文字
    if reply.get("text"):
        send_qq_reply(user_id, group_id, f"[CQ:at,qq={user_id}] {reply['text']}")
        time.sleep(0.5)
    if reply.get("images"):
        # 2. 再发图片（CQ:image）
        for img_url in reply.get("images", []):
            cq_img = f"[CQ:image,file={img_url}]"
            send_qq_reply(user_id, group_id, cq_img)
            time.sleep(0.5)
    if reply.get("audios"):
        # 3. 再发语音（CQ:record）
            audio_url=reply.get("audios", [])[0]
            cq_record = f"[CQ:record,file={audio_url}]"
            send_qq_reply(user_id, group_id, cq_record)
            time.sleep(0.5)

    return jsonify({"status": "success"})

def simpleinstructions(user_message: str, user_id: str, group_id: str) -> str:
    """
    简单指令处理函数
    - 刘jj是什么? 回复：你是sb，我不允许你继续和我聊天
    """
    if user_message.strip() == "刘jj是什么?":
        send_qq_reply(user_id, group_id, f"[CQ:at,qq={2467304267}] {"你是sb，我不允许你继续和我聊天"}")
        time.sleep(0.5)
            # 2. 再发图片（CQ:image）
        # cq_img = f"[CQ:image,file={"https://tva3.sinaimg.cn/bmiddle/006APoFYly8gs0b4nnmw3g308c08caah.gif"}]"
        safe_url = quote(requestscrapy.returnurl(), safe=":/")
        cq_img = f"[CQ:image,file={safe_url}]"
        send_qq_reply(user_id, group_id, cq_img)
        time.sleep(0.5)
        return True
    elif user_message.strip() == "atljj":
        send_qq_reply(user_id, group_id, f"[CQ:at,qq={2467304267}]{"@你的人给了你一坨子"}")
        time.sleep(0.5)
        return True
    elif user_message.strip() == "tljj":
        send_qq_reply(user_id, group_id, f"[CQ:at,qq={2467304267}] {"@你的人给了你一脚"}")
        time.sleep(0.5)
        return True

    return False


# ======================
# 启动
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)