#!/usr/bin/env python3
"""Draw the README images into docs/img: hero, states and flow, in light and dark, English and Korean.

    python3 tools/make-images.py

Everything shown is made up (host gpu-box, sessions train and eval); nothing is captured from a real screen.
"""
import os
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "img")

SANS = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Helvetica Neue', Arial, sans-serif"
MONO = "'SF Mono', SFMono-Regular, Menlo, Consolas, 'D2Coding', 'Apple SD Gothic Neo', monospace"

THEMES = {
    "light": dict(window="#FFFFFF", term="#FCFCFB", side="#F2F2F5", bar="#ECECEF", line="#DEDEE3",
                  text="#1D1D1F", text2="#6B6B72", dim="#8C9098", sel="#2F6FE4", seltext="#FFFFFF",
                  seltext2="#DCE7FF", blue="#2F6FE4", grey="#8E8E93", green="#1F9D55", orange="#C9653F",
                  toast="#FFFFFF", shadow="0.16", chip="#FFFFFF", panel="#F6F6F8", flow="#2F6FE4",
                  box="#E7EEFC"),
    "dark": dict(window="#1E1E20", term="#19191B", side="#252528", bar="#2B2B2F", line="#3A3A3F",
                 text="#F2F2F7", text2="#A1A1A8", dim="#7D828C", sel="#2F6FE4", seltext="#FFFFFF",
                 seltext2="#D6E3FF", blue="#5B95FF", grey="#8E8E93", green="#3FB871", orange="#E08A65",
                 toast="#2C2C30", shadow="0.55", chip="#2B2B2F", panel="#212124", flow="#5B95FF",
                 box="#1F2B45"),
}

TEXT = {
    "en": dict(
        idle="idle", needs="needs input", m12="12m", m13="13m", m3="3m", task="retrain on v2 data",
        task2="compare checkpoints", t_input2="Claude needs input · eval",
        t_input="Claude needs input · train", b_input="Claude needs your permission to use Bash",
        t_done="Claude finished · train", b_done="Validation loss went from 0.41 to 0.32.",
        perm_title="Bash command", perm_q="Do you want to proceed?", yes="1. Yes", no="2. No",
        final="Retrained on v2. Validation loss went from 0.41 to 0.32.",
        s_run="Running", s_in="Needs input", s_idle="Idle",
        c_run="Working on your prompt, with the time it has taken",
        c_in="Waiting for a permission or an answer",
        c_idle="Finished, or no Claude in this tab",
        remote="Remote host", remote2="Linux, over SSH or Eternal Terminal",
        mac="Your Mac", mac2="macOS, cmux",
        f_tmux="tmux session  train", f_agent="Claude Code  ·  Codex", f_hook="hook.py",
        f_hook2="on start, finish, wait", f_events="events.jsonl",
        f_watch="watcher", f_watch2="launchd, one per host",
        f_cmux="cmux notify  ·  set-status",
        f_out1="tab ring + banner", f_out2="sidebar status",
        f_link="ssh  ·  tail -F",
    ),
    "ko": dict(
        idle="대기", needs="확인 필요", m12="12분", m13="13분", m3="3분", task="v2 데이터로 다시 학습",
        task2="체크포인트 비교", t_input2="Claude 확인 필요 · eval",
        t_input="Claude 확인 필요 · train", b_input="Claude needs your permission to use Bash",
        t_done="Claude 완료 · train", b_done="검증 손실이 0.41 에서 0.32 로 줄었어요.",
        perm_title="Bash command", perm_q="Do you want to proceed?", yes="1. Yes", no="2. No",
        final="v2 로 다시 학습했어요. 검증 손실이 0.41 에서 0.32 로 줄었어요.",
        s_run="Running", s_in="Needs input", s_idle="Idle",
        c_run="질문을 받아 일하는 중, 일한 시간과 함께",
        c_in="권한이나 답을 기다리는 중",
        c_idle="일을 마쳤거나 이 탭에 Claude 가 없음",
        remote="원격 장비", remote2="Linux, SSH 나 Eternal Terminal 로 접속",
        mac="내 맥", mac2="macOS, cmux",
        f_tmux="tmux 세션  train", f_agent="Claude Code  ·  Codex", f_hook="hook.py",
        f_hook2="시작, 끝, 기다림마다", f_events="events.jsonl",
        f_watch="감시 프로그램", f_watch2="launchd, 장비마다 하나",
        f_cmux="cmux notify  ·  set-status",
        f_out1="탭 테두리 + 배너", f_out2="사이드바 상태",
        f_link="ssh  ·  tail -F",
    ),
}


def fit(s, width, size):
    """Cut s with an ellipsis so it fits about `width` px at font `size` (the sidebar truncates the same way)."""
    def w(ch):
        return size * (1.0 if ord(ch) > 0x2E80 else 0.56 if ch not in "il.·' " else 0.3)
    total = 0.0
    for i, ch in enumerate(s):
        total += w(ch)
        if total > width:
            return s[:max(i - 1, 1)].rstrip() + "…"
    return s


def esc(s):
    return escape(s, {'"': "&quot;"})


# ---------------------------------------------------------------- icons (drawn, 16x16 box)
def bolt(x, y, color, s=1.0):
    return ('<path transform="translate(%g %g) scale(%g)" fill="%s" '
            'd="M9.2 0.8 L2.6 9.1 H7.3 L6.5 15.2 L13.4 6.7 H8.6 Z"/>' % (x, y, s, color))


def bell(x, y, color, s=1.0):
    return ('<path transform="translate(%g %g) scale(%g)" fill="%s" '
            'd="M8 1.2c-2.6 0-4.4 2-4.4 4.6v2.9L2.2 11v0.9h11.6V11l-1.4-2.3V5.8C12.4 3.2 10.6 1.2 8 1.2z'
            'M6.1 13a1.9 1.9 0 0 0 3.8 0z"/>' % (x, y, s, color))


def pause(x, y, color, inner, s=1.0):
    return ('<g transform="translate(%g %g) scale(%g)"><circle cx="8" cy="8" r="7" fill="%s"/>'
            '<rect x="5.4" y="4.8" width="1.8" height="6.4" rx="0.6" fill="%s"/>'
            '<rect x="8.8" y="4.8" width="1.8" height="6.4" rx="0.6" fill="%s"/></g>' % (x, y, s, color, inner, inner))


def text(x, y, s, size, color, weight=400, family=SANS, anchor="start", extra=""):
    return ('<text x="%g" y="%g" font-family="%s" font-size="%g" font-weight="%d" fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, esc(family), size, weight, color, anchor, extra, esc(s)))


def svg(w, h, body, style="", title=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">\n'
            '<title>%s</title>\n<style>%s</style>\n%s\n</svg>\n' % (w, h, w, h, esc(title), esc(title), style, body))


# ---------------------------------------------------------------- hero (animated)
CYCLE = 16  # seconds


def show(name, a, b, slide=False, fade=0.8):
    """Keyframes that make an element visible from a% to b% of the cycle."""
    hide = "opacity:0;" + ("transform:translateX(26px);" if slide else "")
    shown = "opacity:1;" + ("transform:translateX(0);" if slide else "")
    pts = []
    if a > 0:
        pts.append("0%%,%g%%{%s}" % (a, hide))
        pts.append("%g%%{%s animation-timing-function:ease-in;}" % (min(a + fade * 2, b), shown))
    else:
        pts.append("0%%{%s}" % shown)
    if b < 100:
        pts.append("%g%%{%s}" % (b, shown))
        pts.append("%g%%,100%%{%s}" % (min(b + fade, 100), "opacity:0;" + ("transform:translateX(12px);" if slide else "")))
    else:
        pts.append("100%%{%s}" % shown)
    ease = "cubic-bezier(.16,1,.3,1)"
    return ("@keyframes %s{%s}\n.%s{animation:%s %ds %s infinite;opacity:0}\n"
            % (name, "".join(pts), name, name, CYCLE, ease))


def hero(theme, lang):
    """You work in a local workspace; the remote one further down the sidebar reports on its own."""
    c, t = THEMES[theme], TEXT[lang]
    W, H = 1000, 480
    wx, wy, ww, wh = 24, 14, 952, 440
    sx, sw = wx, 262             # sidebar
    mx = sx + sw                 # main area
    ty = wy + 38                 # under the title bar
    tab_h = 34
    body = []
    style = []

    body.append('<defs><filter id="sh" x="-10%%" y="-10%%" width="120%%" height="130%%">'
                '<feDropShadow dx="0" dy="10" stdDeviation="13" flood-color="#000" flood-opacity="%s"/></filter>'
                '<filter id="tsh" x="-20%%" y="-30%%" width="140%%" height="170%%">'
                '<feDropShadow dx="0" dy="6" stdDeviation="9" flood-color="#000" flood-opacity="%s"/></filter>'
                '<clipPath id="win"><rect x="%d" y="%d" width="%d" height="%d" rx="12"/></clipPath></defs>'
                % (c["shadow"], c["shadow"], wx, wy, ww, wh))
    body.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s" filter="url(#sh)"/>' % (wx, wy, ww, wh, c["window"]))
    body.append('<g clip-path="url(#win)">')
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (sx, wy, sw, wh, c["side"]))
    body.append('<rect x="%d" y="%d" width="%d" height="38" fill="%s"/>' % (mx, wy, ww - sw, c["bar"]))
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        body.append('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (wx + 20 + i * 20, wy + 19, col))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx + 0.5, wy, mx + 0.5, wy + wh, c["line"]))
    body.append(text(mx + 18, wy + 24, "web-app", 12.5, c["text2"], 600))

    bx, bw = sx + 10, sw - 20
    # workspace 1: the one you are working in (local)
    by = ty + 10
    body.append('<rect x="%d" y="%d" width="%d" height="62" rx="9" fill="%s"/>' % (bx, by, bw, c["sel"]))
    body.append(text(bx + 14, by + 24, "web-app", 13.5, c["seltext"], 650))
    body.append(text(bx + 14, by + 43, "~/code/web-app", 11.5, c["seltext2"], 500))

    # workspace 2: the remote one. It is not selected; it speaks up by itself.
    ry = by + 76
    rh = 98
    for name, a, b in (("hl1", 30, 100),):
        style.append(show(name, a, b, fade=0.6))
    body.append('<rect class="hl1" x="%d" y="%d" width="%d" height="%d" rx="9" fill="%s" stroke="%s" stroke-width="1.6"/>'
                % (bx + 0.8, ry + 0.8, bw - 1.6, rh - 1.6, c["box"], c["blue"]))
    body.append(text(bx + 14, ry + 24, "ml-research", 13.5, c["text"], 650))
    body.append(text(bx + 14, ry + 43, "gpu-box", 11.5, c["text2"], 500))
    # unread badge next to the title
    for name, a, b, n in (("bd1", 30, 60, "1"), ("bd2", 60, 100, "2")):
        style.append(show(name, a, b, fade=0.5))
        body.append('<g class="%s"><rect x="%d" y="%d" width="22" height="18" rx="9" fill="%s"/>%s</g>'
                    % (name, bx + bw - 34, ry + 11, c["blue"], text(bx + bw - 23, ry + 24, n, 11.5, "#FFFFFF", 700, anchor="middle")))
    r1, r2 = ry + 64, ry + 84
    tw = bw - 44
    rows = [
        ("tRun", bolt(bx + 12, r1 - 11, c["blue"], 0.8), "train · %s · %s" % (t["m12"], t["task"]), 0, 30, c["text"]),
        ("tIdle", pause(bx + 12, r1 - 11, c["grey"], c["side"], 0.8), "train · %s" % t["idle"], 30, 100, c["text2"]),
        ("eRun", bolt(bx + 12, r2 - 11, c["blue"], 0.8), "eval · %s · %s" % (t["m3"], t["task2"]), 0, 60, c["text"]),
        ("eIn", bell(bx + 12, r2 - 11, c["blue"], 0.8), "eval · %s · %s" % (t["needs"], t["task2"]), 60, 100, c["text"]),
    ]
    for name, icon, label, a, b, col in rows:
        style.append(show(name, a, b, fade=0.6))
        y = r1 if name[0] == "t" else r2
        body.append('<g class="%s">%s%s</g>' % (name, icon, text(bx + 32, y, fit(label, tw, 11.5), 11.5, col, 500)))

    # workspace 3
    y3 = ry + rh + 14
    body.append(text(bx + 14, y3 + 18, "notes", 13.5, c["text"], 650))
    body.append(text(bx + 14, y3 + 36, "~/notes", 11.5, c["text2"], 500))

    # tab bar: local tabs
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (mx, ty, ww - sw, tab_h, c["side"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx, ty + 0.5, wx + ww, ty + 0.5, c["line"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx, ty + tab_h - 0.5, wx + ww, ty + tab_h - 0.5, c["line"]))
    body.append('<rect x="%d" y="%d" width="120" height="%d" fill="%s"/>' % (mx, ty + 1, tab_h - 1, c["term"]))
    body.append(text(mx + 18, ty + 22, "zsh", 12.5, c["text"], 600))
    body.append(text(mx + 138, ty + 22, "dev server", 12.5, c["text2"], 500))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx + 120.5, ty, mx + 120.5, ty + tab_h, c["line"]))

    # terminal: your own local work
    tx, top = mx + 22, ty + tab_h
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (mx, top, ww - sw, wh - (top - wy), c["term"]))
    lh, fs, cw = 21, 12.5, 7.53

    def mono(x, yy, s, color, weight=400):
        return text(x, yy, s, fs, color, weight, MONO, extra=' xml:space="preserve"')

    def line(name, a, parts, yy):
        g = "".join(mono(x, yy, s, col, w) for x, s, col, w in parts)
        if name:
            style.append(show(name, a, 100, fade=0.4))
            return '<g class="%s">%s</g>' % (name, g)
        return g

    p = "~/code/web-app $ "
    y = top + 30
    body.append(line(None, 0, [(tx, p, c["dim"], 400), (tx + cw * len(p), "npm test", c["text"], 400)], y))
    y += lh
    body.append(line("l1", 4, [(tx, " PASS ", c["green"], 600), (tx + cw * 7, "src/cart.test.ts", c["text2"], 400)], y))
    y += lh
    body.append(line("l2", 8, [(tx, " PASS ", c["green"], 600), (tx + cw * 7, "src/checkout.test.ts", c["text2"], 400)], y))
    y += lh
    body.append(line("l3", 13, [(tx, "Tests: ", c["text"], 600), (tx + cw * 7, "128 passed, 128 total", c["green"], 400)], y))
    y += lh * 1.5
    body.append(line("l4", 22, [(tx, p, c["dim"], 400), (tx + cw * len(p), 'git commit -am "fix cart totals"', c["text"], 400)], y))
    y += lh
    body.append(line("l5", 34, [(tx, "[main 3f2a91c] fix cart totals", c["text2"], 400)], y))
    y += lh
    body.append(line("l6", 36, [(tx, " 2 files changed, 14 insertions(+), 3 deletions(-)", c["text2"], 400)], y))
    y += lh * 1.5
    body.append(line("l7", 44, [(tx, p, c["dim"], 400), (tx + cw * len(p), "npm run dev", c["text"], 400)], y))
    y += lh
    body.append(line("l8", 52, [(tx, "  ready in 412 ms", c["text2"], 400)], y))
    y += lh
    body.append(line("l9", 53, [(tx, "  Local:  ", c["text2"], 400), (tx + cw * 10, "http://localhost:5173/", c["blue"], 400)], y))
    style.append("@keyframes caret{0%,49%{opacity:1}50%,100%{opacity:0}}.caret{animation:caret 1.1s steps(1) infinite}\n")
    style.append(show("cw", 54, 100, fade=0.3))
    body.append('<g class="cw"><rect class="caret" x="%g" y="%d" width="7.5" height="15" fill="%s"/></g>' % (tx, y + lh - 12, c["text2"]))
    body.append('</g>')

    # macOS banners from cmux
    def toast(name, a, b, title, sub, msg):
        style.append(show(name, a, b, slide=True, fade=0.7))
        x0, y0, w0, h0 = wx + ww - 352, wy + 52, 334, 76
        return ('<g class="%s"><rect x="%d" y="%d" width="%d" height="%d" rx="16" fill="%s" filter="url(#tsh)"/>'
                '<rect x="%d" y="%d" width="38" height="38" rx="9" fill="%s"/>'
                '<path d="M%d %d l7 6 -7 6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
                '<rect x="%d" y="%d" width="9" height="2.6" rx="1.3" fill="#fff"/>%s%s%s</g>'
                % (name, x0, y0, w0, h0, c["toast"], x0 + 14, y0 + 19, "#26262B",
                   x0 + 24, y0 + 31, x0 + 34, y0 + 42,
                   text(x0 + 64, y0 + 25, title, 13, c["text"], 650),
                   text(x0 + 64, y0 + 43, sub, 12, c["text2"], 500),
                   text(x0 + 64, y0 + 61, msg, 12, c["text"], 400)))
    body.append(toast("tsDone", 30.5, 54, t["t_done"], "gpu-box", t["b_done"]))
    body.append(toast("tsIn", 60.5, 90, t["t_input2"], "gpu-box", t["b_input"]))

    style.append("@media (prefers-reduced-motion: reduce){*{animation:none!important}"
                 ".hl1,.bd2,.tIdle,.eIn,.l1,.l2,.l3,.l4,.l5,.l6,.l7,.l8,.l9,.tsIn{opacity:1!important;transform:none!important}}\n")
    title = ("cmux: while you work in a local workspace, the remote ml-research workspace reports that train finished "
             "and eval needs input") if lang == "en" else \
        "cmux: 로컬 작업 공간에서 일하는 동안, 원격 ml-research 작업 공간이 train 완료와 eval 확인 필요를 알린다"
    return svg(W, H, "\n".join(body), "".join(style), title)


# ---------------------------------------------------------------- states
def states(theme, lang):
    c, t = THEMES[theme], TEXT[lang]
    W, H = 1000, 156
    col = W / 3.0
    body = []
    items = [
        (t["s_run"], bolt, "train · %s · %s" % (t["m12"], t["task"]), t["c_run"], c["blue"]),
        (t["s_in"], bell, "train · %s" % t["needs"], t["c_in"], c["blue"]),
        (t["s_idle"], None, "train · %s" % t["idle"], t["c_idle"], c["grey"]),
    ]
    for i, (name, icon, row, cap, color) in enumerate(items):
        x = 8 + i * col
        w = col - 16
        body.append(text(x + 2, 22, name, 15, c["text"], 700))
        body.append('<rect x="%g" y="38" width="%g" height="46" rx="10" fill="%s" stroke="%s"/>' % (x, w, c["side"], c["line"]))
        if icon:
            body.append(icon(x + 14, 53, color, 1.0))
        else:
            body.append(pause(x + 14, 53, color, c["side"], 1.0))
        body.append(text(x + 40, 66, row, 13.5, c["text"], 500))
        body.append(text(x + 2, 112, cap, 13, c["text2"], 400))
    title = "Sidebar states: Running, Needs input, Idle"
    return svg(W, H, "\n".join(body), "", title)


# ---------------------------------------------------------------- flow
def flow(theme, lang):
    c, t = THEMES[theme], TEXT[lang]
    W, H = 1000, 330
    body = []
    style = ("@keyframes dash{to{stroke-dashoffset:-28}}.flowline{animation:dash 1.2s linear infinite}"
             "@media (prefers-reduced-motion: reduce){.flowline{animation:none}}")
    body.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>' % c["text2"])

    def panel(x, title, sub):
        return ('<rect x="%d" y="10" width="380" height="310" rx="16" fill="%s" stroke="%s"/>%s%s'
                % (x, c["panel"], c["line"], text(x + 22, 42, title, 16, c["text"], 700),
                   text(x + 22, 62, sub, 12.5, c["text2"], 400)))

    def chip(x, y, label, sub=None, mono_=False, accent=False):
        w = 336
        fill = c["box"] if accent else c["chip"]
        out = '<rect x="%d" y="%d" width="%d" height="44" rx="10" fill="%s" stroke="%s"/>' % (x, y, w, fill, c["line"])
        out += text(x + 16, y + 27, label, 13.5, c["text"], 600, MONO if mono_ else SANS)
        if sub:
            out += text(x + w - 16, y + 27, sub, 12, c["text2"], 400, anchor="end")
        return out

    def down(x, y1, y2):
        return '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" marker-end="url(#ar)"/>' % (x, y1, x, y2, c["text2"])

    lx, rx = 20, 600
    body.append(panel(lx, t["remote"], t["remote2"]))
    body.append(panel(rx, t["mac"], t["mac2"]))
    ys = (84, 142, 200, 258)
    body.append(chip(lx + 22, ys[0], t["f_tmux"]))
    body.append(chip(lx + 22, ys[1], t["f_agent"]))
    body.append(chip(lx + 22, ys[2], t["f_hook"], t["f_hook2"], mono_=True))
    body.append(chip(lx + 22, ys[3], t["f_events"], mono_=True, accent=True))
    for a, b in zip(ys, ys[1:]):
        body.append(down(lx + 190, a + 44, b - 2))
    # right side flows upward: watcher at the bottom, results at the top
    body.append(chip(rx + 22, ys[3], t["f_watch"], t["f_watch2"], accent=True))
    body.append(chip(rx + 22, ys[2], t["f_cmux"], mono_=True))
    body.append('<rect x="%d" y="%d" width="160" height="44" rx="10" fill="%s" stroke="%s"/>' % (rx + 22, ys[0] + 29, c["chip"], c["line"]))
    body.append('<rect x="%d" y="%d" width="160" height="44" rx="10" fill="%s" stroke="%s"/>' % (rx + 198, ys[0] + 29, c["chip"], c["line"]))
    body.append(text(rx + 102, ys[0] + 56, t["f_out1"], 13, c["text"], 600, anchor="middle"))
    body.append(text(rx + 278, ys[0] + 56, t["f_out2"], 13, c["text"], 600, anchor="middle"))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" marker-end="url(#ar)"/>'
                % (rx + 190, ys[3], rx + 190, ys[2] + 46, c["text2"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" marker-end="url(#ar)"/>'
                % (rx + 120, ys[2], rx + 102, ys[0] + 75, c["text2"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.5" marker-end="url(#ar)"/>'
                % (rx + 260, ys[2], rx + 278, ys[0] + 75, c["text2"]))
    # the link between the two
    y = ys[3] + 22
    body.append('<line class="flowline" x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.4" stroke-dasharray="8 6" stroke-linecap="round"/>'
                % (lx + 360, y, rx + 20, y, c["flow"]))
    body.append(text((lx + 360 + rx + 20) / 2, y - 12, t["f_link"], 13, c["flow"], 600, MONO, anchor="middle"))
    title = "How it works: a hook on the remote host writes events, the Mac follows them over SSH and drives cmux"
    return svg(W, H, "\n".join(body), style, title)


def main():
    os.makedirs(OUT, exist_ok=True)
    for lang in ("en", "ko"):
        suffix = "" if lang == "en" else ".ko"
        for theme in ("light", "dark"):
            for name, fn in (("hero", hero), ("states", states), ("flow", flow)):
                path = os.path.join(OUT, "%s-%s%s.svg" % (name, theme, suffix))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fn(theme, lang))
                print(os.path.relpath(path))


if __name__ == "__main__":
    main()
