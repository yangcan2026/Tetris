/**
 * 俄罗斯方块（Tetris）—— C++ 版（Win32 API + GDI）
 * ================================================
 * 功能特性：
 * - 7 种标准俄罗斯方块（I, O, T, S, Z, J, L）
 * - 键盘控制：方向键移动/旋转、空格硬降、P 暂停、R 重新开始
 * - 影子预览（绿色空心边框显示落点位置）
 * - 下一个方块预览
 * - 计分与等级系统（等级越高下落越快）
 * - AI 自动托管模式（Pierre Dellacherie 启发式算法，点击右侧按钮切换）
 * - 游戏结束判定：新方块生成时与已堆叠方块重叠则结束
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <vector>
#include <array>
#include <algorithm>
#include <cmath>
#include <random>
#include <string>
#include <cstdint>

// ============================================================
// 常量定义
// ============================================================
constexpr int COLS = 10;
constexpr int ROWS = 20;
constexpr int CELL_SIZE = 40;
constexpr int PREVIEW_CELL_SIZE = 25;
constexpr int PLAY_WIDTH = COLS * CELL_SIZE;          // 400
constexpr int PLAY_HEIGHT = ROWS * CELL_SIZE;         // 800
constexpr int SIDE_PANEL = 240;
constexpr int WINDOW_WIDTH = PLAY_WIDTH + SIDE_PANEL; // 640
constexpr int WINDOW_HEIGHT = PLAY_HEIGHT;            // 800

// 颜色
constexpr COLORREF CLR_BLACK   = RGB(0, 0, 0);
constexpr COLORREF CLR_WHITE   = RGB(255, 255, 255);
constexpr COLORREF CLR_GRAY    = RGB(128, 128, 128);
constexpr COLORREF CLR_CYAN    = RGB(0, 255, 255);
constexpr COLORREF CLR_YELLOW  = RGB(255, 255, 0);
constexpr COLORREF CLR_PURPLE  = RGB(160, 32, 240);
constexpr COLORREF CLR_GREEN   = RGB(0, 255, 0);
constexpr COLORREF CLR_RED     = RGB(255, 0, 0);
constexpr COLORREF CLR_BLUE    = RGB(0, 0, 255);
constexpr COLORREF CLR_ORANGE  = RGB(255, 165, 0);
constexpr COLORREF CLR_GHOST   = RGB(100, 220, 100);
constexpr COLORREF CLR_BTN_ON  = RGB(0, 180, 80);
constexpr COLORREF CLR_BTN_OFF = RGB(60, 60, 60);

// 定时器 ID
constexpr int TIMER_FALL = 1;
constexpr int TIMER_AI_STEP = 2;

// ============================================================
// 形状定义
// ============================================================
// 每个形状是 4x4 矩阵，用 uint16_t 的位表示（每行 4 bit）
// 但为了方便，用 vector<vector<int>>
using Shape = std::vector<std::vector<int>>;

const std::vector<Shape> SHAPES = {
    // I 形
    {{1, 1, 1, 1}},
    // O 形
    {{1, 1},
     {1, 1}},
    // T 形
    {{0, 1, 0},
     {1, 1, 1}},
    // S 形
    {{0, 1, 1},
     {1, 1, 0}},
    // Z 形
    {{1, 1, 0},
     {0, 1, 1}},
    // J 形
    {{1, 0, 0},
     {1, 1, 1}},
    // L 形
    {{0, 0, 1},
     {1, 1, 1}},
};

const std::vector<COLORREF> SHAPE_COLORS = {
    CLR_CYAN, CLR_YELLOW, CLR_PURPLE, CLR_GREEN, CLR_RED, CLR_BLUE, CLR_ORANGE
};

// ============================================================
// 工具函数
// ============================================================
Shape rotate_shape(const Shape& s) {
    // 顺时针旋转 90 度
    int rows = (int)s.size();
    int cols = (int)s[0].size();
    Shape result(cols, std::vector<int>(rows, 0));
    for (int r = 0; r < rows; ++r)
        for (int c = 0; c < cols; ++c)
            result[c][rows - 1 - r] = s[r][c];
    return result;
}

// ============================================================
// Tetromino 类
// ============================================================
class Tetromino {
public:
    int shape_idx;
    Shape shape;
    COLORREF color;
    int x, y;

    Tetromino(int idx) : shape_idx(idx), x(0), y(0) {
        shape = SHAPES[idx];
        color = SHAPE_COLORS[idx];
        // 居中
        x = COLS / 2 - (int)shape[0].size() / 2;
        y = 0;
    }

    Shape get_rotated() const {
        return rotate_shape(shape);
    }
};

// ============================================================
// Tetris 类
// ============================================================
class Tetris {
public:
    // 面板
    std::vector<std::vector<int>> board;
    // 游戏状态
    int score = 0;
    int level = 1;
    int lines_cleared = 0;
    int fall_speed = 1000; // 毫秒
    bool game_over = false;
    bool paused = false;

    // 方块
    Tetromino* current_piece = nullptr;
    Tetromino* next_piece = nullptr;

    // AI 托管
    bool auto_play = false;
    int ai_target_x = -1;
    int ai_target_y = 0;
    int ai_target_rotations = 0;
    bool ai_falling = false;

    // 窗口句柄
    HWND hwnd = nullptr;

    // 随机数
    std::mt19937 rng;

    Tetris() : rng(std::random_device{}()) {
        reset_game();
    }

    ~Tetris() {
        delete current_piece;
        delete next_piece;
    }

    // ----------------------------------------------------------
    // 游戏状态管理
    // ----------------------------------------------------------
    void reset_game() {
        board.assign(ROWS, std::vector<int>(COLS, 0));
        score = 0;
        level = 1;
        lines_cleared = 0;
        fall_speed = 1000;
        game_over = false;
        paused = false;

        auto_play = false;
        ai_target_x = -1;
        ai_target_y = 0;
        ai_target_rotations = 0;
        ai_falling = false;

        delete current_piece;
        delete next_piece;
        current_piece = new_piece();
        next_piece = new_piece();
    }

    Tetromino* new_piece() {
        int idx = std::uniform_int_distribution<int>(0, (int)SHAPES.size() - 1)(rng);
        return new Tetromino(idx);
    }

    // ----------------------------------------------------------
    // 碰撞检测
    // ----------------------------------------------------------
    bool valid_move(int x, int y, const Shape& shape) const {
        for (size_t r = 0; r < shape.size(); ++r) {
            for (size_t c = 0; c < shape[r].size(); ++c) {
                if (shape[r][c]) {
                    int nx = x + (int)c;
                    int ny = y + (int)r;
                    if (nx < 0 || nx >= COLS || ny >= ROWS) return false;
                    if (ny >= 0 && board[ny][nx]) return false;
                }
            }
        }
        return true;
    }

    bool valid_move_piece(const Tetromino* piece, int x, int y, const Shape* shape_override = nullptr) const {
        const Shape& s = shape_override ? *shape_override : piece->shape;
        return valid_move(x, y, s);
    }

    // ----------------------------------------------------------
    // 锁定方块
    // ----------------------------------------------------------
    void lock_piece() {
        if (!current_piece) return;
        // 写入面板
        for (size_t r = 0; r < current_piece->shape.size(); ++r) {
            for (size_t c = 0; c < current_piece->shape[r].size(); ++c) {
                if (current_piece->shape[r][c]) {
                    int y = current_piece->y + (int)r;
                    int x = current_piece->x + (int)c;
                    if (y >= 0) board[y][x] = current_piece->shape_idx + 1;
                }
            }
        }
        // 消行
        clear_lines();
        // 切换到下一个
        delete current_piece;
        current_piece = next_piece;
        next_piece = new_piece();
        // 检查游戏结束
        if (!valid_move(current_piece->x, current_piece->y, current_piece->shape)) {
            game_over = true;
            stop_timers();
        }
    }

    // ----------------------------------------------------------
    // 消行
    // ----------------------------------------------------------
    void clear_lines() {
        std::vector<int> full_rows;
        for (int r = 0; r < ROWS; ++r) {
            bool full = true;
            for (int c = 0; c < COLS; ++c) {
                if (!board[r][c]) { full = false; break; }
            }
            if (full) full_rows.push_back(r);
        }
        if (full_rows.empty()) return;
        // 删除满行，顶部插入空行
        for (int r : full_rows) {
            board.erase(board.begin() + r);
            board.insert(board.begin(), std::vector<int>(COLS, 0));
        }
        int cleared = (int)full_rows.size();
        lines_cleared += cleared;
        int line_scores[] = {0, 100, 300, 500, 800};
        score += line_scores[std::min(cleared, 4)] * level;
        level = lines_cleared / 10 + 1;
        fall_speed = std::max(200, 1000 - (level - 1) * 80);
    }

    // ----------------------------------------------------------
    // 硬降
    // ----------------------------------------------------------
    void drop_piece() {
        if (!current_piece) return;
        while (valid_move(current_piece->x, current_piece->y + 1, current_piece->shape)) {
            current_piece->y++;
        }
        lock_piece();
    }

    // ----------------------------------------------------------
    // 影子位置
    // ----------------------------------------------------------
    int get_ghost_y() const {
        if (!current_piece) return 0;
        int gy = current_piece->y;
        while (valid_move(current_piece->x, gy + 1, current_piece->shape)) {
            gy++;
        }
        return gy;
    }

    // ----------------------------------------------------------
    // AI 评估（Pierre Dellacherie 算法）
    // ----------------------------------------------------------
    std::vector<std::vector<int>> simulate_board(const Shape& shape, int x, int y) const {
        auto b = board;
        for (size_t r = 0; r < shape.size(); ++r) {
            for (size_t c = 0; c < shape[r].size(); ++c) {
                if (shape[r][c]) {
                    int ny = y + (int)r;
                    int nx = x + (int)c;
                    if (ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS)
                        b[ny][nx] = 1;
                }
            }
        }
        return b;
    }

    // 计算 6 项特征并评估（Pierre Dellacherie）
    double evaluate_board(const std::vector<std::vector<int>>& b,
                          double landing_height, double eroded_cells) const {
        // 1. 空洞数
        int holes = 0;
        for (int c = 0; c < COLS; ++c) {
            bool found_block = false;
            for (int r = 0; r < ROWS; ++r) {
                if (b[r][c]) found_block = true;
                else if (found_block) holes++;
            }
        }

        // 2. 行变换
        int row_transitions = 0;
        for (int r = 0; r < ROWS; ++r) {
            int prev = 1; // 左边界
            for (int c = 0; c < COLS; ++c) {
                int cur = b[r][c] ? 1 : 0;
                if (cur != prev) row_transitions++;
                prev = cur;
            }
            if (prev == 0) row_transitions++; // 右边界
        }

        // 3. 列变换
        int col_transitions = 0;
        for (int c = 0; c < COLS; ++c) {
            int prev = 1; // 上边界
            for (int r = 0; r < ROWS; ++r) {
                int cur = b[r][c] ? 1 : 0;
                if (cur != prev) col_transitions++;
                prev = cur;
            }
            if (prev == 0) col_transitions++; // 下边界
        }

        // 4. 井深和
        int well_sums = 0;
        for (int c = 0; c < COLS; ++c) {
            int depth = 0;
            for (int r = 0; r < ROWS; ++r) {
                if (b[r][c] == 0) {
                    bool left_blocked = (c == 0) || (b[r][c - 1] != 0);
                    bool right_blocked = (c == COLS - 1) || (b[r][c + 1] != 0);
                    if (left_blocked && right_blocked) {
                        depth++;
                    } else {
                        well_sums += depth * (depth + 1) / 2;
                        depth = 0;
                    }
                } else {
                    well_sums += depth * (depth + 1) / 2;
                    depth = 0;
                }
            }
            if (depth > 0) well_sums += depth * (depth + 1) / 2;
        }

        // 加权公式：返回负值，外部选最小
        double score = (-4.5 * landing_height)
                     + (3.4 * eroded_cells)
                     + (-3.2 * row_transitions)
                     + (-3.2 * col_transitions)
                     + (-7.9 * holes)
                     + (-1.2 * well_sums);
        return -score;
    }

    // 计算落地高度和消行贡献
    void evaluate_candidate(const Shape& shape, int x, int y,
                            double& out_landing_height, double& out_eroded_cells,
                            std::vector<std::vector<int>>& out_board) const {
        // 落地高度
        int shape_h = (int)shape.size();
        out_landing_height = (double)(ROWS - (y + shape_h / 2));

        // 模拟放置
        auto temp = board;
        for (size_t r = 0; r < shape.size(); ++r) {
            for (size_t c = 0; c < shape[r].size(); ++c) {
                if (shape[r][c]) {
                    int ny = y + (int)r;
                    int nx = x + (int)c;
                    if (ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS)
                        temp[ny][nx] = 1;
                }
            }
        }

        // 消行贡献
        int eroded = 0;
        int cleared_lines = 0;
        for (int r = 0; r < ROWS; ++r) {
            bool full = true;
            for (int c = 0; c < COLS; ++c) {
                if (!temp[r][c]) { full = false; break; }
            }
            if (full) {
                cleared_lines++;
                for (size_t sr = 0; sr < shape.size(); ++sr) {
                    for (size_t sc = 0; sc < shape[sr].size(); ++sc) {
                        if (shape[sr][sc]) {
                            int ny = y + (int)sr;
                            int nx = x + (int)sc;
                            if (ny == r && ny >= 0 && ny < ROWS && nx >= 0 && nx < COLS)
                                eroded++;
                        }
                    }
                }
            }
        }
        out_eroded_cells = (double)(cleared_lines * eroded);

        // 构建消行后棋盘
        out_board.clear();
        for (int r = 0; r < ROWS; ++r) {
            bool full = true;
            for (int c = 0; c < COLS; ++c) {
                if (!temp[r][c]) { full = false; break; }
            }
            if (!full) {
                std::vector<int> row(COLS, 0);
                for (int c = 0; c < COLS; ++c) row[c] = temp[r][c] ? 1 : 0;
                out_board.push_back(row);
            }
        }
        while ((int)out_board.size() < ROWS) {
            out_board.insert(out_board.begin(), std::vector<int>(COLS, 0));
        }
    }

    // 获取最佳落点
    void get_best_move(int& out_x, int& out_y, int& out_rotations) {
        out_x = current_piece->x;
        out_y = 0;
        out_rotations = 0;

        double best_score = 1e30;
        int best_x = -1, best_y = 0, best_rot = 0, best_steps = 99999;

        Shape shape = current_piece->shape;
        int shape_idx = current_piece->shape_idx;

        int max_rotations;
        if (shape_idx == 1) max_rotations = 1;       // O
        else if (shape_idx == 0 || shape_idx == 3 || shape_idx == 4) max_rotations = 2; // I, S, Z
        else max_rotations = 4;                       // T, J, L

        for (int rot = 0; rot < max_rotations; ++rot) {
            Shape rotated = shape;
            for (int r = 0; r < rot; ++r) rotated = rotate_shape(rotated);

            int max_x = COLS - (int)rotated[0].size();
            int center = COLS / 2;

            // 从中心向两边展开
            std::vector<int> x_range;
            for (int x = 0; x <= max_x; ++x) x_range.push_back(x);
            std::sort(x_range.begin(), x_range.end(),
                      [center](int a, int b) { return std::abs(a - center) < std::abs(b - center); });

            for (int x : x_range) {
                // 硬降到底
                int y = -1;
                while (valid_move(x, y + 1, rotated)) y++;
                if (y < 0) continue;

                double lh, ec;
                std::vector<std::vector<int>> new_board;
                evaluate_candidate(rotated, x, y, lh, ec, new_board);
                double score = evaluate_board(new_board, lh, ec);

                int steps = rot + std::abs(x - current_piece->x);

                if (score < best_score || (score == best_score && steps < best_steps)) {
                    best_score = score;
                    best_x = x;
                    best_y = y;
                    best_rot = rot;
                    best_steps = steps;
                }
            }
        }

        if (best_x >= 0) {
            out_x = best_x;
            out_y = best_y;
            out_rotations = best_rot;
        }
    }

    // ----------------------------------------------------------
    // AI 执行
    // ----------------------------------------------------------
    void ai_plan_move() {
        if (game_over || paused || !current_piece) return;
        get_best_move(ai_target_x, ai_target_y, ai_target_rotations);
        ai_falling = false;
    }

    void ai_execute_step() {
        if (game_over || paused || !current_piece) return;

        // 旋转阶段
        if (ai_target_rotations > 0) {
            Shape rotated = current_piece->get_rotated();
            int kicks[] = {0, -1, 1, -2, 2};
            for (int dx : kicks) {
                if (valid_move(current_piece->x + dx, current_piece->y, rotated)) {
                    current_piece->shape = rotated;
                    current_piece->x += dx;
                    ai_target_rotations--;
                    return;
                }
            }
            ai_plan_move();
            return;
        }

        // 水平移动阶段
        if (current_piece->x < ai_target_x) {
            if (valid_move(current_piece->x + 1, current_piece->y, current_piece->shape)) {
                current_piece->x++;
                return;
            }
        } else if (current_piece->x > ai_target_x) {
            if (valid_move(current_piece->x - 1, current_piece->y, current_piece->shape)) {
                current_piece->x--;
                return;
            }
        }

        // 对齐完成，进入下落
        ai_falling = true;
    }

    void ai_fall_step() {
        if (game_over || paused || !current_piece) return;
        // 直接速降到目标位置
        while (current_piece->y < ai_target_y) {
            if (valid_move(current_piece->x, current_piece->y + 1, current_piece->shape)) {
                current_piece->y++;
            } else break;
        }
        lock_piece();
        ai_target_x = -1;
        ai_falling = false;
        if (!game_over) {
            ai_plan_move();
        }
    }

    // ----------------------------------------------------------
    // 定时器管理
    // ----------------------------------------------------------
    void stop_timers() {
        KillTimer(hwnd, TIMER_FALL);
        KillTimer(hwnd, TIMER_AI_STEP);
    }

    void start_fall_timer() {
        KillTimer(hwnd, TIMER_FALL);
        SetTimer(hwnd, TIMER_FALL, fall_speed, nullptr);
    }

    void start_ai_step_timer() {
        SetTimer(hwnd, TIMER_AI_STEP, 50, nullptr);
    }

    // ----------------------------------------------------------
    // 用户输入
    // ----------------------------------------------------------
    void on_key_down(WPARAM key) {
        if (game_over) {
            if (key == 'R') { reset_game(); start_fall_timer(); }
            return;
        }
        if (key == 'P') {
            paused = !paused;
            if (paused) stop_timers();
            else if (auto_play) start_ai_step_timer();
            else start_fall_timer();
            return;
        }
        if (paused || !current_piece) return;
        if (auto_play) return;

        switch (key) {
            case VK_LEFT:
                if (valid_move(current_piece->x - 1, current_piece->y, current_piece->shape))
                    current_piece->x--;
                break;
            case VK_RIGHT:
                if (valid_move(current_piece->x + 1, current_piece->y, current_piece->shape))
                    current_piece->x++;
                break;
            case VK_DOWN:
                if (valid_move(current_piece->x, current_piece->y + 1, current_piece->shape)) {
                    current_piece->y++;
                    score++;
                }
                break;
            case VK_UP: {
                Shape rotated = current_piece->get_rotated();
                if (valid_move(current_piece->x, current_piece->y, rotated))
                    current_piece->shape = rotated;
                else if (valid_move(current_piece->x - 1, current_piece->y, rotated)) {
                    current_piece->shape = rotated;
                    current_piece->x--;
                } else if (valid_move(current_piece->x + 1, current_piece->y, rotated)) {
                    current_piece->shape = rotated;
                    current_piece->x++;
                }
                break;
            }
            case VK_SPACE:
                drop_piece();
                break;
        }
    }

    void on_timer_fall() {
        if (game_over || paused || !current_piece) return;
        if (auto_play) return;
        if (valid_move(current_piece->x, current_piece->y + 1, current_piece->shape)) {
            current_piece->y++;
        } else {
            lock_piece();
        }
    }

    void on_timer_ai_step() {
        if (game_over || paused || !current_piece) return;
        if (!auto_play) return;

        if (ai_target_x < 0) {
            ai_plan_move();
            return;
        }
        if (ai_falling) {
            KillTimer(hwnd, TIMER_AI_STEP);
            ai_fall_step();
            if (!game_over && auto_play) start_ai_step_timer();
            InvalidateRect(hwnd, nullptr, TRUE);
            return;
        }
        ai_execute_step();
        InvalidateRect(hwnd, nullptr, TRUE);
    }

    void toggle_auto_play() {
        if (game_over) return;
        auto_play = !auto_play;
        if (auto_play) {
            stop_timers();
            ai_target_x = -1;
            ai_plan_move();
            start_ai_step_timer();
        } else {
            stop_timers();
            start_fall_timer();
        }
    }

    // ----------------------------------------------------------
    // 渲染
    // ----------------------------------------------------------
    void draw_cell(HDC hdc, int x, int y, COLORREF color, int size = CELL_SIZE) const {
        HBRUSH brush = CreateSolidBrush(color);
        RECT rect = {x + 1, y + 1, x + size - 1, y + size - 1};
        FillRect(hdc, &rect, brush);
        DeleteObject(brush);

        // 高光
        HBRUSH light = CreateSolidBrush(RGB(
            std::min(255, GetRValue(color) + 60),
            std::min(255, GetGValue(color) + 60),
            std::min(255, GetBValue(color) + 60)));
        rect = {x + 1, y + 1, x + size - 1, y + 4};
        FillRect(hdc, &rect, light);
        rect = {x + 1, y + 1, x + 4, y + size - 1};
        FillRect(hdc, &rect, light);
        DeleteObject(light);

        // 阴影
        HBRUSH dark = CreateSolidBrush(RGB(
            std::max(0, GetRValue(color) - 60),
            std::max(0, GetGValue(color) - 60),
            std::max(0, GetBValue(color) - 60)));
        rect = {x + size - 4, y + 1, x + size - 1, y + size - 1};
        FillRect(hdc, &rect, dark);
        rect = {x + 1, y + size - 4, x + size - 1, y + size - 1};
        FillRect(hdc, &rect, dark);
        DeleteObject(dark);
    }

    void draw_board(HDC hdc) const {
        for (int r = 0; r < ROWS; ++r) {
            for (int c = 0; c < COLS; ++c) {
                if (board[r][c]) {
                    COLORREF color = SHAPE_COLORS[board[r][c] - 1];
                    draw_cell(hdc, c * CELL_SIZE, r * CELL_SIZE, color);
                }
            }
        }
    }

    void draw_grid(HDC hdc) const {
        HPEN pen = CreatePen(PS_SOLID, 1, CLR_GRAY);
        HGDIOBJ old = SelectObject(hdc, pen);
        for (int x = 0; x <= PLAY_WIDTH; x += CELL_SIZE) {
            MoveToEx(hdc, x, 0, nullptr);
            LineTo(hdc, x, PLAY_HEIGHT);
        }
        for (int y = 0; y <= PLAY_HEIGHT; y += CELL_SIZE) {
            MoveToEx(hdc, 0, y, nullptr);
            LineTo(hdc, PLAY_WIDTH, y);
        }
        SelectObject(hdc, old);
        DeleteObject(pen);
    }

    void draw_piece(HDC hdc, const Tetromino* piece, int ox, int oy, int size = CELL_SIZE) const {
        if (!piece) return;
        for (size_t r = 0; r < piece->shape.size(); ++r) {
            for (size_t c = 0; c < piece->shape[r].size(); ++c) {
                if (piece->shape[r][c]) {
                    draw_cell(hdc, (ox + (int)c) * size, (oy + (int)r) * size, piece->color, size);
                }
            }
        }
    }

    void draw_ghost(HDC hdc) const {
        if (!current_piece) return;
        int ghost_y = get_ghost_y();
        if (ghost_y == current_piece->y) return;
        HPEN pen = CreatePen(PS_SOLID, 1, CLR_GHOST);
        HGDIOBJ old = SelectObject(hdc, pen);
        HBRUSH old_brush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
        for (size_t r = 0; r < current_piece->shape.size(); ++r) {
            for (size_t c = 0; c < current_piece->shape[r].size(); ++c) {
                if (current_piece->shape[r][c]) {
                    int x = (current_piece->x + (int)c) * CELL_SIZE;
                    int y = (ghost_y + (int)r) * CELL_SIZE;
                    RECT rect = {x, y, x + CELL_SIZE, y + CELL_SIZE};
                    Rectangle(hdc, rect.left, rect.top, rect.right, rect.bottom);
                }
            }
        }
        SelectObject(hdc, old);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);
    }

    void draw_text(HDC hdc, int x, int y, const std::string& text, COLORREF color, int size = 22) const {
        // 将 UTF-8 字符串转换为 UTF-16 以正确显示中文
        int wlen = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
        std::wstring wtext(wlen, L'\0');
        MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, &wtext[0], wlen);

        HFONT font = CreateFontW(size, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                 DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                 DEFAULT_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Microsoft YaHei");
        HGDIOBJ old = SelectObject(hdc, font);
        SetTextColor(hdc, color);
        SetBkMode(hdc, TRANSPARENT);
        RECT rect = {x, y, x + 400, y + 50};
        DrawTextW(hdc, wtext.c_str(), -1, &rect, DT_LEFT);
        SelectObject(hdc, old);
        DeleteObject(font);
    }

    void draw_preview(HDC hdc) const {
        int px = PLAY_WIDTH + 25, py = 110;
        // 边框
        HPEN pen = CreatePen(PS_SOLID, 2, CLR_GRAY);
        HGDIOBJ old = SelectObject(hdc, pen);
        HBRUSH old_brush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
        Rectangle(hdc, px - 10, py - 30, px - 10 + SIDE_PANEL - 20, py - 30 + 120);
        SelectObject(hdc, old);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);

        draw_text(hdc, px, py - 25, "下一个", CLR_WHITE);

        if (!next_piece) return;
        int rows = (int)next_piece->shape.size();
        int cols = (int)next_piece->shape[0].size();
        int cx = px + (SIDE_PANEL - 20) / 2 - cols * PREVIEW_CELL_SIZE / 2;
        int cy = py + 15;
        for (int r = 0; r < rows; ++r) {
            for (int c = 0; c < cols; ++c) {
                if (next_piece->shape[r][c]) {
                    draw_cell(hdc, cx + c * PREVIEW_CELL_SIZE, cy + r * PREVIEW_CELL_SIZE,
                              next_piece->color, PREVIEW_CELL_SIZE);
                }
            }
        }
    }

    void draw_info(HDC hdc) const {
        int ix = PLAY_WIDTH + 25;

        // 分数面板
        HPEN pen = CreatePen(PS_SOLID, 2, CLR_GRAY);
        HGDIOBJ old = SelectObject(hdc, pen);
        HBRUSH old_brush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
        Rectangle(hdc, ix, 240, ix + SIDE_PANEL - 20, 310);
        Rectangle(hdc, ix, 335, ix + SIDE_PANEL - 20, 405);
        Rectangle(hdc, ix, 430, ix + SIDE_PANEL - 20, 500);
        SelectObject(hdc, old);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);

        draw_text(hdc, ix + 10, 245, "分数", CLR_WHITE);
        draw_text(hdc, ix + 10, 275, std::to_string(score), CLR_WHITE);
        draw_text(hdc, ix + 10, 340, "等级", CLR_WHITE);
        draw_text(hdc, ix + 10, 365, std::to_string(level), CLR_WHITE);
        draw_text(hdc, ix + 10, 435, "消除行数", CLR_WHITE);
        draw_text(hdc, ix + 10, 460, std::to_string(lines_cleared), CLR_WHITE);

        // 操作提示
        const char* controls[] = {
            "<- -> 移动", "UP 旋转", "DOWN 加速下落",
            "SPACE 直接落底", "P 暂停/继续", "R 重新开始"
        };
        int y = 550;
        for (int i = 0; i < 6; ++i) {
            draw_text(hdc, ix + 5, y + i * 28, controls[i], CLR_WHITE, 18);
        }

        // 托管按钮
        RECT btn = {PLAY_WIDTH + 25, 740, PLAY_WIDTH + 25 + SIDE_PANEL - 20, 780};
        HBRUSH btn_brush = CreateSolidBrush(auto_play ? CLR_BTN_ON : CLR_BTN_OFF);
        FillRect(hdc, &btn, btn_brush);
        DeleteObject(btn_brush);
        pen = CreatePen(PS_SOLID, 2, CLR_WHITE);
        old = SelectObject(hdc, pen);
        old_brush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
        RoundRect(hdc, btn.left, btn.top, btn.right, btn.bottom, 6, 6);
        SelectObject(hdc, old);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);

        draw_text(hdc, btn.left + (btn.right - btn.left) / 2 - 30, btn.top + 8,
                  auto_play ? "取消托管" : "托管", CLR_WHITE);
    }

    void draw_game_over(HDC hdc) const {
        // 半透明遮罩
        HBRUSH overlay = CreateSolidBrush(RGB(0, 0, 0));
        RECT rect = {0, 0, PLAY_WIDTH, PLAY_HEIGHT};
        FillRect(hdc, &rect, overlay);
        DeleteObject(overlay);

        // 但需要半透明效果，用 GDI 不容易实现，直接画文字
        std::string score_text = "最终得分: " + std::to_string(score);
        draw_text(hdc, PLAY_WIDTH / 2 - 80, PLAY_HEIGHT / 2 - 40, "游戏结束", CLR_RED, 28);
        draw_text(hdc, PLAY_WIDTH / 2 - 80, PLAY_HEIGHT / 2 + 10, score_text, CLR_WHITE, 18);
        draw_text(hdc, PLAY_WIDTH / 2 - 80, PLAY_HEIGHT / 2 + 50, "按 R 重新开始", CLR_WHITE, 18);
    }

    void draw_pause(HDC hdc) const {
        draw_text(hdc, PLAY_WIDTH / 2 - 40, PLAY_HEIGHT / 2, "暂停中", CLR_WHITE, 28);
    }

    void render(HDC hdc) {
        // 背景
        RECT rect = {0, 0, WINDOW_WIDTH, WINDOW_HEIGHT};
        HBRUSH bg = CreateSolidBrush(CLR_BLACK);
        FillRect(hdc, &rect, bg);
        DeleteObject(bg);

        // 游戏区域边框
        HPEN pen = CreatePen(PS_SOLID, 2, CLR_WHITE);
        HGDIOBJ old = SelectObject(hdc, pen);
        HBRUSH old_brush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
        Rectangle(hdc, 0, 0, PLAY_WIDTH, PLAY_HEIGHT);
        SelectObject(hdc, old);
        SelectObject(hdc, old_brush);
        DeleteObject(pen);

        // 已固定的方块
        draw_board(hdc);
        // 网格
        draw_grid(hdc);

        if (!game_over) {
            // 影子
            draw_ghost(hdc);
            // 当前方块
            draw_piece(hdc, current_piece, current_piece->x, current_piece->y);
        }

        // 侧边栏
        draw_preview(hdc);
        draw_info(hdc);

        if (game_over) draw_game_over(hdc);
        else if (paused) draw_pause(hdc);
    }
};

// ============================================================
// 全局变量
// ============================================================
Tetris* g_game = nullptr;

// ============================================================
// 窗口过程
// ============================================================
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_CREATE: {
            g_game->hwnd = hwnd;
            g_game->start_fall_timer();
            return 0;
        }
        case WM_TIMER: {
            if (!g_game) return 0;
            int id = (int)wParam;
            if (id == TIMER_FALL) {
                g_game->on_timer_fall();
                InvalidateRect(hwnd, nullptr, TRUE);
            } else if (id == TIMER_AI_STEP) {
                g_game->on_timer_ai_step();
            }
            return 0;
        }
        case WM_KEYDOWN: {
            if (g_game) g_game->on_key_down(wParam);
            InvalidateRect(hwnd, nullptr, TRUE);
            return 0;
        }
        case WM_LBUTTONDOWN: {
            if (!g_game) return 0;
            int mx = LOWORD(lParam);
            int my = HIWORD(lParam);
            // 检查按钮点击
            if (mx >= PLAY_WIDTH + 25 && mx <= PLAY_WIDTH + 25 + SIDE_PANEL - 20 &&
                my >= 740 && my <= 780) {
                g_game->toggle_auto_play();
                InvalidateRect(hwnd, nullptr, TRUE);
            }
            return 0;
        }
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            if (g_game) g_game->render(hdc);
            EndPaint(hwnd, &ps);
            return 0;
        }
        case WM_DESTROY: {
            g_game->stop_timers();
            PostQuitMessage(0);
            return 0;
        }
    }
    return DefWindowProc(hwnd, msg, wParam, lParam);
}

// ============================================================
// WinMain
// ============================================================
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int nCmdShow) {
    // 注册窗口类
    const char CLASS_NAME[] = "TetrisWindow";

    WNDCLASS wc = {};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = CLASS_NAME;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);

    RegisterClass(&wc);

    // 计算窗口客户区大小
    RECT winRect = {0, 0, WINDOW_WIDTH, WINDOW_HEIGHT};
    AdjustWindowRect(&winRect, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);

    // 创建游戏对象
    Tetris game;
    g_game = &game;

    // 创建窗口
    HWND hwnd = CreateWindowEx(
        0, CLASS_NAME, "俄罗斯方块",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT,
        winRect.right - winRect.left, winRect.bottom - winRect.top,
        nullptr, nullptr, hInstance, nullptr
    );

    if (!hwnd) return 1;

    ShowWindow(hwnd, nCmdShow);

    // 消息循环
    MSG msg = {};
    while (GetMessage(&msg, nullptr, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    g_game = nullptr;
    return 0;
}