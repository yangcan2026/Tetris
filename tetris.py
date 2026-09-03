"""
俄罗斯方块（Tetris）游戏 —— 完整实现
======================================
功能特性：
- 7 种标准俄罗斯方块（I, O, T, S, Z, J, L）
- 键盘控制：方向键移动/旋转、空格硬降、P 暂停、R 重新开始
- 影子预览（绿色空心边框显示落点位置）
- 下一个方块预览
- 计分与等级系统（等级越高下落越快）
- AI 自动托管模式（点击右侧按钮切换）
- 游戏结束判定：新方块生成时与已堆叠方块重叠则结束
"""

import pygame
import random
import sys
import os

# ============================================================
# 初始化 Pygame
# ============================================================
pygame.init()


def get_font(size):
    """
    尝试加载中文字体，找不到则用默认字体。
    按优先级依次尝试系统已安装的字体文件，
    避免因字体缺失导致中文无法显示。
    """
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",    # 微软雅黑
        r"C:\Windows\Fonts\msyhbd.ttc",   # 微软雅黑加粗
        r"C:\Windows\Fonts\simsun.ttc",   # 宋体
        r"C:\Windows\Fonts\simhei.ttf",   # 黑体
        r"C:\Windows\Fonts\yahei.ttf",    # 微软雅黑（备选）
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    # 所有字体加载失败时回退到 Pygame 默认字体
    return pygame.font.Font(None, size)


# ============================================================
# 颜色常量（RGB 三元组）
# ============================================================
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
CYAN = (0, 255, 255)      # I 方块
YELLOW = (255, 255, 0)    # O 方块（田字）
PURPLE = (160, 32, 240)   # T 方块
GREEN = (0, 255, 0)       # S 方块
RED = (255, 0, 0)         # Z 方块
BLUE = (0, 0, 255)        # J 方块
ORANGE = (255, 165, 0)    # L 方块

# ============================================================
# 游戏区域尺寸常量
# ============================================================
COLS = 10                     # 面板列数
ROWS = 20                     # 面板行数
CELL_SIZE = 40                # 每个格子的像素大小
PREVIEW_CELL_SIZE = 25        # 预览区域格子的像素大小

# 窗口尺寸计算
PLAY_WIDTH = COLS * CELL_SIZE           # 游戏区域宽度（400px）
PLAY_HEIGHT = ROWS * CELL_SIZE          # 游戏区域高度（800px）
SIDE_PANEL = 240                        # 侧边栏宽度
WINDOW_WIDTH = PLAY_WIDTH + SIDE_PANEL  # 整体窗口宽度
WINDOW_HEIGHT = PLAY_HEIGHT             # 整体窗口高度

# ============================================================
# 七种标准俄罗斯方块形状定义
# 每个方块用二维列表表示，1 表示有方块，0 表示空
# 约定：初始朝向为生成时的默认朝向
# ============================================================
SHAPES = [
    # I 形 —— 长条，4 格一行
    [[1, 1, 1, 1]],
    # O 形 —— 田字，2x2 正方形
    [[1, 1],
     [1, 1]],
    # T 形 —— 凸字形
    [[0, 1, 0],
     [1, 1, 1]],
    # S 形 —— 反 Z 形
    [[0, 1, 1],
     [1, 1, 0]],
    # Z 形 —— 正 Z 形
    [[1, 1, 0],
     [0, 1, 1]],
    # J 形 —— 反 L 形（向左拐）
    [[1, 0, 0],
     [1, 1, 1]],
    # L 形 —— 正 L 形（向右拐）
    [[0, 0, 1],
     [1, 1, 1]],
]

# 每个形状对应的颜色（与 SHAPES 索引一一对应）
SHAPE_COLORS = [CYAN, YELLOW, PURPLE, GREEN, RED, BLUE, ORANGE]


# ============================================================
# 方块类 —— 表示一个正在活动或预览的方块
# ============================================================
class Tetromino:
    """方块类：存储方块的形状、颜色、位置信息"""

    def __init__(self, shape_idx):
        """
        初始化方块。
        shape_idx: 对应 SHAPES 列表的索引（0~6）
        - 从 SHAPES 中复制形状数据（避免引用共享）
        - 初始 x 居中，y 为 0（面板顶部）
        """
        self.shape_idx = shape_idx
        self.shape = [row[:] for row in SHAPES[shape_idx]]
        self.color = SHAPE_COLORS[shape_idx]
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotate(self):
        """
        顺时针旋转 90 度，返回旋转后的新形状列表。
        实现方式：矩阵转置后每行反转
        - 原形状：[[a,b],[c,d]]  -> 转置 [[a,c],[b,d]] -> 反转每行 [[c,a],[d,b]]
        - 结果即为顺时针旋转 90 度的形状
        """
        rotated = [list(row) for row in zip(*self.shape[::-1])]
        return rotated


# ============================================================
# 游戏主类 —— 包含所有游戏逻辑、AI 和渲染
# ============================================================
class Tetris:
    """游戏主类：管理游戏状态、方块的移动与锁定、AI 自动托管、画面绘制等"""

    def __init__(self):
        """
        初始化游戏窗口、字体、时钟，并重置游戏状态。
        """
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("俄罗斯方块")
        self.clock = pygame.time.Clock()               # 用于控制帧率
        self.font = get_font(18)                        # 普通字体
        self.big_font = get_font(28)                    # 大号字体（标题用）
        self.auto_btn_rect = pygame.Rect(PLAY_WIDTH + 25, 740, SIDE_PANEL - 20, 40)
        self.reset_game()

    # ----------------------------------------------------------
    # 游戏状态管理
    # ----------------------------------------------------------

    def reset_game(self):
        """
        重置所有游戏状态到初始值。
        每次新游戏或按 R 重新开始时调用。
        """
        self.board = [[0] * COLS for _ in range(ROWS)]  # 面板：0 表示空，>0 表示已固定的方块（值为 shape_idx+1）
        self.score = 0                                  # 当前得分
        self.level = 1                                  # 当前等级
        self.lines_cleared = 0                          # 已消除的总行数
        self.fall_speed = 1000                          # 下落间隔（毫秒），等级越高越快
        self.fall_time = 0                              # 下落计时器累积
        self.game_over = False                          # 游戏是否结束
        self.paused = False                             # 是否暂停

        # ---- AI 托管相关状态 ----
        self.auto_play = False                          # 是否开启自动托管
        self.ai_target_x = None                         # AI 目标列位置
        self.ai_target_y = 0                            # AI 目标行位置
        self.ai_target_rotations = 0                    # AI 需要旋转的次数
        self.ai_step_timer = 0                          # AI 执行步骤的计时器
        self.ai_falling = False                         # AI 是否处于下落阶段
        self.ai_fall_timer = 0                          # AI 下落动画计时器

        # 生成当前方块和下一个方块
        self.current_piece = self.new_piece()
        self.next_piece = self.new_piece()

    def new_piece(self):
        """
        随机生成一个新方块（从 7 种形状中随机选择）。
        返回: Tetromino 实例
        """
        return Tetromino(random.randint(0, len(SHAPES) - 1))

    # ----------------------------------------------------------
    # 碰撞检测与方块锁定
    # ----------------------------------------------------------

    def valid_move(self, piece, x, y, shape=None):
        """
        检查方块在指定位置 (x, y) 是否有效（不碰撞、不越界）。
        piece: 要检查的方块对象
        x, y: 目标位置（左上角所在格子坐标）
        shape: 可选的形状覆盖（用于旋转后的碰撞检测）
        返回: True 表示位置有效，False 表示无效
        """
        if shape is None:
            shape = piece.shape
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    new_x = x + col_idx
                    new_y = y + row_idx
                    # 越界或与已固定的方块重叠则无效
                    if (new_x < 0 or new_x >= COLS or
                        new_y >= ROWS or
                        (new_y >= 0 and self.board[new_y][new_x])):
                        return False
        return True

    def lock_piece(self):
        """
        将当前方块固定到面板上。
        执行步骤：
        1. 将当前方块的每个格子写入 board 数组
        2. 消除满行并更新分数
        3. 切换到下一个方块作为当前方块，并生成新的下一个方块
        4. 检查新方块生成位置（y=0）是否与已有方块重叠，是则游戏结束
        """
        # ---- 步骤 1：将当前方块写入面板 ----
        for row_idx, row in enumerate(self.current_piece.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    y = self.current_piece.y + row_idx
                    x = self.current_piece.x + col_idx
                    if y >= 0:
                        self.board[y][x] = self.current_piece.shape_idx + 1

        # ---- 步骤 2：消除满行 ----
        self.clear_lines()

        # ---- 步骤 3：切换到下一个方块 ----
        self.current_piece = self.next_piece
        self.next_piece = self.new_piece()

        # ---- 步骤 4：检查新方块生成时是否与已有方块重叠 ----
        # 新方块生成在面板顶部中央（y=0），如果该位置已被已堆叠的方块占据，
        # 说明面板已满，游戏结束。这是标准的俄罗斯方块游戏结束判定规则。
        if not self.valid_move(self.current_piece,
                               self.current_piece.x,
                               self.current_piece.y):
            self.game_over = True

    # ----------------------------------------------------------
    # 消行逻辑
    # ----------------------------------------------------------

    def clear_lines(self):
        """
        消除面板中所有满行，并更新分数、等级和下落速度。
        计分规则：消除 1 行得 100×等级，2 行 300×等级，
                  3 行 500×等级，4 行（Tetris）800×等级。
        等级提升：每消除 10 行升一级。
        速度变化：每升一级下落间隔减少 80ms，最低 200ms。
        """
        # 找出所有满行
        lines_to_clear = []
        for row_idx in range(ROWS):
            if all(self.board[row_idx]):
                lines_to_clear.append(row_idx)

        if lines_to_clear:
            # 从面板中移除满行，并在顶部插入空行
            for row_idx in lines_to_clear:
                del self.board[row_idx]
                self.board.insert(0, [0] * COLS)

            # 更新分数
            cleared = len(lines_to_clear)
            self.lines_cleared += cleared
            line_scores = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += line_scores.get(cleared, 0) * self.level

            # 更新等级和下落速度
            self.level = self.lines_cleared // 10 + 1
            self.fall_speed = max(200, 1000 - (self.level - 1) * 80)

    # ----------------------------------------------------------
    # 硬降（直接落底）
    # ----------------------------------------------------------

    def drop_piece(self):
        """
        硬降：将当前方块直接落到最底部可用的位置（空格硬降）。
        之后立即锁定方块。
        """
        while self.valid_move(self.current_piece,
                              self.current_piece.x,
                              self.current_piece.y + 1):
            self.current_piece.y += 1
        self.lock_piece()

    # ============================================================
    # AI 自动托管（电脑自动玩）
    # ============================================================
    #
    # AI 策略：
    # 1. 遍历所有可能的旋转态（最多 4 种）
    # 2. 对每个旋转态，遍历所有可能的水平位置
    # 3. 模拟方块放置后的面板状态
    # 4. 用评估函数打分（越低越好），选择最优位置
    # 5. 执行时先旋转对齐，再水平移动，最后下落
    # ----------------------------------------------------------

    def simulate_board(self, piece, x, y, shape):
        """
        模拟将方块放置在指定位置后的面板状态。
        返回一个副本（不影响实际面板），用于 AI 评估。
        piece: 方块对象（仅用于获取形状）
        x, y: 放置位置
        shape: 方块形状（可能已旋转）
        """
        board = [row[:] for row in self.board]
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    if y + row_idx < ROWS:
                        board[y + row_idx][x + col_idx] = 1
        return board

    def evaluate_board(self, board, landing_height, eroded_cells):
        """
        经典俄罗斯方块启发式评估函数。
        提取 6 项特征，分数越大越优（这里转换为：返回 -score，外部找最小值）。
        
        特征定义：
        1. landing_height (LH): 方块重心距底部高度，越低越稳，权重 -4.5
        2. eroded_cells (EC): 消行数 × 本方块消行格子数，权重 +3.4
        3. row_transitions (RT): 每行中 0↔1 切换次数总和，权重 -3.2
        4. col_transitions (CT): 每列中 0↔1 切换次数总和，权重 -3.2
        5. holes (H): 被上方方块遮挡的空格总数，权重 -7.9
        6. well_sums (WS): 两侧有方块阻挡的井深度和，权重 -1.2
        
        返回：- (weighted_score)，调用方选分数最小即为原加权得分最大
        """
        # 计算每列高度和空洞数
        holes = 0             # 空洞总数：有方块覆盖的空格（某列中下方为空、上方有方块）
        for col in range(COLS):
            found_block = False
            for row in range(ROWS):
                if board[row][col]:
                    found_block = True
                elif found_block:
                    holes += 1             # 方块下方的空格 → 空洞，无法直接填充

        # 行变换：每行中 0↔1 切换次数总和（值越小代表表面越平整）
        row_transitions = 0
        for row in range(ROWS):
            prev = 1  # 面板左侧边界视为有方块
            for col in range(COLS):
                curr = 1 if board[row][col] else 0
                if curr != prev:
                    row_transitions += 1
                prev = curr
            if prev == 0:
                row_transitions += 1       # 右侧边界最后一次切换

        # 列变换：每列中 0↔1 切换次数总和（反映空洞集中趋势）
        col_transitions = 0
        for col in range(COLS):
            prev = 1  # 面板上方边界视为有方块
            for row in range(ROWS):
                curr = 1 if board[row][col] else 0
                if curr != prev:
                    col_transitions += 1
                prev = curr
            if prev == 0:
                col_transitions += 1       # 底部边界最后一次切换

        # 井深总和：某一列左右邻列均有方块阻挡的连续空位，深度累加计分
        # 深度为 n 的井贡献 n*(n+1)/2，越深惩罚越大
        well_sums = 0
        for col in range(COLS):
            depth = 0
            for row in range(ROWS):
                if board[row][col] == 0:
                    # 检查这一行中左右邻居是否都有方块
                    left_blocked = (col == 0) or (board[row][col - 1] != 0)
                    right_blocked = (col == COLS - 1) or (board[row][col + 1] != 0)
                    if left_blocked and right_blocked:
                        depth += 1
                    else:
                        well_sums += depth * (depth + 1) // 2  # 等差数列求和
                        depth = 0
                else:
                    well_sums += depth * (depth + 1) // 2
                    depth = 0
            if depth > 0:
                well_sums += depth * (depth + 1) // 2

        # 加权公式：score = sum(weight_i * feature_i)
        # 返回负的 score，因为外部找最小值，所以返回值越小表示原分数越大
        return - ( (-4.5 * landing_height)
                   + (3.4 * eroded_cells)
                   + (-3.2 * row_transitions)
                   + (-3.2 * col_transitions)
                   + (-7.9 * holes)
                   + (-1.2 * well_sums) )

    def evaluate_candidate(self, shape, x, y):
        """
        计算候选动作的特征值（落地高度、消行贡献）。
        这些依赖于当前落子的方块位置，所以单独计算。
        
        返回: (new_board, landing_height, eroded_cells)
        - new_board: 放置并消行后的新棋盘
        - landing_height: 方块重心距底部高度
        - eroded_cells: 消行数 × 本方块参与消行的格子数
        """
        # 1. 落地高度：方块重心距底部高度，越低越稳
        shape_h = len(shape)
        landing_height = ROWS - (y + shape_h // 2)

        # 2. 消行贡献：计算本方块参与消行的行数和格子数
        # 消行数 × 本方块参与消行的格子数
        # 先模拟放置到临时棋盘
        temp_board = [row[:] for row in self.board]
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    if 0 <= y + row_idx < ROWS and 0 <= x + col_idx < COLS:
                        temp_board[y + row_idx][x + col_idx] = 1

        # 计算本方块占了多少个满行格子
        eroded = 0
        cleared_lines = 0
        for row_idx in range(ROWS):
            if all(cell != 0 for cell in temp_board[row_idx]):
                cleared_lines += 1
                # 数本方块在这行占了几个格子
                for col_idx, cell in enumerate(shape):
                    if cell and 0 <= y + row_idx < ROWS and 0 <= x + col_idx < COLS:
                        if temp_board[y + row_idx][x + col_idx] != 0:
                            eroded += 1
        eroded_cells = cleared_lines * eroded

        # 获取放置消行后的棋盘（用于 evaluate_board 计算其他特征）
        new_board = []
        for row_idx in range(ROWS):
            if not all(cell != 0 for cell in temp_board[row_idx]):
                new_board.append([1 if cell != 0 else 0 for cell in temp_board[row_idx]])
        # 消行后顶部补空行
        while len(new_board) < ROWS:
            new_board.insert(0, [0] * COLS)
        
        return new_board, landing_height, eroded_cells

    def get_best_move(self):
        """
        计算当前方块的最佳落点。
        遍历所有旋转态和水平位置，模拟硬降到底并评估 6 项特征，
        选择加权得分最高的动作。若平局，选移动步数最少的。
        返回: (target_x, target_y, rotations)
        - target_x: 目标列
        - target_y: 目标行（落底位置）
        - rotations: 需要旋转的次数
        """
        best_score = float('inf')
        best_x = None
        best_y = None
        best_rot = None
        best_steps = float('inf')    # 平局时选步数少的

        shape = self.current_piece.shape

        # 确定该方块需要遍历的旋转次数
        # O 形（田字，索引1）：只有 1 种旋转态
        # I/S/Z 形（索引0/4/3）：只有 2 种旋转态
        # 其余（T/J/L，索引2/5/6）：4 种旋转态
        shape_idx = self.current_piece.shape_idx
        if shape_idx == 1:          # O 形
            max_rotations = 1
        elif shape_idx in (0, 3, 4):  # I, S, Z 形
            max_rotations = 2
        else:                        # T, J, L 形
            max_rotations = 4

        # 遍历所有有效旋转态
        for rotations in range(max_rotations):
            rotated = shape
            for _ in range(rotations):
                rotated = [list(row) for row in zip(*rotated[::-1])]

            # 遍历所有可能的水平位置（从中间向两边展开，避免偏左）
            max_x = COLS - len(rotated[0])
            center = COLS // 2
            x_range = sorted(range(max_x + 1),
                             key=lambda x: abs(x - center))
            for x in x_range:
                # 模拟硬降到底
                y = -1
                while self.valid_move(self.current_piece, x, y + 1, rotated):
                    y += 1
                if y < 0:
                    continue

                # 计算落地高度和消行贡献，获取消行后的棋盘
                new_board, landing_height, eroded_cells = self.evaluate_candidate(rotated, x, y)

                # 计算 6 项特征的综合评分
                score = self.evaluate_board(new_board, landing_height, eroded_cells)

                # 计算移动步数（平局用）：旋转次数 + 水平距离
                steps = rotations + abs(x - self.current_piece.x)

                # 选分数更低的动作（即加权得分更高）
                if score < best_score or (score == best_score and steps < best_steps):
                    best_score = score
                    best_x = x
                    best_y = y
                    best_rot = rotations
                    best_steps = steps

        # 如果没有找到任何有效位置，保持当前状态
        if best_x is None:
            return self.current_piece.x, 0, 0
        return best_x, best_y, best_rot

    def ai_plan_move(self):
        """
        AI 制定走棋计划：计算最佳落点，并重置执行状态。
        """
        if self.game_over or self.paused:
            return
        self.ai_target_x, self.ai_target_y, self.ai_target_rotations = self.get_best_move()
        self.ai_step_timer = 0
        self.ai_falling = False

    def ai_execute_step(self):
        """
        AI 执行一步操作：旋转或水平移动。
        每步执行一个操作（旋转一次或移动一格），
        直到对齐目标位置后切换到下落动画阶段。
        """
        if self.game_over or self.paused:
            return

        # ---- 旋转阶段：如果还需要旋转 ----
        if self.ai_target_rotations > 0:
            rotated = self.current_piece.rotate()
            kicks = [0, -1, 1, -2, 2]          # 墙踢偏移量：尝试不同偏移
            for dx in kicks:
                if self.valid_move(self.current_piece,
                                   self.current_piece.x + dx,
                                   self.current_piece.y, rotated):
                    self.current_piece.shape = rotated
                    self.current_piece.x += dx
                    self.ai_target_rotations -= 1
                    return
            # 所有墙踢偏移都失败，重新制定计划
            self.ai_plan_move()
            return

        # ---- 水平移动阶段：向目标列移动 ----
        if self.current_piece.x < self.ai_target_x:
            # 向右移动
            if self.valid_move(self.current_piece, self.current_piece.x + 1,
                               self.current_piece.y):
                self.current_piece.x += 1
                return
        elif self.current_piece.x > self.ai_target_x:
            # 向左移动
            if self.valid_move(self.current_piece, self.current_piece.x - 1,
                               self.current_piece.y):
                self.current_piece.x -= 1
                return

        # ---- 旋转和水平移动都已对齐，进入下落动画阶段 ----
        self.ai_falling = True
        self.ai_fall_timer = 0

    def ai_fall_step(self, dt):
        """
        AI 方块速降阶段。旋转和水平移动完成后立即调用。
        策略：直接速降到目标位置，不再显示下落动画。
        """
        if self.game_over or self.paused:
            return

        # ---- 直接速降到目标位置 ----
        while self.current_piece.y < self.ai_target_y:
            if self.valid_move(self.current_piece,
                               self.current_piece.x,
                               self.current_piece.y + 1):
                self.current_piece.y += 1
            else:
                break
        self.lock_piece()
        self.ai_target_x = None
        self.ai_falling = False

    # ----------------------------------------------------------
    # 影子位置（绿色空心预览框）
    # ----------------------------------------------------------

    def get_ghost_y(self):
        """
        计算当前方块垂直落底后的 y 坐标（影子位置）。
        用于在目标位置显示绿色空心瞄准框。
        """
        ghost_y = self.current_piece.y
        while self.valid_move(self.current_piece,
                              self.current_piece.x,
                              ghost_y + 1):
            ghost_y += 1
        return ghost_y

    # ============================================================
    # 用户输入处理
    # ============================================================

    def handle_input(self, event):
        """
        处理键盘和鼠标输入事件。
        键盘控制：
        - 方向键：移动和旋转方块
        - 空格：硬降
        - P：暂停/继续
        - R：游戏结束后重新开始
        鼠标控制：
        - 点击"托管/取消托管"按钮
        """
        if event.type == pygame.KEYDOWN:
            # ---- 游戏结束时的处理 ----
            if self.game_over:
                if event.key == pygame.K_r:
                    self.reset_game()
                return

            # ---- P 键切换暂停 ----
            if event.key == pygame.K_p:
                self.paused = not self.paused
                return

            # ---- 暂停时忽略其他按键 ----
            if self.paused:
                return

            # ---- 托管时禁用键盘操作 ----
            if self.auto_play:
                return

            # ---- 方向键控制 ----
            if event.key == pygame.K_LEFT:
                # 左移
                if self.valid_move(self.current_piece,
                                   self.current_piece.x - 1,
                                   self.current_piece.y):
                    self.current_piece.x -= 1
            elif event.key == pygame.K_RIGHT:
                # 右移
                if self.valid_move(self.current_piece,
                                   self.current_piece.x + 1,
                                   self.current_piece.y):
                    self.current_piece.x += 1
            elif event.key == pygame.K_DOWN:
                # 软降（加速下落），每降一格加 1 分
                if self.valid_move(self.current_piece,
                                   self.current_piece.x,
                                   self.current_piece.y + 1):
                    self.current_piece.y += 1
                    self.score += 1
            elif event.key == pygame.K_UP:
                # 旋转（带墙踢）
                rotated = self.current_piece.rotate()
                # 尝试原地旋转
                if self.valid_move(self.current_piece, self.current_piece.x,
                                   self.current_piece.y, rotated):
                    self.current_piece.shape = rotated
                # 尝试向左偏移旋转
                elif self.valid_move(self.current_piece, self.current_piece.x - 1,
                                     self.current_piece.y, rotated):
                    self.current_piece.shape = rotated
                    self.current_piece.x -= 1
                # 尝试向右偏移旋转
                elif self.valid_move(self.current_piece, self.current_piece.x + 1,
                                     self.current_piece.y, rotated):
                    self.current_piece.shape = rotated
                    self.current_piece.x += 1
            elif event.key == pygame.K_SPACE:
                # 硬降（直接落底）
                self.drop_piece()

        # ---- 鼠标点击：托管按钮 ----
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.auto_btn_rect.collidepoint(event.pos):
                if self.game_over:
                    return
                self.auto_play = not self.auto_play
                if self.auto_play:
                    self.ai_target_x = None             # 清除旧计划，重新计算

    # ============================================================
    # 游戏更新逻辑
    # ============================================================

    def update(self, dt):
        """
        每帧更新游戏状态。
        dt: 上一帧到这一帧的时间间隔（毫秒）
        
        非托管模式：按固定时间间隔自动下落
        托管模式：AI 自动执行旋转、移动和下落
        """
        if self.game_over or self.paused:
            return

        # ---- AI 自动托管模式 ----
        if self.auto_play:
            if self.ai_target_x is None:
                # 无计划，立即制定（首次进入或锁定后重新计划）
                self.ai_plan_move()
                return
            if self.ai_falling:
                # 下落动画阶段
                self.ai_fall_step(dt)
            else:
                # 旋转/移动阶段（每 50ms 执行一步）
                self.ai_step_timer += dt
                if self.ai_step_timer >= 50:
                    self.ai_step_timer = 0
                    self.ai_execute_step()
            return

        # ---- 手动模式：自然下落 ----
        self.fall_time += dt
        if self.fall_time >= self.fall_speed:
            self.fall_time = 0
            if self.valid_move(self.current_piece,
                               self.current_piece.x,
                               self.current_piece.y + 1):
                self.current_piece.y += 1
            else:
                self.lock_piece()

    # ============================================================
    # 渲染绘制
    # ============================================================

    def draw_grid(self):
        """
        绘制游戏面板的网格线（灰色细线）。
        """
        # 垂直线
        for x in range(0, PLAY_WIDTH, CELL_SIZE):
            pygame.draw.line(self.screen, GRAY, (x, 0), (x, PLAY_HEIGHT), 1)
        # 水平线
        for y in range(0, PLAY_HEIGHT, CELL_SIZE):
            pygame.draw.line(self.screen, GRAY, (0, y), (PLAY_WIDTH, y), 1)

    def draw_board(self):
        """
        绘制已固定在面板上的所有方块。
        board 数组中存储的值是 shape_idx + 1，
        用于索引 SHAPE_COLORS 获取对应颜色。
        """
        for row_idx, row in enumerate(self.board):
            for col_idx, cell in enumerate(row):
                if cell:
                    color = SHAPE_COLORS[cell - 1]
                    x = col_idx * CELL_SIZE
                    y = row_idx * CELL_SIZE
                    self.draw_cell(x, y, color)

    def draw_cell(self, x, y, color, size=CELL_SIZE):
        """
        绘制单个方块格子，带 3D 立体效果（高光和阴影）。
        x, y: 左上角坐标
        color: 主颜色
        size: 格子大小（默认 CELL_SIZE，预览时较小）
        """
        # 主色块（留 1px 间隙形成网格线效果）
        pygame.draw.rect(self.screen, color, (x + 1, y + 1, size - 2, size - 2))
        # 高光效果（左上角亮边）
        lighter = tuple(min(255, c + 60) for c in color)
        pygame.draw.rect(self.screen, lighter, (x + 1, y + 1, size - 2, 3))
        pygame.draw.rect(self.screen, lighter, (x + 1, y + 1, 3, size - 2))
        # 阴影效果（右下角暗边）
        darker = tuple(max(0, c - 60) for c in color)
        pygame.draw.rect(self.screen, darker, (x + size - 4, y + 1, 3, size - 2))
        pygame.draw.rect(self.screen, darker, (x + 1, y + size - 4, size - 2, 3))

    def draw_piece(self, piece, offset_x, offset_y, size=CELL_SIZE, alpha=False):
        """
        绘制一个方块（当前活动方块或预览方块）。
        piece: 要绘制的方块对象
        offset_x, offset_y: 绘制的偏移位置（格子坐标）
        size: 格子大小
        alpha: 是否使用半透明绘制（当前未使用，保留参数）
        """
        for row_idx, row in enumerate(piece.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    x = (offset_x + col_idx) * size
                    y = (offset_y + row_idx) * size
                    if alpha:
                        # 半透明模式（用于某些特效）
                        s = pygame.Surface((size - 2, size - 2))
                        s.set_alpha(100)
                        s.fill(piece.color)
                        self.screen.blit(s, (x + 1, y + 1))
                    else:
                        # 正常绘制
                        self.draw_cell(x, y, piece.color, size)

    def draw_ghost(self):
        """
        绘制绿色空心瞄准框，预览方块落到底部后的位置。
        仅当落点位置与当前位置不同时才绘制。
        """
        ghost_y = self.get_ghost_y()
        if ghost_y == self.current_piece.y:
            return
        for row_idx, row in enumerate(self.current_piece.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    x = (self.current_piece.x + col_idx) * CELL_SIZE
                    y = (ghost_y + row_idx) * CELL_SIZE
                    # 浅绿色空心边框，线宽 1px
                    pygame.draw.rect(self.screen, (100, 220, 100),
                                     (x, y, CELL_SIZE, CELL_SIZE), 1)

    def draw_preview(self):
        """
        在侧边栏绘制"下一个方块"的预览。
        使用较小的格子尺寸（PREVIEW_CELL_SIZE）居中显示。
        """
        preview_x = PLAY_WIDTH + 25
        preview_y = 110

        # 预览区域边框
        pygame.draw.rect(self.screen, GRAY,
                         (preview_x - 10, preview_y - 30,
                          SIDE_PANEL - 20, 120), 2)

        # "下一个"标签
        label = self.font.render("下一个", True, WHITE)
        self.screen.blit(label, (preview_x, preview_y - 25))

        # 计算居中偏移，绘制下一个方块的形状
        shape = self.next_piece.shape
        rows = len(shape)
        cols = len(shape[0])
        center_x = preview_x + (SIDE_PANEL - 20) // 2 - cols * PREVIEW_CELL_SIZE // 2
        center_y = preview_y + 15

        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    x = center_x + col_idx * PREVIEW_CELL_SIZE
                    y = center_y + row_idx * PREVIEW_CELL_SIZE
                    self.draw_cell(x, y, self.next_piece.color, PREVIEW_CELL_SIZE)

    def draw_info(self):
        """
        在侧边栏绘制分数、等级、消除行数、操作提示和托管按钮。
        """
        info_x = PLAY_WIDTH + 25

        # ---- 分数面板 ----
        pygame.draw.rect(self.screen, GRAY,
                         (info_x, 240, SIDE_PANEL - 20, 70), 2)
        score_label = self.font.render("分数", True, WHITE)
        score_value = self.font.render(str(self.score), True, WHITE)
        self.screen.blit(score_label, (info_x + 10, 245))
        self.screen.blit(score_value, (info_x + 10, 275))

        # ---- 等级面板 ----
        pygame.draw.rect(self.screen, GRAY,
                         (info_x, 335, SIDE_PANEL - 20, 70), 2)
        level_label = self.font.render("等级", True, WHITE)
        level_value = self.font.render(str(self.level), True, WHITE)
        self.screen.blit(level_label, (info_x + 10, 340))
        self.screen.blit(level_value, (info_x + 10, 365))

        # ---- 消除行数面板 ----
        pygame.draw.rect(self.screen, GRAY,
                         (info_x, 430, SIDE_PANEL - 20, 70), 2)
        lines_label = self.font.render("消除行数", True, WHITE)
        lines_value = self.font.render(str(self.lines_cleared), True, WHITE)
        self.screen.blit(lines_label, (info_x + 10, 435))
        self.screen.blit(lines_value, (info_x + 10, 460))

        # ---- 操作提示列表 ----
        controls = [
            "← → 移动",
            "↑ 旋转",
            "↓ 加速下落",
            "空格 直接落底",
            "P 暂停/继续",
            "R 重新开始",
        ]
        y_start = 550
        for i, text in enumerate(controls):
            ctrl = self.font.render(text, True, WHITE)
            self.screen.blit(ctrl, (info_x + 5, y_start + i * 28))

        # ---- 托管按钮 ----
        # 托管中为绿色，非托管为深灰色
        btn_color = (0, 180, 80) if self.auto_play else (60, 60, 60)
        btn_text = "取消托管" if self.auto_play else "托管"
        pygame.draw.rect(self.screen, btn_color, self.auto_btn_rect, border_radius=6)
        pygame.draw.rect(self.screen, (200, 200, 200), self.auto_btn_rect, 2, border_radius=6)
        btn_surf = self.font.render(btn_text, True, WHITE)
        btn_rect = btn_surf.get_rect(center=self.auto_btn_rect.center)
        self.screen.blit(btn_surf, btn_rect)

    def draw_game_over(self):
        """
        绘制游戏结束画面：半透明黑色遮罩 + 结束信息。
        """
        overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        go_text = self.big_font.render("游戏结束", True, RED)
        score_text = self.font.render(f"最终得分: {self.score}", True, WHITE)
        restart_text = self.font.render("按 R 重新开始", True, WHITE)

        text_rect = go_text.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 - 40))
        self.screen.blit(go_text, text_rect)
        text_rect = score_text.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 + 10))
        self.screen.blit(score_text, text_rect)
        text_rect = restart_text.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 + 50))
        self.screen.blit(restart_text, text_rect)

    def draw_pause(self):
        """
        绘制暂停画面：半透明黑色遮罩 + "暂停中"提示。
        """
        overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT))
        overlay.set_alpha(120)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        pause_text = self.big_font.render("暂停中", True, WHITE)
        text_rect = pause_text.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2))
        self.screen.blit(pause_text, text_rect)

    def draw(self):
        """
        主绘制方法：按顺序绘制所有画面元素。
        每帧调用一次，更新屏幕显示。
        """
        self.screen.fill(BLACK)

        # 游戏区域外边框
        pygame.draw.rect(self.screen, WHITE, (0, 0, PLAY_WIDTH, PLAY_HEIGHT), 2)

        # 绘制已固定的方块
        self.draw_board()

        # 绘制网格线
        self.draw_grid()

        if not self.game_over:
            # 绘制影子（绿色空心预览框）
            self.draw_ghost()
            # 绘制当前活动方块
            self.draw_piece(self.current_piece,
                            self.current_piece.x,
                            self.current_piece.y)

        # 绘制侧边栏信息（预览、分数、按钮等）
        self.draw_preview()
        self.draw_info()

        # 叠加状态画面（游戏结束或暂停）
        if self.game_over:
            self.draw_game_over()
        elif self.paused:
            self.draw_pause()

        # 刷新屏幕显示
        pygame.display.flip()

    # ============================================================
    # 游戏主循环
    # ============================================================

    def run(self):
        """
        游戏主循环：以 60 FPS 的帧率持续运行。
        每帧处理：
        1. 事件输入（键盘、鼠标、窗口关闭）
        2. 更新游戏状态（下落、AI 等）
        3. 绘制画面
        """
        running = True
        while running:
            dt = self.clock.tick(60)         # 控制帧率 60 FPS，返回距上一帧的毫秒数

            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_input(event)

            # 更新状态
            self.update(dt)

            # 绘制画面
            self.draw()

        # 退出游戏
        pygame.quit()
        sys.exit()


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    game = Tetris()
    game.run()