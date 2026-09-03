# 俄罗斯方块（Tetris）高层设计文档（HLDD）

- 版本：v1.0
- 日期：2026-09-03
- 关联文档：`PRD.md`
- 本设计文档基于现有代码实现归纳：`tetris.py`（Python/pygame）与 `tetris.cpp`（C++/Win32 GDI）。
- 两者共享同一套游戏逻辑模型，仅在「输入/渲染/主循环」适配层不同。下文先给出统一架构，再分别说明两个版本的平台适配。

---

## 1. 架构总览

采用「单进程、单窗口、逻辑与渲染分离」的分层结构。游戏逻辑（Model）完全独立于平台，输入适配与渲染适配分别对接逻辑层。

```
┌──────────────────────────────────────────────────────────┐
│                    应用入口 / 主循环                       │
│   Python: run() @ pygame   /   C++: WinMain + getmsg 循环  │
└───────────────┬──────────────────────────┬────────────────┘
                │ 事件                       │ 每帧/每次绘制
                ▼                           ▼
┌───────────────────────┐      ┌───────────────────────────────┐
│      输入适配层         │      │        渲染适配层               │
│  handle_input /        │      │  draw_* / render             │
│  on_key_down /         │      │  draw_cell / draw_preview /   │
│  WM_KEYDOWN / 鼠标按钮  │      │  draw_info / draw_game_over   │
└───────────────┬────────┘      └───────────────┬──────────────┘
                │ 修改状态                       │ 读取状态
                ▼                               ▼
┌────────────────────────────────────────────────────────────┐
│                游戏逻辑层（Tetris / Tetromino）              │
│  状态：board / score / level / lines / piece / game_over    │
│  流程：new_piece → update → valid_move → lock_piece →        │
│        clear_lines → get_ghost_y                            │
│  AI：simulate → evaluate → get_best_move → execute          │
└────────────────────────────────────────────────────────────┘
```

**关键设计原则：**
- **逻辑与平台解耦**：核心落子、消行、计分、AI 评估全部不依赖具体平台库，可两版共享逻辑心智模型。
- **统一坐标系**：棋盘用 `board[rows][cols]`，方块位置用左上角格坐标 `(x, y)`，列宽 10、行高 20。
- **驱动机制差异**：Python 用「帧累积计时（dt）」驱动下落；C++ 用 Windows 定时器（`WM_TIMER`）驱动。两者在逻辑层收敛为同一套 API。

---

## 2. 模块设计

### 2.1 数据/常量定义（全局）

| 常量 | 值 | 说明 |
| --- | --- | --- |
| `COLS` / `ROWS` | 10 / 20 | 棋盘列、行 |
| `CELL_SIZE` | 40 | 主格子像素 |
| `PREVIEW_CELL_SIZE` | 25 | 预览格子像素 |
| `PLAY_WIDTH/HEIGHT` | 400 / 800 | 游戏区 |
| `SIDE_PANEL` | 240 | 侧边栏宽 |
| `WINDOW_WIDTH/HEIGHT` | 640 / 800 | 窗口 |

### 2.2 形状与颜色

- `SHAPES[]`：7 个二维 0/1 矩阵，顺序固定为 **I、O、T、S、Z、J、L**。
- `SHAPE_COLORS[]`：与 `SHAPES` 一一对应的 RGB/COLORREF 颜色。
- `board` 中落定单元格的值 = `shape_idx + 1`，据此反查颜色。

### 2.3 Tetromino（方块对象）

属性：`shape_idx`、`shape`（当前形状，可与初始不同）、`color`、`x`、`y`。

行为：
- 构造：`x = COLS/2 - width/2`，`y = 0`（顶部居中）。
- `rotate()` / `get_rotated()`：顺时针旋转 90°。Python 用 `zip(*shape[::-1])` + 行反转；C++ 用 `result[c][rows-1-r] = s[r][c]`。

### 2.4 Tetris（游戏主对象）

集中管理状态、输入、逻辑、AI 与渲染。核心成员：

| 成员 | 说明 |
| --- | --- |
| `board` | `ROWS × COLS` 二维数组，`0`=空，`>0`=已固定方块（值=shape_idx+1） |
| `score / level / lines_cleared` | 分数、等级、累计消行数 |
| `fall_speed / fall_time` | 当前下落间隔（ms）；累计帧计时（Python 用） |
| `current_piece / next_piece` | 当前与下一方块 |
| `game_over / paused` | 结束 / 暂停标志 |
| `auto_play` 及 `ai_*` 系列 | AI 托管开关与执行状态 |

提供的方法面向以下四类职责，见 **[3. 核心流程](#3-核心流程与算法)** 与 **[4. AI 子系统](#4-ai-子系统高层设计)**。

---

## 3. 核心流程与算法

### 3.1 初始化 / 重置（reset_game）
清空棋盘、归零分数/等级/消行数、重置下落速度与 AI 状态，`current_piece`、`next_piece` 各随机生成一个。

### 3.2 碰撞检测（valid_move）
对目标位置 `(x, y)` 和形状（可为旋转后的覆盖形状）逐格判断：
- 越界（左右越界、底部越界）→ 无效；
- 与已占用格重叠（`board[y][x] != 0` 且 `y >= 0`）→ 无效。
- 允许 `y < 0` 的部分处于棋盘上方（尚未进入但合法）。

### 3.3 下落 / 移动 / 旋转（手动输入）
- 左右移/软降：仅当 `valid_move` 通过才更新坐标；软降每次 `+1` 分。
- 旋转：SRS 简易墙踢，依次尝试偏移 `{0, -1, +1}`（C++ AI 侧另有 `{0,-1,1,-2,2}`）。
- 硬降（hard drop）：循环下移到最底，然后锁定。

### 3.4 自然下落（update，仅 Python，非托管）
- `fall_time += dt`；当 `fall_time >= fall_speed` 时触发一次下落。
- 可下移则 `y++`，否则 `lock_piece()`。

> C++ 版等价逻辑由 `TIMER_FALL` 定时器回调 `on_timer_fall()` 承担。

### 3.5 锁定（lock_piece）
1. 将 `current_piece` 各格写入 `board`（`value = shape_idx + 1`）。
2. 调 `clear_lines()` 消除满行并结算。
3. `current_piece = next_piece`；`next_piece = 新生成`。
4. 游戏结束判定：新方块在其生成位置无法 `valid_move` → `game_over = true`（C++ 版同时 `stop_timers()`）。

### 3.6 消行（clear_lines）
1. 扫描所有行，收集满行。
2. 从 `board` 中删除满行，顶部 `insert` 空行补齐。
3. 计分 `score += {1:100, 2:300, 3:500, 4:800}[n] × level`。
4. `level = lines_cleared / 10 + 1`。
5. `fall_speed = max(200, 1000 - (level-1)×80)`。

### 3.7 影子位置（get_ghost_y）
从当前 `y` 开始反复下探直到不可下移，返回落点行号。

### 3.8 渲染装配（draw / render）
顺序：背景 → 游戏区边框 → **board**（已固定）→ **网格** → **影子** → **当前方块** → 侧边栏（预览、信息、按钮）→ 状态遮罩（game_over / paused）→ `flip`/`Present`。

绘制细节：
- `draw_cell` 用主色块 + 高光（左上亮 60）+ 阴影（右下暗 60）实现 3D 立体格子。
- 影子：浅绿色空心矩形边框。
- 墙踢旋转用 `draw_piece` 绘制当前方块。

---

## 4. AI 子系统高层设计

### 4.1 总体流程

```
锁定完成 ──► ai_plan_move(): 计算 best_move
             │ 目标 =（target_x, target_y, rotations）
             ▼
      ai_execute_step() 每 50ms 一步：
         ① rotation 阶段：旋转到目标姿态（带墙踢，失败则重规划）
         ② move 阶段：水平逐步移动到 target_x
         ③ 对齐完成 → ai_falling = true
             ▼
      ai_fall_step(): 垂直速降到 target_y，锁盘
```

- Python 版由主循环按帧调用（`ai_step_timer` ≥ 50ms 触发一步）。
- C++ 版由 `TIMER_AI_STEP`（50ms）定时器驱动 `on_timer_ai_step()`。

### 4.2 落点规划（get_best_move）
1. 依据方块类型决定需遍历的旋转态数量：
   - O（idx=1）：1；I/S/Z（idx=0/3/4）：2；T/J/L：4。
2. 对每个旋转态，遍历全部合法水平位置（按离列中心由近到远排序，避免偏向一侧）。
3. 对每个 `x`，模拟硬降到底得到 `y`，调用 `evaluate_candidate` 得落地高度与消行贡献。
4. 对消行后的新棋盘调用 `evaluate_board` 得综合分。
5. 选**评分最优**；评分相同选**步数最少**（`rotations + |dx|`）。

### 4.3 候选评估（evaluate_candidate）
- `landing_height = ROWS - (y + shape_h/2)`。
- `eroded_cells = 消行数(cleared_lines) × 本方块参与消行的格子数(eroded)`。
- 输出消行折叠后的 `new_board`（满行删除，顶部补空行）。

### 4.4 启发式打分（evaluate_board）

| 特征 | 计算方式 |
| --- | --- |
| holes | 每列自上而下，已见方块后的空位计数加总 |
| row_transitions | 每行内 0↔1 切换计数，含左右边界外视为 1 的段 |
| col_transitions | 每列内 0↔1 切换计数，含上下边界外视为 1 的段 |
| well_sums | 每列：左右邻均被堵的连续空位深度 `depth`，按 `depth(depth+1)/2` 累加 |

评分：`weighted = -4.5·LH + 3.4·EC + -3.2·RT + -3.2·CT + -7.9·H + -1.2·WS`，函数返回 `-weighted`，调用方取最小值（即加权最大）。

### 4.5 AI 执行细节
- **旋转墙踢**：偏移序列 `{0, -1, 1, -2, 2}`（C++）逐项尝试，全失败则 `re-plan`。
- **状态机**：`ai_target_x` 为 `None`/负数时先规划；`ai_falling` 进入速降，否则执行旋转/移动步。
- **暂停/结束**：AI 与自然下落同样受 `game_over`/`paused` 门控暂停；结束即停止，切回手动时重开下落计时。

---

## 5. 平台适配设计

### 5.1 Python / pygame 版（tetris.py）

**驱动模型：**
- 单文件约 1000 行；入口 `if __name__ == "__main__"` 创建 `Tetris` 并 `run()`。
- 主循环 `run()`：`clock.tick(60)` 得 `dt` → 遍历事件 → `handle_input(event)` → `update(dt)` → `draw()`。
- 事件：`pygame.KEYDOWN`（方向键/空格/P/R）、`pygame.MOUSEBUTTONDOWN`（托管按钮命中检测）、`pygame.QUIT`。

**组件：**
- `get_font(size)`：按优先级探测系统中文字体（微软雅黑/宋体/黑体），缺失则回退 `pygame.font.Font(None, size)`。
- 渲染全部基于 `pygame.draw` 与 `pygame.Surface`，每帧 `display.flip()`。
- 状态遮罩通过半透明 `Surface(alpha)` 叠加实现。

**内存/生命周期：** 仅有 Python 对象，无手动资源释放需求。

### 5.2 C++ / Win32 版（tetris.cpp）

**驱动模型：**
- 单文件，依赖 `windows.h` + 标准库；入口 `WinMain`。
- `WndProc` 消息循环：`WM_CREATE` 启动下落定时器、`WM_TIMER` 分流下落/AI 计时、`WM_KEYDOWN` 转 `on_key_down`、`WM_LBUTTONDOWN` 命中托管按钮、`WM_PAINT` 触发 `render(hdc)`、`WM_DESTROY` 停表并退出消息循环。
- 定时器：`TIMER_FALL`（间隔=fall_speed）与 `TIMER_AI_STEP`（50ms）用 `SetTimer/KillTimer` 管理。

**组件：**
- 资源管理：画刷 `CreateSolidBrush`、画笔 `CreatePen`、字体 `CreateFontW` 均在使用后 `DeleteObject`，`SelectObject` 复原旧对象。
- 中文显示：`MultiByteToWideChar(CP_UTF8,...)` 将 UTF-8 转 UTF-16 后 `DrawTextW`，字体锁定「Microsoft YaHei」。
- 半透明遮罩因 GDI 限制简化为：纯黑填充 + 文字（`draw_game_over`/`draw_pause`），与 Python 版视觉略有差异（可接受）。

**生命周期：** `current_piece`/`next_piece` 由 `new` 分配、重置与切换时 `delete` 管理，析构函数兜底释放。

---

## 6. 关键数据结构

```
board: list/vector<vector<int>> [ROWS][COLS]   // 0=空, k=shape_idx+1

Tetromino: { int shape_idx; matrix shape; color color; int x, y; }

AI 状态: { bool auto_play;
           int ai_target_x, ai_target_y, ai_target_rotations;
           bool ai_falling; int ai_step_timer / ai_fall_timer; }
```

---

## 7. 设计权衡与说明

| 决策 | 权衡 |
| --- | --- |
| 手动旋转采用简易墙踢（非完整 SRS） | 实现简单、够用；不做踢墙表带来的复杂角点逻辑 |
| AI 用「硬降到底」枚举候选 | 时间与代码量小，且在硬降规则下等价于完整搜索；未做面板裁剪等优化 |
| Python 用帧计时、C++ 用定时器 | 各平台自然实现；共享同一个逻辑层，行为一致 |
| AI 评估在 Python/C++ 间逻辑一致 | 权重与特征完全相同，保证双版本 AI 行为一致 |
| C++ 遮罩非半透明 | GDI 半透明成本高，取舍为纯色+文字覆盖 |

---

## 8. 已知实现差异

- 手动旋转墙踢：Python `{0,-1,+1}`；AI 旋转（C++）`{0,-1,1,-2,2}`（Python 版 AI 旋转未使用墙踢数组，直接尝试原坐标，进入 `ai_plan_move` 除外）。
- Python 版 `draw_piece` 保留 `alpha` 参数但实际未使用。
- AI 旋转墙踢逻辑存在版本差异：Python `ai_execute_step` 使用 `kicks` 数组（`{0,-1,1,-2,2}`），C++ 亦相同；手动旋转偏移两版一致为 `{0,-1,+1}`。