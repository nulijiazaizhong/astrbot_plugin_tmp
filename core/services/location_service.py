"""core.services.location_service

维护英文 -> 中文翻译映射的服务层封装。

实现要点：
    - 静态字典来自 ``core.utils.constants``；
    - 启动时尝试从插件目录下的 ``TruckersMP-cities/<name>.md``
      加载更完整的英文 -> 中文对照表；
    - 通过 ``TranslationService`` 调用百度翻译作为兜底。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astrbot.api import logger

from ..utils.constants import (
    CITY_MAP_EN_TO_CN as _CITY_BASE,
    COUNTRY_MAP_EN_TO_CN as _COUNTRY_BASE,
    LOCATION_FIX_MAP as _FIX_BASE,
    PROMODS_SERVER_IDS,
)
from ..utils.text_utils import (
    cleanup_cn_location_text,
    has_cjk,
    strip_cn_city_suffix,
)
from .translation_service import TranslationService


class LocationService:
    """国家/城市/位置名称翻译器。"""

    CITY_MAP_EN_TO_CN: Dict[str, str] = dict(_CITY_BASE)
    COUNTRY_MAP_EN_TO_CN: Dict[str, str] = dict(_COUNTRY_BASE)
    LOCATION_FIX_MAP: Dict[str, str] = dict(_FIX_BASE)

    # 行格式: `| English | 中文 | (可选) 其它列`
    _TABLE_RE = re.compile(r"^\|\s*([^\|]+?)\s*\|\s*([^\|]+?)\s*\|")
    # 跳过说明表头/分隔行
    _SKIP_HEADER = re.compile(r"^\|\s*(?:English|---)\b", re.IGNORECASE)
    # 形如 `"Foo - bar (City) - Deprecated (3)"` -> base="Foo - bar", status="Deprecated"
    _STATUS_TAG_RE = re.compile(
        r"\s*-\s*(?P<status>[A-Za-z]+)\s*\((?P<num>\d+)\)\s*$"
    )
    _CITY_SUFFIX_RE = re.compile(r"\s*\(City\)\s*$", re.IGNORECASE)

    def __init__(
        self,
        translation: TranslationService,
        cities_dir: Optional[str] = None,
    ) -> None:
        self._translate = translation
        if cities_dir:
            self.load_extra_tables(cities_dir)
        else:
            logger.info("未指定 cities 目录，使用基础映射。")

    # ------------------------------------------------------------------ #
    # 加载外部对照表
    # ------------------------------------------------------------------ #
    def load_extra_tables(self, cities_dir: str) -> None:
        """从 ``cities_dir`` 中加载 ``*-cities.md`` 到映射表。"""
        path = Path(cities_dir)
        if not path.is_dir():
            logger.info(f"cities 目录不存在: {path}")
            return

        count = 0
        for md_file in sorted(path.glob("*-cities.md")):
            count += self._parse_table(md_file)
        logger.info(
            f"从 {cities_dir} 加载 {count} 条扩展映射。"
        )

    def _parse_table(self, file_path: Path) -> int:
        rows: List[Tuple[str, str]] = []
        try:
            with file_path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line.startswith("|") or self._SKIP_HEADER.match(line):
                        continue
                    m = self._TABLE_RE.match(line)
                    if not m:
                        continue
                    en = m.group(1).strip()
                    cn = m.group(2).strip()
                    if en and cn:
                        rows.append((en, cn))
        except Exception as exc:
            logger.warning(f"读取 {file_path} 失败: {exc}")
            return 0

        added = 0
        for en, cn in rows:
            if self._add_mapping(en, cn):
                added += 1
        return added

    def _add_mapping(self, en: str, cn: str) -> bool:
        en_raw = (en or "").strip()
        cn_raw = (cn or "").strip()
        if not en_raw or not cn_raw or cn_raw == en_raw:
            return False

        en_key = en_raw.lower()
        cn_clean = cleanup_cn_location_text(cn_raw)
        if not cn_clean:
            return False

        # 1) 状态后缀，例如 "Deprecated (3)"
        status_m = self._STATUS_TAG_RE.search(en_raw)
        en_base = en_raw
        if status_m:
            en_base = en_raw[: status_m.start()].strip()
        # 将英文 base 名同样做一轮"清洗"，以便与中文 base (cn_clean) 同比对
        en_clean = cleanup_cn_location_text(en_base) or en_base
        if en_clean.lower() == cn_clean.lower():
            return False

        # 2) "(City)" 后缀的英文，表示城市
        city_m = self._CITY_SUFFIX_RE.search(en_base)
        if city_m:
            city_en_base = en_base[: city_m.start()].strip()
            city_cn_base = strip_cn_city_suffix(cn_clean)
            if city_en_base and (city_cn_base or cn_clean).lower() == city_en_base.lower():
                # 完全重复的城市英文本身不再加入
                pass
            else:
                if city_en_base:
                    self.CITY_MAP_EN_TO_CN[city_en_base.lower()] = city_cn_base or cn_clean
                    self.LOCATION_FIX_MAP[city_en_base.lower()] = city_cn_base or cn_clean
                self.LOCATION_FIX_MAP[en_base.lower()] = city_cn_base or cn_clean
                self.LOCATION_FIX_MAP[en_key] = city_cn_base or cn_clean
            return True

        # 3) 默认为国家
        self.COUNTRY_MAP_EN_TO_CN[en_base.lower()] = cn_clean
        self.LOCATION_FIX_MAP[en_base.lower()] = cn_clean
        self.LOCATION_FIX_MAP[en_key] = cn_clean
        return True

    # ------------------------------------------------------------------ #
    # 翻译入口
    # ------------------------------------------------------------------ #
    async def translate_country_city(
        self,
        country: Optional[str],
        city: Optional[str],
    ) -> Tuple[str, str]:
        """同时翻译国家与城市。如本地查不到则调用百度翻译。"""
        country_en = self._clean_raw(country)
        city_en = self._clean_raw(city)
        city_en = self._normalize_city(city_en, country_en)

        country_key = country_en.lower()
        city_key = city_en.lower()

        country_cn = self.COUNTRY_MAP_EN_TO_CN.get(country_key) or ""
        if country_en and not has_cjk(country_cn):
            translated = await self._translate.translate(country_en)
            if has_cjk(translated):
                country_cn = translated

        city_cn = self.CITY_MAP_EN_TO_CN.get(city_key) or ""
        if city_en and not has_cjk(city_cn):
            translated = await self._translate.translate(city_en)
            if has_cjk(translated):
                city_cn = translated

        # 应用修正表
        fix_country = self.LOCATION_FIX_MAP.get(country_key)
        if fix_country and has_cjk(fix_country):
            country_cn = fix_country
        fix_city = self.LOCATION_FIX_MAP.get(city_key)
        if fix_city and has_cjk(fix_city):
            city_cn = fix_city

        country_cn = self._ensure_cn(country_cn, country_en, is_city=False)
        city_cn = self._ensure_cn(city_cn, city_en, is_city=True)
        return country_cn, city_cn

    async def translate_traffic_name(self, name: Optional[str]) -> str:
        """翻译路况接口返回的地点名（混合策略）。"""
        s = (name or "").strip()
        if not s:
            return s
        s = re.sub(r"\s+", " ", s).strip()
        key = s.lower()

        # 1. 修正表
        fix = self.LOCATION_FIX_MAP.get(key)
        if fix:
            return fix
        city_fix = self.CITY_MAP_EN_TO_CN.get(key)
        if city_fix:
            return city_fix

        # 2. 处理 "X intersection/quarry" 后缀
        m = re.search(
            r"^(?P<base>.+?)\s+(?P<suffix>intersection|quarry)\s*$",
            s,
            flags=re.IGNORECASE,
        )
        if m:
            base = m.group("base").strip()
            suffix = m.group("suffix").lower()
            base_cn = await self.translate_traffic_name(base)
            suffix_cn = "交叉口" if suffix == "intersection" else "采石场"
            merged_key = f"{base} {suffix}".strip().lower()
            merged_fix = self.LOCATION_FIX_MAP.get(merged_key)
            if merged_fix:
                return merged_fix
            if base_cn and base_cn != base:
                return f"{base_cn} {suffix_cn}".strip()

        # 3. 复合名 "A - B" 拆段翻译
        for sep in (" - ", "–", "-", "/"):
            if sep in s:
                parts = [p.strip() for p in s.split(sep) if p.strip()]
                if len(parts) >= 2:
                    translated = []
                    for p in parts:
                        pk = p.lower()
                        if pk in self.LOCATION_FIX_MAP:
                            translated.append(self.LOCATION_FIX_MAP[pk])
                        elif pk in self.CITY_MAP_EN_TO_CN:
                            translated.append(self.CITY_MAP_EN_TO_CN[pk])
                        else:
                            translated.append(p)
                    joiner = " - " if sep.strip() in ("-", "–") else sep
                    return joiner.join(translated)

        # 4. 兜底：百度翻译
        return await self._translate.translate(s)

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #
    def _clean_raw(self, text: Optional[str]) -> str:
        s = (text or "").strip()
        if not s or has_cjk(s):
            return s
        s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
        s = re.sub(r"\s*（[^）]*）\s*", " ", s)
        s = re.sub(r"\s*\[[^\]]*\]\s*", " ", s)
        s = re.sub(r"[^A-Za-z\s\-]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _normalize_city(self, raw_city: str, raw_country: str) -> str:
        s = (raw_city or "").strip()
        if not s:
            return s
        s = re.sub(r"\s+", " ", s).strip()
        c = (raw_country or "").strip()
        if c:
            c_norm = re.sub(r"\s+", " ", c).strip()
            if s.lower().startswith((c_norm + " - ").lower()):
                s = s[len(c_norm) + 3 :].strip()
            elif s.lower().startswith((c_norm + " ").lower()):
                s = s[len(c_norm) + 1 :].strip()
        if " - " in s:
            left, right = s.split(" - ", 1)
            left_k = left.strip().lower()
            if left_k in self.COUNTRY_MAP_EN_TO_CN:
                s = right.strip()
        low = s.lower()
        for k in sorted(self.COUNTRY_MAP_EN_TO_CN.keys(), key=len, reverse=True):
            if not k:
                continue
            if low.startswith(k + " - "):
                s = s[len(k) + 3 :].strip()
                break
            if low.startswith(k + " "):
                s = s[len(k) + 1 :].strip()
                break
        return s

    def _ensure_cn(self, text: Optional[str], en_fallback: str, is_city: bool) -> str:
        t = (text or "").strip()
        if has_cjk(t):
            return t
        key = (en_fallback or "").strip().lower()
        mapped = self.CITY_MAP_EN_TO_CN.get(key) if is_city else self.COUNTRY_MAP_EN_TO_CN.get(key)
        if mapped and has_cjk(mapped):
            return mapped
        fixed = self.LOCATION_FIX_MAP.get(key)
        if fixed and has_cjk(fixed):
            return fixed
        return ""


__all__ = ["LocationService", "PROMODS_SERVER_IDS"]
