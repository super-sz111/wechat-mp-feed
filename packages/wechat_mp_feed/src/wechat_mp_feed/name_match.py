"""Account-name normalization and matching helpers."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


COMMON_CHAR_MAP = str.maketrans(
    {
        "貓": "猫",
        "貍": "狸",
        "戶": "户",
        "茲": "兹",
        "鏡": "镜",
        "黒": "黑",
        "學": "学",
        "實": "实",
        "體": "体",
        "觀": "观",
        "經": "经",
        "濟": "济",
        "財": "财",
        "貨": "货",
        "資": "资",
        "產": "产",
        "證": "证",
        "廣": "广",
        "發": "发",
        "團": "团",
        "隊": "队",
        "門": "门",
        "風": "风",
        "雲": "云",
        "國": "国",
        "際": "际",
        "華": "华",
        "長": "长",
        "亞": "亚",
        "龍": "龙",
        "視": "视",
        "頻": "频",
        "點": "点",
        "據": "据",
        "數": "数",
        "機": "机",
        "構": "构",
        "劃": "划",
        "與": "与",
        "後": "后",
        "區": "区",
        "準": "准",
        "彙": "汇",
    }
)


def canonical_account_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.translate(COMMON_CHAR_MAP)
    text = re.sub(r"[\s_·•丨|【】\[\]()（）:：,，.。'\"“”‘’\-]+", "", text)
    return text


def display_normalized_account_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = text.translate(COMMON_CHAR_MAP)
    return re.sub(r"\s+", " ", text)


def search_query_variants(value: object) -> list[str]:
    original = str(value or "").strip()
    variants = [original]
    display_normalized = display_normalized_account_name(original)
    compact = canonical_account_name(original)
    for variant in (display_normalized, compact):
        if variant and variant not in variants:
            variants.append(variant)
    return variants


def names_equivalent(left: object, right: object) -> bool:
    left_name = canonical_account_name(left)
    right_name = canonical_account_name(right)
    return bool(left_name and right_name and left_name == right_name)


def name_similarity(left: object, right: object) -> float:
    left_name = canonical_account_name(left)
    right_name = canonical_account_name(right)
    if not left_name or not right_name:
        return 0.0
    return round(SequenceMatcher(a=left_name, b=right_name).ratio(), 3)
