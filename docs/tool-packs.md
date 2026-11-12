# Tool packs

A tool pack is a toolchain you add to AerieOS yourself, from a git
repository you choose. AerieOS ships no packs and keeps no list of them:
a pack is somebody's repository, and adding one is your decision. Once
added, it installs onto a node like any shipped toolchain, and it gives
sessions commands of its own through `aerie tool`.

Use one for a tool AerieOS does not carry: a decompiler, a protocol
analyzer, a game engine's headless editor, your company's internal CLI.

## Adding one

A pack is a `bbtool.json` (Writing one, below, says what goes in it) and
whatever scripts it runs. It does not have to come from the tool's own
authors: you can write one for any tool, as Wrapping someone else's tool,
at the end, shows.

1. On the **Library**, press **Add your own** and pick a tool pack. Only an
   account whose roles give Curate can. Then pick where it comes from:
   - **A repository**: a git repository with the `bbtool.json` at its root
     (`https://`, ssh, or `http://` for a git host on your network).
   - **Paste bbtool.json**: the manifest alone, which is the whole pack
     when its install steps fetch the tool itself.
   - **Upload files**: a zip or tar of the pack's folder, the `bbtool.json`
     at its top beside the scripts it runs. A single top-level folder is
     dropped, as with a space's archive, and it is at most 8 MB, since
     every node carries it; a pack fetches anything bigger as it installs.
2. Press **Look**. AerieOS shows what it would do: what it fetches and
   runs to install, each command a session would get and the exact words it
   runs, its license, and whether it comes with guidance.
3. Press **Add**. A repository's pack is kept at the commit you looked at,
   and a later commit to it changes nothing here until somebody approves it.
   A pasted or uploaded pack is kept on the controller as a repository of
   its own, its version a commit there; the nodes take it from the
   controller, so it needs no git host at all.
4. Install it on a node from its card on the Library, like any toolchain.
5. In each space that should use it, open **Settings**, then
   **Toolchains**, and tick it. A pack starts off in every space, so
   adding one hands it to nobody by itself.

To update a pack you added yourself, open its card's **Edit**. For a repository's pack it looks
at the repository's head as it opens; for a pack made here it opens on its
`bbtool.json`, to change in place, or takes an upload of a new version, and
**Look** reads what you gave. Either way the form marks every command the
new version adds, changes (with what it was) or removes, and **Update**
keeps it. Where the pack is installed, uninstall it and install it again to
take the new version.
**Remove** takes it out of the catalog. It is refused while a node's store
holds the pack, naming the node: uninstall it there first, since a pack gone
from the catalog leaves no row to uninstall its files from.

## Official packs and agent packs

Everything AerieOS ships is a pack in this same format too (R169): under
`packs/official/` one `bbtool.json` per shipped toolchain, carrying the
recipe `config/toolchains.json` has for it under `shipped` (where it is
fetched from, how it is verified, the system packages it needs), and under
`packs/agents/` one per coding agent, carrying the adapter under `agent`
(the program sessions run, how it installs and updates, how a person signs
in, how it takes the briefing and AerieOS's guards, where its
conversations are). Both carry `"tier": "official"`, which is what lets
them stand in for install steps and verbs and take a shipped name; a pack
you add is `url`, and a pack from the vetted catalog takes the tier its
index entry says (the Library reads official and `aerie` as Packaged by Aerie).
An agent whose manifest cannot name how it takes the guards is
not a pack and is not listed. The files are written from the tables by
`tools/packs-export.py --write` and `aerie lint` fails when they drift, so
the format is one; the installer and the agents' adapters still read
their own tables, with one exception: how a shipped coding agent is
installed is its pack's `agent.install`, and the catalog's copy is the one
used when it is newer than the release's
([agents.md](agents.md#where-an-agent-s-install-recipe-comes-from)). The same folders live in the catalog repository
(`packs/official/NAME`, `packs/agents/NAME`, written there by
`tools/packs-export.py --catalog DIR`), and its index pins every one of
them at tier official to the catalog's own commit (`--catalog DIR
--index`, then the maintainer signs), so the catalog is the one list of
everything official and an install's Library shows a shipped row as the
catalog's, never twice.

### A coding agent of your own

A pack from the vetted catalog can bring a coding agent beside the five
AerieOS ships. Its `agent` block is an adapter of data, never code: it
says how AerieOS starts the agent, hands it the briefing and holds it to
the same guards, in the shapes AerieOS already writes for the shipped
agents. The pack installs the agent's program like any pack (its `install`
steps, its `layout.bin` on `PATH`), and a catalog update updates it.

```json
"agent": {
  "name": "Kite", "product": "Kite CLI", "provider": "Kite Labs",
  "command": "kite",
  "briefing": {"how": "flag-text", "flag": "--rules"},
  "hooks": {"file": ".kite/hooks/builderbot.json", "shape": "grouped", "payload": "camel",
            "events": {"pre": "PreToolUse", "prompt": "UserPromptSubmit", "stop": "Stop",
                       "recall": "PostCompact", "asking": "PermissionRequest"},
            "tools": {"shell": ["run_command"], "edit": ["edit_file"]}},
  "env": {"KITE_DISABLE_AUTOUPDATER": "1"},
  "respawn": ["-c"],
  "first_prompt": {"how": "after-dashdash"},
  "signin": {"file": ".kite/auth.json", "env": "KITE_API_KEY", "login": ["kite", "login"]},
  "transcripts": {"dir": ".kite/sessions", "file": "{session}/log.jsonl", "session_key": "sessionId"},
  "models": ["kite-1", "kite-1-mini"], "model_flag": "--model"
}
```

| Key | What it says |
|---|---|
| `name`, `product`, `provider` | What the page calls it (Start, the dock, the Library card). |
| `command` | The program a session runs, on `PATH` from the pack's own `layout.bin`. |
| `briefing` | How it takes AerieOS's briefing: `flag-text` (the text after `flag`), `flag-file` (the file's path after `flag`), `env-file` (a variable naming the file), `hook` (handed to the model by its own hooks, at its `start` event and again on the first prompt after a restart changed it; its `hooks.answers` says how, below) or `none`. |
| `hooks` | Its hooks file under the account's home, written by AerieOS at each start. `shape` is `grouped` (`{hooks: {EVENT: [{hooks: [{type, command, timeout}]}]}}`, as Claude Code, Codex CLI and Grok Build read) or `flat` (`{version: 1, hooks: {EVENT: [{type, bash, timeoutSec}]}}`, as Copilot CLI reads). `payload` is the fields its hooks send: `snake` (`tool_name`, `tool_input`, `session_id`) or `camel` (`toolName`, `toolInput`, `sessionId`). `events` names its own event for AerieOS's `pre` (before a tool), `prompt`, `stop`, and optionally `recall` (after a summary), `asking` (its permission prompt) and `start` (a conversation's start, for a briefing handed over by `hook`). `tools` adds its own names for a shell, an edit and a search where they are not the usual ones. An agent whose hooks are neither shape says its own as data: [A protocol of its own](#a-protocol-of-its-own). |
| `env` | Up to eight fixed words its sessions start with (an updater or telemetry off). Never a path, `PATH`, `HOME`, `LD_*` or a `BB_` name. |
| `respawn` | The arguments that resume its newest conversation, when a session comes back. |
| `first_prompt` | How a new space's brief is handed over: after `--`, after a `flag`, or not at all. |
| `signin` | Where its sign-in is kept (`file`, under the account's home, or `env`, a variable such as an API key): with either, a session does not start until one is there. `login` is the command that starts its sign-in, and `flow` says how that sign-in goes, so the page can run it: [A sign-in from the page](#a-sign-in-from-the-page). |
| `transcripts` | Where its conversations are kept, so `aerie transcripts` and the Sessions view read them, and which payload field carries a session's id. |
| `models`, `model_flag` | What Start's model step offers, and the option a pick is handed over with. |
| `allow` | How it is told that a command needs no asking: `how` is `settings` (a rule in the settings file its session starts with, as Claude Code reads), `flag` (the option `flag` repeated with one rule each, as Grok Build's `--allow` and Copilot CLI's `--allow-tool`), `rules-file` (a `file` under the account's home with one rule a line, as Codex CLI's execpolicy), `hook` (its own hook's answer before a tool approves each such verb typed alone, with no `rule`, where an agent's rules are in a settings file that is the person's own; its `hooks.answers.pre` gives the `approve`) or `none`. `rule` is the agent's own rule for one command, with `{cmd}` (`aerie version`) or `{argv}` (`["aerie", "version"]`) where the command goes. AerieOS fills it once for each `aerie` verb its controller decides ([agents.md](agents.md#what-an-agent-need-not-ask-about)). Left out, the agent asks by its own judgment. |

`pre`, `prompt` and `stop` are required: an agent that cannot take the
guards is refused, as the shipped ones would be. The pack's name is its
sessions' name (`kite-myproject`), so it is 2 to 16 lowercase letters and
digits and never a shipped agent's. An agent is offered only from a pack the
vetted catalog pinned (or an official one): a pack added by its address
installs its program but never offers its agent, since the adapter decides
what runs in every session of it.

### A protocol of its own

`grouped`, `flat`, `snake` and `camel` are names for descriptions AerieOS
keeps. An agent whose hooks file, payload or answers are none of them
writes the description out, and nothing in AerieOS has to know the agent:
the next one with words of its own is a manifest in the catalog and no
release.

```json
"hooks": {
  "file": ".otter/settings.json",
  "document": {"under": ["agent", "hooks"], "keep": true, "with": {"schema": 3},
               "handler": {"run": "{command}", "limit": "{seconds}"},
               "entry": ["{handler}"],
               "entries": {"pre": [{"matcher": "*", "hooks": ["{handler}"]}]}},
  "payload": {"session": "ctx.id", "cwd": "ctx.dir", "tool": "call.tool", "input": "call.params",
              "prompt": "message", "stop_active": "again",
              "args": {"command": "script", "file": "target"}},
  "answers": {"pre":    {"refuse": {"ok": false, "why": "{reason}"}, "pass": {"ok": true}},
              "prompt": {"refuse": {"block": true, "message": "{reason}"}, "say": {"context": "{text}"}},
              "stop":   {"refuse": {"again": true, "because": "{reason}"}}},
  "events": {"pre": "before_tool", "prompt": "on_message", "stop": "on_done"},
  "tools": {"shell": ["terminal"], "edit": ["patch_file"]}
}
```

| Key | What it says |
|---|---|
| `document` | How its hooks file is laid out, in place of `shape`. `under` is the keys down to the object that maps an event to its hooks. `handler` is one hook, with `{command}` where AerieOS's call goes and `{seconds}` for the time it is given. `entry` is an event's value, with `{handler}` where the hook goes, and `entries` gives one of AerieOS's events (`pre`, `prompt`, ...) an entry of its own. `with` is keys the file carries at its top. `keep` is true where the file is not AerieOS's alone (the agent's settings, a hooks file a person's own hooks are in): everything else in it is kept and only what `under` names is replaced. |
| `payload` | Where its hooks' payload keeps each thing, in place of a named shape: `session`, `tool` and `input` (the tool's arguments) at least, and `cwd`, `prompt`, `stop_active` (a stop a hook already refused), `transcript` and `call` (the number of the call to its model, 0 opening a turn) where it has them. Each is a dotted path, or up to four tried in order. `args` adds its own names for a command, a file and a search pattern inside the tool's arguments. |
| `answers` | What it reads back, as JSON on stdout, for each event: `refuse` when a guard said no (`{reason}` is why), `pass` when the call goes on (`{}` when left out), `say` for words meant for the model (`{text}`: a rule's text, a note, the briefing) and, before a tool, `approve` for an `aerie` verb the controller decides. `pre`, `prompt` and `stop` each need a `refuse`: an agent that cannot be refused cannot take the guards. Without `answers` it is answered as its shape's agents are. |
| `prompt_fires` | `each-call` for an agent whose `prompt` event is raised before every call to its model rather than once for each thing a person sends: the hooks of a prompt then run on the first call of a turn alone. |

A template is JSON the agent reads, so what it may hold is narrow: keys
that are names, numbers, true and false, and strings that are one
placeholder, whole, or one plain word (`command`, `allow`, `*`). No string
in one can be a command line, a path or an address: the only command a
hooks file runs is AerieOS's own, in `{command}`'s place.

A manifest written with a named shape stays valid: the names are kept for
good, and mean what they meant. Describing a protocol this way is pack
format 2, so such a manifest says `"format": 2`.

### A sign-in from the page

An agent that signs in on a screen of its own (a menu, a link, a field for
a code) can only be signed in at a keyboard, in its session's terminal,
unless its pack says how the sign-in goes. With `signin.flow`, Sign in on
the agent's page of the Installed page runs it on the node and shows a
person the link and a field for the code, which is what a phone can use:

```json
"signin": {
  "login": ["kite"],
  "flow": {
    "answers": [{"when": "Select login method", "send": ""}],
    "url": "https://auth.example.com/oauth/",
    "prompt": "paste the authorization code",
    "refused": "Got an error",
    "kept": ".kite/oauth-token"
  }
}
```

| Key | What it says |
|---|---|
| `answers` | Up to four things its screen asks before the link: `when` is the plain words it shows, `send` the key or short word typed there (letters and digits, eight at most; empty for Enter alone). Enter follows each. |
| `url` | How the link it prints starts: `https`, its host, and as much of the path as never changes. The link is read whole however the program wraps it. A program that signs in at one of several hosts gives up to four, as a list (framework 2.2). |
| `prompt` | The words it waits at for the code the provider's page hands back. The page draws a field, and what a person pastes there is typed into the program. |
| `code_after` | In `prompt`'s place, for a flow where a person types a code on the provider's page: the words that code follows on its screen. The page shows the code, and nothing is typed back. |
| `refused` | The words it shows when it does not take the code. The flow ends then and the page says why in the program's own words; without it, a code that was not taken is noticed after two minutes. |
| `kept` | The file under the account's home its sign-in is kept in. Its arrival ends the flow, signed in; it is what says who is signed in on a node, it is sealed where a node seals sign-ins, and a sign-out removes it. |
| `logout` | Its own sign-out command, where it has one (`["kite", "logout"]`); the kept file is removed after it. |
| `ends` | `exit` for a program that ends itself once signed in (`kite login` that returns): the flow waits for it, and it is signed in when it exits clean. Left out, the flow ends when the kept file arrives and the program is ended then, which is for one that stays up on its own screens (framework 2.2). |

Nothing in a flow is a pattern or a command line: the words are plain ones,
compared without their spaces or case, and the only program run is the
agent's own. The program is started in an empty folder of the account's,
on a terminal wide enough that a link stays on one row, and is ended once
its sign-in is kept: whatever it asks after that (a color scheme, its
terms, whether a folder is trusted) is the person's own to answer, in
their first session. The code a person pastes is typed into the program
and never written to the job's log.

`flow` is framework 2.1's ([the framework's version](#the-frameworks-version)),
so a manifest that describes one says `"framework": "2.1"`. An AerieOS from
before it leaves the flow out, and the agent signs in in its terminal there
as it did.

## The format, and what it promises

Everything a catalog entry can be is written in one format: a tool pack's
`bbtool.json`, a Docker app's `bbapp.json` and `compose.yml`, a coding
agent's adapter. The format has a number, and the number keeps a promise to
whoever writes a pack:

- **The format only grows.** A manifest that is valid at one number is
  valid at every later one, and means what it meant. Nothing already in the
  catalog is rewritten because something was added beside it, and you never
  have to follow AerieOS's releases to keep a pack working.
- **A manifest says the number it needs** (`format`), and its entry in the
  catalog's signed index repeats it. An AerieOS that reads that number takes
  the pack; one too old for it lists the card with what it needs (Needs
  AerieOS 0.10.0 or newer) and fetches nothing. It never guesses at a
  format it has not met.
- **Adding something to the catalog needs no release of AerieOS** as long
  as it is written in a format installs already read: a tool, a Docker app,
  a coding agent with words of its own are each a signed commit to the
  catalog.

### The framework's version

The framework has a version of its own, apart from AerieOS's, and it moves
whenever the framework changes. It is two numbers, written `X.Y`:

- **X is the format.** It moves when an AerieOS that does not read it could
  not run the entry at all. Such an install lists the card with what it
  needs and fetches nothing.
- **Y moves when something is added** that an AerieOS from before it simply
  leaves out, the rest meaning what it meant. An entry that uses it is still
  taken by every install that took it before, minus the new part. Y never
  goes back: after 2.1 comes 2.2, or 3.2 if X moves first.

A manifest says both, in two keys:

```json
"format": 2,
"framework": "2.1"
```

`format` is the least X an install must read to run the pack, a whole
number (left out, it is 1). `framework` is the version the manifest is
written for; left out, it is the format's first, `X.0`. What a manifest
uses has to be in the version it says: a manifest that names a `maker`
says `"framework": "2.1"` or later, and the check tells you so when it does
not. So the number on a manifest is what an AerieOS has to know to do all
of it, and a card written for a later version than an install reads says
on its Details what that install leaves out.

| Version | What it added | An AerieOS from before it | First read by |
|---|---|---|---|
| 1.0 | Tool packs (install steps, layout, verbs, config, system packages), Docker apps, and a coding agent whose hooks are a named shape (`grouped` or `flat`, `snake` or `camel`). | | 0.9.0's first releases |
| 2.0 | A coding agent that describes its own hook protocol (`hooks.document`, `hooks.payload` as paths, `hooks.answers`), `prompt_fires`, the `start` event, and the briefing and the allow list handed over by `hook`. | Hides the entry: needs AerieOS 0.9.0 or newer. | 0.9.0 |
| 2.1 | A coding agent's sign-in as data (`signin.flow`), so its page runs it; who a tool is by (`maker`) and each maker's tool where a pack carries several (`credits`). | Takes the entry: the agent signs in in its session's terminal, and the card names nobody as the maker. | the releases after 0.9.0-dev.5284 |
| 2.2 | A sign-in whose program ends itself once signed in (`signin.flow.ends`), and whose link may start in more than one way (`signin.flow.url` as a list). | Takes the entry; one that reads 2.1 runs neither kind of flow from its page, and the agent signs in in its terminal. | the releases after 0.9.0-dev.5284 |

### What stays AerieOS's own

A manifest describes; it never brings code that AerieOS runs as itself. So
a few things are words a manifest can only name, each with a meaning
AerieOS carries. These are the format's primitives:

| Primitive | The words |
|---|---|
| What a command's words may hold | `{dir}`, `{dist}`, `{project}`, `{args}` |
| A node's package managers (`system`) | `apt`, `dnf`, `pacman`, `zypper`, `apk` |
| A config field's kind | `secret`, `text`, `choice`, `list`, `switch`, `projects` |
| A Docker app's blanks | `${PORT}`, `${DATA}`, `${MEDIA}`, `${PUID}`, `${PGID}`, `${TZ}` |
| How an agent takes the briefing | `flag-text`, `flag-file`, `env-file`, `hook`, `none` |
| A named hooks file shape and payload | `grouped`, `flat`; `snake`, `camel` |
| AerieOS's events an agent's own are named for | `pre`, `prompt`, `stop`, `recall`, `asking`, `start` |
| What an agent is answered | `refuse`, `pass`, `say`, `approve` |
| A template's placeholders | `{command}`, `{seconds}`, `{handler}`, `{reason}`, `{text}` |
| When its prompt event is raised | `once`, `each-call` |
| How a first prompt is handed over | `after-dashdash`, `flag`, `none` |
| How it is told what needs no asking | `settings`, `flag`, `rules-file`, `hook`, `none` |
| An official toolchain's source, its version resolver and how its download is checked | `tarball`, `script`, `git`, `command`, `sdkmanager`; `approximate`, `android-repo`, `command-urls`, `zig-index`, `url-matches`, `text`, `node-index`, `github-release`; `json`, `go-json`, `none`, `file`, `github-asset`, `zsync`, `signature` |
| An official service's kind | `router` |

A new primitive is a new format number, never a change to an old one: the
words above mean what they mean for good. When something cannot be said
with them, the answer is a new word in the next number, and every manifest
already written stays as it is.

A toolchain AerieOS ships is a row of its own table and an official pack
in the catalog, written from that row. Most of a row is other people's
facts: where a release is downloaded, how its version is found, which
system packages it needs. So a row has a `rev`, and its entry in the signed
index repeats it: when the catalog's is higher than an install's own, the
install fetches that pack at its pin, checks its sha256, holds the row to
the primitives above and uses it in the shipped row's place, on the
controller and in what every node installs from. A recipe that moved
upstream is then a catalog commit and no release. The image's own row is
what runs with no network and whenever the catalog's is no newer; a row
that names a primitive an install does not carry is refused there and its
shipped row stays. A toolchain nobody ships yet is not a row at all: it is
a pack with its own install steps.

How the promise is held: AerieOS keeps manifests of every format it has
read (`scripts/dashboard/unit/packformat/`), each of which must pass its
validators in every later build, and its lint refuses a change to one a
release shipped. The catalog's own check holds every entry to each AerieOS
release still supported, so an entry is signed only when the oldest install
that reads its format takes it as the newest does.

## The vetted catalog

The public catalog (the `aerieos-catalog` repository, R169) is an index
of packs reviewed by AerieOS's maintainers, each entry pinning a pack's
repository to an exact commit and the sha256 of its archive at that
commit, never a branch or latest. The index is signed with the
maintainers' Ed25519 key; the public half ships with AerieOS
(`config/catalog.pub`), and an install reads an entry only after the
signature checks: an index changed on the way, or signed by another key,
is refused and the one read before stands, with the reason said. The file
may name a spare key on a second line, and an index signed by either is
read ([security.md](security.md#the-signing-keys-and-replacing-one)). Where it
is read from is the **Address** in Controller settings' Vetted catalog group. A pack the
catalog withdraws (`withdrawn: true` in the next signed index) is a line on
the bell for every install that holds it, saying to remove it. The Library
is what reads it. An entry may name a `path`, the folder of its repository
the pack lives in (the catalog's own packs do; a repository of several
packs may): its sha256 is then of that folder's archive at the commit,
Look reads the manifest there, and an install keeps the folder's files as
a pack made here, so a node fetches the folder and nothing else.

### Installing from the catalog

The Library's **Tool packs** cards are the index's packs not yet added,
each with who stands behind it, what it is and the platforms it works on:

| On the card | What it means | The index's word |
|---|---|---|
| **Packaged by Aerie** | The pack is AerieOS's own work: how the tool is fetched, checked and installed, for a toolchain, agent or app it ships or a pack its maintainers wrote. The tool itself is usually somebody else's, named beside the pill. | `official` (a shipped row), `aerie` |
| **Verified** | The vendor's own pack, from a vendor the maintainers have verified: a shorter list than Vetted. | `verified` |
| **Vetted** | Anybody's pack, reviewed by the maintainers. | `vetted` |
| **Sideloaded** | Added here by its address, or made here: no index pins it. | none |

To the left of that pill a card names who the tool itself is by: the
organization or the person that makes it, which an entry says in `maker`
(`"maker": "Google"`), in its manifest and again in its index entry so the
card can say it before the pack is fetched. A pack that puts several
makers' tools together says `"maker": "AerieOS"` (or whoever put it
together) and lists each under `credits`, which its Details page reads
out:

```json
"maker": "AerieOS",
"credits": [{"name": "shellcheck", "maker": "Vidar Holen"}, {"name": "ruff", "maker": "Astral"}]
```

Every entry in the vetted catalog names its maker; its check refuses one
that does not. A sideloaded pack's card names none, whatever its manifest
says: what nobody vetted does not get to say whose it is. Both keys are
framework 2.1's ([the framework's version](#the-frameworks-version)).

The words on the card are a person's; a manifest and the index keep their
own, and an AerieOS from before `aerie` and `verified` reads both as
vetted. **Install** opens
the same dialog as Add your own on the commit the index pins, with the
archive's sha256 checked on the way in: Look (on the card, or in the
dialog) shows what it fetches and runs, and Add keeps exactly that. A pack
the catalog withdrew is not offered, one already added is its own card,
and an official entry is the shipped row it names. The catalog's trouble,
when it cannot be read, is said over the cards.

A pack kept from the catalog stays at the commit it was kept at. When a
later index pins a newer commit of it (the same repository and folder), its
card says so and offers **Catalog update**, which opens the dialog on the
new pin with what it changes marked verb by verb, as Edit does for a pack
added by address; **Update** keeps it at that pin with the index's sha256
checked, its tier kept. A pack kept from the catalog has no Edit on its
card: its kept copy is reached from its Details page, where the line that
says where it came from carries **Look for a newer pin, or remove it**,
which looks at the index's pin too, never at the repository's head. A pack
that brings a coding agent sits with the coding agents, on the Library and
on the Installed page. A pack is kept at the
index's tier only at a commit and sha256 the signed index pins; anything
else is a pack by address, Sideloaded.

### Without the network

A controller that cannot reach the catalog installs from a mirror of it.
`tools/catalog-mirror.py catalog-mirror.tar.gz`, run on a machine with the
network (from a checkout of AerieOS), reads the catalog's index, checks
its signature, and fetches every repository the index pins at each commit it
pins, into one archive: the index as signed and a git bundle per repository.
`--from-dir` reads the index from a checkout of the catalog instead.

Controller settings' **Vetted catalog** imports it with **Import a mirror**.
The import is refused when the index is not the maintainers', when a pinned
repository is missing, or when the mirror was made before the one held.
Once imported, the Library reads the mirror's index whenever the catalog
does not answer, and a pack or app the mirror holds is fetched from its
bundle with nothing going to the network. A pack kept this way is kept as a
pack made here, so the nodes take it from the controller too. **Forget**
drops the mirror; what was kept from it stays. The same group holds the
catalog's address. A USB stick can carry one from the start: the stick
maker's `--mirror FILE` writes it onto the stick, and the controller imports
it as it starts (docs/image.md).

### Docker apps in the catalog

An entry of `"kind": "app"` is a Docker app: its folder holds `bbapp.json`
(`name`, `label`, `about`, `port`, `media`, `platforms`, `license`, and an
optional `icon`, a PNG, WebP or SVG file in the folder held to a pack's
rules) and
`compose.yml` beside it, the compose held to what an app of your own is held
to (every image pinned to a tag that is not latest, never built or
privileged, only the blanks New container fills). The Library lists it as
an **Apps** card with its tier. **Install** fetches the folder at the commit
the signed index pins, checks its archive's sha256, keeps the app and opens
New container with it picked, on the Library's node when that node runs
Docker (the card says when it does not); from then on New container offers
it to everyone, and each Create makes another container of it.

### A session asking for one

A session looks through the catalog with `aerie tool search WORDS`: each
entry's name, kind, tier and what it is, and whether it is added here, never
its address or commit. `aerie tool install NAME --why "what it is for"` asks for
a tool pack from it, and the space's **Install a tool pack** setting,
under Agents may, says what happens: **deny** refuses, **ask** (the default)
puts it on the bell for a person who may curate the catalog, whose Allow
adds it at the commit the signed index pins, its sha256 checked, and
**auto** adds it at once the same way. A session never installs a pack on a
node itself: once it is added, a person installs it from the Library. The
briefing names the two verbs and the setting's value.

## What a space's sessions can use

Each space's **Settings → Toolchains** lists every toolchain installed on
its node, shipped ones and packs alike. Shipped toolchains start on, packs
off. A toolchain left off is:

- not on a session's `PATH` or in its environment,
- hidden from the session's view of the toolchain store, and
- refused by `aerie`, which names this setting as the reason.

A session started after you save takes the change.

## Writing one

A pack is a `bbtool.json`, at the top of a repository or of an upload, beside
the scripts it runs:

```json
{
  "name": "hexkit",
  "label": "Hex kit",
  "about": "Looks inside binaries: dumps, strings, headers.",
  "platforms": ["linux/amd64", "linux/arm64"],
  "terms": [{"label": "MIT", "url": "https://opensource.org/license/mit"}],
  "install": {
    "steps": [["sh", "{dir}/install.sh"]],
    "verify": ["{dir}/bin/hexkit", "--version"]
  },
  "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
  "system": {"apt": ["libmagic1"], "dnf": ["file-libs"], "pacman": ["file"]},
  "verbs": {
    "dump": {"about": "A file's bytes as hex.", "usage": "FILE",
             "run": ["{dir}/bin/hexkit", "dump", "{args}"]},
    "report": {"about": "A report on a binary, into dist/.", "usage": "FILE",
               "run": ["python3", "{dir}/verbs/report.py", "--out", "{dist}", "{args}"]}
  },
  "guidance": "GUIDE.md"
}
```

| Field | What it is |
|---|---|
| `name` | The pack's name, 2 to 40 of `a-z`, `0-9` and `-`. It is the toolchain's name and the word after `aerie tool`, and it cannot be a shipped toolchain's. |
| `label`, `about` | What the Library and the Installed page show. |
| `format` | The pack format the manifest needs, a whole number; left out, it is 1. Say the number of the newest thing you use that an older AerieOS could not run ([The format, and what it promises](#the-format-and-what-it-promises)). |
| `framework` | The framework's version the manifest is written for, as `"2.1"`: the newest thing it uses, whichever number brought it ([The framework's version](#the-frameworks-version)). |
| `platforms` | Where it works, as `linux/amd64`, `linux/arm64`, `darwin/arm64` and so on; `linux/*` or `darwin/*` for any architecture of that system. A bare `*` is refused. |
| `terms` | The licenses or agreements it is under, each a label and a link, shown on its row. |
| `install.steps` | What runs after the repository is fetched into the store, each a list of words; `{dir}` is the pack's directory. This is where a pack downloads its binaries. |
| `install.verify` | One command that must succeed for the install to count. |
| `layout` | `bin`: directories inside the pack to put on `PATH`. `env`: variables to set, each a path inside the pack or `=VALUE`. `tool`: a file whose presence means it is installed. |
| `system.apt`, `system.dnf`, `system.pacman`, `system.zypper`, `system.apk` | The system packages the node needs, in each package manager's own names, installed first where the node lets AerieOS administer it. A node's family installs its own manager's list; a pack that names lists, but none for a node's manager, is not offered on that node, its card and an Install there saying which managers it names. A pack with no system packages fits every family. |
| `verbs` | The commands a session calls as `aerie tool NAME VERB`. |
| `works_with` | The AerieOS release lines it works with, e.g. `["0.9", "0.10"]`; none named is every one. A pack that does not name this install's line is not added, and one held that stops fitting after an upgrade is a line on the bell saying to update or remove it (R169 step 6). |
| `touches` | What it touches: `hosts`, up to 16 host names its install fetches from, and `root`, true when it needs root on the node to install. Look shows both before it is added, and a pack that needs root is added by an administrator alone (R169 step 4). |
| `config` | What it asks for on each node (R172): a list of fields, each `{name, label, kind, help, required, env, scope}`, the kind one of `secret`, `text`, `choice` (with `choices`), `list` (with `fields`, rows of them), `switch` or `projects`. The Installed page draws them as Configure on the pack's row for the node picked; the answers are kept on the controller, a secret sealed and never shown again, and handed to the node, where a field with `env` reaches the pack's verbs as that environment variable (a switch as `1` or empty, a list as JSON). `scope` is `node` (the default: one answer for everybody on that node, set by whoever may Configure there) or `person`: each person's own, set under **Yours** on the same row by anyone who works on that node's spaces, a secret sealed under their own key, written into their home on the node and read by their sessions' verbs over the node's answer. |
| `guidance` | A Markdown file in the repository telling a session, whichever coding agent runs it, when and how to use the pack. It reads it with `aerie help tool-NAME`. |
| `icon` | Optional: a PNG, WebP or SVG file in the repository, at most 64 KB, which its Library card shows in place of its kind's glyph. It is read at the commit the pack is kept at, and refused with the pack when it is not the image its name says. It is shown as an image and nothing else, so an SVG's scripts never run. A pack without one keeps its kind's glyph. |

### Verbs

Each verb's `run` is a list of words, never a line a shell reads. Its first
word is a file inside the pack (`{dir}/...`), or `sh`, `bash` or `python3`
followed by a script inside the pack. These may appear in the words:

- `{dir}`: the pack's directory in the store.
- `{dist}`: the space's `dist/`, made if it is missing, where results the
  Artifacts view lists belong.
- `{project}`: the space's name.
- `{args}`: a word on its own, replaced by whatever the caller typed after
  the verb, each word passed as one word.

So `aerie tool hexkit dump "a b" '$(id)'` runs `{dir}/bin/hexkit` with
exactly the arguments `dump`, `a b` and `$(id)`. Nothing is expanded.

The install marks executable every file a verb, an install step or
`verify` runs by its path, the layout's `tool`, and the files in its `bin`
directories. A file committed without its executable bit, as a forge's web
editor commits one, still runs.

### What a pack can and cannot do

- It installs and runs as the node's job account, inside the session's view
  and network, like everything else a session runs. It gets no access a
  session does not already have.
- Its files are read-only to sessions, so a session cannot change what a
  verb runs.
- It runs only what its manifest says, at the commit an administrator
  approved.

## Wrapping someone else's tool

A tool's authors need never have heard of AerieOS. To give a session a
decompiler, say, write the pack yourself: a `bbtool.json` whose install
steps download the tool's own release, and whose verbs run it.

```json
{
  "name": "ghidra",
  "label": "Ghidra",
  "platforms": ["linux/amd64"],
  "terms": [{"label": "Apache-2.0", "url": "https://github.com/NationalSecurityAgency/ghidra/blob/master/LICENSE"}],
  "install": {
    "steps": [["sh", "{dir}/install.sh"]],
    "verify": ["{dir}/ghidra/support/analyzeHeadless", "-help"]
  },
  "layout": {"tool": "ghidra/support/analyzeHeadless"},
  "verbs": {
    "analyze": {"about": "Decompile a binary headless, the results into dist/.", "usage": "FILE",
                "run": ["{dir}/ghidra/support/analyzeHeadless", "{dist}", "proj", "-import", "{args}"]}
  }
}
```

`install.sh` beside it fetches the release archive and unpacks it into the
pack's directory. Upload the two files as a zip, or keep them in a
repository of your own; a pack whose install needs no script of its own
can be pasted as its `bbtool.json` alone. A session then has
`aerie tool ghidra analyze FILE`, and nothing else of the tool's.
