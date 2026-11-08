# 予其真实 · AstrBot 插件

**v0.2.2** · 2026-11-08

一个独立的「予其真实」面板，加上一套轻量的状态引擎。装进 AstrBot 后：

- 右上角「记忆」看 3D 星图；
- 「此刻 / 情绪 / 今天她 / 成长」四块实时状态；
- 「命令」抽屉发 7 个白名单指令：睡觉 / 起床 / 吃饭 / 出门 / 喝水 / 夸她 / 安静；
- 记忆详情立即展开，显示 `#id`；支持上一条/下一条、方向键、悬停提示、小星图选中高亮；
- 心跳每分钟推进作息、消费命令；
- **主人私聊**会更新她的活动、心情、今天她、情绪和记忆（可关）；
- 面板是独立进程，崩了不影响 bot。

![面板示例](docs/demo_main.png)

![记忆星图示例](docs/demo_memory.png)

![主人私聊后的面板（B）](docs/demo_chat.png)

> 这是可安装的**通用版**，不是把某一位的私人记忆、人格和聊天记录直接打包。示例数据是虚构的；聊天写入也只存在你自己的插件数据目录。

> 发布前把 `metadata.yaml` 里的 `repo` 改成你的仓库地址。

---

## 安装

1. 把整个 `astrbot_plugin_companion/` 放进：

```
AstrBot/data/plugins/astrbot_plugin_companion/
```

2. 重启 AstrBot（或在插件管理里重载）。
3. 在 AstrBot 的插件配置里改端口、名字；默认：
   - 面板：`http://127.0.0.1:8765`
   - 心跳：60 秒
   - 示例数据：开
4. 也可以对 bot 发 `/面板`（仅管理员）拿地址。

插件数据在：

```
AstrBot/data/plugin_data/astrbot_plugin_companion/
```

卸载/重置：停 bot，删掉这个数据目录即可。**不要**删 AstrBot 的 `data/` 或记忆库。

---

## 配置

| 键 | 默认 | 说明 |
|---|---|---|
| `enabled` | `true` | 启用面板与心跳 |
| `demo_mode` | `true` | 首次启动写示例数据；关掉则空白状态 |
| `port` | `8765` | 只监听 `127.0.0.1`；被占用会自动往后找 |
| `her_name` | `她` | 面板上的名字 |
| `owner_name` | `你` | 主人称呼 |
| `title` | `予其真实` | 面板标题 |
| `heartbeat_seconds` | `60` | 推进作息 / 消费命令的间隔 |
| `data_dir` | `""` | 状态目录；留空用 plugin_data，或环境变量 `COMPANION_DATA_DIR` |
| `runtime_dir` | `""` | 缓存/日志/配置目录；留空用 plugin_data，或 `COMPANION_RUNTIME_DIR` |
| `source_mode` | `plugin` | `plugin` = 插件自带引擎（B）；`external` = 读外部状态目录（A） |
| `external_data_dir` | `""` | external 模式的状态目录；或环境变量 `COMPANION_EXTERNAL_DATA_DIR` |
| `owner_ids` | `""` | 主人 ID，逗号分隔；留空用管理员判断 |
| `chat_events` | `true` | 接 AstrBot 消息事件，主人消息更新状态 |
| `chat_owner_only` | `true` | 只处理主人消息 |
| `chat_private_only` | `true` | 只处理私聊 |
| `chat_memory` | `true` | 主人消息写进记忆导出（本地） |
| `chat_memory_interval` | `120` | 两条聊天记忆的最小间隔（秒） |
| `chat_growth` | `true` | 消息含「第一次」时写成长里程碑 |
| `memory_enabled` | `true` | 显示记忆页 |
| `sim_enabled` | `true` | 模拟页；插件已自带 `sim/sim_her.py`，只跑示例数据 |

### 模拟页（可选）

默认开启模拟页；需要隐藏时把 `sim_enabled` 设为 false。面板会显示三个安全场景：

- `full`：插件引擎自检
- `weather_matrix`：5 档天气 × 身体
- `outing_day`：示例商场 / 示例公园一日
- `custom_outing`：自定义地点/地址/路线/天气/场景

只使用插件示例数据和临时目录，不读生产 `data/`，不含成人场景。

#### 自定义出门

| 字段 | 默认 | 说明 |
|---|---|---|
| `place_name` | 自定义商场 | 显示地点名 |
| `address` | 自定义路9号 | 显示地址；不做真实地理编码 |
| `district` | 示例区 | 区/县 |
| `station` | 自定义站 | 地铁站名 |
| `line` | 9号线 | 线路名 |
| `location` | `121.400000,31.200000` | 经纬度，格式 `lng,lat` |
| `route_minutes` | 18 | 1–45；手动填，不调地图 |
| `fare` | 3 | 0–100；手动填 |
| `weather_text` | 多云 | 任意展示文本 |
| `scene_name` | 中庭 | 任意场景名 |
| `mood / pain / energy` | .75 / .1 / .7 | 0–1 |
| `seed` | 42 | 可复现随机 |

示例：打开 `http://127.0.0.1:8765/?view=sim&scenario=custom_outing`，填写后点“开始模拟”。

> 地址、路线、票价都是**模拟输入**，不会请求高德/地图，也不会读写生产 `data/`。

一条命令跑同一个场景：

```powershell
python demo_custom.py
```

实际输出：[docs/demo_sim_custom.txt](docs/demo_sim_custom.txt)

---

## 两种模式

### plugin（默认，B）

插件自己在 `plugin_data/astrbot_plugin_companion` 里维护状态：

- 心跳推进作息、消费命令；
- 主人私聊（默认只私聊、只主人）更新活动/心情/今天她/情绪；
- 同一条消息按间隔写一条 v3 记忆；含「第一次」时写成长；
- 不需要 livingmemory，不直连任何记忆库。

### 路径解析

所有路径统一按：

```
配置 > 环境变量 > 默认 plugin_data
```

- 状态：`data_dir` > `COMPANION_DATA_DIR` > `StarTools.get_data_dir("astrbot_plugin_companion")`
- 缓存/日志/配置：`runtime_dir` > `COMPANION_RUNTIME_DIR` > plugin_data
- external：`external_data_dir` > `COMPANION_EXTERNAL_DATA_DIR` > 无（无效则回退 plugin 模式）
- 相对路径相对于 plugin_data 解析；包里没有盘符或绝对路径。

### external（A：接你已有的 bot）

```json
{
  "source_mode": "external",
  "external_data_dir": "<你的 bot 数据目录>"
}
```

- 面板只读外部状态（`rhythm/state.json`、`mood.json`、`now.json`、`her_life.json`、`exports/memory_export.json` 等）；
- 不启动插件心跳、不写外部状态，避免双写；
- 命令仍写到外部 `ui_commands/`，由你现有 bot 的心跳消费；
- 面板缓存/日志/配置放在插件自己的 `plugin_data`，不污染外部 `data/`。

---

## 命令

面板「命令」只写：

```
data/ui_commands/<id>.json   {"id":"panel-...","cmd":"praise","at":1794...}
```

心跳读取后执行，移到 `data/ui_commands/done/<id>.json`，带 `status` / `handled_at`。

白名单：

`sleep / wake / eat / water / out / praise / quiet`

- `sleep` 480 分钟；`wake` 30 分钟；`eat` 40 分钟；`out` 90 分钟；`quiet` 15 分钟；
- `water` 心情 +0.02；`praise` 心情 +0.05；
- 10 分钟内有效；未知 / 过期丢弃；不重试。

---

## 数据契约（可选接入）

状态都在插件数据目录，面板只读：

```
rhythm/state.json       活动：activity{id,label,started,expected_end}, history[]
rhythm/body.json        phase/day/period/energy/pain/libido
mood.json               value, baseline, ts
now.json                place, room
wardrobe.json           current{occasion,outer,inner,accessories}
reality.json            weather{text}
emotion/emotion.json    e{name:{i,t,cause,n}}
emotion/shadow.jsonl    24h 事件：ts,kind,cause,i,e{}
growth/growth.db        milestones(ts,text,key,kind,source,created,status)
her_life.json           date, events[], discovery
exports/memory_export.json
```

记忆导出按面板的 v3 格式：

```json
{
  "version": 3,
  "generated_at": "2026-01-01T12:00:00+08:00",
  "items": [
    {
      "id": 1,
      "text": "……",
      "kind": "事件",
      "tags": ["日常"],
      "created_at": "2026-01-01T12:05:00+08:00",
      "event_at": "2026-01-01T11:58:00+08:00",
      "event_date": "2026-01-01",
      "event_precision": "datetime",
      "refs": {
        "source_time_start": "2026-01-01T11:58:00+08:00",
        "source_time_end": "2026-01-01T11:58:00+08:00",
        "pinned": false
      }
    }
  ],
  "stats": {"total": 1}
}
```

面板优先用 `refs.source_time_end` 作为「对话时间」，详情同时显示「对话 / 记于」；`event_at` 仅在 ±1 天内作「标注」。这样不会把批量写入时间当成发生时间。

---

## 聊天 → 状态 / 记忆（B）

插件默认监听 AstrBot 消息事件（`chat_events`），只处理**主人私聊**：

- 活动切到「陪你聊天」10 分钟；
- 心情按关键词轻微变化；
- `her_life.json` 加一条「和你说了一会儿话」；
- `emotion/shadow.jsonl` 加一个对话事件；
- 每 `chat_memory_interval` 秒最多写一条 v3 记忆（`你说：…`，截断 160 字）；
- 消息含「第一次」时写一条成长里程碑。

不调用 LLM、不读群聊、不直连 `livingmemory.db`。记忆文本只存在自己的 `plugin_data`；面板上镜模式会遮。

要接自己的记忆库：按上面 v3 契约写 `exports/memory_export.json` 即可；要接自己的状态引擎：按契约写 `rhythm/state.json` / `mood.json` / `now.json` / `her_life.json`，或直接用 external 模式。

---

## 目录

```
main.py                 AstrBot 插件入口（面板 + 心跳 + 聊天 hook）
panel/server.py         只读面板 HTTP 服务
panel/static/           前端（无依赖、无 CDN）
engine/seed.py          示例/空白数据
engine/tick.py          时间推进
engine/commands.py      命令消费
engine/chat.py          聊天 -> 状态/记忆
engine/memory.py        v3 记忆导出适配器
engine/growth.py        「第一次」里程碑
engine/store.py         原子读写
sim/sim_her.py          便携隔离模拟（示例地点 + 临时目录）
tests/                  无依赖测试
```

---

## 验证

- AstrBot **4.29.3** 真实 `astrbot.api` 加载 `CompanionPlugin`：面板返回 200、名字生效、`terminate` 干净（临时数据目录）。
- 真实 API 下跑聊天 hook：主人私聊 → 活动「陪你聊天」、记忆 30 → 31、面板同步。
- 真实 API 下跑 external 模式：面板读外部状态、插件心跳为空、外部状态无新增写入。
- `python -m unittest discover -s tests -v`：**17/17 PASS**。
- 包内不包含本机盘符路径、私人名字或真实记忆；示例数据是虚构的。
- 路径审计：[docs/PORTABILITY.md](docs/PORTABILITY.md)（盘符 0、绝对路径 0）。

---

## 开发

```powershell
# 生成示例数据并跑面板
python -c "from engine.seed import seed; seed('demo_data', demo=True)"
python panel\server.py --data-dir demo_data --port 8780

# 或一键 demo
python demo.py

# 测试
python -m unittest discover -s tests -v
```

面板进程只读状态，只写 `ui_commands/` 和面板缓存；插件引擎负责状态。默认只监听 `127.0.0.1`，没有登录，**不要**把它暴露到公网。

---

## 边界

- Windows / Linux 都可以跑；插件用 `sys.executable` 起面板，Windows 下隐藏控制台。
- 模拟页默认开启；插件自带 `sim/sim_her.py`，只使用示例地点和临时目录，不读生产 `data/`。需要隐藏时把 `sim_enabled` 设为 false。
- 记忆页的编辑/删除默认关闭（没有记忆库消费者），只读展示。
- 聊天 hook 默认只主人私聊；群聊、非管理员不写状态/记忆。
- external 模式不启动插件心跳、不写外部状态；只写外部命令队列。
- 没有把私人数据、人格、聊天记录放进仓库；示例数据可删。

## License

MIT
