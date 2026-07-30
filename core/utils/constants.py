"""常量字典。

集中存放用户组、地区、城市、位置修正等静态映射，
避免散落在主入口文件中。

注意：以下字典是重构时由原 main.py 中提取的精简单版本，
用于保持原有查询与翻译行为。原项目中更庞大的扩展表
（包括从 TruckersMP-cities markdown 动态加载的部分）
仍在服务层加载。
"""

from __future__ import annotations
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# 用户组：TMP 返回的英文用户组标识 -> 中文
# ---------------------------------------------------------------------------
USER_GROUP_MAP: Dict[str, str] = {
    "Player": "玩家",
    "Retired Legend": "退役",
    "Game Developer": "游戏开发者",
    "Retired Team Member": "退休团队成员",
    "Add-On Team": "附加组件团队",
    "Game Moderator": "游戏管理员",
}


# ---------------------------------------------------------------------------
# Promods 服务器 ID 集合
# ---------------------------------------------------------------------------
PROMODS_SERVER_IDS: set[int] = {50, 51}


# ---------------------------------------------------------------------------
# 国家名 / 城市名 英文 -> 中文（精简核心表）
# 服务层会在启动时尝试从 `TruckersMP-cities/` 目录加载更完整的对照表。
# ---------------------------------------------------------------------------
COUNTRY_MAP_EN_TO_CN: Dict[str, str] = {
    "germany": "德国",
    "de": "德国",
    "france": "法国",
    "fr": "法国",
    "united kingdom": "英国",
    "uk": "英国",
    "gb": "英国",
    "netherlands": "荷兰",
    "nl": "荷兰",
    "belgium": "比利时",
    "be": "比利时",
    "poland": "波兰",
    "pl": "波兰",
    "czech republic": "捷克",
    "czechia": "捷克",
    "cz": "捷克",
    "slovakia": "斯洛伐克",
    "sk": "斯洛伐克",
    "italy": "意大利",
    "it": "意大利",
    "spain": "西班牙",
    "es": "西班牙",
    "portugal": "葡萄牙",
    "pt": "葡萄牙",
    "switzerland": "瑞士",
    "ch": "瑞士",
    "austria": "奥地利",
    "at": "奥地利",
    "hungary": "匈牙利",
    "hu": "匈牙利",
    "denmark": "丹麦",
    "dk": "丹麦",
    "sweden": "瑞典",
    "se": "瑞典",
    "norway": "挪威",
    "no": "挪威",
    "finland": "芬兰",
    "fi": "芬兰",
    "estonia": "爱沙尼亚",
    "ee": "爱沙尼亚",
    "latvia": "拉脱维亚",
    "lv": "拉脱维亚",
    "lithuania": "立陶宛",
    "lt": "立陶宛",
    "russia": "俄罗斯",
    "ru": "俄罗斯",
    "turkey": "土耳其",
    "tr": "土耳其",
    "romania": "罗马尼亚",
    "ro": "罗马尼亚",
    "greece": "希腊",
    "gr": "希腊",
    "united states": "美国",
    "usa": "美国",
    "us": "美国",
    "iceland": "冰岛",
    "is": "冰岛",
}


CITY_MAP_EN_TO_CN: Dict[str, str] = {
    "calais": "加来",
    "duisburg": "杜伊斯堡",
    "berlin": "柏林",
    "paris": "巴黎",
    "london": "伦敦",
    "milano": "米兰",
    "milan": "米兰",
    "rome": "罗马",
    "madrid": "马德里",
    "barcelona": "巴塞罗那",
    "lisbon": "里斯本",
    "rotterdam": "鹿特丹",
    "amsterdam": "阿姆斯特丹",
    "brussels": "布鲁塞尔",
    "prague": "布拉格",
    "vienna": "维也纳",
    "budapest": "布达佩斯",
    "warsaw": "华沙",
    "krakow": "克拉科夫",
    "akureyri": "阿克雷里",
    "burgos": "布尔戈斯",
    "praha": "布拉格",
    "steinkjer": "斯泰恩谢尔",
    "valmiera": "瓦尔米耶拉",
    "umeå": "于默奥",
    "umea": "于默奥",
    "longyearbyen": "朗伊尔城",
    "napoli": "那不勒斯",
    "sundsvall": "松兹瓦尔",
}


# ---------------------------------------------------------------------------
# 翻译结果特殊修正表（用于交通地名等）
# key 必须是全小写
# ---------------------------------------------------------------------------
LOCATION_FIX_MAP: Dict[str, str] = {
    "kirkenes": "希尔克内斯",
    "kirkenes quarry": "希尔克内斯 采石场",
    "c-d road": "加莱-杜伊斯堡",
    "cd road": "加莱-杜伊斯堡",
    "calais-duisburg road": "加莱-杜伊斯堡",
    "calais - duisburg": "加莱-杜伊斯堡",
    "calais–duisburg": "加莱-杜伊斯堡",
    "calais-duisburg": "加莱-杜伊斯堡",
    "calais intersection": "加来 交叉口",
    "dortmund": "多特蒙德",
    "hannover": "汉诺威",
    "hamburg": "汉堡",
    "strasbourg": "斯特拉斯堡",
    "dijon": "第戎",
    "reims": "兰斯",
    "brussel": "布鲁塞尔",
    "aalborg": "奥尔堡",
    "kiruna": "基律纳",
    "skellefteå": "谢莱夫特奥",
    "skelleftea": "谢莱夫特奥",
    "ljubjana": "卢布尔雅那",
    "ljubljana": "卢布尔雅那",
    "nikel": "尼克尔",
    "travemünde": "特拉弗明德",
    "travemunde": "特拉弗明德",
    "zürich": "苏黎世",
    "zurich": "苏黎世",
}


__all__: List[str] = [
    "USER_GROUP_MAP",
    "COUNTRY_MAP_EN_TO_CN",
    "CITY_MAP_EN_TO_CN",
    "LOCATION_FIX_MAP",
    "PROMODS_SERVER_IDS",
]


def translate_user_groups(groups: List[Any]) -> List[str]:
    """将 TMP 接口返回的玩家用户组列表翻译为中文，跳过 None。"""
    result: List[str] = []
    for g in groups:
        if g is None:
            continue
        key = str(g)
        result.append(USER_GROUP_MAP.get(key, key))
    return result
