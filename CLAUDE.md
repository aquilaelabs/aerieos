# Working inside AerieOS

What this tree is, how it is built and tested, and where its parts live.
How to work here is the house rules (`aerie rules`); what this machine is and
does is the briefing every session gets; the reasons behind both are in
CONTRIBUTING.md and docs/decisions.md.

## About this project

This repository **is** AerieOS: the source of the container the
controller runs in. `scripts/` becomes `/opt/aerieos/scripts`,
`config/templates/briefing.md` is the briefing every session on every
project is handed, and the Dockerfile is the whole product. There is no
application here; the deliverable is the environment.

**Editing a file here does not change the running controller.** `aerie` on the
PATH is the installed copy, not `scripts/aerie` in this tree; `bash scripts/aerie
<verb>` runs the checkout's (it sources the library beside itself), and
`aerie lint` prints `[skip]` for a tool the running image does not carry.
Nothing is live until the operator rebuilds the controller from the branch,
which `aerie status` and the dashboard header say the short commit of; `aerie
catchup` says what the box has run and what changed since.

## Build

The image, and nothing else: `.github/workflows/build-image.yml` builds and
pushes `ghcr.io/aquilaelabs/aerieos` on a push to `main` that touches the
image's inputs (Dockerfile, `scripts/`, `config/`), plus a weekly uncached
rebuild; a manual dispatch is cached unless its `no_cache` box is ticked. It
runs on a hosted, pinned `ubuntu-24.04`, and a pull request does not build
it. Claude Code is in neither the image nor the boot: a session runs on a
node, which carries its own.

## Test

```bash
aerie lint                       # shellcheck, hadolint, ruff, actionlint, compose, XML, the doc checks: the set CI runs
aerie tests unit                 # the python unit tier, scripts/dashboard/unit, under a minute
aerie tests run                  # the dashboard's Playwright suite; aerie dashboard test FILE for one file
aerie tests preflight            # what the branch changed, the suites that reach it, lint, voice, design: before a push
aerie tests lab                  # the lab suites, against the lab's own stack (lab/compose.yml)
```

The browser suite runs the checkout's `server.py` on a spare port with a
scratch state directory, fake projects and a private tmux server, from a
copy of the tree, one run at a time. A project whose settings name a
**test node** (picked in its Build and test section) sends `aerie tests run`, `aerie dashboard test`
and the gate's suites there as a job, the tree snapshotted and the lines
streamed back. Its discipline is the house rule
`tests`. `surface.mjs` holds the page's top-level names; a new one is
added there. `lib.mjs` is the pattern a suite follows (real touch over
CDP, dialogs recorded, console errors collected). `BB_TEST_TIMING=1`
prefixes each result with its seconds, which `aerie tests ingest` keeps on
the Tests tab. The `dashboard tests` workflow is separate from `lint` so a
timing-bound red run does not take the linters' verdict with it; `aerie
ci-log` reads either.

- **One suite or one question:** `aerie tests keep` holds the fixture up;
  `aerie dashboard test SUITE` and `aerie tests probe FILE.mjs` then attach to it.
  A probe is a scratch Playwright script importing `./lib.mjs` that asks the
  page a question. The kept world's server is the kept copy's, so a change
  to the dashboard's python needs `aerie tests keep stop` and a new keep.
- **What the page asks for:** `aerie dashboard trace [SECONDS]` prints what the
  server was asked over that window, by endpoint and by who asked;
  `uniform.mjs` holds the invariant (an idle page issues only its polls).
- **What the suite covers:** `aerie tests coverage [SUITE...]` counts every
  function the copy's page, server and agent reach and merges it into
  `.bb-map/coverage.json`; `aerie map covered NAME`, `aerie map uncovered [FILE]`
  and `aerie map unused` read it. A whole run refreshes it, and preflight picks
  suites by it (`aerie map affected`).
- **Before a push:** `aerie tests preflight`; `--dry` prints the plan,
  `--files F...` names the files, `--base HEAD` measures the working tree.
- **What other projects' sessions report:** `aerie diag reports` lists what
  sessions elsewhere said with `aerie report`; one worth fixing is added here
  with `aerie bug add`. Nothing goes back to the reporter.

## Finding your way

`aerie map find NAME`, `aerie map who-calls NAME`, `aerie map draws ID` and `aerie map
suites FILE` answer "where would I look" from `scripts/lib/codemap.py`'s
index, with the function's own comment; `aerie map sections FILE` reads a file
by its `// ---- name ----` headers, `aerie map state [FILE]` lists a page
script's page-level `let`s, `aerie map addresses` says which `file ~line`
details on the roadmap have moved. A miss is a bug to file and fix in
codemap.py. `aerie drift` lists what this checkout changed that the running
controller is not serving; `aerie dashboard dev` serves the live dashboard
from `./scripts/dashboard` until the container restarts (`--off` reverts).
`tools/readme-shots.mjs` retakes the README's pictures from a running
dashboard.

## Lint

`aerie lint` runs the set CI runs on a pull request: shellcheck (file list
from shebangs, a heredoc inside a script included), hadolint
(`.hadolint.yaml`), ruff (`ruff.toml`; the agent's own pins to a Rocky
node's python), actionlint (`.github/actionlint.yaml`, generated by `aerie
ci-labels --write`), compose validation, XML, and the doc checks: `aerie help`
against `docs/reference.md` (written by `tools/bb-ref.sh`), the settings
across compose, `.env.example`, the Unraid template and the reference,
`docs/api.md` against the routes, `docs/layout.md` against `git ls-files`,
the agent's version against its file, and the instruction channels (this
file, the briefing, the shipped rules). CI runs `aerie lint` itself, with
nothing skipped (`BB_LINT_STRICT=1`), and the unit tier, on the pull
request's merge ref and on a release's tag, where it and the browser suites
pass before anything is published; `aerie ci-log` reads a run's output.

## Layout and conventions

- **The agent's compatibility window.** `AGENT_VERSION` in
  `scripts/agent/aerieos_agent/__init__.py` is `WINDOW.BUILD`. A node
  whose agent is behind is sent nothing but its own update
  (`nodes.agent_stale`): inside a window its sessions run on and the
  controller sends that update by itself once the node is idle; across one
  the controller ends the sessions on a project whose node's agent is from
  the old window until a person updates it (`server.compat_holds`). BUILD never resets; the minor moves only for a
  break, in the same change as the removal of what it supersedes.
  `test/version.mjs` holds both WINDOWs to the VERSION file.
- **Three numbers.** `aerie version` moves per commit; a file two builds may
  read carries a format it checks (`.bb-map/map3.json`,
  `.bb-map/coverage.json`); `AGENT_VERSION` moves by hand with any change to
  the agent, and `aerie lint` fails when it did not.
- **/config's state.** `scripts/dashboard/stateversion.py` stamps
  `/config/state.json` with the newest file in `statemigrations/`, and a
  start refuses a `/config` newer than the build or older than
  `SUPPORTED_FROM`. A change to what a released install stores adds the
  next numbered migration; a shipped one is never edited (`aerie lint`). A
  release commits its `/config` snapshot with `tools/upgrade-snapshot.py`,
  which `test/upgrade.mjs` starts every later build on, and `aerie version
  release` refuses a version without one.
- **The dashboard is dependency-free.** `server.py` is stdlib-only and holds
  the routes, the transport and the gates; each handler checks who may ask
  and makes one call into the feature's module beside it, which answers
  `(payload, status)` and is handed what it needs by `configure()`.
  `index.html` is the markup, the stylesheet and the wiring that runs at
  load; `tab-*.js` one per document tab, `nb-*.js` one per notebook view
  (`nb-core.js` the notebook), `page-*.js` one per part of the page that is
  neither; all pure declarations, all `"use strict"`, served only by name
  from the page's own script tags (`server.page_scripts`). A tab kind
  declares `multi`, `live` and `open`.
- **The design language** is `docs/design-language.md`, written by this
  project's own Design view (`aerie design file > docs/design-language.md`,
  or `--from FILE` with the branch's own record, committed with the
  change) and measured by `test/uniform.mjs`; the house rule `design`
  holds it.
- **Anything the page can execute is a table lookup** (`MACROS`,
  the terminal's `TERM_KEYS`, `TOOLCHAINS`), never a command string, and
  `bb-tty` validates its one URL argument against directories that exist.
  The terminal, at `/termws`, is there for anything else.
- **A setting that has to be in the environment lands in five places:**
  `.env.example`, `docker-compose.yml`, `platforms/unraid/aerie-workshop.xml`,
  `docs/reference.md`, and `docs/unraid.md` when it needs host-side setup.
- **The briefing** is `config/templates/briefing.md`, assembled per session
  by `preamble.py` with the project's rules, roadmap and bugs: the core
  before `BUILDERBOT:CORE-END` and the project's own lines are in every
  session's block, and each `## Heading` with a `BUILDERBOT:TOPIC slug:
  gist` marker is a topic, named in the block's index and read with `aerie
  help TOPIC`. Nothing is copied into a project.

`README.md` is the front page and `docs/README.md` the index of the docs;
`docs/reference.md` holds the configuration and `aerie` references;
`docs/install.md` is the setup checklist, `docs/unraid.md` the host-side
walkthrough, `docs/how-it-works.md` the overview and the docs it names the
explanatory prose,
`docs/decisions.md` the design decisions with their dates and reasons, and
`docs/layout.md` the file-by-file layout.
