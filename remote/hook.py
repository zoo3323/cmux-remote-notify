#!/usr/bin/env python3
"""cmux-remote-notify remote hook.

Claude Code hooks and Codex (notify) call this whenever an agent starts work, finishes,
or waits for you. It appends one line to ~/.local/state/cmux-remote-notify/events.jsonl.
On the Mac, `cmux-remote-notify watch` follows that file over SSH, notifies the cmux tab
attached to the same tmux session and keeps its sidebar status (Running, Needs input, Idle).

    hook.py claude              # hook JSON arrives on stdin
    hook.py codex '<json>'      # Codex passes the JSON as the last argument
    hook.py sweep               # called every minute by the Mac's connection: reaps dead Claude sessions

Event kinds: running, input (waiting for you), idle, done (finished a turn),
error (stopped on an error), note (any other notification), end (session ended).

Work outside tmux (scripts, cron) is ignored. The exception is a Claude Code background
session (/bg, or one started from the agents view): it runs under the daemon outside tmux,
so its events go to the tab of the tmux client that is watching it.
CMUX_REMOTE_NOTIFY_SESSION forces a session name for tests.
The hook always exits 0 so it never blocks Claude Code or Codex.
"""
import json
import os
import re
import subprocess
import sys
import time

STATE_DIR = os.path.expanduser("~/.local/state/cmux-remote-notify")
EVENTS = os.path.join(STATE_DIR, "events.jsonl")
# One file per live Claude session (named by session ID) holding its state and process.
LIVE_DIR = os.path.join(STATE_DIR, "live")
ROTATE_BYTES = 512 * 1024
TEXT_LIMIT = 300
# Records whose process could not be found are dropped after this long.
LIVE_MAX_AGE = 7 * 24 * 3600
# Notifications that wait for your answer. Others notify without changing the state.
INPUT_TYPES = ("permission_prompt", "elicitation_dialog", "elicitation_url_dialog",
               "agent_needs_input", "worker_permission_prompt")
# idle_prompt fires after a minute without input. It overlaps Stop, so it only sets idle.
SKIP_NOTIFICATION_TYPES = ("auth_success",)
SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# Length of the prompt's first line shown in the sidebar as the current task.
TASK_LIMIT = 80


# Where the Claude Code daemon records clients attaching to background sessions.
DAEMON_DIR = os.path.expanduser("~/.claude/daemon")


def is_bg_session():
    """Whether the Claude that called this hook is a background session.

    Claude Code strips CLAUDE_CODE_SESSION_KIND from the children of a background session
    (hooks included), so read the calling Claude process's environment, not our own."""
    if os.environ.get("CLAUDE_CODE_SESSION_KIND") == "bg":
        return True
    pid, _ = claude_process()
    if pid is None:
        return False
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            return b"\0CLAUDE_CODE_SESSION_KIND=bg\0" in b"\0" + f.read() + b"\0"
    except OSError:
        return False


def proc_tmux(pid):
    """(TMUX, TMUX_PANE) of that process, or None outside tmux or when unreadable."""
    try:
        with open("/proc/%d/environ" % pid, "rb") as f:
            env = dict(kv.split("=", 1) for kv in
                       f.read().decode("utf-8", "replace").split("\0") if "=" in kv)
    except (OSError, ValueError):
        return None
    if not env.get("TMUX"):
        return None
    return env["TMUX"], env.get("TMUX_PANE", "")


def bg_client_tmux():
    """(TMUX, TMUX_PANE) of the Claude client in tmux that is watching the background session.

    With several live clients in attach-journal, the most recently attached wins.
    Without any record, fall back to the client that spawned the daemon (--spawned-by)."""
    found = []
    jdir = os.path.join(DAEMON_DIR, "attach-journal")
    try:
        names = os.listdir(jdir)
    except OSError:
        names = []
    for name in names:
        try:
            with open(os.path.join(jdir, name), encoding="utf-8") as f:
                rec = json.load(f)
            pid = int(rec.get("pid") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        stat = proc_stat(pid) if pid > 1 else None
        if stat is None or str(rec.get("procStart") or stat[1]) != stat[1]:
            continue
        got = proc_tmux(pid)
        if got:
            found.append((rec.get("startedAtEpochMs") or 0, got))
    if found:
        return max(found, key=lambda x: x[0])[1]
    try:
        with open(os.path.join(DAEMON_DIR, "roster.json"), encoding="utf-8") as f:
            sup = int(json.load(f).get("supervisorPid") or 0)
        with open("/proc/%d/cmdline" % sup, "rb") as f:
            argv = f.read().decode("utf-8", "replace").split("\0")
        pid = int(json.loads(argv[argv.index("--spawned-by") + 1]).get("pid") or 0)
    except (OSError, ValueError, TypeError, AttributeError, IndexError):
        return None
    return proc_tmux(pid) if pid > 1 else None


def tmux_session():
    """Name of the tmux session this runs in. None outside tmux, "" when tmux cannot be asked."""
    forced = os.environ.get("CMUX_REMOTE_NOTIFY_SESSION")
    if forced:
        return forced
    tmux = os.environ.get("TMUX")
    pane = os.environ.get("TMUX_PANE")
    if not tmux and is_bg_session():
        got = bg_client_tmux()
        if got:
            tmux, pane = got
    if not tmux:
        return None
    socket_path, _, rest = tmux.partition(",")
    server_pid = rest.partition(",")[0]
    # Ask with the binary that started the server so the protocol versions match.
    binary = "tmux"
    try:
        exe = os.readlink("/proc/%s/exe" % server_pid)
        if exe.endswith(" (deleted)"):
            exe = exe[: -len(" (deleted)")]
        if os.access(exe, os.X_OK):
            binary = exe
    except OSError:
        pass
    # display-message only reads. It never starts or changes a server.
    cmd = [binary, "-S", socket_path, "display-message", "-p"]
    if pane:
        cmd += ["-t", pane]
    cmd.append("#{session_name}")
    try:
        out = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.decode("utf-8", "replace").strip()


def proc_stat(pid):
    """(parent pid, start time), or None if the process is gone."""
    try:
        with open("/proc/%d/stat" % pid) as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return int(fields[1]), fields[19]
    except (OSError, IndexError, ValueError):
        return None


def claude_process():
    """(pid, start time) of the Claude Code process that called this hook, or (None, None)."""
    pid = os.getppid()
    for _ in range(6):
        stat = proc_stat(pid) if pid > 1 else None
        if stat is None:
            break
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                argv = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            argv = []
        try:
            exe = os.readlink("/proc/%d/exe" % pid)
        except OSError:
            exe = ""
        if (argv and os.path.basename(argv[0]) == "claude") or "/claude/" in exe \
                or any("claude-code" in a for a in argv[:2]):
            return pid, stat[1]
        pid = stat[0]
    return None, None


def live_path(sid):
    return os.path.join(LIVE_DIR, sid)


def read_live(sid):
    try:
        with open(live_path(sid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_live(sid, info):
    os.makedirs(LIVE_DIR, exist_ok=True)
    tmp = live_path(sid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f)
    os.replace(tmp, live_path(sid))


def remove_live(sid):
    try:
        os.remove(live_path(sid))
    except OSError:
        pass


def claude_kind(data, sid):
    """Turn Claude hook input into (kind, text), or None when there is nothing to report."""
    name = data.get("hook_event_name")
    if name == "UserPromptSubmit":
        lines = [l.strip() for l in str(data.get("prompt") or "").splitlines() if l.strip()]
        return "running", lines[0][:TASK_LIMIT] if lines else ""
    if name == "PostToolUse":
        # Fires on every tool call, so only report a session resuming after a permission
        # prompt, or one we have no record of yet (already working before the install).
        if not sid:
            return None
        live = read_live(sid)
        if live is None or live.get("state") == "input":
            return "running", ""
        return None
    if name == "Stop":
        return "done", data.get("last_assistant_message")
    if name == "StopFailure":
        return "error", data.get("error_details") or data.get("error") or data.get("last_assistant_message")
    if name == "SessionStart":
        # compact also fires mid-turn, so it does not change the state.
        if data.get("source") == "compact":
            return None
        return "idle", ""
    if name == "SessionEnd":
        return "end", ""
    if name == "Notification":
        kind_of = data.get("notification_type")
        if kind_of in SKIP_NOTIFICATION_TYPES:
            return None
        if kind_of == "idle_prompt":
            return "idle", ""
        if kind_of is None or kind_of in INPUT_TYPES:
            return "input", data.get("message")
        return "note", data.get("message")
    return None


def build_event(agent, data):
    """Event dict to record, or None."""
    sid = ""
    if agent == "claude":
        sid = str(data.get("session_id") or "")
        if not SID_RE.match(sid):
            sid = ""
        got = claude_kind(data, sid)
        if got is None:
            return None
        kind, text = got
    elif agent == "codex":
        name = data.get("type")
        if name == "agent-turn-complete":
            kind, text = "done", data.get("last-assistant-message")
        elif name == "approval-requested":
            kind, text = "input", data.get("message")
        else:
            return None
    else:
        return None
    event = {
        "v": 1,
        "ts": int(time.time() * 1000),
        "agent": agent,
        "kind": kind,
        "cwd": data.get("cwd") or os.getcwd(),
        "text": " ".join(str(text or "").split())[:TEXT_LIMIT],
    }
    if sid:
        event["sid"] = sid
    return event


def append(event):
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        if os.path.getsize(EVENTS) > ROTATE_BYTES:
            os.replace(EVENTS, EVENTS + ".1")
    except OSError:
        pass
    line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
    # A single write keeps lines whole when several sessions append at once.
    fd = os.open(EVENTS, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


STATE_OF = {"running": "running", "input": "input", "idle": "idle", "done": "idle", "error": "idle"}


def track(event):
    """Record the session's current state and process in live/ (read by sweep and PostToolUse)."""
    sid = event.get("sid")
    if not sid:
        return
    if event["kind"] == "end":
        remove_live(sid)
        return
    state = STATE_OF.get(event["kind"])
    if state is None:
        return
    old = read_live(sid) or {}
    info = {"session": event["session"], "state": state, "pid": old.get("pid"), "start": old.get("start")}
    if not info["pid"] or proc_stat(info["pid"]) is None:
        info["pid"], info["start"] = claude_process()
    write_live(sid, info)


def sweep():
    """Emit end events for Claude sessions that died without SessionEnd."""
    try:
        names = os.listdir(LIVE_DIR)
    except OSError:
        return
    now = time.time()
    for sid in names:
        if not SID_RE.match(sid):
            continue
        path = live_path(sid)
        info = read_live(sid)
        if info is None:
            continue
        pid, start = info.get("pid"), info.get("start")
        if pid:
            stat = proc_stat(int(pid))
            alive = stat is not None and stat[1] == start
        else:
            try:
                alive = now - os.path.getmtime(path) < LIVE_MAX_AGE
            except OSError:
                continue
        if alive:
            continue
        remove_live(sid)
        append({"v": 1, "ts": int(now * 1000), "agent": "claude", "kind": "end",
                "cwd": "", "text": "", "sid": sid, "session": info.get("session", "")})


def main(argv):
    agent = argv[1] if len(argv) > 1 else ""
    if agent == "sweep":
        sweep()
        return
    if agent == "claude":
        raw = sys.stdin.read()
    elif agent == "codex":
        raw = argv[2] if len(argv) > 2 else ""
    else:
        return
    # Outside tmux do nothing (an env check, so it is fast). Background sessions are the exception.
    if not os.environ.get("CMUX_REMOTE_NOTIFY_SESSION") and not os.environ.get("TMUX") \
            and not is_bg_session():
        return
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    event = build_event(agent, data)
    if event is None:
        return
    session = tmux_session()
    if session is None:
        return
    event["session"] = session
    append(event)
    track(event)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception:
        pass
    sys.exit(0)
