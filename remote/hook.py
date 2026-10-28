#!/usr/bin/env python3
"""cmux-remote-notify remote hook.

Claude Code hooks and Codex (notify) call this whenever an agent starts work, finishes,
or waits for you. It appends one line to ~/.local/state/cmux-remote-notify/events.jsonl.
On the Mac, `cmux-remote-notify watch` follows that file over SSH, notifies the cmux tab
the agent is seen from and keeps its sidebar status (Running, Needs input, Idle).

    hook.py claude              # hook JSON arrives on stdin
    hook.py codex '<json>'      # Codex passes the JSON as the last argument
    hook.py sweep               # called every minute by the Mac's connection: reaps dead Claude
                                # sessions and reports the ones whose viewers changed

Event kinds: running, input (waiting for you), idle, done (finished a turn),
error (stopped on an error), note (any other notification), end (session ended),
where (the session is now seen from other terminals).

Where an agent is seen from, so the Mac can find the tab:
  in tmux     the session name, and the tmux clients attached to it
  no tmux     the terminal (pts/N) of the login it runs in
Each viewer is the login a terminal runs in: an ssh login (with the Mac's port from
SSH_CONNECTION), an Eternal Terminal login or a mosh login (with its UDP port), with the time it
started, the server address the Mac connected to and the terminal size.
Work with no login terminal (scripts, cron, `ssh host cmd`) is ignored. A Claude Code
background session (/bg, or one started from the agents view) runs under the daemon, so it is
placed where the client watching it is.
CMUX_REMOTE_NOTIFY_SESSION forces a session name (`cmux-remote-notify test` and tests), with
viewers from CMUX_REMOTE_NOTIFY_VIEWERS (JSON). CMUX_REMOTE_NOTIFY_PROC and _DEV replace /proc
and /dev in tests.
The hook always exits 0 so it never blocks Claude Code or Codex.
"""
import json
import os
import struct
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
PROC = os.environ.get("CMUX_REMOTE_NOTIFY_PROC", "/proc")
DEV = os.environ.get("CMUX_REMOTE_NOTIFY_DEV", "/dev")
# The parent of a login shell names how the terminal is reached.
LOGIN_VIA = (("sshd", "ssh"), ("etterminal", "et"), ("mosh-server", "mosh"))


def read_environ(pid):
    """Environment a process started with, or {} when unreadable."""
    try:
        with open("%s/%d/environ" % (PROC, pid), "rb") as f:
            return dict(kv.split("=", 1) for kv in
                        f.read().decode("utf-8", "replace").split("\0") if "=" in kv)
    except (OSError, ValueError, TypeError):
        return {}


def bg_client_pid():
    """Pid of the Claude client watching this background session, or None.

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
        found.append((rec.get("startedAtEpochMs") or 0, pid))
    if found:
        return max(found)[1]
    try:
        with open(os.path.join(DAEMON_DIR, "roster.json"), encoding="utf-8") as f:
            sup = int(json.load(f).get("supervisorPid") or 0)
        with open("%s/%d/cmdline" % (PROC, sup), "rb") as f:
            argv = f.read().decode("utf-8", "replace").split("\0")
        pid = int(json.loads(argv[argv.index("--spawned-by") + 1]).get("pid") or 0)
    except (OSError, ValueError, TypeError, AttributeError, IndexError):
        return None
    return pid if pid > 1 and proc_stat(pid) else None


def tmux_info(tmux, pane):
    """(session name, pids of the clients attached to it) for $TMUX/$TMUX_PANE, or None."""
    socket_path, _, rest = tmux.partition(",")
    server_pid = rest.partition(",")[0]
    # Ask with the binary that started the server so the protocol versions match.
    binary = "tmux"
    try:
        exe = os.readlink("%s/%s/exe" % (PROC, server_pid))
        if exe.endswith(" (deleted)"):
            exe = exe[: -len(" (deleted)")]
        if os.access(exe, os.X_OK):
            binary = exe
    except OSError:
        pass
    # display-message and list-clients only read. They never start or change a server.
    target = ["-t", pane] if pane else []
    cmd = [binary, "-S", socket_path, "display-message", "-p"] + target + ["#{session_name}",
           ";", "list-clients"] + target + ["-F", "#{client_pid}"]
    try:
        out = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.decode("utf-8", "replace").splitlines()
    if not lines or not lines[0].strip():
        return None
    return lines[0].strip(), [int(x) for x in lines[1:] if x.strip().isdigit()]


_boot = []


def started_at(ticks):
    """Epoch seconds from a /proc start time in clock ticks."""
    if not _boot:
        try:
            with open(PROC + "/stat") as f:
                _boot.append(next(int(l.split()[1]) for l in f if l.startswith("btime ")))
        except (OSError, StopIteration, ValueError, IndexError):
            _boot.append(0)
    try:
        hz = os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError):
        hz = 100
    return _boot[0] + int(ticks) // hz


def udp_port(pid):
    """Local UDP port of a socket the process holds (mosh-server), or None."""
    inodes = set()
    try:
        for fd in os.listdir("%s/%d/fd" % (PROC, pid)):
            target = os.readlink("%s/%d/fd/%s" % (PROC, pid, fd))
            if target.startswith("socket:["):
                inodes.add(target[8:-1])
    except OSError:
        return None
    for name in ("udp", "udp6"):
        try:
            with open("%s/%d/net/%s" % (PROC, pid, name)) as f:
                rows = [l.split() for l in f.readlines()[1:]]
        except OSError:
            continue
        for r in rows:
            if len(r) > 9 and r[9] in inodes:
                return int(r[1].rsplit(":", 1)[1], 16)
    return None


def tty_size(tty):
    """(rows, cols) of a terminal, or None. Only reads; the terminal is not taken over."""
    try:
        import fcntl
        import termios
        fd = os.open("%s/%s" % (DEV, tty), os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    except (OSError, ImportError):
        return None
    try:
        rows, cols = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))[:2]
        return (rows, cols) if rows and cols else None
    except OSError:
        return None
    finally:
        os.close(fd)


def viewer(pid):
    """The login terminal process pid runs in, or None:
    {via, start, tty[, sip][, port, sport][, mport][, rows, cols]}.

    Walks up to the login shell, the child of sshd, etterminal or mosh-server."""
    cur = pid
    for _ in range(40):
        stat = proc_stat(cur)
        if stat is None or stat[0] <= 1:
            return None
        try:
            with open("%s/%d/comm" % (PROC, stat[0])) as f:
                comm = f.read().strip()
        except OSError:
            return None
        via = next((v for prefix, v in LOGIN_VIA if comm.startswith(prefix)), None)
        if via:
            try:
                tty = os.readlink("%s/%d/fd/0" % (PROC, cur))
            except OSError:
                tty = ""
            if not tty.startswith("/dev/pts/") and not tty.startswith("/dev/tty"):
                return None   # `ssh host cmd` without a terminal: no tab shows it
            v = {"via": via, "start": started_at(stat[1]), "tty": tty[len("/dev/"):]}
            # The address the Mac connected to (et and mosh logins start over ssh too).
            conn = read_environ(cur).get("SSH_CONNECTION", "").split()
            if len(conn) == 4:
                v["sip"] = conn[2]
            if via == "ssh" and len(conn) == 4 and conn[1].isdigit() and conn[3].isdigit():
                v["port"], v["sport"] = int(conn[1]), int(conn[3])
            if via == "mosh":
                port = udp_port(stat[0])
                if port:
                    v["mport"] = port
            size = tty_size(v["tty"])
            if size:
                v["rows"], v["cols"] = size
            return v
        cur = stat[0]
    return None


def place(pid, env):
    """(key, viewers) for the agent process pid, or None to ignore it.

    key names the sidebar line: the tmux session, or the login terminal (pts/N) without tmux.
    viewers lists the logins the agent is seen from (None when unknown)."""
    forced = os.environ.get("CMUX_REMOTE_NOTIFY_SESSION")
    if forced:
        try:
            viewers = json.loads(os.environ.get("CMUX_REMOTE_NOTIFY_VIEWERS") or "null")
        except ValueError:
            viewers = None
        return forced, viewers if isinstance(viewers, list) else None
    if env.get("CLAUDE_CODE_SESSION_KIND") == "bg":
        pid = bg_client_pid()
        if pid is None:
            return None
        env = read_environ(pid)
    if env.get("TMUX"):
        got = tmux_info(env["TMUX"], env.get("TMUX_PANE", ""))
        if got is None:
            return None
        name, clients = got
        return name, [v for v in (viewer(c) for c in clients) if v]
    v = viewer(pid)
    if v is None:
        return None
    return v["tty"], [v]


def is_bg_session():
    """Whether the Claude that called this hook is a background session.

    Claude Code strips CLAUDE_CODE_SESSION_KIND from the children of a background session
    (hooks included), so read the calling Claude process's environment, not our own."""
    if os.environ.get("CLAUDE_CODE_SESSION_KIND") == "bg":
        return True
    pid, _ = claude_process()
    return pid is not None and read_environ(pid).get("CLAUDE_CODE_SESSION_KIND") == "bg"


def proc_stat(pid):
    """(parent pid, start time), or None if the process is gone."""
    try:
        with open("%s/%d/stat" % (PROC, pid)) as f:
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
            with open("%s/%d/cmdline" % (PROC, pid), "rb") as f:
                argv = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            argv = []
        try:
            exe = os.readlink("%s/%d/exe" % (PROC, pid))
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
    """Record the session's state, place and process in live/ (read by sweep and PostToolUse)."""
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
    info = {"session": event["session"], "name": event.get("name", ""),
            "viewers": event.get("viewers"), "state": state,
            "pid": old.get("pid"), "start": old.get("start")}
    if not info["pid"] or proc_stat(info["pid"]) is None:
        info["pid"], info["start"] = claude_process()
    write_live(sid, info)


def sweep():
    """Emit end events for Claude sessions that died without SessionEnd, and where events for
    the ones now seen from other terminals (a tmux session attached elsewhere, or detached)."""
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
            got = place(int(pid), read_environ(int(pid))) if pid else None
            if got and got[1] is not None and list(got) != [info.get("session"), info.get("viewers")]:
                info["session"], info["viewers"] = got
                write_live(sid, info)
                append({"v": 1, "ts": int(now * 1000), "agent": "claude", "kind": "where",
                        "cwd": "", "text": "", "sid": sid, "session": got[0],
                        "name": info.get("name", ""), "viewers": got[1]})
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
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    event = build_event(agent, data)
    if event is None:
        return
    # Claude Code strips some variables from a background session's hooks, so read the
    # environment of the Claude process itself.
    pid = claude_process()[0] if agent == "claude" else None
    env = read_environ(pid) if pid else {}
    if not env:
        pid, env = os.getppid(), dict(os.environ)
    got = place(pid, env)
    if got is None:
        return
    event["session"] = got[0]
    if got[1] is not None:
        event["viewers"] = got[1]
    # Without tmux the key is a terminal (pts/N), so the line is named after the folder.
    if got[1] and [v.get("tty") for v in got[1]] == [got[0]]:
        event["name"] = os.path.basename(event["cwd"].rstrip("/")) or got[0]
    append(event)
    track(event)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception:
        pass
    sys.exit(0)
