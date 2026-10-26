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
        idle="idle", needs="needs input", m12="12m", m13="13m", task="retrain on v2 data",
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
        idle="대기", needs="확인 필요", m12="12분", m13="13분", task="v2 데이터로 다시 학습",
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
    # title bar + sidebar
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (sx, wy, sw, wh, c["side"]))
    body.append('<rect x="%d" y="%d" width="%d" height="38" fill="%s"/>' % (mx, wy, ww - sw, c["bar"]))
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        body.append('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (wx + 20 + i * 20, wy + 19, col))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx + 0.5, wy, mx + 0.5, wy + wh, c["line"]))
    body.append(text(mx + 18, wy + 24, "ml-research", 12.5, c["text2"], 600))

    # sidebar: workspace 1 (selected)
    bx, by, bw = sx + 10, ty + 10, sw - 20
    body.append('<rect x="%d" y="%d" width="%d" height="104" rx="9" fill="%s"/>' % (bx, by, bw, c["sel"]))
    body.append(text(bx + 14, by + 22, "ml-research", 13.5, c["seltext"], 650))
    body.append(text(bx + 14, by + 40, "gpu-box", 11.5, c["seltext2"], 500))
    r1 = by + 60   # first status row baseline
    r2 = by + 82
    white = c["seltext"]
    # train row: four states
    rows = [
        ("rRun1", bolt(bx + 12, r1 - 11, white, 0.8), "train · %s · %s" % (t["m12"], t["task"]), 0, 30),
        ("rIn", bell(bx + 12, r1 - 11, white, 0.8), "train · %s · %s" % (t["needs"], t["task"]), 30, 48),
        ("rRun2", bolt(bx + 12, r1 - 11, white, 0.8), "train · %s · %s" % (t["m13"], t["task"]), 48, 70),
        ("rIdle", pause(bx + 12, r1 - 11, "rgba(255,255,255,.85)", c["sel"], 0.8), "train · %s" % t["idle"], 70, 100),
    ]
    for name, icon, label, a, b in rows:
        style.append(show(name, a, b, fade=0.6))
        body.append('<g class="%s">%s%s</g>' % (name, icon, text(bx + 32, r1, fit(label, bw - 44, 11.5), 11.5, white, 500)))
    body.append(pause(bx + 12, r2 - 11, "rgba(255,255,255,.85)", c["sel"], 0.8))
    body.append(text(bx + 32, r2, "eval · %s" % t["idle"], 11.5, white, 500))

    # workspace 2 and 3
    y2 = by + 122
    body.append(text(bx + 14, y2 + 18, "web-app", 13.5, c["text"], 650))
    body.append(text(bx + 14, y2 + 36, "staging", 11.5, c["text2"], 500))
    body.append(pause(bx + 12, y2 + 56 - 11, c["grey"], c["side"], 0.8))
    body.append(text(bx + 32, y2 + 56, "api · %s" % t["idle"], 11.5, c["text2"], 500))
    y3 = y2 + 84
    body.append(text(bx + 14, y3 + 18, "notes", 13.5, c["text"], 650))
    body.append(text(bx + 14, y3 + 36, "~/notes", 11.5, c["text2"], 500))

    # tab bar
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (mx, ty, ww - sw, tab_h, c["side"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx, ty + 0.5, wx + ww, ty + 0.5, c["line"]))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx, ty + tab_h - 0.5, wx + ww, ty + tab_h - 0.5, c["line"]))
    body.append('<rect x="%d" y="%d" width="120" height="%d" fill="%s"/>' % (mx, ty + 1, tab_h - 1, c["term"]))
    body.append(text(mx + 18, ty + 22, "train", 12.5, c["text"], 600))
    body.append(text(mx + 138, ty + 22, "eval", 12.5, c["text2"], 500))
    body.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (mx + 120.5, ty, mx + 120.5, ty + tab_h, c["line"]))

    # terminal
    tx, top = mx + 22, ty + tab_h
    body.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (mx, top, ww - sw, wh - (top - wy), c["term"]))
    lh = 21
    y = top + 30
    fs = 12.5

    def mono(x, yy, s, color, weight=400):
        return text(x, yy, s, fs, color, weight, MONO, extra=' xml:space="preserve"')

    def line(name, a, parts, yy):
        g = "".join(mono(x, yy, s, col, w) for x, s, col, w in parts)
        if name:
            style.append(show(name, a, 100, fade=0.4))
            return '<g class="%s">%s</g>' % (name, g)
        return g

    cw = 7.53  # monospace advance at 12.5px
    body.append(line(None, 0, [(tx, "me@gpu-box:~/ml$ ", c["dim"], 400), (tx + cw * 17, "claude", c["text"], 400)], y))
    y += lh * 1.5
    body.append(line(None, 0, [(tx, "> ", c["dim"], 400), (tx + cw * 2, t["task"], c["text"], 600)], y))
    y += lh * 1.5
    body.append(line(None, 0, [(tx, "●", c["green"], 400), (tx + cw * 2, "Read", c["text"], 600),
                               (tx + cw * 6, "(data/v2/manifest.json)", c["text2"], 400)], y))
    y += lh * 1.4
    body.append(line("l1", 6, [(tx, "●", c["green"], 400), (tx + cw * 2, "Bash", c["text"], 600),
                               (tx + cw * 6, "(python train.py --data v2)", c["text2"], 400)], y))
    y += lh
    body.append(line("l2", 14, [(tx + cw * 2, "⎿  epoch 10/10  loss 0.31  done", c["dim"], 400)], y))
    y += lh * 1.4
    # permission prompt (30% - 48%)
    py = y - 15
    style.append(show("perm", 30, 48, fade=0.5))
    perm = ['<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="none" stroke="%s" stroke-width="1.4"/>'
            % (tx - 8, py, 470, lh * 5 + 22, c["orange"]),
            mono(tx + 6, py + 22, t["perm_title"], c["orange"], 600),
            mono(tx + 6, py + 22 + lh, "python eval.py --ckpt best", c["text"]),
            mono(tx + 6, py + 22 + lh * 2.3, t["perm_q"], c["text2"]),
            mono(tx + 6, py + 22 + lh * 3.3, "❯ " + t["yes"], c["blue"], 600),
            mono(tx + 6, py + 22 + lh * 4.3, "  " + t["no"], c["text2"])]
    body.append('<g class="perm">%s</g>' % "".join(perm))
    # after the permission
    body.append(line("l3", 49, [(tx, "●", c["green"], 400), (tx + cw * 2, "Bash", c["text"], 600),
                                (tx + cw * 6, "(python eval.py --ckpt best)", c["text2"], 400)], y))
    body.append(line("l4", 58, [(tx + cw * 2, "⎿  val loss 0.32  (was 0.41)", c["dim"], 400)], y + lh))
    body.append(line("l5", 70, [(tx, "●", c["text"], 400), (tx + cw * 2, t["final"], c["text"], 400)], y + lh * 2.6))
    # input box at the bottom
    iy = wy + wh - 46
    body.append('<rect x="%d" y="%d" width="%d" height="30" rx="7" fill="none" stroke="%s"/>' % (tx - 8, iy, ww - sw - 30, c["line"]))
    body.append(mono(tx + 4, iy + 20, ">", c["dim"]))
    style.append("@keyframes caret{0%,49%{opacity:1}50%,100%{opacity:0}}.caret{animation:caret 1.1s steps(1) infinite}\n")
    body.append('<rect class="caret" x="%g" y="%d" width="7.5" height="15" fill="%s"/>' % (tx + 4 + cw * 2, iy + 8, c["text2"]))
    # working spinner text while running
    for name, a, b in (("w1", 0, 30), ("w2", 48, 70)):
        style.append(show(name, a, b, fade=0.5))
        body.append('<g class="%s">%s</g>' % (name, mono(tx, iy - 14, "✻ Working…", c["orange"])))

    # pane ring (cmux marks the pane that has a new notification)
    for name, a, b in (("ring1", 30, 48), ("ring2", 70, 94)):
        style.append(show(name, a, b, fade=0.5))
        body.append('<rect class="%s" x="%d" y="%d" width="%d" height="%d" rx="3" fill="none" stroke="%s" stroke-width="2.5"/>'
                    % (name, mx + 2, top + 2, ww - sw - 4, wh - (top - wy) - 4, c["blue"]))
    body.append('</g>')

    # macOS banner
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
    body.append(toast("tIn", 30.5, 46, t["t_input"], "gpu-box", t["b_input"]))
    body.append(toast("tDone", 70.5, 92, t["t_done"], "gpu-box", t["b_done"]))

    style.append("@media (prefers-reduced-motion: reduce){*{animation:none!important}.rIdle,.l1,.l2,.l3,.l4,.l5,.tDone,.ring2{opacity:1!important;transform:none!important}}\n")
    title = "cmux window: a remote Claude Code session moves from Running to Needs input to Idle" if lang == "en" else \
        "cmux 창: 원격 Claude Code 세션이 Running, Needs input, Idle 로 바뀌는 모습"
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
