"""cmux-remote-notify remote setup: adds or removes the Claude Code hooks, the Codex hooks and
the Codex notify.

The Mac's `cmux-remote-notify install|uninstall` sends this file over SSH and runs it:

    python3 - install   [en|ko] < setup.py
    python3 - uninstall [en|ko] < setup.py

Only our own entries are touched; every other setting stays as it is. A file is copied to
<file>.bak.cmux-remote-notify.<time> before it changes.

This tool sends every notification itself, so the agents' own terminal notifications are turned
off on install (Claude Code preferredNotifChannel, Codex [tui] notifications); otherwise the same
turn would notify twice. Their previous values are kept in ~/.local/state/cmux-remote-notify/
stock.json and put back on uninstall.
"""
import copy
import json
import os
import re
import shutil
import sys
import time

MARK = "cmux-remote-notify"
HOME = os.path.expanduser("~")
HOOK = os.path.join(HOME, ".local", "share", MARK, "hook.py")
CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CODEX_CONFIG = os.path.join(HOME, ".codex", "config.toml")
CODEX_HOOKS = os.path.join(HOME, ".codex", "hooks.json")
# Codex hooks drive the status like Claude's. Codex runs them only after you trust them once
# (/hooks in Codex); until then the notify below still reports finished turns.
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PermissionRequest", "PostToolUse",
                "Stop", "Interrupt", "SessionEnd")
# Codex caps Interrupt and SessionEnd hooks at 3 seconds.
CODEX_TIMEOUTS = {"PostToolUse": 5, "Interrupt": 3, "SessionEnd": 3}
# Stop and Notification notify; the rest drive the sidebar status (Running, Needs input, Idle).
CLAUDE_EVENTS = ("Stop", "Notification", "UserPromptSubmit", "PostToolUse",
                 "StopFailure", "SessionStart", "SessionEnd")
# The hook that runs on every tool call gets a short timeout (hook.py returns at once mostly).
CLAUDE_TIMEOUTS = {"PostToolUse": 5}
CODEX_COMMENT = "# %s: tells the Mac's cmux tab when a Codex turn ends (remove with: cmux-remote-notify uninstall)" % MARK
STAMP = time.strftime("%Y%m%d-%H%M%S")
STOCK_STATE = os.path.join(HOME, ".local", "state", MARK, "stock.json")
OFF = "notifications_disabled"
# Marks the lines we write in the Codex config; it carries the line it replaced.
STOCK_MARK = "# %s: Codex's own notifications are off so a turn does not notify twice; uninstall puts back: " % MARK
LANG = "en"

TEXT = {
    "skip_claude": ("Claude Code: not installed, skipped", "Claude Code: 설치돼 있지 않아 건너뜀"),
    "skip_codex": ("Codex: not installed, skipped", "Codex: 설치돼 있지 않아 건너뜀"),
    "claude_same": ("Claude Code: nothing to change", "Claude Code: 바꿀 것 없음"),
    "codex_same": ("Codex: nothing to change", "Codex: 바꿀 것 없음"),
    "hooks_same": ("Codex hooks: nothing to change", "Codex 훅: 바꿀 것 없음"),
    "hooks_add": ("Codex hooks: added %d hooks (%s) to %s. Codex runs them once you trust them: "
                  "open Codex, type /hooks and trust the cmux-remote-notify hooks",
                  "Codex 훅: 훅 %d개 추가(%s), %s. Codex 에서 한 번 신뢰해야 돌아요: "
                  "Codex 를 열고 /hooks 에서 cmux-remote-notify 훅을 신뢰해 주세요"),
    "hooks_del": ("Codex hooks: removed hooks from %s", "Codex 훅: 훅 제거, %s"),
    "claude_add": ("Claude Code: added %d hooks (%s) to %s", "Claude Code: 훅 %d개 추가(%s), %s"),
    "claude_del": ("Claude Code: removed hooks from %s", "Claude Code: 훅 제거, %s"),
    "codex_other": ("Codex: another notify is already set, left alone",
                    "Codex: 이미 다른 notify 설정이 있어 건드리지 않음"),
    "codex_add": ("Codex: added notify to %s", "Codex: notify 추가, %s"),
    "codex_del": ("Codex: removed notify from %s", "Codex: notify 제거, %s"),
    "failed": ("%s: failed: %s", "%s: 실패: %s"),
    "claude_stock_off": ("Claude Code: turned off its own notifications (preferredNotifChannel) so nothing notifies twice",
                         "Claude Code: 자체 알림(preferredNotifChannel)을 껐어요, 알림이 두 번 오지 않게"),
    "claude_stock_back": ("Claude Code: put back its own notifications (preferredNotifChannel)",
                          "Claude Code: 자체 알림(preferredNotifChannel)을 원래대로 돌렸어요"),
    "codex_stock_off": ("Codex: turned off its own notifications ([tui] notifications) so nothing notifies twice",
                        "Codex: 자체 알림([tui] notifications)을 껐어요, 알림이 두 번 오지 않게"),
    "codex_stock_back": ("Codex: put back its own notifications ([tui] notifications)",
                         "Codex: 자체 알림([tui] notifications)을 원래대로 돌렸어요"),
}


def t(key, *args):
    text = TEXT[key][1 if LANG == "ko" else 0]
    return text % args if args else text


def save(path, text):
    if os.path.exists(path):
        shutil.copy2(path, "%s.bak.%s.%s" % (path, MARK, STAMP))
    tmp = "%s.%s.tmp" % (path, MARK)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def is_ours(hook):
    return isinstance(hook, dict) and MARK in str(hook.get("command", ""))


def merge_hooks(path, install, events, command, timeouts, matcher_events=()):
    """Add (install) or remove our entries in a Claude-style hooks file. Returns "same", "add"
    or "del". Other hooks, and lists that were empty to begin with, stay."""
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    before = copy.deepcopy(data)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept, removed = [], False
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(inner, list) and any(is_ours(h) for h in inner):
                removed = True
                rest = [h for h in inner if not is_ours(h)]
                if rest:
                    kept.append(dict(group, hooks=rest))
            else:
                kept.append(group)
        if removed:
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
    if install:
        for event in events:
            group = {"hooks": [{"type": "command", "command": command,
                                "timeout": timeouts.get(event, 10)}]}
            if event in matcher_events:
                group = dict({"matcher": ""}, **group)
            hooks.setdefault(event, []).append(group)
    if hooks or ("hooks" in before and (install or before["hooks"] == {})):
        data["hooks"] = hooks
    else:
        # Our entries were all there was: leave no empty "hooks" behind.
        data.pop("hooks", None)
    if data == before:
        return "same"
    save(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return "add" if install else "del"


def claude(install):
    if not os.path.isdir(os.path.dirname(CLAUDE_SETTINGS)):
        return t("skip_claude")
    done = merge_hooks(CLAUDE_SETTINGS, install, CLAUDE_EVENTS, "%s claude" % HOOK,
                       CLAUDE_TIMEOUTS, matcher_events=("PostToolUse",))
    if done == "same":
        return t("claude_same")
    if done == "add":
        return t("claude_add", len(CLAUDE_EVENTS), ", ".join(CLAUDE_EVENTS), CLAUDE_SETTINGS)
    return t("claude_del", CLAUDE_SETTINGS)


def codex_hooks(install):
    if not os.path.isdir(os.path.dirname(CODEX_HOOKS)):
        return t("skip_codex")
    done = merge_hooks(CODEX_HOOKS, install, CODEX_EVENTS, "%s codex-hook" % HOOK, CODEX_TIMEOUTS)
    if done == "same":
        return t("hooks_same")
    if done == "add":
        return t("hooks_add", len(CODEX_EVENTS), ", ".join(CODEX_EVENTS), CODEX_HOOKS)
    return t("hooks_del", CODEX_HOOKS)


def codex(install):
    if not os.path.isdir(os.path.dirname(CODEX_CONFIG)):
        return t("skip_codex")
    text = ""
    if os.path.exists(CODEX_CONFIG):
        with open(CODEX_CONFIG, encoding="utf-8") as f:
            text = f.read()
    lines = text.split("\n")
    # Older versions wrote the comment in Korean; any comment line carrying our mark is ours.
    kept = [l for l in lines
            if l.startswith(STOCK_MARK)
            or not (l.startswith("# " + MARK + ":") or (l.startswith("notify") and MARK in l))]
    if install:
        # notify is a top-level key, so it must come before the first [table].
        # A notify the user set themselves is left alone.
        first_table = next((i for i, l in enumerate(kept) if l.lstrip().startswith("[")), len(kept))
        if any(re.match(r"\s*notify\s*=", l) for l in kept[:first_table]):
            return t("codex_other")
        kept = [CODEX_COMMENT, "notify = [%s, \"codex\"]" % json.dumps(HOOK)] + kept
    new = "\n".join(kept)
    if new == text:
        return t("codex_same")
    save(CODEX_CONFIG, new)
    return t("codex_add" if install else "codex_del", CODEX_CONFIG)


def load_stock():
    try:
        with open(STOCK_STATE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_stock(state):
    os.makedirs(os.path.dirname(STOCK_STATE), exist_ok=True)
    with open(STOCK_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def claude_stock(install):
    """Turn Claude Code's own terminal notifications off (install) or back (uninstall)."""
    if not os.path.isdir(os.path.dirname(CLAUDE_SETTINGS)):
        return None
    data = {}
    if os.path.exists(CLAUDE_SETTINGS):
        with open(CLAUDE_SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
    state = load_stock()
    key = "preferredNotifChannel"
    if install:
        if data.get(key) == OFF:
            return None
        # Remember what it was only the first time, so installing again keeps the original.
        if "claude" not in state:
            state["claude"] = {"had": key in data, "value": data.get(key)}
            save_stock(state)
        data[key] = OFF
        save(CLAUDE_SETTINGS, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return t("claude_stock_off")
    was = state.pop("claude", None)
    if was is None:
        return None
    save_stock(state)
    # Changed by the user since: leave it.
    if data.get(key) != OFF:
        return None
    if was.get("had"):
        data[key] = was.get("value")
    else:
        data.pop(key, None)
    save(CLAUDE_SETTINGS, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return t("claude_stock_back")


def tui_range(lines):
    """(start, end) line indexes of the [tui] table body, or None."""
    start = next((i for i, l in enumerate(lines) if l.strip() == "[tui]"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    return start + 1, end


def codex_stock(install):
    """Turn Codex's own TUI notifications off (install) or back (uninstall)."""
    if not os.path.exists(CODEX_CONFIG):
        return None
    with open(CODEX_CONFIG, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    ours = [i for i, l in enumerate(lines) if l.startswith(STOCK_MARK)]
    if install:
        if ours:
            return None
        rng = tui_range(lines)
        top = next((i for i, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
        found = None
        if rng:
            found = next((i for i in range(*rng) if re.match(r"\s*notifications\s*=", lines[i])), None)
        if found is None:
            found = next((i for i in range(top) if re.match(r"\s*tui\.notifications\s*=", lines[i])), None)
        if found is not None:
            if re.match(r"\s*(tui\.)?notifications\s*=\s*false\s*(#.*)?$", lines[found]):
                return None
            was = lines[found]
            off = "tui.notifications = false" if lines[found].lstrip().startswith("tui.") else "notifications = false"
            lines[found:found + 1] = [STOCK_MARK + json.dumps({"was": was}), off]
        elif rng:
            lines[rng[0]:rng[0]] = [STOCK_MARK + json.dumps({"was": None}), "notifications = false"]
        else:
            if lines and lines[-1] != "":
                lines.append("")
            lines += ["[tui]", STOCK_MARK + json.dumps({"was": None, "table": True}), "notifications = false", ""]
        save(CODEX_CONFIG, "\n".join(lines))
        return t("codex_stock_off")
    if not ours:
        return None
    i = ours[0]
    try:
        info = json.loads(lines[i][len(STOCK_MARK):])
    except ValueError:
        info = {"was": None}
    nxt = i + 1 if i + 1 < len(lines) and re.match(r"\s*(tui\.)?notifications\s*=\s*false\s*$", lines[i + 1]) else None
    if nxt is None:
        # The user changed the line since: only drop our comment.
        del lines[i]
    elif info.get("was") is not None:
        lines[i:nxt + 1] = [info["was"]]
    elif info.get("table") and i > 0 and lines[i - 1].strip() == "[tui]" \
            and (nxt + 1 >= len(lines) or lines[nxt + 1].strip() == "" or lines[nxt + 1].lstrip().startswith("[")):
        lines[i - 1:nxt + 1] = []
        # and the blank line we put before the table
        k = i - 1
        if 0 < k < len(lines) and lines[k - 1] == "" and lines[k] == "":
            del lines[k]
    else:
        lines[i:nxt + 1] = []
    save(CODEX_CONFIG, "\n".join(lines))
    return t("codex_stock_back")


def main():
    global LANG
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if len(sys.argv) > 2 and sys.argv[2] in ("en", "ko"):
        LANG = sys.argv[2]
    if mode not in ("install", "uninstall"):
        print("usage: python3 setup.py install|uninstall [en|ko]", file=sys.stderr)
        return 2
    status = 0
    for step in (claude, claude_stock, codex_hooks, codex, codex_stock):
        try:
            out = step(mode == "install")
            if out:
                print(out)
        except Exception as e:
            print(t("failed", step.__name__, e))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
