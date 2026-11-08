# 可移植性审计（v0.2.1）

## 路径优先级

所有包内路径统一为：**配置 > 环境变量 > 默认 plugin_data**。

| 用途 | 配置键 | 环境变量 | 默认 |
|---|---|---|---|
| 状态目录 | `data_dir` | `COMPANION_DATA_DIR` | `StarTools.get_data_dir("astrbot_plugin_companion")` |
| 缓存/日志/配置 | `runtime_dir` | `COMPANION_RUNTIME_DIR` | plugin_data |
| external 状态 | `external_data_dir` | `COMPANION_EXTERNAL_DATA_DIR` | 无 → 回退 plugin 模式 |

相对路径相对于 plugin_data 解析。`engine/*` 不自己猜路径，全部通过 `Store(data_dir)`；唯一解析点在 `main.py` / `engine/paths.py`。

## 改了哪些文件

| 文件 | 改了什么 |
|---|---|
| `main.py` | 新增 `data_dir` / `runtime_dir` / `external_data_dir` 解析；统一走 `resolve_path`；外部模式不再用相对路径猜 |
| `engine/paths.py` | 新增，`resolve_path` / `resolve_data_dir` / `resolve_runtime_dir` / `resolve_external_dir` |
| `engine/__init__.py` | 导出 path helpers |
| `panel/server.py` | 支持 `--runtime-dir` / `--profile`；`--data-dir` / `--runtime-dir` / `--profile` 支持对应环境变量；external 缓存/日志不写外部 data |
| `_conf_schema.json` | 新增 `data_dir` / `runtime_dir`；`external_data_dir` 说明环境变量；聊天/主人配置齐全 |
| `README.md` | 新增路径优先级、A/B 模式、聊天/记忆配置；删掉盘符示例 |
| `tests/test_paths.py` | 新增配置 > 环境 > 默认、相对路径测试 |
| `sim/sim_her.py` / `tests/test_sim.py` | 便携隔离模拟纳入包（示例地点 + 临时目录，无盘符） |
| `metadata.yaml` | 版本 0.2.1，描述聊天/记忆桥 |
| `engine/chat.py` / `memory.py` / `growth.py` | B：聊天 → 状态/心情/今天她/情绪；v3 记忆；第一次成长（上一轮新增，本轮无路径） |

## 还剩几处

| 位置 | 剩余 | 说明 |
|---|---:|---|
| 盘符路径（任意 Windows 盘符） | **0** | 源码、配置、README、tests 全量扫描 |
| 硬编码绝对路径（`/home`、`/mnt`、`/Users` 等） | **0** | 同上 |
| `main.py` 默认 plugin_data | 1 | `StarTools.get_data_dir(...)`，这是“默认”而非硬编码路径 |
| `panel/server.py` 默认 `ROOT/data` | 1 | 仅独立运行面板时的兜底；插件运行总是传 `--data-dir` |
| `demo.py` 默认 `ROOT/demo_data` | 1 | 仅本地 demo 脚本；可用 `COMPANION_DATA_DIR` 覆盖 |

结论：**盘符 0 处、绝对路径 0 处**；剩下 3 处都是有意的相对默认值，且前两处可被配置/环境变量覆盖。

## 复现

```bash
python -m unittest discover -s tests -v     # 17/17
python panel/server.py --data-dir <状态目录> --runtime-dir <运行时目录> --profile <profile.json>
```

external 模式（A）只读外部状态；缓存/日志/配置写 `runtime_dir`，不写外部状态。
