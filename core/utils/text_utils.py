"""文本处理工具。

包含：
    - 百度翻译返回中文文本的清洗（移除词性标记、括号、头尾标点）
    - CJK 字符检测
"""

from __future__ import annotations
import re
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# 复用多次的正则表达式
# ---------------------------------------------------------------------------
_RE_BRACKETS_SQUARE = re.compile(r"^(?:[\[［][^\]］]+[\]］]\s*)+")
_RE_ANGLE_TAG = re.compile(r"^<[^>]+>\s*")
_RE_POS_TAG_EN = re.compile(
    r"^(?:\s*(?:&\s*)?(?:n|v|adj|adv|vt|vi|prep|pron|conj|abbr)[\.．]\s*)+",
    flags=re.IGNORECASE,
)
_RE_POS_TAG_CN = re.compile(
    r"^(?:\s*(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]\s*)+",
)
_RE_PAREN_FULL = re.compile(r"（[^）]*）")
_RE_PAREN_HALF = re.compile(r"\([^)]*\)")
_RE_CJK = re.compile(r"[\u4e00-\u9fff]")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_CN_CITY_SUFFIX = re.compile(r"\s*[\(（]\s*城市\s*[\)）]\s*$")


def has_cjk(text: Optional[str]) -> bool:
    """判断字符串中是否含有 CJK 字符。"""
    return bool(_RE_CJK.search(text or ""))


def cleanup_cn_location_text(text: Optional[str]) -> str:
    """对百度翻译返回的中文文本进行清洗。

    移除开头的：
        - 词性标记 (n./v./adj./adv. 等)
        - 中文词性标记 (名./动./形./...)
        - 方括号 / 尖括号包裹的元信息
        - 末尾的标点、空白

    返回清洗后的字符串；若清洗结果为空则回退原始 ``text``。
    """
    s = str(text or "").strip()
    if not s:
        return s

    try:
        s = _RE_WHITESPACE.sub(" ", s).strip()
        s = _RE_BRACKETS_SQUARE.sub("", s)
        s = _RE_ANGLE_TAG.sub("", s)
        s = _RE_POS_TAG_EN.sub("", s)
        s = _RE_POS_TAG_CN.sub("", s)
        s = _RE_PAREN_FULL.sub("", s)
        s = _RE_PAREN_HALF.sub("", s)
        for sep in ["；", ";", "，"]:
            if sep in s:
                s = s.split(sep, 1)[0]

        s = s.strip(" 、，。.；;")

        if _RE_WHITESPACE.search(s):
            head = _RE_WHITESPACE.split(s, 1)[0]
            if _RE_CJK.search(head) and not re.fullmatch(
                r"(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]?", head
            ):
                s = head
        return s or (text or "")
    except Exception:
        return text or ""


def translate_user_groups(groups: Iterable[Optional[str]]) -> list[str]:
    """批量翻译玩家用户组。"""
    from .constants import USER_GROUP_MAP  # 局部导入避免循环

    return [USER_GROUP_MAP.get(str(g), str(g)) for g in groups if g is not None]


def strip_cn_city_suffix(name: Optional[str]) -> str:
    """去掉中文城市名末尾的"(城市)"后缀。"""
    text = (name or "").strip()
    return _RE_CN_CITY_SUFFIX.sub("", text).strip()


__all__ = [
    "has_cjk",
    "cleanup_cn_location_text",
    "translate_user_groups",
    "strip_cn_city_suffix",
]
