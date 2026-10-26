#!/bin/bash
# cmux-remote-notify tests. They use fake cmux, ps and osascript, so no cmux app or remote host is needed.
#   bash tests/run.sh
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CLI=$ROOT/bin/cmux-remote-notify
HOOK=$ROOT/remote/hook.py
SETUP=$ROOT/remote/setup.py
TMP=$(mktemp -d "${TMPDIR:-/tmp}/crn-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
export CMUX_REMOTE_NOTIFY_LANG=en
# Never look at the real LaunchAgents.
export CMUX_REMOTE_NOTIFY_AGENTS=$TMP/agents
mkdir -p "$CMUX_REMOTE_NOTIFY_AGENTS"

pass=0 fail=0
ok()   { pass=$((pass + 1)); printf '  ok   %s\n' "$1"; }
bad()  { fail=$((fail + 1)); printf '  FAIL %s\n' "$1"; [ -z "${2:-}" ] || printf '       %s\n' "$2"; }
check() { if eval "$2"; then ok "$1"; else bad "$1" "${3:-}"; fi; }
lines() { [ -f "$1" ] && wc -l < "$1" | tr -d ' ' || echo 0; }

# ---------------------------------------------------------------- hook.py
echo "hook.py"
H=$TMP/hookhome; mkdir -p "$H"
EV=$H/.local/state/cmux-remote-notify/events.jsonl
hook() { env -u TMUX HOME="$H" CMUX_REMOTE_NOTIFY_SESSION="${SESSION-s1}" python3 "$HOOK" "$@"; }

long=$(python3 -c 'print("first line\n\n  second   line " + "é" * 400)')
jq -cn --arg m "$long" '{hook_event_name:"Stop", cwd:"/home/me/proj", last_assistant_message:$m}' | hook claude
check "Stop writes one done line" '[ "$(lines "$EV")" = 1 ] && [ "$(jq -r .kind "$EV")" = done ]'
check "it carries session, agent and folder" '[ "$(jq -r "[.session,.agent,.cwd]|join(\",\")" "$EV")" = "s1,claude,/home/me/proj" ]'
check "text: whitespace squeezed, cut at 300 characters" '[ "$(jq -r ".text|length" "$EV")" = 300 ] && jq -r .text "$EV" | grep -q "^first line second line é"'

echo '{"hook_event_name":"Notification","notification_type":"idle_prompt","message":"waiting"}' | hook claude
check "idle_prompt is idle, not a notification" '[ "$(lines "$EV")" = 2 ] && [ "$(tail -n 1 "$EV" | jq -r .kind)" = idle ]'
echo '{"hook_event_name":"Notification","notification_type":"auth_success","message":"ok"}' | hook claude
check "auth_success is skipped" '[ "$(lines "$EV")" = 2 ]'

echo '{"hook_event_name":"Notification","notification_type":"permission_prompt","message":"Claude needs your permission to use Bash"}' | hook claude
check "a permission prompt is input" '[ "$(tail -n 1 "$EV" | jq -r "[.kind,.text]|join(\"|\")")" = "input|Claude needs your permission to use Bash" ]'

hook codex '{"type":"agent-turn-complete","cwd":"/w","last-assistant-message":"Finished","input-messages":["x"]}'
check "a finished Codex turn is done" '[ "$(tail -n 1 "$EV" | jq -r "[.agent,.kind,.text]|join(\"|\")")" = "codex|done|Finished" ]'

n=$(lines "$EV")
echo '{"hook_event_name":"Stop"}' | SESSION= hook claude
check "nothing is written outside tmux" '[ "$(lines "$EV")" = "$n" ]'
echo 'not json' | hook claude; hook codex '{"type":"other"}'; hook nobody
check "broken input and unknown events are ignored" '[ "$(lines "$EV")" = "$n" ]'
echo 'not json' | hook claude; check "it exits 0 even on failure" '[ $? = 0 ]'

# events for the sidebar status
LIVE=$H/.local/state/cmux-remote-notify/live
last() { tail -n 1 "$EV" | jq -r "$1"; }
cc() { local extra=${3:-'{}'}; jq -cn --arg e "$1" --arg sid "${2:-S1}" "{hook_event_name:\$e, session_id:\$sid, cwd:\"/p\"} + $extra" | hook claude; }
cc UserPromptSubmit
check "UserPromptSubmit is running and carries the Claude session ID" '[ "$(last "[.kind,.sid,.session]|join(\",\")")" = "running,S1,s1" ]'
check "the session state goes to live/" '[ "$(jq -r "[.state,.session]|join(\",\")" "$LIVE/S1")" = "running,s1" ]'
n=$(lines "$EV"); cc PostToolUse
check "PostToolUse while working writes nothing" '[ "$(lines "$EV")" = "$n" ]'
cc Notification S1 '{notification_type:"permission_prompt", message:"Claude needs your permission"}'
check "permission prompt: input, live is input too" '[ "$(last .kind)" = input ] && [ "$(jq -r .state "$LIVE/S1")" = input ]'
cc PostToolUse
check "PostToolUse after the permission is running again" '[ "$(last .kind)" = running ] && [ "$(jq -r .state "$LIVE/S1")" = running ]'
cc PostToolUse S7
check "PostToolUse of an unknown session is running" '[ "$(last .sid)" = S7 ] && [ "$(last .kind)" = running ] && [ "$(jq -r .state "$LIVE/S7")" = running ]'
n=$(lines "$EV"); cc PostToolUse S7
check "the next PostToolUse writes nothing" '[ "$(lines "$EV")" = "$n" ]'
cc Notification S1 '{notification_type:"agent_completed", message:"run failed"}'
check "a notification that does not wait is note (state unchanged)" '[ "$(last .kind)" = note ] && [ "$(jq -r .state "$LIVE/S1")" = running ]'
n=$(lines "$EV"); cc SessionStart S1 '{source:"compact"}'
check "SessionStart from compact writes nothing" '[ "$(lines "$EV")" = "$n" ]'
cc SessionStart S2 '{source:"startup"}'
check "a new session is idle" '[ "$(last "[.kind,.sid]|join(\",\")")" = "idle,S2" ]'
cc StopFailure S1 '{error:"rate_limit", error_details:"429 too many"}'
check "StopFailure is error with the error text" '[ "$(last "[.kind,.text]|join(\",\")")" = "error,429 too many" ] && [ "$(jq -r .state "$LIVE/S1")" = idle ]'
cc SessionEnd S1 '{reason:"prompt_input_exit"}'
check "SessionEnd is end and deletes the live file" '[ "$(last .kind)" = end ] && [ ! -e "$LIVE/S1" ]'
n=$(lines "$EV"); jq -cn '{hook_event_name:"UserPromptSubmit", session_id:"../x"}' | hook claude
check "a strange session ID is dropped" '[ "$(last ".sid // \"none\"")" = none ] && [ ! -e "$H/.local/state/cmux-remote-notify/x" ]'
n=$(lines "$EV"); HOME="$H" python3 "$HOOK" sweep
check "sweep: recent sessions stay" '[ "$(lines "$EV")" = "$n" ] && [ -e "$LIVE/S2" ]'
touch -t 202001010000 "$LIVE/S2"; HOME="$H" python3 "$HOOK" sweep
check "sweep: an old session with no known process ends" '[ "$(last "[.kind,.sid,.session]|join(\",\")")" = "end,S2,s1" ] && [ ! -e "$LIVE/S2" ]'
if [ -d /proc/self ]; then
  printf '{"session":"s1","state":"running","pid":%s,"start":"x"}' $$ > "$LIVE/S3"; HOME="$H" python3 "$HOOK" sweep
  check "sweep: a different process start time (it died) ends" '[ "$(last .sid)" = S3 ] && [ ! -e "$LIVE/S3" ]'
fi
jq -cn '{hook_event_name:"UserPromptSubmit", session_id:"S5", prompt:"\n   summarize the   eval results\nsecond line"}' | hook claude
check "UserPromptSubmit carries the prompt's first line" '[ "$(last .text)" = "summarize the eval results" ]'
n=$(lines "$EV"); jq -cn '{hook_event_name:"UserPromptSubmit", session_id:"S9"}' | env -u TMUX -u CMUX_REMOTE_NOTIFY_SESSION HOME="$H" python3 "$HOOK" claude
check "outside tmux live/ is not written either" '[ "$(lines "$EV")" = "$n" ] && [ ! -e "$LIVE/S9" ]'
n=$(lines "$EV"); jq -cn '{hook_event_name:"UserPromptSubmit", session_id:"S8"}' | env -u TMUX -u CMUX_REMOTE_NOTIFY_SESSION HOME="$H" CLAUDE_CODE_SESSION_KIND=bg python3 "$HOOK" claude
check "background session with no watching tmux client: nothing written" '[ "$(lines "$EV")" = "$n" ] && [ ! -e "$LIVE/S8" ]'
mkdir -p "$H/.claude/daemon/attach-journal"; echo '{"pid":999999999,"procStart":"1","startedAtEpochMs":1}' > "$H/.claude/daemon/attach-journal/g.json"
n=$(lines "$EV"); jq -cn '{hook_event_name:"UserPromptSubmit", session_id:"S8"}' | env -u TMUX -u CMUX_REMOTE_NOTIFY_SESSION HOME="$H" CLAUDE_CODE_SESSION_KIND=bg python3 "$HOOK" claude
check "background session: records of dead clients are ignored" '[ "$(lines "$EV")" = "$n" ]'
if [ -d /proc/self ]; then
  # Claude Code strips CLAUDE_CODE_SESSION_KIND from a background session's hooks; read the calling claude's env.
  BGPY='import os, subprocess, sys
e = dict(os.environ); e.pop("CLAUDE_CODE_SESSION_KIND", None)
code = "import sys; sys.path.insert(0, sys.argv[1]); import hook; print(hook.is_bg_session())"
sys.stdout.write(subprocess.run(["python3", "-c", code, sys.argv[1]], env=e, capture_output=True, text=True).stdout)'
  got=$(env CLAUDE_CODE_SESSION_KIND=bg bash -c 'exec -a claude python3 -c "$1" "$2"' _ "$BGPY" "$ROOT/remote")
  check "background session is recognized from the calling claude's env" '[ "$got" = True ]' "$got"
  got=$(env -u CLAUDE_CODE_SESSION_KIND bash -c 'exec -a claude python3 -c "$1" "$2"' _ "$BGPY" "$ROOT/remote")
  check "a normal session is not taken for a background one" '[ "$got" = False ]' "$got"
fi

python3 -c "import sys; open(sys.argv[1], 'a').write('x' * 600000 + '\n')" "$EV"
echo '{"hook_event_name":"Stop","last_assistant_message":"new file"}' | hook claude
check "past 512KB the log rolls to events.jsonl.1" '[ -f "$EV.1" ] && [ "$(lines "$EV")" = 1 ] && [ "$(jq -r .text "$EV")" = "new file" ]'

# ---------------------------------------------------------------- setup.py
echo "setup.py"
S=$TMP/setuphome; mkdir -p "$S/.claude" "$S/.codex"
cat > "$S/.claude/settings.json" <<'EOF'
{
  "permissions": {
    "defaultMode": "acceptEdits"
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/other.sh"
          }
        ]
      }
    ],
    "PreToolUse": []
  },
  "theme": "dark"
}
EOF
printf 'model = "x"\napproval_policy = "never"\n\n[projects."/a"]\ntrust_level = "trusted"\n' > "$S/.codex/config.toml"
cp "$S/.claude/settings.json" "$TMP/settings.orig"; cp "$S/.codex/config.toml" "$TMP/config.orig"
setup() { HOME="$S" python3 - "$@" < "$SETUP"; }

out=$(setup install)
SJ=$S/.claude/settings.json
check "one entry in each of the 7 hook events" '[ "$(jq -c "[.hooks | to_entries[] | select(any(.value[].hooks[]; .command|test(\"cmux-remote-notify/hook.py claude\"))) | .key] | sort" "$SJ")" = "[\"Notification\",\"PostToolUse\",\"SessionEnd\",\"SessionStart\",\"Stop\",\"StopFailure\",\"UserPromptSubmit\"]" ]' "$(jq -c .hooks "$SJ")"
check "PostToolUse: every tool, 5 second timeout" '[ "$(jq -c "[.hooks.PostToolUse[] | select(any(.hooks[]; .command|test(\"cmux-remote-notify\"))) | [.matcher, .hooks[0].timeout]]" "$SJ")" = "[[\"\",5]]" ]'
check "other hooks and settings stay" '[ "$(jq -c "[.hooks.Stop[0], .hooks.PreToolUse, .permissions, .theme]" "$SJ")" = "$(jq -c "[.hooks.Stop[0], .hooks.PreToolUse, .permissions, .theme]" "$TMP/settings.orig")" ]'
check "Codex notify goes at the top, before the first [table]" 'sed -n 2p "$S/.codex/config.toml" | grep -q "^notify = \[\".*cmux-remote-notify/hook.py\", \"codex\"\]$" && [ "$(sed -n "3,\$p" "$S/.codex/config.toml")" = "$(cat "$TMP/config.orig")" ]'
check "files are backed up before they change" 'ls "$S/.claude/" | grep -q "settings.json.bak.cmux-remote-notify." && ls "$S/.codex/" | grep -q "config.toml.bak.cmux-remote-notify."'
check "the Codex config still parses as TOML" 'python3 -c "import sys,tomllib; tomllib.load(open(sys.argv[1],\"rb\"))" "$S/.codex/config.toml" 2>/dev/null || ! python3 -c "import tomllib" 2>/dev/null'

out=$(setup install)
check "installing again adds nothing" '! echo "$out" | grep -v "nothing to change" | grep -q .' "$out"
out=$(setup install ko)
check "Korean output with ko" 'echo "$out" | grep -q "Claude Code: 바꿀 것 없음"' "$out"

setup uninstall >/dev/null
check "uninstall restores the Claude settings" 'cmp -s "$SJ" "$TMP/settings.orig"'
check "uninstall restores the Codex config" 'cmp -s "$S/.codex/config.toml" "$TMP/config.orig"'
printf '# cmux-remote-notify: Codex 작업이 끝나면 맥 cmux 탭에 알린다\nnotify = ["%s/.local/share/cmux-remote-notify/hook.py", "codex"]\nmodel = "x"\n' "$S" > "$S/.codex/config.toml"
setup uninstall >/dev/null
check "uninstall also removes the comment older versions wrote" '[ "$(cat "$S/.codex/config.toml")" = "model = \"x\"" ]' "$(cat "$S/.codex/config.toml")"

printf 'notify = ["my-notifier"]\nmodel = "x"\n' > "$S/.codex/config.toml"
out=$(setup install)
check "a notify of your own is left alone" 'echo "$out" | grep -q "another notify" && [ "$(head -n 1 "$S/.codex/config.toml")" = "notify = [\"my-notifier\"]" ]'
check "tools that are not installed are skipped" 'out=$(HOME="$TMP/empty" python3 - install < "$SETUP"); echo "$out" | grep -q "Claude Code: not installed, skipped"'

# ---------------------------------------------------------------- finding tabs
echo "finding tabs"
F=$TMP/fake; mkdir -p "$F"
cat > "$F/ps" <<'EOF'
#!/bin/bash
case "$*" in
  *tty=*) cat "$FAKE_DIR/ps.txt" ;;
  *) sed -E 's/^[^ ]+ +//' "$FAKE_DIR/ps.txt" ;;
esac
EOF
chmod 755 "$F/ps"
cat > "$F/ps.txt" <<'EOF'
ttys001  /Users/me/.local/share/ezet/et/current --close-on-hangup -p 2022 gpu-box -c '/usr/local/bin/tmux' -L 'ezet-x' new-session -A -s 'train'
ttys002  ssh -t gpu-box tmux new -A -s api
ttys003  ssh -p 2222 -o ServerAliveInterval=30 me@gpu-box -t "tmux attach -t notes:2"
ttys004  et -c tmux a -t 'big run' gpu-box:2022
ttys005  ssh gpu-box
ttys006  ssh -W gpu-box:22 jump
ttys007  /bin/zsh -c grep -F " gpu-box " | grep new-session -s 'train'
??       ssh -o BatchMode=yes -n gpu-box tail -F x
ttys008  ssh -t lab tmux -L sock new-session -d -s side \; attach -t main
EOF
tabs() { FAKE_DIR="$F" PATH="$F:$PATH" bash "$CLI" _tabs gpu-box | tr '\t' '|'; }
check "ezet's et command line" 'tabs | grep -qx "ttys001|gpu-box|train"' "$(tabs)"
check "ssh -t host tmux new -A -s NAME" 'tabs | grep -qx "ttys002|gpu-box|api"'
check "ssh with options, user@, tmux attach -t NAME:window" 'tabs | grep -qx "ttys003|gpu-box|notes"'
check "et -c before the host, host:port, quoted name with a space" 'tabs | grep -qx "ttys004|gpu-box|big run"'
check "plain ssh: host known, session empty" 'tabs | grep -qx "ttys005|gpu-box|"'
check "ssh -W jumps, shells and tty-less ssh are ignored" '! tabs | grep -qE "^(ttys006|ttys007|\?\?)"'
check "a later attach after ; wins" 'tabs | grep -qx "ttys008|lab|main"' "$(tabs)"

# ---------------------------------------------------------------- watch: events
echo "watch (events)"
cat > "$F/cmux" <<'EOF'
#!/bin/bash
case $1 in
  tree) [ -z "${FAKE_TREE_FAIL:-}" ] || { echo "Error: Access denied - only processes started inside cmux can connect" >&2; exit 1; }
        cat "$FAKE_DIR/tree.json" ;;
  notify) shift; printf '%s\n' "$*" >> "$FAKE_DIR/notify.log" ;;
esac
EOF
cat > "$F/osascript" <<'EOF'
#!/bin/bash
cat > /dev/null; shift; printf '%s\n' "$*" >> "$FAKE_DIR/banner.log"
EOF
chmod 755 "$F"/*
cat > "$F/tree.json" <<'EOF'
{"windows":[{"workspaces":[{"panes":[
 {"surfaces":[{"id":"UUID-TRAIN","type":"terminal","title":"train","tty":"ttys005"}]},
 {"surfaces":[{"id":"UUID-NOTES","type":"terminal","title":"notes","tty":"ttys014"}]},
 {"surfaces":[{"id":"UUID-OTHER","type":"terminal","title":"train","tty":"ttys009"}]},
 {"surfaces":[{"id":"UUID-SHELL","type":"terminal","title":"zsh","tty":"ttys020"}]}
]}]}]}
EOF
cat > "$F/ps.txt" <<'EOF'
ttys020  /bin/zsh -c grep -F " gpu-box " | grep -F new-session | sed "s/-s 'train' x/"
ttys005  bash /opt/homebrew/bin/ezet
ttys005  /Users/me/.local/share/ezet/et/current --close-on-hangup -p 2022 gpu-box -c '/usr/local/bin/tmux' -L 'ezet-x' new-session -A -s 'train'
ttys009  /Users/me/.local/share/ezet/et/current -p 2022 lab -c 'tmux' -L 'ezet-x' new-session -A -s 'train'
ttys011  /Users/me/.local/share/ezet/et/current -p 2022 gpu-box -c 'tmux' new-session -A -s 'train-2'
EOF
run() { FAKE_DIR="$F" PATH="$F:$PATH" CMUX_BIN="$F/cmux" CMUX_REMOTE_NOTIFY_STATE="$TMP/state" bash "$CLI" _handle "$@"; }
now_ms=$(( $(date +%s) * 1000 ))
ev() { jq -cn --argjson ts "$1" --arg s "$2" --arg k "${3:-done}" '{v:1, ts:$ts, agent:"claude", kind:$k, session:$s, cwd:"/home/me/proj", text:"All done"}'; }

run gpu-box "$(ev "$now_ms" train)" >/dev/null
check "only the tab with the same host and session" '[ "$(cat "$F/notify.log")" = "--surface UUID-TRAIN --title Claude finished · train --body All done --desktop true" ]' "$(cat "$F/notify.log" 2>/dev/null)"
run gpu-box "$(ev "$now_ms" train)" >/dev/null
check "the same event is not notified twice" '[ "$(lines "$F/notify.log")" = 1 ]'
run gpu-box "$(ev $((now_ms + 1)) train input)" >/dev/null
check "needs input notification" 'tail -n 1 "$F/notify.log" | grep -q "^--surface UUID-TRAIN --title Claude needs input · train "'
run gpu-box "$(ev $((now_ms + 2)) notes)" >/dev/null
check "no process match: the one tab with that title" 'tail -n 1 "$F/notify.log" | grep -q "^--surface UUID-NOTES "'
run gpu-box "$(ev $((now_ms + 3)) ghost)" >/dev/null
check "no tab: macOS banner" '[ "$(lines "$F/notify.log")" = 3 ] && grep -q "Claude finished · ghost gpu-box All done" "$F/banner.log"'
rm -rf "$TMP/state"
run gpu-box "$(ev $((now_ms - 3600 * 1000)) train)" >/dev/null
check "old events come without a banner (--desktop false)" 'tail -n 1 "$F/notify.log" | grep -q -- "--desktop false$"'
out=$(run gpu-box "ssh: connect to host gpu-box port 22: Operation timed out")
check "lines that are not JSON are only logged" 'echo "$out" | grep -q "gpu-box: ssh: connect" && [ "$(lines "$F/notify.log")" = 4 ]'
out=$(run gpu-box "#hb")
check "heartbeats pass quietly" '[ -z "$out" ] && [ "$(lines "$F/notify.log")" = 4 ]'
out=$(FAKE_TREE_FAIL=1 run gpu-box "$(ev $((now_ms + 10)) train)")
check "cmux unreachable: log why and use a macOS banner" 'echo "$out" | grep -q "could not reach cmux: Error: Access denied" && echo "$out" | grep -q "macOS banner (cannot reach cmux)" && [ "$(lines "$F/notify.log")" = 4 ]' "$out"

# a plain `ssh host` tab (tmux started by hand): the session is unknown, but it is the only one
cp "$F/ps.txt" "$F/ps.keep"
printf 'ttys014  ssh me@solo\n' > "$F/ps.txt"
run solo "$(ev $((now_ms + 20)) whatever)" >/dev/null
check "the one tab on a host with an unknown session gets it" 'tail -n 1 "$F/notify.log" | grep -q "^--surface UUID-NOTES --title Claude finished · whatever "' "$(tail -n 1 "$F/notify.log")"
printf 'ttys014  ssh solo\nttys020  ssh solo\n' > "$F/ps.txt"
n=$(lines "$F/notify.log"); run solo "$(ev $((now_ms + 21)) whatever)" >/dev/null
check "two such tabs: no guessing, banner" '[ "$(lines "$F/notify.log")" = "$n" ]'
cp "$F/ps.keep" "$F/ps.txt"

delay() { bash "$CLI" _delay "$1" "$2"; }
check "quick drops double the wait, up to 60s" '[ "$(delay 15 3)" = 30 ] && [ "$(delay 30 3)" = 60 ] && [ "$(delay 60 3)" = 60 ]'
check "after a long connection the wait is 15s again" '[ "$(delay 60 600)" = 15 ]'

pick() { FAKE_DIR="$F" PATH="$F:$PATH" bash "$CLI" _pick "$1"; }
check "test picks a session from a connection (shells ignored)" '[ "$(pick gpu-box)" = train ] && [ "$(pick lab)" = train ] && [ -z "$(pick nohost)" ]' "$(pick gpu-box)"

# ---------------------------------------------------------------- watch: sidebar
echo "watch (sidebar)"
G=$TMP/fake2; mkdir -p "$G/st"
cp "$F/ps" "$F/osascript" "$G/"
cat > "$G/cmux" <<'EOF'
#!/bin/bash
# Fake cmux: status lives in st/<workspace> as "key=text icon=.. color=.. [work=..] [priority=..]", descriptions in desc.json.
cmd=$1; shift
case $cmd in
  tree) d=$(cat "$FAKE_DIR/desc.json" 2>/dev/null || echo '{}')
        jq -c --argjson d "$d" '.windows[].workspaces[] |= (.description = ($d[.id] // .description // ""))' "$FAKE_DIR/tree.json" ;;
  notify) printf '%s\n' "$*" >> "$FAKE_DIR/notify.log" ;;
  set-status)
    key=$1 val=$2; shift 2; extra="" ws=""
    while [ $# -gt 0 ]; do
      case $1 in
        --workspace) ws=$2 ;;
        --icon) extra="$extra icon=$2" ;;
        --color) extra="$extra color=$2" ;;
        --work) extra="$extra work=$2" ;;
        --priority) extra="$extra priority=$2" ;;
      esac; shift 2
    done
    printf 'set %s %s=%s\n' "$ws" "$key" "$val" >> "$FAKE_DIR/status.log"
    f=$FAKE_DIR/st/$ws; touch "$f"; grep -v "^$key=" "$f" > "$f.tmp"; mv "$f.tmp" "$f"
    printf '%s=%s%s\n' "$key" "$val" "$extra" >> "$f"; echo OK ;;
  clear-status)
    key=$1 ws=$3
    printf 'clear %s %s\n' "$ws" "$key" >> "$FAKE_DIR/status.log"
    f=$FAKE_DIR/st/$ws; [ -f "$f" ] && { grep -v "^$key=" "$f" > "$f.tmp"; mv "$f.tmp" "$f"; }; echo OK ;;
  list-status)
    f=$FAKE_DIR/st/$2; if [ -s "$f" ]; then cat "$f"; else echo "No status entries"; fi ;;
  workspace-action)
    act="" ws="" desc=""
    while [ $# -gt 0 ]; do
      case $1 in --action) act=$2 ;; --workspace) ws=$2 ;; --description) desc=$2 ;; esac; shift 2
    done
    d=$(cat "$FAKE_DIR/desc.json" 2>/dev/null || echo '{}')
    case $act in
      set-description) printf '%s' "$d" | jq -c --arg w "$ws" --arg v "$desc" '.[$w] = $v' > "$FAKE_DIR/desc.json" ;;
      clear-description) printf '%s' "$d" | jq -c --arg w "$ws" '.[$w] = ""' > "$FAKE_DIR/desc.json" ;;
    esac
    printf '%s %s %s\n' "$act" "$ws" "$desc" >> "$FAKE_DIR/desc.log"; echo OK ;;
esac
EOF
chmod 755 "$G"/*
cat > "$G/tree.json" <<'EOF'
{"windows":[{"workspaces":[
 {"id":"WS-ML","panes":[
   {"surfaces":[{"id":"UUID-API","type":"terminal","title":"api","tty":"ttys006"}]},
   {"surfaces":[{"id":"UUID-TRAIN","type":"terminal","title":"train","tty":"ttys007"}]}]},
 {"id":"WS-DOCS","panes":[{"surfaces":[{"id":"UUID-DOCS","type":"terminal","title":"docs","tty":"ttys008"}]}]},
 {"id":"WS-MIX","description":"my notes","panes":[{"surfaces":[{"id":"UUID-X","type":"terminal","title":"x","tty":"ttys009"}]}]},
 {"id":"WS-MAC","panes":[{"surfaces":[{"id":"UUID-MAC","type":"terminal","title":"zsh","tty":"ttys003"}]}]},
 {"id":"WS-SSH","panes":[{"surfaces":[{"id":"UUID-SSH","type":"terminal","title":"zsh","tty":"ttys010"}]}]}
]}]}
EOF
cat > "$G/ps.full" <<'EOF'
ttys006  /Users/me/.local/share/ezet/et/current --close-on-hangup -p 2022 gpu-box -c '/usr/local/bin/tmux' -L 'ezet-x' new-session -A -s 'api'
ttys007  /Users/me/.local/share/ezet/et/current --close-on-hangup -p 2022 gpu-box -c '/usr/local/bin/tmux' -L 'ezet-x' new-session -A -s 'train'
ttys008  ssh -t gpu-box tmux new -A -s docs
ttys009  ssh -o BatchMode=no -t lab '/usr/bin/tmux' new-session -A -s 'x'
ttys003  /bin/zsh -l
ttys010  ssh web-1
EOF
cp "$G/ps.full" "$G/ps.txt"
ST=$TMP/state2
# Fixed clock: now is 2026-10-22 10:00 UTC, events start an hour earlier.
export TZ=UTC
NOW=$(python3 -c 'import datetime; print(int(datetime.datetime(2026, 10, 22, 10, 0, tzinfo=datetime.timezone.utc).timestamp()))')
echo $(( (NOW - 3601) * 1000 )) > "$G/t"
srun() { FAKE_DIR="$G" PATH="$G:$PATH" CMUX_BIN="$G/cmux" CMUX_REMOTE_NOTIFY_STATE="$ST" CMUX_REMOTE_NOTIFY_NOW="$NOW" bash "$CLI" _handle "$@"; }
# Kept in a file so the clock advances even when called inside $( ).
sev() { local t; t=$(( $(cat "$G/t") + 1 )); echo "$t" > "$G/t"; jq -cn --argjson ts "$t" --arg s "$1" --arg k "$2" --arg sid "$3" --arg x "${4:-}" '{v:1, ts:$ts, agent:"claude", kind:$k, session:$s, cwd:"/p", text:$x, sid:$sid}'; }
stat() { cat "$G/st/$1" 2>/dev/null; }
desc() { jq -r --arg w "$1" '.[$w] // ""' "$G/desc.json" 2>/dev/null; }
K=remote.gpu-box.train
tr_() { stat WS-ML | grep "^$K="; }

srun gpu-box "$(sev train running A "summarize the eval results")" >/dev/null
check "running: session · time worked · prompt (work=running)" '[ "$(tr_)" = "$K=train · 1h · summarize the eval results icon=bolt.fill color=#4C8DFF work=running priority=50" ]' "$(stat WS-ML)"
check "a tab with no Claude still gets an idle line" 'stat WS-ML | grep -qx "remote.gpu-box.api=api · idle icon=pause.circle.fill color=#8E8E93 priority=30" && stat WS-DOCS | grep -q "^remote.gpu-box.docs=docs · idle "' "$(stat WS-ML)"
check "running does not notify" '[ ! -f "$G/notify.log" ]'
check "description: the host the workspace's tabs are on" '[ "$(desc WS-ML)" = gpu-box ] && [ "$(desc WS-DOCS)" = gpu-box ]' "$(cat "$G/desc.json")"
check "a description you wrote is never touched" '[ -z "$(desc WS-MIX)" ] && ! grep -q WS-MIX "$G/desc.log"'
check "no description where no tab is connected" '! grep -q WS-MAC "$G/desc.log"'
check "no description for a plain ssh to a host that is not installed" '! grep -q WS-SSH "$G/desc.log"'
srun gpu-box "$(sev train input A)" >/dev/null
check "input: needs input · prompt (priority 100) and a notification" '[ "$(tr_)" = "$K=train · needs input · summarize the eval results icon=bell.fill color=#4C8DFF priority=100" ] && [ "$(lines "$G/notify.log")" = 1 ]' "$(stat WS-ML)"
srun gpu-box "$(sev train running A)" >/dev/null
check "after the permission the time counts from the prompt" 'stat WS-ML | grep -q "^$K=train · 1h · summarize the eval results icon=bolt.fill"' "$(stat WS-ML)"
srun gpu-box "$(sev train done A "All done")" >/dev/null
check "done: idle and a finished notification" '[ "$(tr_)" = "$K=train · idle icon=pause.circle.fill color=#8E8E93 priority=30" ] && tail -n 1 "$G/notify.log" | grep -q "Claude finished · train"' "$(stat WS-ML)"
n=$(lines "$G/status.log"); srun gpu-box "$(sev train idle A)" >/dev/null
check "an unchanged state does not call cmux again" '[ "$(lines "$G/status.log")" = "$n" ]'
echo $(( (NOW - 301) * 1000 )) > "$G/t"
srun gpu-box "$(sev train running B "cleanup")" >/dev/null
check "two Claudes in one session: the working one shows" 'stat WS-ML | grep -q "^$K=train · 5m · cleanup "' "$(stat WS-ML)"
srun gpu-box "$(sev train end B)" >/dev/null
check "when it ends the other one (idle) shows" 'stat WS-ML | grep -q "^$K=train · idle "'
srun gpu-box "$(sev api running C)" >/dev/null
check "one line per session" 'stat WS-ML | grep -q "^remote.gpu-box.api=api · 5m icon=bolt.fill" && stat WS-ML | grep -q "^$K=train · idle "' "$(stat WS-ML)"
srun gpu-box "$(sev api end C)" >/dev/null
check "Claude gone but the tab open: idle stays" 'stat WS-ML | grep -q "^remote.gpu-box.api=api · idle icon=pause" && [ "$(stat WS-ML | wc -l | tr -d " ")" = 2 ]' "$(stat WS-ML)"
srun gpu-box "$(sev nowhere running E)" >/dev/null
check "a session with no tab is put nowhere" '! grep -q nowhere "$G/status.log"'
srun gpu-box "$(jq -cn --argjson ts $(( $(cat "$G/t") + 1 )) '{v:1, ts:$ts, agent:"codex", kind:"done", session:"docs", cwd:"/p", text:"x"}')" >/dev/null
check "events without a session ID (Codex) leave the state alone" '[ "$(stat WS-DOCS)" = "remote.gpu-box.docs=docs · idle icon=pause.circle.fill color=#8E8E93 priority=30" ]' "$(stat WS-DOCS)"

# heartbeat
rm -f "$G/st/WS-ML"
srun gpu-box "#hb" >/dev/null
check "heartbeat: restores lines cmux lost (app restart)" '[ "$(tr_)" = "$K=train · idle icon=pause.circle.fill color=#8E8E93 priority=30" ]' "$(stat WS-ML)"
n=$(lines "$G/status.log"); srun gpu-box "#hb" >/dev/null
check "heartbeat: nothing changed, nothing written" '[ "$(lines "$G/status.log")" = "$n" ]'
cp "$G/tree.json" "$G/tree.full"
grep -v " docs$" "$G/ps.full" > "$G/ps.txt"; jq -c 'del(.windows[0].workspaces[1].panes[0].surfaces[0])' "$G/tree.full" > "$G/tree.json"
srun gpu-box "#hb" >/dev/null
check "heartbeat: closing a tab removes its line and description" '[ ! -s "$G/st/WS-DOCS" ] && [ -z "$(desc WS-DOCS)" ]' "$(stat WS-DOCS); $(desc WS-DOCS)"
cp "$G/ps.full" "$G/ps.txt"; cp "$G/tree.full" "$G/tree.json"
srun gpu-box "#hb" >/dev/null
check "heartbeat: reopening brings both back" 'stat WS-DOCS | grep -q "=docs · idle " && [ "$(desc WS-DOCS)" = gpu-box ]'
jq -c '.["WS-ML"] = "changed by me"' "$G/desc.json" > "$G/d.tmp" && mv "$G/d.tmp" "$G/desc.json"
n=$(lines "$G/desc.log"); srun gpu-box "#hb" >/dev/null
check "a description you change later is not overwritten" '[ "$(desc WS-ML)" = "changed by me" ] && [ "$(lines "$G/desc.log")" = "$n" ]'

a=$(sev docs running D); b=$(printf '%s' "$a" | jq -c '.session = "train" | .sid = "A" | .kind = "input"')
srun gpu-box "$a" >/dev/null; srun gpu-box "$b" >/dev/null
check "two lines in the same ms are both handled" 'stat WS-DOCS | grep -q "icon=bolt.fill" && stat WS-ML | grep -q "icon=bell.fill"'
n=$(lines "$G/status.log"); srun gpu-box "$a" >/dev/null; srun gpu-box "$b" >/dev/null
check "lines replayed on reconnect are skipped" '[ "$(lines "$G/status.log")" = "$n" ]'
printf '%s' "$a" | jq .ts > "$ST/old.last"
n=$(lines "$G/notify.log"); FAKE_DIR="$G" PATH="$G:$PATH" CMUX_BIN="$G/cmux" CMUX_REMOTE_NOTIFY_STATE="$ST" bash "$CLI" _handle old "$a" >/dev/null
check "a last file holding only a time counts as handled" '[ "$(lines "$G/notify.log")" = "$n" ] && [ ! -f "$ST/old.agents.json" ]'

# labels: the name shown for a host
echo '{"gpu-box":"GPU"}' > "$ST/labels.json"
srun gpu-box "#hb" >/dev/null
check "label: the description shows the host's label" '[ "$(desc WS-DOCS)" = GPU ]' "$(cat "$G/desc.json")"
rm -f "$ST/labels.json"

# Korean
KST=$TMP/state3; mkdir -p "$G/st3"
ksrun() { FAKE_DIR="$G" PATH="$G:$PATH" CMUX_BIN="$G/cmux" CMUX_REMOTE_NOTIFY_STATE="$KST" CMUX_REMOTE_NOTIFY_NOW="$NOW" CMUX_REMOTE_NOTIFY_LANG=ko bash "$CLI" _handle "$@"; }
echo $(( (NOW - 3901) * 1000 )) > "$G/t"
ksrun gpu-box "$(sev train running K "결과 정리")" >/dev/null
check "Korean: time worked in 시간·분" 'stat WS-ML | grep -q "^$K=train · 1시간 5분 · 결과 정리 icon=bolt.fill"' "$(stat WS-ML)"
ksrun gpu-box "$(sev train done K "다 했어요")" >/dev/null
check "Korean: 대기 and the 완료 notification" 'stat WS-ML | grep -q "^$K=train · 대기 " && tail -n 1 "$G/notify.log" | grep -q "Claude 완료 · train"' "$(tail -n 1 "$G/notify.log")"
unset TZ

echo
echo "passed $pass, failed $fail"
[ "$fail" = 0 ]
