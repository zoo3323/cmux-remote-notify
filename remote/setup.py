"""cmux-remote-notify remote setup: adds or removes the Claude Code hooks and the Codex notify.

The Mac's `cmux-remote-notify install|uninstall` sends this file over SSH and runs it:

    python3 - install   [en|ko] < setup.py
    python3 - uninstall [en|ko] < setup.py

Only our own entries are touched; every other setting stays as it is. A file is copied to
<file>.bak.cmux-remote-notify.<time> before it changes.
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
# Stop and Notification notify; the rest drive the sidebar status (Running, Needs input, Idle).
CLAUDE_EVENTS = ("Stop", "Notification", "UserPromptSubmit", "PostToolUse",
                 "StopFailure", "SessionStart", "SessionEnd")
# The hook that runs on every tool call gets a short timeout (hook.py returns at once mostly).
CLAUDE_TIMEOUTS = {"PostToolUse": 5}
CODEX_COMMENT = "# %s: tells the Mac's cmux tab when a Codex turn ends (remove with: cmux-remote-notify uninstall)" % MARK
STAMP = time.strftime("%Y%m%d-%H%M%S")
LANG = "en"

TEXT = {
    "skip_claude": ("Claude Code: not installed, skipped", "Claude Code: 설치돼 있지 않아 건너뜀"),
    "skip_codex": ("Codex: not installed, skipped", "Codex: 설치돼 있지 않아 건너뜀"),
    "claude_same": ("Claude Code: nothing to change", "Claude Code: 바꿀 것 없음"),
    "codex_same": ("Codex: nothing to change", "Codex: 바꿀 것 없음"),
    "claude_add": ("Claude Code: added %d hooks (%s) to %s", "Claude Code: 훅 %d개 추가(%s), %s"),
    "claude_del": ("Claude Code: removed hooks from %s", "Claude Code: 훅 제거, %s"),
    "codex_other": ("Codex: another notify is already set, left alone",
                    "Codex: 이미 다른 notify 설정이 있어 건드리지 않음"),
    "codex_add": ("Codex: added notify to %s", "Codex: notify 추가, %s"),
    "codex_del": ("Codex: removed notify from %s", "Codex: notify 제거, %s"),
    "failed": ("%s: failed: %s", "%s: 실패: %s"),
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


def claude(install):
    if not os.path.isdir(os.path.dirname(CLAUDE_SETTINGS)):
        return t("skip_claude")
    data = {}
    if os.path.exists(CLAUDE_SETTINGS):
        with open(CLAUDE_SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
    before = copy.deepcopy(data)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    # Remove only our entries. Other hooks and lists that were empty to begin with stay.
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
        for event in CLAUDE_EVENTS:
            group = {"hooks": [{"type": "command", "command": "%s claude" % HOOK,
                                "timeout": CLAUDE_TIMEOUTS.get(event, 10)}]}
            if event == "PostToolUse":
                group = dict({"matcher": ""}, **group)
            hooks.setdefault(event, []).append(group)
    if hooks or "hooks" in before:
        data["hooks"] = hooks
    if data == before:
        return t("claude_same")
    save(CLAUDE_SETTINGS, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    if install:
        return t("claude_add", len(CLAUDE_EVENTS), ", ".join(CLAUDE_EVENTS), CLAUDE_SETTINGS)
    return t("claude_del", CLAUDE_SETTINGS)


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
            if not (l.startswith("# " + MARK + ":") or (l.startswith("notify") and MARK in l))]
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


def main():
    global LANG
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if len(sys.argv) > 2 and sys.argv[2] in ("en", "ko"):
        LANG = sys.argv[2]
    if mode not in ("install", "uninstall"):
        print("usage: python3 setup.py install|uninstall [en|ko]", file=sys.stderr)
        return 2
    status = 0
    for step in (claude, codex):
        try:
            print(step(mode == "install"))
        except Exception as e:
            print(t("failed", step.__name__, e))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
