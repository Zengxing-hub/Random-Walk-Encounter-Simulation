# -*- coding: utf-8 -*-
"""
随机游走 · 两个人还能再相遇吗 — Python (pygame) 版

对应网页版：随机游走相遇模拟-传奇背景版.html
- 默认背景为同目录下的 传奇.png（找不到时回退到暗色晕影）
- 空格走一步（可长按），自动 / 重置，换背景（文件选择器或直接拖图片进窗口）
- 依赖：pygame（pip install pygame）
"""

import math
import os
import re
import random
import time

import pygame

# ============================================================
# 设计 token（对应网页版 CSS 变量）
# ============================================================
INK_950  = (9, 11, 16)        # 画布晕影边缘
INK_900  = (11, 13, 20)       # 页面底色
INK_800  = (14, 16, 22)       # 画布晕影中心
INK_700  = (18, 20, 27)       # 面板实色
PANEL    = (18, 20, 27)
PANEL_A  = 235                # 面板透明度 ≈92%
PAPER_50   = (238, 240, 245)  # 主文字、主按钮
PAPER_100  = (255, 255, 255)  # 主按钮 hover
SLATE_300  = (201, 209, 222)  # 次级按钮文字
SLATE_400  = (163, 169, 184)  # 次要文字
SLATE_500  = (122, 130, 150)  # 弱化文字
BLUE_400   = (78, 168, 255)   # 甲
ORANGE_400 = (255, 122, 89)   # 乙
AMBER      = (242, 178, 90)   # 相遇脉冲
AMBER_200  = (232, 178, 106)  # 相遇文字
BG_DIM     = (9, 11, 16, 102)     # 背景压暗 40%
LINE       = (255, 255, 255, 20)  # hairline
GRID       = (255, 255, 255, 13)  # 网格线 5%
ORIGIN_MK  = (255, 255, 255, 77)  # 起点环 30%
DOT_RING   = (9, 11, 16, 115)     # 位置点描边 45%
DOT_HI     = (255, 255, 255, 230) # 位置点高光 90%

# 面板几何（4px 基准）
PANEL_X, PANEL_Y, PANEL_W, PANEL_PAD = 16, 16, 240, 16
BTN_H, BTN_R, BTN_GAP = 32, 8, 8
TOAST_H = 36

AUTO_DELAY = 130   # 自动模式每步间隔(ms)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BG = os.path.join(SCRIPT_DIR, '传奇.png')  # 默认背景图（与本文件同目录）

# ============================================================
# 全局状态
# ============================================================
W, H = 1280, 800
screen = None
OVERLAY = None
BG_SURF = None

A, B = [], []                 # 两条轨迹（点数组）
steps = meetings = 0
last_meet = None
flash = 0.0                   # 相遇脉冲动画进度
bounds = [0, 0, 0, 0]         # minX, maxX, minY, maxY
cell = 16

auto = False
auto_acc = 0

bg_default = None             # 默认背景（传奇图，加载成功后）
bg_img = None                 # 当前生效背景

toast_msg = None
toast_t = 0.0

mouse_down = False
pressed_btn = None
hover_btn = None
BUTTONS = {}                  # id -> pygame.Rect

# ============================================================
# 字体与文本缓存
# ============================================================
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
FONT_FILES = {
    'cjk':  ['msyh.ttc', 'msyh.ttf', 'simhei.ttf', 'simsun.ttc'],
    'mono': ['consola.ttf', 'cour.ttf', 'lucon.ttf'],
}
FONT_NAMES = {
    'cjk':  ['microsoftyahei', 'msyh', 'simhei', 'simsun', 'notosanscjk', 'wenquanyimicrohei'],
    'mono': ['consolas', 'couriernew', 'dejavusansmono'],
}

def load_font(kind, size):
    # 先走 match_font（某些 pygame 版本枚举系统字体时会抛异常，直接回退到文件路径）
    try:
        for name in FONT_NAMES[kind]:
            path = pygame.font.match_font(name)
            if path:
                return pygame.font.Font(path, size)
    except Exception:
        pass
    for fn in FONT_FILES[kind]:
        path = os.path.join(FONT_DIR, fn)
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
    return pygame.font.Font(None, size)

F = {}

_TEXT_CACHE = {}
def text(s, font_key, color):
    key = (s, font_key, color)
    if key not in _TEXT_CACHE:
        _TEXT_CACHE[key] = F[font_key].render(s, True, color)
    return _TEXT_CACHE[key]

_VALUE_CACHE = {}
def render_value(s):
    """统计值：数字用 mono，其余用界面字体（混合排版）"""
    if s in _VALUE_CACHE:
        return _VALUE_CACHE[s]
    surfs = []
    for p in re.split(r'(\d+(?:\.\d+)?)', s):
        if not p:
            continue
        fk = 'mono13' if re.fullmatch(r'[\d.]+', p) else 'ui13'
        surfs.append(text(p, fk, PAPER_50))
    w = sum(x.get_width() for x in surfs)
    h = max(x.get_height() for x in surfs)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    for s2 in surfs:
        surf.blit(s2, (x, 0))
        x += s2.get_width()
    _VALUE_CACHE[s] = surf
    return surf

def wrap(text_str, font_key, max_w):
    lines, cur = [], ''
    for ch in text_str:
        if F[font_key].size(cur + ch)[0] <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines

# ============================================================
# 面板布局
# ============================================================
def layout_panel():
    global PANEL_H
    x0 = PANEL_X + PANEL_PAD
    content_w = PANEL_W - PANEL_PAD * 2
    y = PANEL_Y + PANEL_PAD

    # 标题行：mark 16px + 8px 间距 + 14px 文字
    title_h = max(20, F['title'].get_linesize())
    y += title_h + 4

    # 副标题（自动换行）
    lines = wrap('两人从同一点出发，每步随机走一格，轨迹一直保留。', 'ui12', content_w)
    sub_h = len(lines) * F['ui12'].get_linesize()
    y += sub_h + 16

    # 按钮：主按钮整行 + 两行双按钮
    bx = x0
    BUTTONS['step'] = pygame.Rect(bx, y, content_w, BTN_H)
    y += BTN_H + BTN_GAP
    BUTTONS['auto']  = pygame.Rect(bx, y, 100, BTN_H)
    BUTTONS['reset'] = pygame.Rect(bx + 108, y, 100, BTN_H)
    y += BTN_H + BTN_GAP
    BUTTONS['bg']     = pygame.Rect(bx, y, 100, BTN_H)
    BUTTONS['bgreset'] = pygame.Rect(bx + 108, y, 100, BTN_H)
    y += BTN_H + 16

    # 统计：4 行 × 20 + 3 × 8
    y += 4 * 20 + 3 * 8 + 16

    # 图例：hairline + 12 + 一行
    y += 12 + 18

    PANEL_H = y + PANEL_PAD - PANEL_Y

# ============================================================
# 模拟逻辑（与网页版一致）
# ============================================================
DIRS = [(0, 1), (0, -1), (-1, 0), (1, 0)]  # 上 下 左 右

def reset():
    global A, B, steps, meetings, last_meet, flash, bounds, auto
    A = [(0, 0)]
    B = [(0, 0)]
    steps = meetings = 0
    last_meet = None
    flash = 0.0
    bounds = [0, 0, 0, 0]
    auto = False
    set_btn('auto', '自动', False)

def grow_bounds(p):
    x, y = p
    if x < bounds[0]: bounds[0] = x
    if x > bounds[1]: bounds[1] = x
    if y < bounds[2]: bounds[2] = y
    if y > bounds[3]: bounds[3] = y

def do_step():
    global steps, meetings, last_meet, flash
    a, b = A[-1], B[-1]
    da, db = random.choice(DIRS), random.choice(DIRS)
    na, nb = (a[0] + da[0], a[1] + da[1]), (b[0] + db[0], b[1] + db[1])
    A.append(na)
    B.append(nb)
    grow_bounds(na)
    grow_bounds(nb)
    steps += 1
    if na == nb:  # 同一时刻站在同一个格子上 = 相遇
        meetings += 1
        last_meet = steps
        flash = 1.0
        toast('第 %d 步，两人再次相遇' % steps)

def set_btn(btn_id, label, on):
    BUTTONS[btn_id]  # 仅确保存在
    if btn_id == 'auto':
        BUTTON_LABELS[btn_id] = label
        BUTTON_ON[btn_id] = on

BUTTON_LABELS = {'step': '走一步', 'auto': '自动', 'reset': '重置',
                 'bg': '换背景', 'bgreset': '恢复默认'}
BUTTON_ON = {'auto': False}

# ============================================================
# 通知 toast
# ============================================================
def toast(msg):
    global toast_msg, toast_t
    toast_msg = msg
    toast_t = time.time()

# ============================================================
# 背景
# ============================================================
def set_bg(path, silent=False):
    global bg_img, bg_default
    try:
        img = pygame.image.load(path).convert_alpha()
        iw, ih = img.get_size()
        if max(iw, ih) > 2560:  # 大图降采样，避免每帧缩放卡顿
            s = 2560 / max(iw, ih)
            img = pygame.transform.smoothscale(img, (max(1, int(iw * s)), max(1, int(ih * s))))
        bg_img = img
        if silent:
            bg_default = img
        else:
            toast('背景已更换')
        rebuild_bg()
    except Exception as ex:
        if silent:
            print('默认背景加载失败：%s（%s）' % (path, ex))
        else:
            toast('无法加载这张图片')

def pick_background():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askopenfilename(
            filetypes=[('图片', '*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp'), ('所有文件', '*.*')])
        root.destroy()
        pygame.event.clear()
        if path:
            set_bg(path)
    except Exception:
        toast('无法打开文件选择器')

def rebuild_bg():
    """重建背景缓存：图片（智能适配 + 压暗）或默认暗色晕影"""
    global BG_SURF
    BG_SURF = pygame.Surface((W, H))
    if bg_img is not None:
        iw, ih = bg_img.get_size()
        wide = iw / ih >= 1.8
        if wide and H > W:                      # 竖屏 + 宽图：铺满
            s = max(W / iw, H / ih)
        elif W / H < iw / ih:                   # 屏幕更窄：整图展示，上下留暗边
            s = min(W / iw, H / ih)
        else:                                   # 铺满裁剪
            s = max(W / iw, H / ih)
        dw, dh = int(iw * s), int(ih * s)
        scaled = pygame.transform.smoothscale(bg_img, (dw, dh))
        BG_SURF.blit(scaled, ((W - dw) // 2, (H - dh) // 2))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill(BG_DIM)
        BG_SURF.blit(dim, (0, 0))
    else:
        R = max(W, H) * 0.75
        STEPS = 240
        for i in range(STEPS + 1):
            t = i / STEPS
            c = tuple(round(INK_800[k] + (INK_950[k] - INK_800[k]) * t) for k in range(3))
            pygame.draw.circle(BG_SURF, c, (W // 2, H // 2), max(1, int(R * (1 - t))))

# ============================================================
# 窗口尺寸
# ============================================================
def resize(w, h):
    global W, H, screen, OVERLAY
    W, H = max(320, w), max(240, h)
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    OVERLAY = pygame.Surface((W, H), pygame.SRCALPHA)
    rebuild_bg()

# ============================================================
# 绘制
# ============================================================
def view():
    """自适应坐标变换（与网页版一致），返回 px/py 与 cell"""
    global cell
    pad = min(W, H) * 0.10 + 40
    span_x = max(bounds[1] - bounds[0], 1)
    span_y = max(bounds[3] - bounds[2], 1)
    cell = min((W - 2 * pad) / span_x, (H - 2 * pad) / span_y)
    cell = max(2, min(cell, 64))
    mid_x = (bounds[0] + bounds[1]) / 2
    mid_y = (bounds[2] + bounds[3]) / 2
    ox = W / 2 - mid_x * cell
    oy = H / 2 + mid_y * cell  # 屏幕 y 轴向下
    return (lambda x: ox + x * cell), (lambda y: oy - y * cell)

def draw_canvas():
    OVERLAY.fill((0, 0, 0, 0))
    px, py = view()

    # 网格
    if cell >= 16:
        for x in range(int(math.floor(bounds[0])), int(math.ceil(bounds[1])) + 1):
            s = int(round(px(x)))
            pygame.draw.line(OVERLAY, GRID, (s, 0), (s, H))
        for y in range(int(math.floor(bounds[2])), int(math.ceil(bounds[3])) + 1):
            s = int(round(py(y)))
            pygame.draw.line(OVERLAY, GRID, (0, s), (W, s))

    # 起点
    pygame.draw.circle(OVERLAY, ORIGIN_MK, (int(px(0)), int(py(0))), 4, 1)

    # 轨迹
    for path, color in ((A, (*BLUE_400, 140)), (B, (*ORANGE_400, 166))):
        if len(path) >= 2:
            pts = [(int(px(x)), int(py(y))) for x, y in path]
            pygame.draw.lines(OVERLAY, color, False, pts, 2)

    # 相遇脉冲
    if flash > 0:
        t = 1 - flash
        p = A[-1]
        pygame.draw.circle(OVERLAY, (*AMBER, int(flash * 0.85 * 255)),
                           (int(px(p[0])), int(py(p[1]))), int(9 + t * 50), 2)

    # 当前位置
    r = max(5, min(9, cell * 0.22))
    for p, color in ((A[-1], BLUE_400), (B[-1], ORANGE_400)):
        x, y = int(px(p[0])), int(py(p[1]))
        pygame.draw.circle(OVERLAY, color, (x, y), r)
        pygame.draw.circle(OVERLAY, DOT_RING, (x, y), r, 1)
        pygame.draw.circle(OVERLAY, DOT_HI, (x, y), max(1, int(r * 0.42)))

def draw_button(ps, btn_id, rect):
    label = BUTTON_LABELS[btn_id]
    is_primary = btn_id == 'step'
    is_on = BUTTON_ON.get(btn_id, False)
    hover = hover_btn == btn_id and not mouse_down
    press = pressed_btn == btn_id and mouse_down
    r = rect.inflate(-2, -2) if press else rect

    if is_primary:
        bg = PAPER_100 if hover else PAPER_50
        pygame.draw.rect(ps, bg, r, border_radius=BTN_R)
        # 标签 + 键帽居中
        t = text(label, 'ui13', INK_900)
        k = text('空格', 'ui11', INK_900)
        total = t.get_width() + 4 + k.get_width() + 8
        cx = r.centerx - total // 2
        ps.blit(t, (cx, r.centery - t.get_height() // 2))
        kx = cx + t.get_width() + 4
        krect = pygame.Rect(kx, r.centery - 9, k.get_width() + 8, 18)
        pygame.draw.rect(ps, (0, 0, 0, 0), krect, border_radius=4)
        pygame.draw.rect(ps, (0, 0, 0, 77), krect, 1, border_radius=4)
        ps.blit(k, (kx + 4, r.centery - k.get_height() // 2))
    else:
        if is_on:
            bg, border, fg = (255, 255, 255, 26), (255, 255, 255, 40), PAPER_50
        elif hover:
            bg, border, fg = (255, 255, 255, 20), LINE, PAPER_50
        else:
            bg, border, fg = (255, 255, 255, 10), LINE, SLATE_300
        pygame.draw.rect(ps, bg, r, border_radius=BTN_R)
        pygame.draw.rect(ps, border, r, 1, border_radius=BTN_R)
        t = text(label, 'ui13', fg)
        ps.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))

def draw_panel():
    ps = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
    pygame.draw.rect(ps, (*PANEL, PANEL_A), (0, 0, PANEL_W, PANEL_H), border_radius=16)
    pygame.draw.rect(ps, LINE, (0, 0, PANEL_W, PANEL_H), 1, border_radius=16)

    x0 = PANEL_PAD
    content_w = PANEL_W - PANEL_PAD * 2
    y = PANEL_PAD

    # 标题：mark + 文字
    m = [(2, 14), (6, 10), (8, 8)]
    pygame.draw.lines(ps, BLUE_400, False, [(a + x0, b + y + 2) for a, b in m], 2)
    m = [(14, 2), (10, 6), (8, 8)]
    pygame.draw.lines(ps, ORANGE_400, False, [(a + x0, b + y + 2) for a, b in m], 2)
    pygame.draw.circle(ps, AMBER, (x0 + 8, y + 10), 2)
    ps.blit(text('两个随机游走的人', 'title', PAPER_50), (x0 + 24, y + 10 - F['title'].get_height() // 2))
    y += max(20, F['title'].get_linesize()) + 4

    # 副标题
    for line in wrap('两人从同一点出发，每步随机走一格，轨迹一直保留。', 'ui12', content_w):
        ps.blit(text(line, 'ui12', SLATE_500), (x0, y))
        y += F['ui12'].get_linesize()
    y += 16

    # 按钮
    for btn_id in ('step', 'auto', 'reset', 'bg', 'bgreset'):
        draw_button(ps, btn_id, BUTTONS[btn_id].move(-PANEL_X, -PANEL_Y))
    y = BUTTONS['bgreset'].bottom - PANEL_Y + 16

    # 统计
    stats = [('步数', str(steps)), ('直线距离', '%.1f' % math.hypot(A[-1][0] - B[-1][0], A[-1][1] - B[-1][1])),
             ('相遇次数', str(meetings)), ('最近一次相遇', '—' if last_meet is None else '第 %d 步' % last_meet)]
    x1 = x0 + content_w
    for label, value in stats:
        ps.blit(text(label, 'ui13', SLATE_500), (x0, y))
        v = render_value(value)
        ps.blit(v, (x1 - v.get_width(), y))
        y += 28
    y += 16

    # 图例
    pygame.draw.line(ps, LINE, (x0, y), (x0 + content_w, y))
    y += 12
    pygame.draw.circle(ps, BLUE_400, (x0 + 4, y + 5), 4)
    ps.blit(text('甲', 'ui12', SLATE_400), (x0 + 14, y))
    pygame.draw.circle(ps, ORANGE_400, (x0 + 56, y + 5), 4)
    ps.blit(text('乙', 'ui12', SLATE_400), (x0 + 66, y))

    screen.blit(ps, (PANEL_X, PANEL_Y))

def draw_toast():
    if toast_msg is None:
        return
    dt = time.time() - toast_t
    if dt > 2.5:
        return
    a_in = min(1.0, dt / 0.3)
    a = a_in * (1.0 if dt <= 2.2 else max(0.0, 1 - (dt - 2.2) / 0.3))
    rise = 4 * (1 - a_in)
    y = PANEL_Y + PANEL_H + 8 + rise

    ts = pygame.Surface((PANEL_W, TOAST_H), pygame.SRCALPHA)
    pygame.draw.rect(ts, (*PANEL, int(245 * a)), (0, 0, PANEL_W, TOAST_H), border_radius=8)
    pygame.draw.rect(ts, (*AMBER, int(77 * a)), (0, 0, PANEL_W, TOAST_H), 1, border_radius=8)
    pygame.draw.circle(ts, (*AMBER, int(255 * a)), (16, TOAST_H // 2), 3)
    t = text(toast_msg, 'ui12', AMBER_200).copy()
    t.set_alpha(int(255 * a))
    ts.blit(t, (26, TOAST_H // 2 - t.get_height() // 2))
    screen.blit(ts, (PANEL_X, y))

def draw():
    screen.blit(BG_SURF, (0, 0))
    draw_canvas()
    screen.blit(OVERLAY, (0, 0))
    draw_panel()
    draw_toast()

# ============================================================
# 交互
# ============================================================
def hit_test(pos):
    for btn_id, rect in BUTTONS.items():
        if rect.collidepoint(pos):
            return btn_id
    return None

def on_click(btn_id):
    global auto, bg_img, auto_acc
    if btn_id == 'step':
        do_step()
    elif btn_id == 'auto':
        auto = not auto
        BUTTON_LABELS['auto'] = '暂停' if auto else '自动'
        BUTTON_ON['auto'] = auto
        auto_acc = 0
    elif btn_id == 'reset':
        reset()
    elif btn_id == 'bg':
        pick_background()
    elif btn_id == 'bgreset':
        bg_img = bg_default  # 默认图加载失败时为 None → 回到暗色晕影
        toast('已恢复默认背景')
        rebuild_bg()

# ============================================================
# 主循环
# ============================================================
def main():
    global screen, mouse_down, pressed_btn, hover_btn, auto_acc, flash
    pygame.init()
    pygame.display.set_caption('随机游走 · 两个人还能再相遇吗')
    pygame.key.set_repeat(250, 60)

    for key, kind, size in (('title', 'cjk', 14),
                            ('ui13', 'cjk', 13),
                            ('ui12', 'cjk', 12),
                            ('ui11', 'cjk', 11),
                            ('mono13', 'mono', 13)):
        F[key] = load_font(kind, size)

    layout_panel()
    resize(W, H)
    reset()
    set_bg(DEFAULT_BG, silent=True)  # 静默加载默认背景（传奇.png）

    clock = pygame.time.Clock()
    running = True
    while running:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.VIDEORESIZE:
                resize(e.w, e.h)
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE:
                    do_step()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mouse_down = True
                pressed_btn = hit_test(e.pos)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                mouse_down = False
                b = hit_test(e.pos)
                if b is not None and b == pressed_btn:
                    on_click(b)
                pressed_btn = None
            elif e.type == pygame.DROPFILE:
                set_bg(e.file)  # 拖图片进窗口直接换背景

        if auto:
            auto_acc += clock.get_time()
            while auto_acc >= AUTO_DELAY:
                auto_acc -= AUTO_DELAY
                do_step()

        if flash > 0:
            flash *= 0.93
            if flash < 0.01:
                flash = 0.0

        hover_btn = hit_test(pygame.mouse.get_pos())
        draw()
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
