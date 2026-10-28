<h1 align="center">cmux-remote-notify</h1>

<p align="center"><b>Remote Claude Code and Codex, right in the cmux sidebar.</b></p>

<p align="center">
  <a href="https://github.com/zoo3323/cmux-remote-notify/actions/workflows/test.yml"><img src="https://github.com/zoo3323/cmux-remote-notify/actions/workflows/test.yml/badge.svg" alt="test"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT"></a>
  <br>
  English · <a href="README.ko.md">한국어</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/hero-dark.svg">
  <img src="docs/img/hero-light.svg" alt="You work in a local cmux workspace. Further down the sidebar, the remote ml-research workspace gets an unread badge and a banner when train finishes and when eval needs input." width="100%">
</picture>

Keep working in another tab. When an agent on a remote server (over SSH, [Eternal Terminal](https://eternalterminal.dev/) or [mosh](https://mosh.org), in tmux or not) finishes or needs you, [cmux](https://cmux.com) tells you: a banner, an unread badge on that workspace, the ring on its tab, and a sidebar line saying what each session is doing. On its own, cmux hears a remote agent only through terminal escape codes: mosh drops them, tmux drops them unless passthrough is on, Claude Code sends them only after about a minute, and a closed tab gets nothing. This tool reports every turn the moment it ends, the same way over any connection.

## Install

```bash
git clone https://github.com/zoo3323/cmux-remote-notify.git
cd cmux-remote-notify
bin/cmux-remote-notify install gpu-box     # the name you give ssh
cmux-remote-notify test gpu-box            # a test notification on that tab
```

Run `install` once per host. It adds hooks on the host and a watcher on your Mac that starts at login and reconnects after sleep. For Codex, open Codex on the host once, type `/hooks` and trust the cmux-remote-notify hooks; until then Codex sends finished turns only, with no sidebar status.

| Where | Needs |
|---|---|
| Mac | cmux, `jq` (built into macOS 15, or `brew install jq`), an SSH key that logs in to the host without a password |
| cmux | Settings › Automation › Socket control mode: **Automation** |
| Host | Linux with `python3` and Claude Code or Codex, in tmux or not |

## The sidebar

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/states-dark.svg">
  <img src="docs/img/states-light.svg" alt="Three sidebar lines: Running with the time worked and the prompt, Needs input, Idle" width="100%">
</picture>

One line per tmux session, or per tab running Claude without tmux (named after its folder), on the workspace that holds the tab. The workspace description names the host; `install gpu-box --label GPU` shows it as `GPU`.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/flow-dark.svg">
  <img src="docs/img/flow-light.svg" alt="On the host, Claude Code hooks run hook.py, which appends to events.jsonl. The Mac's watcher follows that file over SSH and calls cmux notify and set-status." width="100%">
</picture>

The hook only appends a line to a file, so it never slows the agent down and nothing listens on a port. The Mac keeps one SSH connection per host.

Nothing has to be set up per tab. The hook says which logins the agent is seen from (for tmux, the clients attached to its session), and the Mac finds the tab that opened each login: an ssh login by its port, a mosh login by its UDP port, et and shared ssh connections (ControlMaster, ProxyJump) by when the login started, and logins started within two seconds of each other by terminal size. A tab may name the host differently (`user@address`, another alias); the address it is connected to tells it is the same host. A tmux session named on the command line is matched by name. All of these work:

```bash
ssh gpu-box                            # then claude, or tmux by hand
ssh -t gpu-box tmux new -A -s train
et gpu-box                             # then claude
et gpu-box -c "tmux attach -t train"
mosh gpu-box                           # then claude
ssh me@10.0.0.9                        # the same host by its address
```

A detached tmux session shows on no tab until you attach it again.

## Commands

| Command | |
|---|---|
| `install <host> [--label NAME]` | add the hooks and start watching (safe to run again) |
| `test <host> [session]` | send one test notification |
| `status` | watchers and their recent log |
| `doctor [host]` | check everything and print the fix for each problem |
| `label <host> [NAME]` | rename the host in the sidebar |
| `uninstall <host>` | remove the hooks and the watcher |

<details>
<summary><b>Troubleshooting</b></summary>

Start with `cmux-remote-notify doctor`. It checks the watcher, the cmux socket mode, SSH, the remote hooks and the open tabs, and prints a fix under each problem.

| Symptom | Usually | Do |
|---|---|---|
| Nothing arrives | watcher stopped, or hooks missing | `install <host>` again |
| `test` works, real work does not | another tool rewrote the host's `~/.claude/settings.json` | `install <host>` again |
| Banner only, no tab ring | no open tab shows that agent (a detached tmux session) | attach to it from a tab |
| Stopped after a cmux update | socket control mode went back to "cmux processes only" | set it to Automation |
| Running stays after Esc | Esc sends no `Stop` | it turns Idle about a minute later |
| A turn notifies twice | Claude Code's or Codex's own notifications were turned on again | `install <host>` again (`doctor` shows which) |

Logs: `~/Library/Logs/cmux-remote-notify/<host>.log` on the Mac, `~/.local/state/cmux-remote-notify/events.jsonl` on the host.

</details>

<details>
<summary><b>What install changes</b></summary>

| Where | What |
|---|---|
| Host | `~/.local/share/cmux-remote-notify/hook.py`, events in `~/.local/state/cmux-remote-notify/` |
| Host | one entry in each of 7 hook events in `~/.claude/settings.json` and in `~/.codex/hooks.json`, and `notify` in `~/.codex/config.toml` unless you already have one. These files are backed up first, and `uninstall` removes only these entries |
| Host | the agents' own terminal notifications are turned off so a turn never notifies twice: `preferredNotifChannel` in `~/.claude/settings.json` and `[tui] notifications` in `~/.codex/config.toml`. `uninstall` puts back what was there |
| Mac | a copy in `~/.local/share/cmux-remote-notify/` (launchd cannot read `~/Desktop`), the link `~/.local/bin/cmux-remote-notify`, and `~/Library/LaunchAgents/io.github.zoo3323.cmux-remote-notify.<host>.plist` |

</details>

<details>
<summary><b>Details</b></summary>

Messages and sidebar text follow your macOS language, English or Korean. `CMUX_REMOTE_NOTIFY_LANG=en` forces English.

Claude Code background sessions (`/bg`) run under a daemon; their status goes to the tab of the Claude client that is watching them. Codex sessions run in Codex's shared app-server the same way, and go to the tab of the Codex window showing them.

Not matched: two tabs to one host whose logins started within two seconds of each other and have the same terminal size, when neither the port nor a tmux session name tells them apart.

After the Mac sleeps, the watcher is back within about a minute, and events from the gap still arrive (older than 10 minutes: tab ring only, no banner). The host sends a heartbeat every minute so a dead connection never lingers there.

Tests run without cmux or a host: `bash tests/run.sh`. The images are drawn by `python3 tools/make-images.py`.

</details>

## License

[MIT](LICENSE)
