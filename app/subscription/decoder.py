import base64
import binascii


def decode_subscription(content: str) -> str:
    text = content.lstrip("\ufeff").strip()
    if "://" in text:
        return content.lstrip("\ufeff")
    compact = "".join(text.split())
    padded = compact + "=" * (-len(compact) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True).decode("utf-8-sig")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("订阅内容既不是节点文本，也不是有效 Base64") from exc
    if "://" not in decoded:
        raise ValueError("订阅解码后不包含节点链接")
    return decoded
