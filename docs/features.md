# What AerieOS does

Everything AerieOS 0.5.0 offers, one area at a time, with the doc that
explains each in full.

## The dashboard

One page in the browser, at a desk or on a phone ([dashboard.md](dashboard.md)).

- **The rail** down the left edge: Home, Spaces, Build, Containers,
  Controller, Machines, Sessions, Jobs, People, Settings and Help. On a phone it is a bar
  at the foot.
- **Home**: tiles for what is running and what needs you (nodes online,
  containers running, jobs and failures, sessions open, updates due, CI in
  the red), your attention list, the last jobs and your pinned spaces.
- **Search** at the top jumps to any page, space, container or node.
- **The bell** holds what waits on your answer and what was said; **the
  doctor's dot** beside it is the controller's health at a glance.
- **The dock** at the foot of every page holds the chat and your terminals.
- **Help** is these docs, with a search across them, inside the dashboard.
- Color schemes, light and dark, chosen per person.

## Spaces

Each space holds git repositories, each in one space ([projects.md](projects.md)).

- **New space** makes one by its name; **Add repository** on its card
  clones one from GitHub, Gitea, Forgejo or any git remote, starts an empty
  one, or unpacks a zip or tarball of code you already have. Link an existing
  local repository to an empty one on a host; move a repository to another
  space.
- Groups, pins, a color of your own, rename, archive, and a trash that
  keeps a deleted repository, and which space it was in, until it is purged.
- A per-space **Settings** page: its node, build and test commands, what
  an agent may do, the toolchains its sessions may use, signing keys, file
  access and who is on it.

## A space's page

Everything about a space, shared between you and every session that
works there ([notebook.md](notebook.md)).

- **Overview**: house rules, memories, the code base at a glance.
- **Roadmap** of items and steps, sent to a session from the page,
  with a history of who did what.
- **Bugs**: a tracker sessions file into and read from.
- **Git**: status, commit, branches with a history graph, fetch, pull and
  push, and the CI runs of the repository's workflows.
- **Tests**: every run recorded and timed, per suite.
- **Analysis**: static-analysis findings from a scanner you run.
- **Artifacts**: the space's builds in `dist/`, with releases.
- **Docker**: the space's containers.
- **Wiki** and **Design**: a wiki read like an encyclopedia, and the
  space's design language and pages, which sessions follow.

## Sessions

([sessions.md](sessions.md), [agents.md](agents.md))

- **Start agent** opens a session of Claude (Claude Code), ChatGPT (Codex
  CLI), Copilot (Copilot CLI) or Grok (Grok Build) on the space's node, in a real terminal in
  the dock. Resume it later, restart it, and pick the model and effort.
- Each session starts **briefed**: the space's house rules, roadmap and
  open bugs, so you ask for the thing rather than explain the place.
- **What an agent may do is a dial per space**: add to the roadmap, file
  bugs, add rules, write the wiki, run its container, sign a build, publish
  a release. Each is allowed, asked of a person, or refused.
- **A session sees only its own space** on disk, with your git identity on
  its commits. Credentials stay out of its reach: it reaches a git host only
  through `aerie git` and signs through AerieOS, without ever holding the
  keys.
- **Asking**: a session waiting on a permission prompt shows amber in the
  dock, on its space and in the bell.
- A session may **read other spaces** you allow, without changing them.
- Each person signs in to each agent with their own account, on each node,
  from the Installed page under Machines.

## The `aerie` command

What a session (or you, in a terminal) uses to work with AerieOS
([aerie-command.md](aerie-command.md), [reference.md](reference.md)).

- The notebook from the terminal: `aerie roadmap`, `aerie bug`, `aerie rules`,
  `aerie design`, `aerie changelog`.
- `aerie build`, `aerie test` and `aerie run` on the space's node.
- `aerie map`: where a name is defined and who calls it, across the code.
- `aerie capture`: screenshots and frame-by-frame reels of a page or the
  emulator that a session can look at.
- `aerie tool`: the commands toolchains and tool packs give a session:
  documents to Markdown, graphics, diagrams, sound, and your own.

## Nodes

The machines that do the work ([machines.md](machines.md), [nodes.md](nodes.md)).

- **Enroll node** gives you one command to run on a machine: it sets the
  machine up and connects it. Nodes run Ubuntu 24.04 or later or Rocky
  Linux 9.
- A node **dials out** to the controller: on your network, or from
  elsewhere through a public hostname.
- **Hosting-only nodes** for a public box such as a cloud VPS: they run the
  containers sent to them and nothing of them reaches back home.
- An **SSH door** through cloudflared, switched on and off from the node's row.
- Each node's **storage**, **network**, sessions and logs on its page, and
  its agent updated from the dashboard.
- **Files**: browse, preview, upload, download, rename, move and delete
  on a node's pools, array and shares, with a trash, for administrators.
- **Jobs**: every build, install and container action as a job, with its
  log, on the Jobs page.

## Toolchains

([toolchains.md](toolchains.md))

- A catalog of toolchains installed per node from the Library: JDK,
  the Android SDK, Flutter, Go, .NET, Node.js, Python, Rust, Swift, Zig,
  Playwright, ffmpeg, language servers, lint tools, document, graphics,
  diagram and speech tools, LibreOffice, and PyTorch with CUDA.
- Kept on a store outside the node's system, so a rebuilt machine keeps them.
- Updates checked and offered; anything under an agreement (Google's Android
  SDK terms, NVIDIA's CUDA license) asks you to accept it first.
- **Tool packs** ([tool-packs.md](tool-packs.md)): add a toolchain of your
  own for any tool, from a git repository, a pasted `bbtool.json` or an
  upload, with the commands it gives Claude. Kept at the version you
  approved.
- Per space, which toolchains and packs its sessions may use.
- **The NVIDIA card**: its driver and container toolkit installed on a node.

## Android

([toolchains.md](toolchains.md), [companion-app.md](companion-app.md))

- Android SDK versions, system images and an **emulator** per space.
- A **real phone** lent to a space through the Android app.
- **Release signing** with keys a session never sees.
- **The Android app**: your spaces, the bell and your sessions on a phone.

## Containers

([containers.md](containers.md))

- A space's compose file becomes a **dev instance** with one press, built
  and run on its node.
- **Copy or move** a container and its data to another node.
- **nginx** per node puts a hostname and a certificate in front of what runs
  there.
- Image updates checked and applied from the Containers page.
- A container given the machine's GPU from its settings: an NVIDIA card
  through the container toolkit, an AMD card or APU through its render
  devices.

## Builds, CI and releases

([building.md](building.md))

- Builds and tests run on the space's node; their output lands in `dist/`.
- A node can be a **self-hosted GitHub Actions runner**, with its CI logs
  readable from the space.
- Versions and a changelog per space, and releases tagged and published
  from the Artifacts view.

## People

([people.md](people.md), [users.md](users.md))

- Accounts with **roles**: built-in or your own, giving each area Read or
  Write, everywhere or per space.
- A space's **owner** and **invitations**.
- A **chat** between the people on a controller.
- **Your profile**: name, email and git identity, your time zone, and the
  devices signed in as you.
- **File access**: a space's files over FTPS, signing in with your own
  account.
- **Your key store**: your agents' sign-ins and the git tokens you give a
  space, sealed under a key of your account's. Profile lists what it
  holds, and you can purge it at any time without a password.
- **The install key**, made at install, seals what the controller keeps;
  an administrator changes it from the Keys page, with no environment
  variable to set.
- **Maintenance mode** closes everyone else's sessions, after saying who has
  one open and whether it is working.

## Running it

- One container, the controller; your spaces, its state and its
  toolchains in folders you choose ([install.md](install.md)).
- **Upgrades** between releases carried forward automatically, with a backup
  first and a clear refusal on an unsupported jump ([install.md](install.md#upgrading)).
- **Settings**, logs and diagnostics on the Controller group's Settings page.
- **Nothing is sent to us**: no telemetry ([privacy.md](privacy.md)).
