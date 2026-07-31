# astrbot_plugin_tmp_bot

欧洲卡车模拟 2 / 美国卡车模拟 **TruckersMP(TMP) 查询机器人** AstrBot 插件（重构版）。

> 本仓库遵循 [AstrBot 官方插件开发指南](https://docs.astrbot.app/dev/star/plugin-new.html) 重新组织代码结构，
> 拆分为 `core/api`、`core/services`、`core/commands`、`core/utils`、`core/render` 五层。

## ✨ 功能特性

- 玩家基本信息 / 封禁记录 / 历史车队
- 实时位置、服务器实时路况
- 总里程 / 今日里程排行榜
- 地图 DLC 列表
- 百度翻译（国家、城市、交通地点）
- TMP ID 绑定（QQ/平台用户 -> TMP ID）

> **注意**：v2 起已**移除**车队平台（VTCM）的成员管理 / 活动 / 加减积分等专属功能。
> `VtcmClient` 现仅承担里程、DLC、足迹、历史车队、官方服务器、插件版本等公开数据接口。
>
> **VTCM 官方已不再提供公开数据接口**（`da.vtcm.link` 不再可用）。里程 / DLC /
> 足迹 / 历史车队 等功能的数据源需要用户**自行部署**以下任一开源项目：
>
> - <https://github.com/Srlily/TMP-API>
> - <https://github.com/79887143/evm-data-api>
>
> 部署完成后，把域名 / 反代地址填到 WebUI 插件配置中的 `vtcm_base_url` 即可启用。
> 默认留空，相关命令会提示「未配置数据源」并指向部署项目地址。

## 🧱 目录结构

```text
astrbot_plugin_tmp_bot/
├── metadata.yaml           # AstrBot 插件元数据（官方 schema）
├── _conf_schema.json       # AstrBot WebUI 配置 schema
├── requirements.txt        # 第三方依赖
├── main.py                 # 插件入口（@register / @filter.command）
├── core/
│   ├── utils/              # 工具：常量 / 时间 / 文本
│   ├── api/                # 外部 API 客户端（TMP / Trucky / VtcmClient / Baidu Translate / ETS2Map）
│   ├── services/           # 业务服务
│   ├── commands/           # AstrBot 命令注册与消息分发
│   └── render/             # HtmlRenderService + 共享 HTML 模板
├── TruckersMP-citties-name # 英文/中文对照表（markdown）
└── resources/template/leaflet # Leaflet 静态资源
```

## 🛠 安装

1. 将整个 `astrbot_plugin_tmp_bot/` 目录拷贝至 AstrBot 的 `data/plugins/`。
2. 在 AstrBot WebUI 中点击「重载插件」或重启 AstrBot。
3. 在 WebUI 插件配置中按需填写：
   - `baidu_translate_app_id` / `baidu_translate_key`：百度翻译凭据。
   - `api_timeout_seconds`：HTTP 超时（秒）。
   - `vtcm_base_url`：**留空则禁用所有依赖 VTCM 数据源的功能**（总里程排行 / 今日里程排行 / DLC列表 / 足迹 / 历史车队 / 玩家扩展信息）。如需启用，请自行部署 [Srlily/TMP-API](https://github.com/Srlily/TMP-API) 或 [79887143/evm-data-api](https://github.com/79887143/evm-data-api) 后填入其域名或反代地址（末尾斜杠可省略）。服务器列表 / 插件版本等命令不受影响（直接对接 `api.truckersmp.com`）。
   - `vtcm_open_url`：预留配置项，留空即可。

## 🧾 命令一览

| 命令               | 说明                          |
|--------------------|-------------------------------|
| `绑定 <TMP ID>`    | 绑定 TMP ID                   |
| `解绑`             | 解除 TMP ID 绑定              |
| `查询 [TMP ID]`    | 玩家信息查询                  |
| `查 [TMP ID]`      | `查询` 的简写                 |
| `定位 [TMP ID]`    | 玩家位置查询并渲染底图        |
| `路况 [s1|s2|p|a]` | 服务器热门地点实时路况        |
| `服务器`           | 官方服务器实时状态            |
| `总里程排行`       | 总里程排行榜                  |
| `今日里程排行`     | 今日里程排行榜                |
| `足迹`             | 个人当日轨迹                  |
| `历史车队`         | 玩家历史车队列表              |
| `DLC列表` / `地图DLC` | 列出 DLC                   |
| `插件版本` / `菜单` / `帮助` | 元信息               |

> 重要：所有绑定数据（AstrBot 用户 -> TMP ID）会写入 AstrBot data 目录，
> 即 `StarTools.get_data_dir("astrbot_plugin_tmp_bot")/tmp_bindings.json`，
> 插件更新或重装时不会被覆盖（符合官方"持久化数据请存储于 data 目录下"原则）。

## 🧪 开发

```bash
pip install -r requirements.txt
```

## 📝 License

MIT
