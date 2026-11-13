# Submitting to the catalog

The vetted catalog is the list an install's Library offers beside what
AerieOS ships: tool packs, coding agents and Docker apps, each pinned to an
exact commit and signed by the maintainers. Anybody can submit an entry.
This page takes one from nothing to merged, for each of the three kinds.

Three things hold for every entry:

- **It is written in the catalog's framework**, the same one AerieOS's own
  toolchains and agents are written in ([tool-packs.md](tool-packs.md)). An
  entry is data: a manifest and, for a tool pack, the scripts its install
  runs. Adding one needs no release of AerieOS, and never a change to an
  entry already there.
- **It fetches the tool from its maker.** A pack's install steps download
  the program from where its authors publish it (their release page, their
  registry, their installer) and hold the download to a checksum or a
  signature where the maker gives one. A copy of somebody's program hosted
  somewhere else is not taken.
- **It names who the tool is by** (`maker`) and the terms it is under.

## What you need

- An AerieOS install to try it on, and an account there whose roles give
  **Curate** (an administrator's does).
- A git repository for the pack. A tool pack or a coding agent lives in a
  repository of your own, the `bbtool.json` at its root or in a folder; a
  Docker app is a folder of two small files, which can live in your
  repository or be proposed straight into the catalog's `packs/apps/`.
- To run the catalog's check before you open the pull request: `git`,
  Python 3 and `pip install cryptography`.

## A tool pack

A tool pack installs a tool on a node and gives sessions commands for it
(`aerie tool NAME VERB`). The whole of it is a `bbtool.json` beside the
scripts it runs:

```
hexkit/
  bbtool.json
  install.sh      fetches the tool's own release and checks it
  GUIDE.md        tells a session when and how to use it
```

```json
{
  "name": "hexkit",
  "label": "Hex kit",
  "about": "Looks inside binaries: dumps, strings, headers.",
  "maker": "Hexkit Project",
  "framework": "2.1",
  "platforms": ["linux/amd64", "linux/arm64"],
  "terms": [{"label": "MIT", "url": "https://opensource.org/license/mit"}],
  "touches": {"hosts": ["github.com", "objects.githubusercontent.com"]},
  "install": {
    "steps": [["sh", "{dir}/install.sh"]],
    "verify": ["{dir}/bin/hexkit", "--version"]
  },
  "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
  "verbs": {
    "dump": {"about": "A file's bytes as hex.", "usage": "FILE",
             "run": ["{dir}/bin/hexkit", "dump", "{args}"]}
  },
  "guidance": "GUIDE.md"
}
```

`install.sh` is where the tool comes from its maker, at a version you pin,
held to the checksum its maker publishes:

```sh
#!/bin/sh
set -eu
v=1.4.2
case "$(uname -m)" in x86_64) a=amd64 s=3f1c...e9 ;; aarch64) a=arm64 s=a07b...4d ;; esac
curl -fsSL -o hexkit.tgz "https://github.com/hexkit/hexkit/releases/download/v$v/hexkit-$v-linux-$a.tar.gz"
echo "$s  hexkit.tgz" | sha256sum -c -
mkdir -p "$(dirname "$0")/bin" && tar -xzf hexkit.tgz -C "$(dirname "$0")/bin" hexkit && rm hexkit.tgz
```

Every field is in [Writing one](tool-packs.md#writing-one); what a verb may
run is in [Verbs](tool-packs.md#verbs). A new version of the tool is a new
commit of your pack, and a new pin in the catalog.

## A coding agent

A coding agent is a tool pack whose manifest also carries an `agent` block:
an adapter of data that says how AerieOS starts the agent, hands it the
briefing, holds it to the same guards as every other agent through its own
hooks, signs a person in, and finds its conversations. The agents AerieOS
ships are described the same way, in `packs/agents/` of the catalog, so
each of them is a worked example beside this one:

```json
{
  "name": "kite",
  "label": "Kite",
  "about": "Kite Labs' coding agent, as a session's agent.",
  "maker": "Kite Labs",
  "framework": "2.2",
  "platforms": ["linux/amd64", "linux/arm64"],
  "terms": [{"label": "Kite terms of service", "url": "https://kite.example/terms"}],
  "touches": {"hosts": ["downloads.kite.example"]},
  "install": {"steps": [["sh", "{dir}/install.sh"]], "verify": ["{dir}/bin/kite", "--version"]},
  "layout": {"bin": ["bin"], "tool": "bin/kite"},
  "agent": {
    "name": "Kite", "product": "Kite CLI", "provider": "Kite Labs",
    "command": "kite",
    "briefing": {"how": "flag-file", "flag": "--rules-file"},
    "hooks": {"file": ".kite/hooks/aerieos.json", "shape": "grouped", "payload": "snake",
              "events": {"pre": "PreToolUse", "prompt": "UserPromptSubmit", "stop": "Stop"},
              "tools": {"shell": ["run_command"], "edit": ["edit_file"]}},
    "env": {"KITE_DISABLE_AUTOUPDATER": "1"},
    "respawn": ["--continue"],
    "allow": {"how": "flag", "flag": "--allow", "rule": "shell({cmd}:*)"},
    "signin": {
      "login": ["kite", "login", "--device"],
      "flow": {
        "url": "https://auth.kite.example/device",
        "code_after": "enter this code",
        "ends": "exit",
        "kept": ".kite/auth.json",
        "logout": ["kite", "logout"],
        "who": {"email": ["account", "email"], "plan": ["account", "plan"]}
      }
    },
    "transcripts": {"dir": ".kite/sessions", "file": "{session}/log.jsonl", "session_key": "session_id"},
    "models": ["kite-1", "kite-1-mini"], "model_flag": "--model"
  }
}
```

What each part means, and what an agent needs to be taken at all:

- **The guards are not optional.** `hooks.events` must name the agent's own
  event before a tool (`pre`), on a prompt (`prompt`) and at the end of a
  turn (`stop`). An agent with no hooks to hold it by is refused, as a
  shipped one would be. An agent whose hooks are not one of the two named
  shapes describes its own protocol as data
  ([A protocol of its own](tool-packs.md#a-protocol-of-its-own)).
- **The sign-in is described, never scripted.** `signin.flow` says how the
  program's sign-in goes in plain words: how its link starts, the words a
  one-time code follows (or the words it waits at for a pasted code), how
  it ends, the file the sign-in is kept in, and where who is signed in is
  read. With it the Installed page signs a person in, on a phone too;
  without it the agent signs in in its session's terminal. Every key is in
  [A sign-in from the page](tool-packs.md#a-sign-in-from-the-page).
- **Its name is its sessions' name** (`kite-myspace`): 2 to 16 lowercase
  letters and digits, never a shipped agent's.
- `"framework"` says the newest thing the manifest uses
  ([The framework's version](tool-packs.md#the-frameworks-version)), and
  the check holds a manifest to the version it says: here 2.2, for a
  sign-in that ends by itself and says where who is signed in is read. An
  AerieOS from before a version takes the entry and leaves that part out.
  `"format": 2` is said only by an agent that describes a hook protocol of
  its own, which an older AerieOS could not run at all.

The full table of keys is under
[A coding agent of your own](tool-packs.md#a-coding-agent-of-your-own).

## A Docker app

An app is a folder with two files: `bbapp.json`, which says what it is, and
a `compose.yml` held to a few rules (every image pinned to a tag that is not
`latest`, nothing built, nothing privileged, and only the blanks New
container fills: `${PORT}`, `${DATA}`, `${MEDIA}`, `${PUID}`, `${PGID}`,
`${TZ}`).

```json
{
  "name": "whoami",
  "label": "whoami",
  "about": "A tiny web server that answers with the hostname, the address and the headers of the request.",
  "maker": "Traefik Labs",
  "framework": "2.1",
  "license": {"label": "MIT (traefik/whoami)", "url": "https://github.com/traefik/whoami/blob/master/LICENSE"},
  "compose": "compose.yml",
  "port": 8089,
  "media": false,
  "platforms": ["linux/amd64", "linux/arm64"]
}
```

```yaml
services:
  whoami:
    image: traefik/whoami:v1.10.4
    restart: unless-stopped
    ports:
      - "${PORT}:80"
```

The image is the maker's own, from the registry they publish to.

## Try it on your own install

Do this before anything else: what the form's **Look** shows is what a
maintainer will read.

**A tool pack.** On the **Library**, press **Add your own**, pick **A tool
pack**, and give it your repository (or paste the manifest, or upload the
folder). **Look** reads the manifest and shows what it would fetch and run,
every verb with the exact words it runs, its terms and what it touches, or
says in a sentence what is wrong with the manifest. **Add** keeps it, as
Sideloaded. Install it on a node from its card, tick it in a space's
**Settings**, **Toolchains**, and run its verbs from a session there
(`aerie tool hexkit dump FILE`). [Adding one](tool-packs.md#adding-one) has
each step.

**A Docker app.** **Add your own**, **An app**: give it a name, an id, one
line of what it is, its port, and paste the compose file. **Look** holds
the compose to the rules above and **Add** offers it in New container. Make
a container of it and open it.

**A coding agent.** Add its pack the same way: **Look** reads the `agent`
block and names anything in it that is not said right. A pack you added
yourself does not offer its agent by itself, since an agent's adapter
decides what runs in every session of it and nobody has vetted yours: turn
on **Offer coding agents from packs added here** in Controller settings,
under Vetted catalog. The agent is then listed with the coding agents on
this install, as Sideloaded: install it on a node, sign in to it from its
page, start a session, and walk what the maintainers will walk (the
briefing in its conversation, a refused command refused, a turn's working
and waiting on the dock). Turn the setting off again when you are done.

## Run the catalog's check

The check is what the catalog's CI runs on a pull request, and it passes
exactly when an install would take the entry: it fetches the pack at the
commit you pin, checks the archive's sha256, and holds the manifest to
AerieOS's own validators as every supported release carries them.

1. Fork and clone <https://github.com/aquilaelabs/aerieos-catalog>.
2. Add your entry to `index.json`, at the end of `packs`:

   ```json
   {"name": "hexkit", "url": "https://github.com/you/hexkit-pack",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "sha256": "…", "tier": "vetted", "withdrawn": false,
    "about": "Looks inside binaries: dumps, strings, headers.",
    "platforms": ["linux/amd64", "linux/arm64"],
    "maker": "Hexkit Project", "framework": "2.1"}
   ```

   | Key | What it is |
   |---|---|
   | `name`, `about`, `platforms`, `maker`, `framework` | The manifest's own, repeated, so a card can show them before anything is fetched. |
   | `url`, `commit` | The pack's repository and the full 40-character commit, never a branch or a tag. |
   | `path` | The pack's folder in that repository, when it is not the root. |
   | `sha256` | Of the archive at that commit: `git archive --format=tar COMMIT \| sha256sum`, or `git archive --format=tar COMMIT PATH \| sha256sum` with a `path`. |
   | `tier` | `vetted`. A maintainer sets `verified` for a vendor `verified-vendors.json` lists. |
   | `format` | The manifest's `format`, when it is more than 1. |
   | `works_with` | The manifest's `works_with`, when it names any: an install on another release line does not list the entry. |
   | `kind` | `"app"` for a Docker app; left out for a pack. |
   | `agent`, `label` | `true` and the agent's name, for a pack that brings a coding agent. |
   | `withdrawn` | `false`. |

3. Run the check on your entry:

   ```sh
   pip install cryptography
   mapfile -t releases < <(tools/aerieos-checkouts.sh)
   python3 tools/catalog-check.py "${releases[@]}" --changed-from origin/main
   ```

   The first line fetches each AerieOS release the catalog supports
   (`aerieos-releases` lists them); the second holds your entry to every
   one that reads its format. It prints each problem in a sentence and
   ends `0 problems` when there are none.

Do not sign anything: `index.sig` is the maintainers', and a pull request
that changes it is not merged.

## Open the pull request

One entry a pull request. It holds:

- the entry in `index.json`, and for an app proposed into the catalog its
  folder under `packs/apps/NAME`;
- in the description: what the tool is and who makes it, where the install
  fetches it from and how the download is checked, the terms it is under,
  what you tried it on (the AerieOS version, the node's system and
  architecture), and for a coding agent the version of the agent you wrote
  the adapter against and how you learned each fact in it (its docs, its
  own help, a run).

The check runs on the pull request. A red check says why in its log.

## What the maintainers do

- **Read what it runs.** The install steps and every verb, at the pinned
  commit: where each download comes from, that it is the maker's own, that
  it is held to a checksum, what needs root (`touches.root`), and that the
  hosts it reaches are the ones `touches.hosts` names.
- **Install it** on each system the entry says it works on, and run its
  verbs. An agent is started, signed in to and walked: the briefing in its
  conversation, a refused command refused, a turn's working and waiting on
  the dock.
- **Run the scanners** over the pack.
- **Sign and merge.** The index is signed with the maintainers' key and the
  pull request merged. From then on every install lists the entry at its
  next look at the catalog.

Vetting says the pack does what its manifest says and fetches what it says
from whom it says. It is not a promise about the tool itself.

## After it is in

- **A pin is for good.** An entry stays at the commit it pins until a later
  signed index pins a newer one. So the commit must stay in your
  repository: never rewrite the branch it is on.
- **An update is another pull request** that moves `commit` and `sha256`
  (and `framework` or `format`, if the manifest now uses more). An install
  that holds the pack sees **Update manifest** on its card, with what the
  new pin changes marked verb by verb, and takes it when a person says so.
  Nothing updates by itself.
- **What is there is never rewritten.** The framework only grows: a
  manifest valid today is valid on every later AerieOS, so no change to
  AerieOS or to the catalog will ask you to rewrite an entry.
- **Say which AerieOS it works with only when you must.** A manifest with
  no `works_with` works with every release line. One that names lines is
  shown only on those, and on an install that upgrades past them a kept
  copy is switched off until you pin a version that names the new line.
- **A pack found wanting is withdrawn** (`withdrawn: true` in the next
  signed index): it is no longer offered, and every install that holds it
  says so on its bell.
