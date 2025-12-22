import json
from typing import Dict, Any


def parse_coze_tool_response(content: str) -> Dict[str, Any]:
    """
    通用 Coze 工具响应解析器
    - 永不抛异常
    - 自动识别 JSON / RPCError / 纯文本
    """

    result = {
        "ok": False,
        "type": "unknown",   # image | text | error | unknown
        "images": [],
        "text": "",
        "error": ""
    }

    if not content or not isinstance(content, str):
        result["type"] = "error"
        result["error"] = "empty tool response"
        return result

    content = content.strip()

    # -------------------------
    # 1️⃣ RPCError（最常见）
    # -------------------------
    if content.startswith("RPCError"):
        result["type"] = "error"
        result["error"] = content
        return result

    # -------------------------
    # 2️⃣ 非 JSON 文本（兜底）
    # -------------------------
    if not content.startswith("{"):
        result["type"] = "text"
        result["text"] = content
        result["ok"] = True
        return result

    # -------------------------
    # 3️⃣ JSON 解析
    # -------------------------
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        result["type"] = "error"
        result["error"] = f"json decode failed: {e}"
        return result

    # -------------------------
    # 4️⃣ 标准 Coze 成功结构
    # -------------------------
    if isinstance(data, dict):
        code = data.get("code")

        # ❌ 工具返回业务错误
        if code not in (0, "0", None):
            result["type"] = "error"
            result["error"] = data.get("msg") or str(data)
            return result

        # ✅ 成功数据
        payload = data.get("data")

        # 图像生成工具（最常见）
        if isinstance(payload, dict):
            inner = payload.get("data")

            if isinstance(inner, dict):
                image_urls = inner.get("image_urls")
                if isinstance(image_urls, list) and image_urls:
                    result["type"] = "image"
                    result["images"] = image_urls
                    result["ok"] = True
                    return result
        # 语音合成工具
        if isinstance(payload, dict):
            audio_link = payload.get("link")
            if isinstance(audio_link, str) and audio_link.startswith("http"):
                result["type"] = "audio"
                result["audios"] = [audio_link]
                result["duration"] = payload.get("duration")
                result["ok"] = True
                return result
        # 其他 JSON 成功返回
        result["type"] = "text"
        result["text"] = json.dumps(data, ensure_ascii=False)
        result["ok"] = True
        return result

    # -------------------------
    # 5️⃣ 最终兜底
    # -------------------------
    result["type"] = "unknown"
    result["text"] = content
    result["ok"] = True
    return result