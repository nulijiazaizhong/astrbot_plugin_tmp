"""core.commands.registry

注册所有 AstrBot 命令处理器。

内部形态：
    每个命令方法都是 ``async def foo(event) -> AsyncGenerator``，与原
    ``main.py`` 业务分支语义保持一致。命令函数中：
        - 输入解析（数字 / at / 绑定）
        - 业务查询（services）
        - 输出渲染（plain 或 chain_result）

本次重构将这些 handlers 一并迁移，使得 ``main.py`` 仅负责挂载。
"""

from __future__ import annotations

import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import Image, Plain

from ..api import Ets2MapClient
from ..render import (
    DEFAULT_TILE_ETS,
    DEFAULT_TILE_PROMODS,
    DLC_LIST_TEMPLATE,
    FOOTPRINT_MAP_TEMPLATE,
    LEAFLET_CSS_URL,
    LEAFLET_JS_URL,
    LOCATE_MAP_TEMPLATE,
    RANK_TEMPLATE,
    HtmlRenderService,
)
from ..services import (
    BindingService,
    ConfigService,
    DlcService,
    FootprintService,
    LocationService,
    PlayerService,
    RankingService,
    ServerService,
    TrafficService,
    VtcmClient,
)
from ..services.helpers import (
    normalize_avatar_url,
    to_int,
    get_steam_id_from_player_info,
)
from ..utils.constants import PROMODS_SERVER_IDS
from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
)
from ..utils.time_utils import (
    format_timestamp_to_beijing,
    format_timestamp_to_readable,
)
from .context import TmpCommandContext


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _extract_target_user_id(message_obj: Any) -> Optional[str]:
    """从消息链中解析被 @ 用户的 ID。"""
    if message_obj is None:
        return None
    chain = getattr(message_obj, "message", None) or []
    for seg in chain:
        seg_type = getattr(seg, "type", None)
        if isinstance(seg, dict):
            seg_type = seg.get("type") or seg_type
        if isinstance(seg_type, str) and seg_type.lower() == "at":
            uid = (
                getattr(seg, "qq", None)
                or getattr(seg, "user_id", None)
                or getattr(seg, "id", None)
            )
            if isinstance(seg, dict):
                uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
            if uid:
                return str(uid)
        uid2 = getattr(seg, "qq", None) or getattr(seg, "user_id", None) or getattr(seg, "id", None)
        if isinstance(seg, dict):
            uid2 = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid2
        if uid2:
            return str(uid2)
    return None


def _strip_paren_text(s: Optional[str]) -> str:
    t = (s or "").strip()
    if not t:
        return t
    t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
    t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
    return t


def _combined_location(country_cn: str, city_cn: str) -> str:
    dc = (country_cn or "").strip()
    dcity = (city_cn or "").strip()
    if dc and dcity:
        if dcity == dc or dcity.startswith(dc):
            return dcity
        return f"{dc}-{dcity}"
    return dcity or dc or "未知位置"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class CommandRegistry:
    """封装所有 AstrBot 命令实现。"""

    def __init__(self, ctx: TmpCommandContext) -> None:
        self.ctx = ctx

    # ====================================================================== #
    # 属性：方便在实现里使用
    # ====================================================================== #
    @property
    def config(self) -> ConfigService:
        return self.ctx.config

    @property
    def binding(self) -> BindingService:
        return self.ctx.binding

    @property
    def translate(self):
        return self.ctx.translate

    @property
    def location(self) -> LocationService:
        return self.ctx.location

    @property
    def player(self) -> PlayerService:
        return self.ctx.player

    @property
    def ranking(self) -> RankingService:
        return self.ctx.ranking

    @property
    def dlc(self) -> DlcService:
        return self.ctx.dlc

    @property
    def traffic(self) -> TrafficService:
        return self.ctx.traffic

    @property
    def server(self) -> ServerService:
        return self.ctx.server

    @property
    def footprint(self) -> FootprintService:
        return self.ctx.footprint_service

    @property
    def vtcm(self) -> VtcmClient:
        return self.ctx.vtcm_client

    @property
    def fullmap(self) -> Ets2MapClient:
        return self.ctx.ets2map_client

    @property
    def render(self) -> HtmlRenderService:
        # 通过插件主体延迟绑定：见 main.py on_load 调用 render_service.bind_star()
        return self.ctx.render

    # ====================================================================== #
    # 绑定 / 解绑
    # ====================================================================== #
    async def bind(self, event) -> AsyncGenerator[Any, None]:
        msg = (event.message_str or "").strip()
        m = re.search(r"绑定\s*(\d+)", msg)
        if not m:
            yield event.plain_result("请使用 `绑定 <TMP ID>` 格式，例如 `绑定 123456`")
            return
        input_id = m.group(1)
        try:
            tmp_id = await self.player.resolve_tmp_id(input_id)
        except SteamIdNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"SteamID绑定失败: {exc}\n请稍后重试或使用TMP ID绑定")
            return
        except Exception as exc:
            yield event.plain_result(
                "Steam ID 查询服务请求失败，请直接使用TMP ID绑定。\n\n格式：绑定 [TMP ID]"
            )
            return

        try:
            data = await self.player.fetch_full_profile(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result("玩家不存在，请检查ID是否正确")
            return
        except Exception as exc:
            yield event.plain_result(f"查询失败: {exc}")
            return

        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        player_name = data.get("profile", {}).get("name", "未知")
        if self.binding.bind(str(user_id), str(tmp_id), player_name):
            yield event.plain_result(
                f"绑定成功！\n已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定"
            )
        else:
            yield event.plain_result("绑定失败，请稍后重试")

    async def unbind(self, event) -> AsyncGenerator[Any, None]:
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        if self.binding.unbind(str(user_id)):
            yield event.plain_result(f"解绑成功！\n已解除与TMP玩家的绑定")
        else:
            yield event.plain_result("您还没有绑定任何TMP账号")

    # ====================================================================== #
    # 查询 (tmpquery)
    # ====================================================================== #
    async def cmd_query(self, event, tmp_id: str | None = None) -> AsyncGenerator[Any, None]:
        """[命令: 查询] 玩家完整信息查询。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""

        target_user_id = _extract_target_user_id(getattr(event, "message_obj", None))
        match = re.search(r"(查询|查)\s*(\d+)", message_str)
        input_id = match.group(2) if match else tmp_id

        try:
            if input_id:
                tmp_id = await self.player.resolve_tmp_id(input_id)
            else:
                bind_user = target_user_id or user_id
                tmp_id = self.binding.get(str(bind_user))
        except SteamIdNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询")
            return
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        try:
            data = await self.player.fetch_full_profile(str(tmp_id))
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except Exception as exc:
            yield event.plain_result(f"查询失败: {exc}")
            return

        info = data.get("profile", {}) or {}
        bans = data.get("sorted_bans", []) or []
        ban_count = data.get("ban_count", 0)
        vtcm = data.get("vtcm", {}) or {}
        online = data.get("online", {}) or {}

        steam_id_to_display = get_steam_id_from_player_info(info)
        is_banned = bool(info.get("banned", False))
        banned_until_main = info.get("bannedUntil", "永久/未知")

        bans_count_raw = info.get("bansCount")
        if bans_count_raw is not None:
            try:
                ban_count = int(str(bans_count_raw).strip())
            except Exception:
                pass

        last_online_raw = (
            info.get("lastOnline")
            or vtcm.get("last_online")
            or vtcm.get("lastOnline")
            or vtcm.get("lastLogin")
            or vtcm.get("last_login")
        )
        last_online_formatted = format_timestamp_to_readable(last_online_raw)

        body = f"🆔 TMP ID: {tmp_id}\n"
        if steam_id_to_display:
            body += f"🆔 Steam ID: {steam_id_to_display}\n"
        body += f"😀玩家名称: {info.get('name', '未知')}\n"
        join_date_raw = (
            info.get("joinDate")
            or info.get("created_at")
            or info.get("registrationDate")
        )
        join_date_formatted = (
            format_timestamp_to_beijing(join_date_raw) if join_date_raw else "未知"
        )
        body += f"📑注册日期: {join_date_formatted}\n"

        # 权限 / 分组
        perms_str = "玩家"
        perms = info.get("permissions")
        if isinstance(perms, dict):
            groups = [
                g for g in ["Staff", "Management", "Game Admin"]
                if perms.get(f"is{g.replace(' ', '')}")
            ]
            if groups:
                from ..utils.text_utils import translate_user_groups
                perms_str = ", ".join(translate_user_groups(groups))
        elif isinstance(perms, list) and perms:
            from ..utils.text_utils import translate_user_groups
            perms_str = ", ".join(translate_user_groups(perms))
        body += f"💼所属分组: {perms_str}\n"

        # 车队
        vtc = info.get("vtc") if isinstance(info.get("vtc"), dict) else {}
        vtc_name = vtc.get("name")
        vtc_role = vtc.get("role") or vtc.get("position") or vtcm.get("vtcRole")
        if vtc_name:
            body += f"🚚所属车队: {vtc_name}\n"
            if vtc_role:
                body += f"🚚车队职位: {vtc_role}\n"

        # 赞助信息
        def _get_nested(d, *keys):
            cur = d
            for k in keys:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        is_patron = any([
            bool(info.get("isPatron")),
            bool(info.get("isPatreon")),
            bool(_get_nested(info, "patreon", "isPatron")),
            bool(_get_nested(info, "patreon", "isPatreon")),
            bool(_get_nested(info, "patron", "isPatron")),
            bool(_get_nested(info, "patron", "isPatreon")),
        ])
        if is_patron:
            current_pledge = (
                _get_nested(info, "patreon", "currentPledge")
                or info.get("currentPledge")
                or _get_nested(info, "patron", "currentPledge")
                or _get_nested(info, "donation", "currentPledge")
                or 0
            )
            lifetime_pledge = (
                _get_nested(info, "patreon", "lifetimePledge")
                or info.get("lifetimePledge")
                or _get_nested(info, "patron", "lifetimePledge")
                or _get_nested(info, "donation", "lifetimePledge")
                or 0
            )
            current_pledge_usd = to_int(current_pledge) // 100
            lifetime_pledge_usd = to_int(lifetime_pledge) // 100
            if lifetime_pledge_usd > 0:
                if current_pledge_usd > 0:
                    body += f"🎁当前赞助金额: {current_pledge_usd}美元\n"
                body += f"🎁历史赞助金额: {lifetime_pledge_usd}美元\n"

        # 里程信息
        total_km = vtcm.get("total_km", 0.0)
        daily_km = vtcm.get("daily_km", 0.0)
        try:
            total_val = float(total_km)
        except Exception:
            total_val = 0.0
        try:
            daily_val = float(daily_km)
        except Exception:
            daily_val = 0.0
        if total_val > 0:
            body += f"🚩历史里程: {total_val:.2f}公里/km\n"
        if daily_val > 0:
            body += f"🚩今日里程: {daily_val:.2f}公里/km\n"

        body += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
        body += f"🚫历史封禁: {ban_count}次\n"

        if is_banned:
            current_ban = None
            for ban in bans:
                if ban.get("active"):
                    current_ban = ban
                    break
            if not current_ban and bans:
                current_ban = bans[0]
            if current_ban:
                ban_reason_raw = current_ban.get("reason", "未知封禁原因 (API V2)")
                # 简单原因直接展示；如需翻译可在这里调用 translate.translate()
                ban_expiration = current_ban.get("expiration", banned_until_main)
                body += f"🚫封禁原因: {ban_reason_raw}\n"
                if ban_expiration and isinstance(ban_expiration, str):
                    if ban_expiration.lower().startswith("never"):
                        body += "🚫封禁截止: 永久封禁\n"
                    else:
                        body += f"🚫封禁截止: {format_timestamp_to_beijing(ban_expiration)}\n"
            else:
                body += "🚫封禁原因: 隐藏\n"
                if banned_until_main and isinstance(banned_until_main, str):
                    if banned_until_main.lower().startswith("never"):
                        body += "🚫封禁截止: 永久封禁\n"
                    else:
                        body += f"🚫封禁截止: {format_timestamp_to_beijing(banned_until_main)}\n"

        # 在线状态
        if online.get("online"):
            server_name = online.get("serverName", "未知服务器")
            game = online.get("game", 0)
            game_mode = "欧卡2" if game == 1 else "美卡" if game == 2 else "未知游戏"
            country_cn = online.get("country_cn") or ""
            city_cn = online.get("city_cn") or ""
            location_display = _combined_location(country_cn, city_cn)
            body += f"📶在线状态: 在线\n"
            body += f"📶所在服务器: {server_name} ({game_mode})\n"
            body += f"📶所在位置: {location_display}\n"
        else:
            body += "📶在线状态: 离线\n"
            body += f"📶上次在线: {last_online_formatted}"

        # 头像组件
        show_avatar = self.config.get_bool("query_show_avatar_enable", True)

        avatar_url = normalize_avatar_url(info.get("avatar") or vtcm.get("avatar_url"))
        components: List[Any] = []
        if show_avatar and avatar_url:
            # 使用 Image.fromBytes + 自协程下载头像以避免 Image.fromURL 在某些适配器下不可用
            try:
                resp_sess = self.ctx.http.session
                if resp_sess is not None:
                    async with resp_sess.get(avatar_url) as resp:
                        if resp.status == 200:
                            img_bytes = await resp.read()
                            if img_bytes:
                                components.append(Image.fromBytes(img_bytes))
            except Exception as exc:
                logger.error(
                    "查询详情: 下载头像失败 (%s)，降级为纯文本",
                    exc.__class__.__name__,
                )

        if components:
            components.append(Plain(body))
            yield event.chain_result(components)
        else:
            yield event.plain_result(body)

    # ====================================================================== #
    # DLC
    # ====================================================================== #
    async def cmd_dlc_list(self, event) -> AsyncGenerator[Any, None]:
        try:
            items = await self.dlc.list(1)
        except Exception:
            yield event.plain_result("查询DLC列表失败")
            return
        if not items:
            yield event.plain_result("暂无数据")
            return

        lines: List[str] = []
        for it in items:
            name = str(it.get("name") or "").strip()
            final_price = it.get("finalPrice")
            discount = it.get("discount") or 0
            try:
                price_str = f"￥{int(final_price) // 100}" if isinstance(final_price, (int, float)) else ""
            except Exception:
                price_str = ""
            if discount and isinstance(discount, (int, float)) and discount > 0:
                lines.append(f"{name} {price_str} (-{int(discount)}%)")
            else:
                lines.append(f"{name} {price_str}")
        text = "\n".join(lines)

        if self.config.get_bool("dlc_list_image", False):
            def _p(v):
                try:
                    return f"￥{int(v) // 100}" if isinstance(v, (int, float)) else ""
                except Exception:
                    return ""

            mapped: List[Dict[str, Any]] = [
                {
                    "name": str(it.get("name") or "").strip(),
                    "desc": str(it.get("desc") or "").strip(),
                    "headerImageUrl": str(it.get("headerImageUrl") or "").strip(),
                    "price_str": _p(it.get("finalPrice")),
                    "original_price_str": _p(it.get("originalPrice")),
                    "discount": int(it.get("discount") or 0)
                    if isinstance(it.get("discount"), (int, float))
                    else 0,
                }
                for it in items
            ]

            options = {"type": "jpeg", "quality": 92, "full_page": True, "omit_background": False}
            data = {"items": mapped, "title": "DLC 列表"}
            # 为渲染准备可能需要的 title
            try:
                url = await self.render.render_html(DLC_LIST_TEMPLATE, data, options=options)
            except Exception:
                url = None
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
            try:
                img = await self.render.render_text(text)
            except Exception:
                img = None
            if isinstance(img, (bytes, bytearray)):
                yield event.chain_result([Image.fromBytes(img)])
                return
            if isinstance(img, str) and img.startswith("http"):
                yield event.chain_result([Image.fromURL(img)])
                return

        yield event.plain_result(text)

    # ====================================================================== #
    # 排行榜
    # ====================================================================== #
    async def cmd_rank_total(self, event) -> AsyncGenerator[Any, None]:
        async for r in self._rank(event, "total"):
            yield r

    async def cmd_rank_today(self, event) -> AsyncGenerator[Any, None]:
        async for r in self._rank(event, "today"):
            yield r

    async def _rank(self, event, kind: str) -> AsyncGenerator[Any, None]:
        if kind == "today":
            rank_list = await self.ranking.today(10)
            title = "- 今日行驶里程排行榜 -"
            header = "🏁 TruckersMP 玩家今日里程排行榜 (前10名)\n"
            stat_key = "daily_km"
            rank_key = "daily_rank"
        else:
            rank_list = await self.ranking.total(10)
            title = "- 总行驶里程排行榜 -"
            header = "🏆 TruckersMP 玩家总里程排行榜 (前10名)\n"
            stat_key = "total_km"
            rank_key = "total_rank"

        if not rank_list:
            yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
            return

        message = header + "=" * 35 + "\n"
        items = self.ranking.build_items(rank_list)
        me_data: Optional[Dict[str, Any]] = None
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        bound = self.binding.get(str(user_id))
        if isinstance(bound, str):
            me_tmp_id, me_name = bound, None
        elif isinstance(bound, dict):
            me_tmp_id = bound.get("tmp_id")
            me_name = bound.get("player_name")
        else:
            me_tmp_id = None

        if me_tmp_id:
            try:
                stats = await self.player.fetch_vtcm_stats(str(me_tmp_id))
            except Exception:
                stats = None
            km = (stats or {}).get(stat_key)
            if isinstance(km, (int, float)):
                km_str = f"{float(km):,.2f}".replace(",", " ")
                display_name = (str(me_name).strip() if me_name else "") or "你"
                message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                message += f"里程: {km_str} km"
                rank_value = (stats or {}).get(rank_key)
                if rank_value is not None:
                    message += f" | 排名: No.{rank_value}"
                message += "\n"
                vtc_role = (stats or {}).get("vtcRole")
                if vtc_role:
                    message += f"车队职位: {str(vtc_role).strip()}\n"
                message += "-" * 35 + "\n"
                me_data = {
                    "name": display_name,
                    "tmp_id": str(me_tmp_id),
                    "rank": rank_value,
                    "km": float(km),
                    "vtc_role": (str(vtc_role).strip() if vtc_role else ""),
                }

        for it in items:
            rank_num = it["rank"]
            name = it["name"]
            distance_str = f"{it['km']:,}".replace(',', ' ')
            tmp_id = it["tmp_id"]
            message += f"No.{rank_num:<2} | {name} (ID:{tmp_id})\n"
            message += f"       {distance_str} km\n"

        message += "=" * 35 + "\n"

        options = {"type": "jpeg", "quality": 92, "full_page": True, "omit_background": False}
        data = {"title": title, "items": items, "me": me_data}
        try:
            url = await self.render.render_html(RANK_TEMPLATE, data, options=options)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception:
            pass

        try:
            img = await self.render.render_text(message)
        except Exception:
            img = None
        if isinstance(img, (bytes, bytearray)):
            yield event.chain_result([Image.fromBytes(img)])
            return
        if isinstance(img, str) and img.startswith("http"):
            yield event.chain_result([Image.fromURL(img)])
            return
        yield event.plain_result(message)

    # ====================================================================== #
    # 路况
    # ====================================================================== #
    async def cmd_traffic(self, event, server: str | None = None) -> AsyncGenerator[Any, None]:
        msg = (event.message_str or "").strip()
        m = re.search(r"路况\s*(\S+)", msg)
        server_token = (m.group(1).strip().lower() if m else "").strip()
        if not server_token:
            yield event.plain_result("用法: 路况 [服务器简称]，例如: 路况 s1")
            return
        try:
            items = await self.traffic.top(server_token, with_translate=True)
        except (NetworkException, ApiResponseException) as exc:
            yield event.plain_result(f"查询路况失败: {exc}")
            return
        except Exception as exc:
            yield event.plain_result(f"查询路况时发生未知错误: {exc}")
            return
        if not items:
            yield event.plain_result("当前服务器暂无热门路段数据。")
            return

        severity_map = {
            "Fluid": "🟢畅通",
            "Moderate": "🟠正常",
            "Congested": "🔴缓慢",
            "Heavy": "🟣拥堵",
        }
        type_map = {
            "City": "城市",
            "Road": "公路",
            "Intersection": "十字路口",
        }
        lines: List[str] = []
        for t in items:
            country_raw = str(t.get("country") or "").strip()
            country_cn, _ = await self.location.translate_country_city(country_raw, None)
            country = country_cn or "未知区域"
            raw_name = str(t.get("name") or "").strip()
            name = raw_name
            place_type = ""
            idx1 = raw_name.rfind("(")
            idx2 = raw_name.rfind(")")
            if idx1 > 0 and idx2 > idx1:
                name = raw_name[:idx1].strip()
                place_type = raw_name[idx1 + 1:idx2].strip()
            translated_name = t.get("name_cn") or await self.location.translate_traffic_name(name)
            severity_key = str(t.get("newSeverity") or "").strip()
            severity_text = severity_map.get(severity_key) or severity_key or "未知"
            if severity_text == severity_key and severity_key:
                translated_severity = await self.translate.translate(severity_key)
                if translated_severity and translated_severity != severity_key:
                    severity_text = translated_severity
            players = t.get("players")
            players_str = ""
            if isinstance(players, (int, float)):
                players_str = str(int(players))
            elif players is not None:
                players_str = str(players)

            line = f"{country} {translated_name}"
            if place_type:
                type_text = type_map.get(place_type, place_type)
                if type_text == place_type and place_type:
                    translated_type = await self.translate.translate(place_type)
                    if translated_type and translated_type != place_type:
                        type_text = translated_type
                line += f" ({type_text})"
            line += f"\n路况: {severity_text}"
            if players_str:
                line += f" | 人数: {players_str}"
            lines.append(line)
        header = "🚦 服务器热门路况\n" + "=" * 20
        yield event.plain_result(header + "\n" + "\n\n".join(lines))

    # ====================================================================== #
    # 服务器 / 版本
    # ====================================================================== #
    async def cmd_servers(self, event) -> AsyncGenerator[Any, None]:
        servers = await self.vtcm.get_official_servers()
        if not servers:
            yield event.plain_result("查询服务器失败，请稍后重试")
            return
        message = ""
        for server in servers:
            if message:
                message += "\n\n"
            is_online = server.get("isOnline")
            if is_online is None:
                is_online = server.get("online")
            if isinstance(is_online, (int, float)):
                online_flag = int(is_online) == 1
            elif isinstance(is_online, str):
                online_flag = is_online.strip().lower() in ("1", "true", "yes", "y")
            else:
                online_flag = bool(is_online)
            name = server.get("serverName") or server.get("name") or "未知服务器"
            status = "🟢" if online_flag else "⚫"
            message += f"服务器: {status}{name}"
            players = server.get("playerCount")
            if players is None:
                players = server.get("players", 0)
            max_players = server.get("maxPlayer")
            if max_players is None:
                max_players = server.get("maxplayers", 0)
            message += f"\n玩家人数: {players}/{max_players}"
            queue_flag = server.get("queue", 0)
            queue_count = server.get("queueCount", queue_flag)
            if queue_flag:
                message += f" (队列: {queue_count})"
            characteristic_list: List[str] = []
            afk_enable = server.get("afkEnable")
            if afk_enable is None:
                afk_enable = server.get("afkEnabled")
            can_afk = False
            if isinstance(afk_enable, bool):
                can_afk = afk_enable
            elif isinstance(afk_enable, (int, float)):
                can_afk = int(afk_enable) == 1
            elif isinstance(afk_enable, str):
                can_afk = afk_enable.strip().lower() in ("1", "true", "yes", "y")
            if not can_afk:
                characteristic_list.append("⏱挂机")
            collisions_enable = server.get("collisionsEnable")
            if collisions_enable is None:
                collisions_enable = server.get("collisions")
            if isinstance(collisions_enable, bool) and collisions_enable:
                characteristic_list.append("💥碰撞")
            elif isinstance(collisions_enable, (int, float)) and int(collisions_enable) == 1:
                characteristic_list.append("💥碰撞")
            if characteristic_list:
                message += "\n服务器特性: " + " ".join(characteristic_list)
        yield event.plain_result(message or "暂无在线服务器")

    async def cmd_plugin_version(self, event) -> AsyncGenerator[Any, None]:
        version_info = await self.vtcm.get_plugin_version()
        if not version_info:
            yield event.plain_result("查询版本信息失败，请稍后重试。")
            return
        plugin_ver = (
            version_info.get("name")
            or version_info.get("version")
            or "未知"
        )
        ets2_ver = (
            version_info.get("supported_game_version")
            or version_info.get("supported_ets2_version")
            or "未知"
        )
        ats_ver = (
            version_info.get("supported_ats_game_version")
            or version_info.get("supported_ats_version")
            or "未知"
        )
        protocol = version_info.get("protocol") or "未知"
        message = "TMP 插件版本信息\n" + "=" * 18 + "\n"
        message += f"TMP 插件版本: {plugin_ver}\n"
        message += f"欧卡支持版本: {ets2_ver}\n"
        message += f"美卡支持版本: {ats_ver}\n"
        message += f"协议版本: {protocol}"
        yield event.plain_result(message)

    async def cmd_help(self, event) -> AsyncGenerator[Any, None]:
        help_text = (
            "TMP查询姬指令菜单\n\n"
            "可用命令:\n"
            "1. 绑定 [TMP ID]\n"
            "2. 查询 [TMP ID]\n"
            "3. 定位 [TMP ID]\n"
            "4. 路况[s1/s2/p/a]\n"
            "5. 总里程排行\n"
            "6. 今日里程排行\n"
            "7. 足迹 [服务器简称] [TMP ID]\n"
            "8. 服务器\n"
            "9. 插件版本\n"
            "10. 历史车队 [TMP ID]\n"
            "使用提示: 绑定后可直接发送 查询/定位/足迹/历史车队 [服务器简称]\n"
        )
        yield event.plain_result(help_text)
        # VTCM 子菜单由 _on_any_message_dispatch 接管

    # ====================================================================== #
    # 定位
    # ====================================================================== #
    async def cmd_locate(self, event, tmp_id: str | None = None) -> AsyncGenerator[Any, None]:
        message_str = event.message_str.strip()
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        target_user_id = _extract_target_user_id(getattr(event, "message_obj", None))
        match = re.search(r"(定位)\s*(\d+)", message_str)
        input_id = match.group(2) if match else tmp_id

        try:
            if input_id:
                tmp_id = await self.player.resolve_tmp_id(input_id)
            else:
                bind_user = target_user_id or user_id
                tmp_id = self.binding.get(str(bind_user))
        except SteamIdNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询")
            return
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        try:
            profile = await self.player.fetch_profile(str(tmp_id))
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except Exception as exc:
            yield event.plain_result(f"查询失败: {exc}")
            return

        info = profile["info"]
        player_name = info.get("name") or "未知"
        avatar_url = normalize_avatar_url(info.get("avatar"))

        online = await self.player.fetch_online_status(str(tmp_id))
        await self.fullmap.fetch_fullmap()
        fullmap_player = self.fullmap.find_player(str(tmp_id))
        if (not online.get("online")) and fullmap_player:
            online = {
                "online": True,
                "serverName": "未知服务器",
                "serverId": fullmap_player.get("ServerId"),
                "x": fullmap_player.get("X"),
                "y": fullmap_player.get("Y"),
                "country": None,
                "realName": None,
                "city": {"name": "未知位置"},
            }
        if fullmap_player:
            online["x"] = fullmap_player.get("X")
            online["y"] = fullmap_player.get("Y")
            online["serverId"] = fullmap_player.get("ServerId")

        if not online.get("online"):
            yield event.plain_result("玩家未在线")
            return

        server_name = online.get("serverName", "未知服务器")
        location_name = online.get("city", {}).get("name") or "未知位置"
        raw_country = online.get("country")
        raw_city = online.get("realName")
        country_cn, city_cn = await self.location.translate_country_city(raw_country, raw_city)
        display_country = _strip_paren_text(country_cn or "未知国家")
        display_city = _strip_paren_text(city_cn or "未知位置")
        if display_country and display_city:
            dc = display_country.strip()
            dcity = display_city.strip()
            if dcity == dc or dcity.startswith(dc):
                location_line = dcity
            else:
                location_line = f"{dc}-{dcity}"
        else:
            location_line = display_city or display_country or "未知位置"

        try:
            server_id = online.get("serverId")
            cx = float(online.get("x") or 0)
            cy = float(online.get("y") or 0)
            ax, ay = cx - 4000, cy + 2500
            bx, by = cx + 4000, cy - 2500
            area_players = await self.vtcm.get_area_players(server_id, ax, ay, bx, by)
            normalized = []
            for p in area_players:
                if not isinstance(p, dict):
                    continue
                axis_x = (
                    p.get("axisX") or p.get("x") or p.get("posX") or p.get("pos_x")
                )
                axis_y = (
                    p.get("axisY") or p.get("y") or p.get("posY") or p.get("pos_y")
                )
                if axis_x is None or axis_y is None:
                    continue
                pid = (
                    p.get("tmpId") or p.get("mpId") or p.get("playerId") or p.get("id")
                )
                normalized.append(
                    {
                        "tmpId": str(pid) if pid is not None else "",
                        "axisX": axis_x,
                        "axisY": axis_y,
                    }
                )
            area_players = [
                p for p in normalized if str(p.get("tmpId")) != str(tmp_id)
            ]
            area_players.append({"tmpId": str(tmp_id), "axisX": cx, "axisY": cy})

            tile_url_ets = DEFAULT_TILE_ETS
            tile_url_promods = DEFAULT_TILE_PROMODS
            fullmap_ets = self.fullmap.find_tile_url("ets")
            fullmap_promods = self.fullmap.find_tile_url("promods")
            if fullmap_ets:
                tile_url_ets = fullmap_ets
            if fullmap_promods:
                tile_url_promods = fullmap_promods
            map_type = "promods" if int(server_id or 0) in PROMODS_SERVER_IDS else "ets"
            if map_type == "ets" and not tile_url_ets:
                raise RuntimeError("fullmap 缓存未包含 ETS 瓦片地址")
            if map_type == "promods" and not tile_url_promods:
                raise RuntimeError("fullmap 缓存未包含 ProMods 瓦片地址")

            data = {
                "server_name": server_name,
                "location_name": location_line,
                "player_name": player_name,
                "me_id": str(tmp_id),
                "players": area_players,
                "avatar": avatar_url or "",
                "location_line": location_line,
                "server_id": int(server_id or 0),
                "center_x": float(cx),
                "center_y": float(cy),
                "leaflet_css": LEAFLET_CSS_URL,
                "leaflet_js": LEAFLET_JS_URL,
                "tile_url_ets": tile_url_ets,
                "tile_url_promods": tile_url_promods,
            }
            options = {
                "type": "jpeg",
                "quality": 92,
                "full_page": True,
                "timeout": 8000,
                "animations": "disabled",
            }
            url = await self.render.render_html(LOCATE_MAP_TEMPLATE, data, options=options)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception:
            pass

        yield event.plain_result(
            f"玩家实时定位\n"
            f"玩家名称: {player_name}\n"
            f"TMP编号: {tmp_id}\n"
            f"服务器: {server_name}\n"
            f"位置: {location_line}"
        )

    # ====================================================================== #
    # 足迹
    # ====================================================================== #
    async def cmd_today_footprint(
        self,
        event,
        server: str | None = None,
        tmp_id: str | None = None,
    ) -> AsyncGenerator[Any, None]:
        message_str = (event.message_str or "").strip()
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        target_user_id = _extract_target_user_id(getattr(event, "message_obj", None))

        tokens = message_str.split()
        server_token = server
        input_id = tmp_id
        if len(tokens) > 1 and not server_token:
            for t in tokens[1:]:
                if t.isdigit():
                    input_id = t
                else:
                    server_token = t
        if not server_token:
            yield event.plain_result("用法: 足迹 [服务器简称] [ID]或 足迹 [服务器简称]，例如: 足迹 s1 123 或足迹 s1")
            return

        server_key = self.footprint.resolve_server(server_token)
        server_label = self.footprint.server_label(server_key)
        map_type = self.footprint.map_type(server_key)

        try:
            if input_id:
                tmp_id = await self.player.resolve_tmp_id(input_id)
            else:
                bind_user = target_user_id or user_id
                tmp_id = self.binding.get(str(bind_user))
        except SteamIdNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询")
            return
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        try:
            profile_data = await self.player.fetch_full_profile(str(tmp_id))
            info = profile_data["profile"]
            vtcm_stats = profile_data["vtcm"]
            online = profile_data["online"]
        except Exception as exc:
            yield event.plain_result(f"查询失败: {exc}")
            return

        player_name = info.get("name", "未知")
        last_online_raw = vtcm_stats.get("last_online") or info.get("lastOnline")
        last_online_formatted = format_timestamp_to_readable(last_online_raw) if last_online_raw else "未知"

        start, end, now_local = self.footprint.day_range()
        server_ids = self.footprint.candidate_server_ids(server_key, online or {})
        points, (range_start, range_end) = await self.footprint.fetch_history(
            str(tmp_id), server_ids, start, end
        )
        if points:
            points = self.footprint.filter_by_server(points, server_key, server_ids)
        if not points:
            points, (range_start, range_end) = await self.footprint.fetch_history_extended(
                str(tmp_id), server_ids, now_local, days=7
            )
            if points:
                points = self.footprint.filter_by_server(points, server_key, server_ids)

        if not points:
            yield event.plain_result("今日/输入的对应服务器暂无足迹数据")
            return

        normalized = self.footprint.normalize_history_points(points)
        distance_km: Optional[float] = self.footprint.to_km(
            vtcm_stats.get("daily_km") or 0
        )

        try:
            stats = vtcm_stats
            daily_km = stats.get("daily_km")
            if daily_km:
                distance_km = round(float(daily_km), 2)
        except Exception:
            pass

        tile_url_ets = DEFAULT_TILE_ETS
        tile_url_promods = DEFAULT_TILE_PROMODS
        fullmap_ets = self.fullmap.find_tile_url("ets")
        fullmap_promods = self.fullmap.find_tile_url("promods")
        if fullmap_ets:
            tile_url_ets = fullmap_ets
        if fullmap_promods:
            tile_url_promods = fullmap_promods

        data = {
            "player_name": player_name,
            "avatar": normalize_avatar_url(info.get("avatar")) or "",
            "points": normalized,
            "points_count": len(normalized),
            "distance_km": distance_km,
            "start_time": range_start,
            "end_time": range_end,
            "last_online": last_online_formatted,
            "map_type": map_type,
            "server_label": server_label,
            "tile_url_ets": tile_url_ets,
            "tile_url_promods": tile_url_promods,
            "leaflet_css": LEAFLET_CSS_URL,
            "leaflet_js": LEAFLET_JS_URL,
        }
        options = {
            "type": "jpeg",
            "quality": 92,
            "full_page": True,
            "timeout": 8000,
            "animations": "disabled",
        }
        url = await self.render.render_html(FOOTPRINT_MAP_TEMPLATE, data, options=options)
        if isinstance(url, str) and url:
            yield event.chain_result([Image.fromURL(url)])
            return

        msg = (
            "📍 足迹\n"
            f"玩家: {player_name} (ID:{tmp_id})\n"
            f"服务器: {server_label}\n"
            f"点位数: {len(normalized)}"
        )
        if distance_km is not None:
            msg += f" | 里程: {distance_km:.2f} km"
        msg += f"\n上次在线: {last_online_formatted}"
        yield event.plain_result(msg)

    # ====================================================================== #
    # 历史车队 / VTCM 命令（其他命令保留 main.py 旧逻辑，待 main.py 完整迁移后统一）
    # ====================================================================== #
    async def cmd_vtc_history(self, event) -> AsyncGenerator[Any, None]:
        message_str = event.message_str.strip()
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        target_user_id = _extract_target_user_id(getattr(event, "message_obj", None))
        match = re.search(r"历史车队\s*(\d+)?", message_str)
        input_id = match.group(1) if match else None

        try:
            if input_id:
                tmp_id = await self.player.resolve_tmp_id(input_id)
            else:
                bind_user = target_user_id or user_id
                tmp_id = self.binding.get(str(bind_user))
        except SteamIdNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询")
            return
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID，或者先绑定账号")
            return

        try:
            await self.player.fetch_profile(str(tmp_id))
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except Exception as exc:
            yield event.plain_result(f"查询失败: {exc}")
            return

        try:
            vtc_history = await self.player.fetch_vtc_history(str(tmp_id))
        except Exception:
            yield event.plain_result("查询历史车队失败，请稍后重试")
            return
        if vtc_history is None:
            yield event.plain_result("该用户的历史车队为私密状态")
            return
        if not vtc_history:
            yield event.plain_result("暂无历史车队记录")
            return

        lines: List[str] = []
        for idx, vtc_item in enumerate(vtc_history, 1):
            vtc_name = (
                vtc_item.get("vtcName") or vtc_item.get("name")
                or vtc_item.get("vtc_name") or "未知"
            )
            vtc_tag = (
                vtc_item.get("vtcTag") or vtc_item.get("tag")
                or vtc_item.get("vtc_tag", "")
            )
            join_date = (
                vtc_item.get("joinDate") or vtc_item.get("join_date")
                or vtc_item.get("joinedAt", "")
            )
            leave_date = (
                vtc_item.get("leaveDate") or vtc_item.get("leave_date")
                or vtc_item.get("leftAt", "")
            )
            role = (
                vtc_item.get("role") or vtc_item.get("position")
                or vtc_item.get("vtcRole", "")
            )
            entry = f"{idx}. {vtc_name}"
            if vtc_tag:
                entry += f" [{vtc_tag}]"
            if role:
                entry += f"\n   职位: {role}"
            if join_date:
                entry += f"\n   加入时间: {join_date}"
            if leave_date:
                entry += f"\n   离开时间: {leave_date}"
            lines.append(entry)
        message = "\n".join(lines)
        if len(vtc_history) > 10:
            message += f"\n\n... 共 {len(vtc_history)} 条记录，仅显示前10条"
        yield event.plain_result(message)

    # 占位：车队平台功能已删除
    async def cmd_event_list(self, event) -> AsyncGenerator[Any, None]:
        yield event.plain_result("车队平台功能已于 v2 中移除。")

    async def cmd_today_event(self, event) -> AsyncGenerator[Any, None]:
        yield event.plain_result("车队平台功能已于 v2 中移除。")

    async def cmd_member_info(self, event) -> AsyncGenerator[Any, None]:
        yield event.plain_result("车队平台功能已于 v2 中移除。")

    async def cmd_change_pwd(self, event) -> AsyncGenerator[Any, None]:
        yield event.plain_result("车队平台功能已于 v2 中移除。")

    async def cmd_member_manage(self, event) -> AsyncGenerator[Any, None]:
        yield event.plain_result("车队平台功能已于 v2 中移除。")

    # ====================================================================== #
    # 全局消息分发（兜底）
    # ====================================================================== #
    async def on_any_message(self, event) -> AsyncGenerator[Any, None]:
        """基于 ``_on_any_message_dispatch`` 兼容旧实现。"""
        async for r in self._on_any_message_dispatch(event):
            yield r

    async def _on_any_message_dispatch(self, event) -> AsyncGenerator[Any, None]:
        """原 main.py ``_on_any_message_dispatch`` 中保留（无空格）命令的兜底实现。

        v2 起车队平台（VTCM）活动 / 成员 / 改密码 等子命令已移除，仅保留常规业务命令。
        """
        msg = (getattr(event, "message_str", "") or "").strip()
        if not msg:
            return

        # 判定 @someone
        has_at = False
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            chain = getattr(message_obj, "message", None) or []
            for seg in chain:
                seg_type = getattr(seg, "type", None)
                if isinstance(seg, dict):
                    seg_type = seg.get("type") or seg_type
                if isinstance(seg_type, str) and seg_type.lower() == "at":
                    has_at = True
                    break
                if isinstance(seg, dict):
                    uid = seg.get("qq") or seg.get("user_id") or seg.get("id")
                else:
                    uid = (
                        getattr(seg, "qq", None)
                        or getattr(seg, "user_id", None)
                        or getattr(seg, "id", None)
                    )
                if uid:
                    has_at = True
                    break

        # 与 @filter.command 写法保持一致：直接 yield event.plain_result 等。
        async def pl(text: str):
            if hasattr(event, "plain_result"):
                yield event.plain_result(text)
            else:
                yield event.plain_result(text)

        # 绑定/解绑/查询/地图DLC 紧凑写法
        if re.match(r"^(查询|查)(\s*\d+)?\s*$", msg) or (re.match(r"^(查询|查)(\s|$)", msg) and has_at):
            async for r in self.cmd_query(event):
                yield r
            return
        if msg in ("地图dlc", "地图DLC"):
            async for r in self.cmd_dlc_list(event):
                yield r
            return
        if re.match(r"^绑定\s*\d+\s*$", msg):
            async for r in self.bind(event):
                yield r
            return
        if re.match(r"^解绑\s*$", msg):
            async for r in self.unbind(event):
                yield r
            return
        if re.match(r"^定位(\s*\d+)?\s*$", msg) or (msg.startswith("定位") and has_at):
            async for r in self.cmd_locate(event):
                yield r
            return
        if re.match(r"^总里程排行\s*$", msg):
            async for r in self.cmd_rank_total(event):
                yield r
            return
        if re.match(r"^今日里程排行\s*$", msg):
            async for r in self.cmd_rank_today(event):
                yield r
            return
        if re.match(r"^足迹(\s+\S+)?(\s+\d+)?\s*$", msg) or (msg.startswith("足迹") and has_at):
            async for r in self.cmd_today_footprint(event):
                yield r
            return
        if re.match(r"^服务器\s*$", msg):
            async for r in self.cmd_servers(event):
                yield r
            return
        if re.match(r"^路况(\s+\S+)?\s*$", msg):
            async for r in self.cmd_traffic(event):
                yield r
            return
        if re.match(r"^插件版本\s*$", msg):
            async for r in self.cmd_plugin_version(event):
                yield r
            return
        if re.match(r"^菜单\s*$", msg):
            async for r in self.cmd_help(event):
                yield r
            return
        if re.match(r"^历史车队(\s*\d+)?\s*$", msg) or (msg.startswith("历史车队") and has_at):
            async for r in self.cmd_vtc_history(event):
                yield r
            return
        # 活动 / 今日活动 / 信息 / 修改密码 / 成员管理 等 VTCM 车队平台子命令
        # 已于 v2 中移除，命中到此处即静默忽略。


__all__ = ["CommandRegistry", "TmpCommandContext"]
