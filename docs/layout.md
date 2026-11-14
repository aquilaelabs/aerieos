# Layout

```
README.md                        the front page: what it is, its features, screenshots, and the way into docs/
CLAUDE.md                        working inside this repository: what a session here is told
CONTRIBUTING.md                  a person's way in: a checkout, seeing a change, proving it, the house rules, landing it
CHANGELOG.md                     the user-facing record, by release and category; aerie changelog writes it
VERSION                          this repository's own version, moved per commit by tools/version-stamp
LICENSE                          the Apache License 2.0
NOTICE                           the copyright line the license's notice section asks a redistribution to keep
.gitignore                       what the tree leaves out of git; .dockerignore what the image build leaves out of its context
.dockerignore                    (see .gitignore)
ruff.toml                        the python linter's settings for the controller; scripts/agent/ruff.toml pins the agent's to a Rocky node's python
Dockerfile                       image definition
docker-compose.yml               compose variant of the stack
.env.example                     annotated compose configuration
lab/compose.yml                  the lab's Gitea and Forgejo for aerie tests lab, a stack of its own beside the dev instance
lab/.env.example                 the lab's one setting: the address other machines reach it at
lab/stick-walk/.gitignore        what a walk leaves in its own folder
lab/stick-walk/README.md         a first run walked on a real stick image in QEMU, blank disks and a reboot included
lab/stick-walk/go.sh             the whole walk from a blank machine
lab/stick-walk/iso.py            the installer ISO in a VM as a person installs it: boot, the console's keys and screen, the installed disk after
lab/stick-walk/person.mjs        one browser step of it, its sign-in kept
lab/stick-walk/rehearse.py       the move off another NAS rehearsed on the walked stick: the branch's agent handed in and run, its checks read back
lab/stick-walk/rehearse-inside.py  that rehearsal, run as root on the stick: the old system's disks laid out, adopted, its VM defined and cloned, the array taken over and checked, every checksum compared
lab/stick-walk/rescue.py         the boot menu's Rescue picked over serial
lab/stick-walk/steps.mjs         the steps a person takes
lab/stick-walk/walk.py           the VM: its stick and disks, boot, stop, and root on its second serial port
platforms/                       each place the container edition installs (R98 step 1), its template and generated files; the installed
                                 edition's own parts (host/, modules/, installer/, image/) land beside it as they are built (R56)
  unraid/aerie-workshop.xml          Unraid Docker template (one-click updates)
image/                           AerieOS, the appliance image the installed editions are made from (R160 step 1): Debian stable by mkosi, pinned to the snapshot in SNAPSHOT, the controller staged in, sealed as a squashfs and laid into a disk with two root slots by build.sh; docs/image.md says what persists and how it boots
  SNAPSHOT                       the snapshot.debian.org timestamp every package is pinned to
  mkosi.conf                     the tree: Debian trixie, its packages (the controller's own come from config/controller-packages.tsv)
  mkosi.postinst                 inside the tree once its packages are in: install-controller.sh --stage, apt diverted, the services enabled
  mkosi.sandbox/                 apt's settings for a dated snapshot (its Release files are past their date by design), and NVIDIA's container toolkit source with its key (R207)
  mkosi.extra/                   what is laid into the tree: the initramfs script that mounts /var and /etc's overlay, fstab, the slot tool, the apt stub, the first-boot unit, the boot's own settings and the stick's network file, the data partition grown to its disk, the screen's login during a first setup, the installer and its unit, nouveau kept off an NVIDIA card (etc/modprobe.d)
  partitions.sh                  the disk's fixed partition UUIDs, sizes and labels, one place for build.sh, the initramfs, fstab and GRUB
  grub.cfg                       GRUB's menu on the ESP: the two slots, bb_slot from grubenv naming the one to boot
  iso-grub.cfg                   the ISO's menu: the same root run live from the medium, and where a new machine starts; it offers no installer
  lay-disk                       one disk laid out as AerieOS: the partitions, GRUB for both firmwares, slot A and the data partition; build.sh runs it on a loop device, the installer on a person's disk
  ovf.xml                        the OVA's descriptor (the VM disk for VMware and VirtualBox, R160 step 3), its marks filled by build.sh
  build.sh                       the build: mkosi, the squashfs, the disk on a loop device with GRUB for UEFI and BIOS, the stamps
scripts/
  entrypoint.sh                  the container's boot: uid remap, the timezone, then lib/boot.sh's steps and gosu
  host-boot.sh                   a bare-metal install's boot under systemd: lib/boot.sh's steps, then setpriv to its account (R90)
  supervisor.sh                  keeps the box alive; the graceful shutdown
  mint-runner-token              root-only token helper (one of the two sudo commands)
  deploy-key                     root-only deploy key helper: make, keep, forget, load; each key sealed under the install key and opened only into the ssh agent (the other)
  secrets-carry                  root-only carrier of the secrets folder across a move on a machine of its own: pack, land (a third sudo command there, B728)
  healthcheck.sh                 docker healthcheck
  aerie                          in-container helper CLI
  bb                             what an older agent calls in the bundle until it updates; no PATH carries it
  as-builder                     privilege-dropping wrapper for docker exec
  lib/common.sh                  shared shell helpers
  lib/host-env.sh                the image's ENV, the release's stamp and the env file, for a bare-metal install's service and its aerie (R90)
  lib/boot.sh                    the boot's steps both installs take: secrets shield, ssh-agent, home seed, hooks, state gate (R90)
  lib/controller-packages.sh     the controller's package list read one way, for the Dockerfile and a bare-metal install (R90)
  lib/relay-verbs                the aerie verbs a node relays to the controller (aerie and bbrelay.py both read it)
  lib/sdk.sh                     the toolchain manager: `aerie toolchains`, sourced by aerie
  lib/preflight.sh               `aerie tests preflight`, sourced by aerie
  lib/bbapi.py                   the controller's API from aerie: one client, the loopback or BB_CONTROLLER, pinned https
  lib/cmdmatch.py                which commands a shell line runs, read as a shell splits it, for a rule that refuses (R200)
  lib/rulehook.py                what a session's hooks keep about the house rules: what fired, the guard list, a refusal's words (R200)
  lib/sealfile.py                what a root helper in shell keeps, sealed and opened under the install key by the controller's own seal (the deploy keys)
  lib/syncwait.py                a session's aerie on a synced node waits for its copy to be in step with the controller's (R163)
  lib/codemap.py                 the code map aerie map answers from: an index over the tree, rebuilt when a source is newer (R75)
  lib/trace-verbs.py             aerie dashboard trace: what the server was asked over a window, by endpoint and asker
  lib/gh-fetch                   one GitHub release asset, kept only when it matches the digest GitHub states for it: the image and the bare-metal installer fetch their own tools with it (B335)
  lib/sdkmeta.py                 reads config/toolchains.json for aerie, with the tool packs beside it: fields, argv, versions
  lib/toolpack-run.py            `aerie tool PACK VERB`: a tool pack's verb from its manifest, the caller's words in place of {args}
  lib/docker-probe.py            which daemon is live, for `aerie doctor` and the boot log
  lib/log-split.sh               splits a long-running process's output: all of it to its own file, warnings to the boot log
  lib/supervise.sh               what the supervisor asks of the dashboard: its pid by the file it leaves, and a JSON string for the saved sessions
  lib/embedded.py                pulls scripts and python out of quoted heredocs so `aerie lint` sees them
  lib/waits.py                   the wait for a person's Allow and the job-log stream, shared by the verbs below
  lib/devapp-verbs.py            `aerie devapp`: status, rebuild, test, new, env, remove, ls, log, start, stop, restart
  lib/capture.py                 `aerie capture`: the sources anything that draws gives (a page, the emulator, an X display) and a shot at rest
  lib/reel.py                    `aerie capture reel`: the frames of a recording that changed, stamped and tiled
  lib/touch.py                   `aerie emu touch` and a drive script's $BB_TOUCH: a tap, hold or glide with its timing kept, through sendevent
  lib/hand.py                    a finger's path through points for a glide (curved, eased, overshooting, wobbling, by seed), played by `aerie emu touch` and `aerie phone touch`
  lib/sound.py                   `aerie tool sound`: sound effects from sfxr's presets and plain tones, into dist/sound/ as OGG with a waveform and a spectrogram (ffmpeg)
  lib/cilog-hosted.py            `aerie ci-log` for a project on GitHub's own runners: the runs and a run's failed jobs, from the controller
  lib/docs.py                    `aerie tool docs`: a document as Markdown (markitdown) or its pages as pictures (PyMuPDF), run with the documents toolchain's Python
  lib/poppler.py                 the pdftoppm and pdfinfo Claude Code's PDF reader asks for, drawn with PyMuPDF; the documents toolchain installs them
  lib/bbftp.py                   bb-ftpd: one project's tree over FTPS, each login asked of the controller through the agent; the ftp toolchain installs it (R151)
  lib/gradle-local-build.gradle  the Gradle init script bb-tty puts in a project's Gradle home: its build folders on the node's disk, linked from app/build (B439)
  lib/tmux.conf                  AerieOS's tmux settings: the controller copies them to ~/.tmux.builderbot.conf, bb-tty applies them to a node's tmux server
  lib/tmux-keys.conf             the keys the dashboard's terminal sends down its socket (a line of history up or down, leaving copy mode before what is typed), which bb-tty gives every tmux server before each attach
  lib/gpu.py                     `aerie gpu`: the node's NVIDIA card from where a session stands, and a turn on it for a heavy job
  lib/tidy.py                    `aerie tidy`: what a task left holding (its emulator, the card, build daemons, browsers, /tmp) given back
  lib/unitpar.py                 `aerie tests unit` across the cores: the modules dealt by their last measured seconds, one unittest process per core (R130), a module that failed run once more alone and said as flaky when it passes then
  lib/flakes.py                  the harness's flakes on record: a line for each suite that failed in a whole run and passed run again, with the first check that failed; `aerie tests flakes` counts them and preflight fails on one it ran
  lib/roottier.py                `aerie tests root`: the root tier's runner, as root in a container alone, a skip failing it (tools/root-tier.sh, `aerie devapp test root-tier`)
  lib/bottleneck.py              what bounded a run of the dashboard suites, from its own numbers: the floor, the machine, the reruns (R130)
  lib/browser.mjs                `aerie browser`: Chrome or Firefox with an unpacked extension loaded, on its own port and profile, driven and stopped by one verb
  lib/proc-verbs.py              `aerie proc`: this account's processes by a word of their command line, listed, ended or waited for, never the call's own shell
  lib/container-verbs.py         `aerie container`: status and new
  lib/pack-verbs.py              `aerie tool search` and `aerie tool install`: the vetted catalog looked through, a pack asked for as the project's Install a tool pack setting says (R169 step 5)
  lib/vm-verbs.py                `aerie vm`: a project's VMs listed, made, started, stopped, snapshotted and removed (R91)
  lib/phone-verbs.py             `aerie phone`: status and run
  lib/root-verbs.py              `aerie root`: status and run
  lib/report.py                  `aerie report`, and file/close from AerieOS's side
  lib/pc.py                      `aerie pc`: a person's Windows PC lent to the project, its verbs asked and their results read
  lib/diag.py                    `aerie diag`
  lib/node-log.py                `aerie logs --node`
  lib/login-check.py             `aerie login --check`: who this account is signed in to each agent as on this machine, told to the controller
  lib/login-flow.py              `aerie login --flow` and `--out` for every coding agent, shipped or a pack's: its sign-in's own screens worked from what its row or its pack says of them, the link sent up and the code typed in
  lib/emu-job.py                 `aerie emu` as a job on the project's node
  lib/run-job.py                 `aerie run`: the snapshot, the job, the log back
  lib/build-or-test.py           the command, place and outputs `aerie build` and `aerie test` read from the settings
  lib/git-policy.py              `aerie git policy`
  lib/relay.py                   a notebook verb relayed from a node to the controller
  lib/release-edit.py            `aerie version release --edit`: the notes and files read where it is typed, the edit asked over the API
  lib/forge-verbs.py             `aerie forge`: a verb and its arguments asked of the controller, which works the git host with the project's token
  lib/controller-stamp.py        the controller's build, for `aerie status` and `aerie catchup`
  lib/dash.py                    the dashboard's modules loaded by path for the notebook verbs, and the account name and "who wrote it" they share
  lib/markup.py                  YAML's subset, JSON, TOML, XML and Markdown's headings read in the standard library, for the records and the code map (R167)
  lib/roadmap-verbs.py           `aerie roadmap`
  lib/bug-verbs.py               `aerie bug`
  lib/brief-verbs.py             `aerie brief`: a new project's brief, and bb-tty's take of it for a first session
  lib/design-verbs.py            `aerie design`: a project's design language and pages, as the notebook's Design view keeps them
  lib/wiki-verbs.py              `aerie wiki`: a project's wiki pages, listed, shown, saved and removed under Agents may: Write the wiki
  lib/transcripts-verbs.py       `aerie transcripts`: the account's own conversations with each agent on a project, listed and printed
  lib/memory-verbs.py            `aerie memory`: the account's memories on a repository, kept for every coding agent, listed, read, added and forgotten
  lib/nb-history.py              `aerie history`: the notebook's logs merged
  lib/rules-verbs.py             `aerie rules`, except check
  lib/rules-check.py             `aerie rules check`: a rule's check command, run in this tree
  lib/tests-verbs.py             `aerie tests`: the registry verbs
  lib/tests-verdict.py           what went wrong, from a run's log (aerie tests last, the end of a run)
  lib/tests-away.py              which node a project's suites go to (R151): the test node its settings name, its workers from its cores and memory, its queue
  lib/preamble-verbs.py          `aerie preamble`
  lib/router-key.py              `aerie router-key`: the model router's address, this project's own key and its models (R144)
  lib/findings-verbs.py          `aerie findings history` and `aerie findings sample`
  lib/settings-verbs.py          `aerie settings`: show, set for build, test and outputs, and node from a controller shell
  lib/projects-adopt.py          `aerie projects adopt`: a folder already under the share made a project
  lib/sign-verbs.py              `aerie sign`: a build signed on the node with one of the project's keys, and its keys and mapping
  lib/busy-verbs.py              `aerie node busy` and `aerie node wait-quiet`: how busy this node is before a measurement
  lib/users-verbs.py             `aerie users`: list, claim, passwd, add, token
  lib/nodes-verbs.py             `aerie nodes` (and enroll-token) and `aerie ci-labels`
  lib/jobs-verbs.py              `aerie jobs`
  lib/work-verbs.py              `aerie work`
  lib/version-verbs.py           `aerie version`
  lib/changelog-verbs.py         `aerie changelog`
  lib/token-verbs.py             `aerie token keep`
  lib/login-list.py              `aerie login --list`: every account this machine is signed in as, each agent's read from what its sign-in data says (who_of), and the sign-out that forgets keys
  lib/doctor-probes.py           egl, project node, commit identity, session-capable node, signed-in account
  lib/lint-checks.py             aerie lint's own checks: runner label pinning, XML well-formedness, settings agreement
  startup.d/*.sh                 startup hooks
  dashboard/                     web dashboard: server.py (the routes, the transport and the gates, each handler one call
                                 into a module beside it); index.html (markup, stylesheet, the wiring that runs at load);
                                 one tab-*.js per document tab, one nb-*.js per notebook view (nb-core.js is the
                                 notebook itself), one page-*.js per part of the page that is neither, all strict,
                                 all pure declarations, served by name from the page's own script tags (R77)
    server.py                    the routes, the transport and the gates; each handler one call into a module beside it
    index.html                   the markup, the stylesheet and the wiring that runs at load
    terminal.html                one terminal on a page of its own: a tab popped out of the dock, and the Android app's session screen (R133)
    tab-*.js                     one per document tab (Docker, Nodes, Jobs, Schedules, nginx, Scanners, Storage, Library, a Library entry's own page, Installed, an installed thing's own page, Files, Toolchains, Agents, Emulator, Phone, Apps, Settings, Keys, Audit, Users, Profile, Findings, Projects)
    nb-*.js                      one per notebook view; nb-core.js is the notebook itself
    page-*.js                    one per part of the page that is neither: the state, the tabs, the panes and the dock, a project's rows, the polls, the bell, the doctor and the rest
    static/                      the favicon set and the SVG marks the page draws
    vendor/                      xterm.js 5.5.0 and its fit addon 0.10.0 as npm publishes them, with xterm's MIT license (R133), served by name under /vendor/
    bb-tty                       what a terminal runs: which tmux session it is, and whose
    bb-agent-hook                Codex's and Copilot's own hooks holding Claude's guards: their payload in Claude's shape, the same hooks run (R95)
    bb-codex-trust               AerieOS's own Codex hooks trusted for one launch, by the hashes that Codex reports for them (B284)
    bb-check-relay               the relay's own check, run by aerie tests preflight
    bb-gate                      the hook every tool call asks before it runs, on a node
    bb-prompt-relay              a node session's prompts and answers, back to the controller
    bb-work-note                 what a session is changing, for the overlap warning, and the named rules its file raises
    bb-rule-hook                 refuses a shell call a rule refuses, hands a definition grep the map's answer, and says the named rules again after a summary (R200)
    users.py                     who may sign in, and what they are allowed to see (docs/users.md)
    roles.py                     roles and permissions (R137): a grant is a capability on a scope, a role a named set of them, in roles.json; the gate (users.may) reads them
    prefs.py                     which model and effort a project's sessions run on, per agent
    settings.py                  controller settings, the things that used to be environment variables; switches, a text and two secrets never shown back
    storage.py                   the Storage page's answer (R169): the nodes an account holds the area on, each project's folders where it may see the project, the rest as one line
    history.py                   reporting for the controller's own machine (R164 step 4): the heartbeat's samples kept for weeks at falling resolution, one file per node under the state, read by /api/history
    extmounts.py                 the other disks and shares the controller's own machine mounts (R162 step 4): the record, a share's password sealed, what the hello hands the agent
    storebackups.py              the backups the controller's own machine copies (R162 step 5): the record, what the hello hands the agent, the summary Home and the bell read
    poolkeys.py                  the passphrases of the own machine's encrypted pools (R162 step 3): kept sealed, or asked after every boot and offered once; what the hello hands the agent, nothing in Safe mode
    nasapps.py                   the catalog of ready apps New container offers (R164 step 2): each a compose file pinned to a tag with its blanks in the environment, filled by render
    schedules.py                 the Schedules page's scripts (R117): an administrator's cron in the state, its timetable in words, its timer and the built-in scan
    tunnel.py                    the home tunnel the controller runs itself (R176): cloudflared as its child from the settings, and the hostname's record and rules through Cloudflare's API
    statefile.py                 writing a state file, and holding it while you read-modify-write one
    stateversion.py              /config's state version: the start's refusal of a newer or too old one, the copy before a migration, the JSON stores' migrations run, and /config put back with the start stopped when one fails
    statemigrations/             numbered migrations for the JSON stores (NNNN_name.py, run(ctx)), each run once as the state moves, never edited once shipped
    toolchains.py                everything behind the toolchains in the Library and the Installed page: catalog, sizes, the job worker
    toolpacks.py                 the tool packs a person adds (docs/tool-packs.md): a repository's bbtool.json, pinned to a commit, as catalog rows
    packconfig.py                what each added pack is configured with per node (R172): the answers to its config block, secrets sealed, handed in the hello
    library.py                   the Library's one list (R170): the toolchains and packs with what a node's store holds, the coding agents, the apps, the catalog's offers and the companions as rows of one shape
    catalogindex.py              the vetted catalog's index (R169 step 2): fetched from the catalog's address, its signature checked against config/catalog.pub before an entry is read, a withdrawn pack on the bell
    catalogrows.py               a shipped toolchain's recipe from the catalog when the catalog's is newer (R234 step 4): its row from its official pack's manifest, held to the primitives this build carries, kept under the state and carried by the table and the nodes' bundle in the shipped row's place
    packformat.py                the catalog's format number (R234): the number this build reads, what each added, and the sentence an entry past it is refused with; unit/packformat/N keeps manifests of each
    catalogmirror.py             the vetted catalog's mirror (R169 step 6): an archive tools/catalog-mirror.py made, imported under Controller settings once its index is the maintainers', answering when the catalog does not and holding each pinned repository as a git bundle
    emulator.py                  everything behind the Emulator page: a node's Android system images
    enrollscript.py              Enroll node as one script: the answers, the token and a WireGuard tunnel inside the provisioner
    memory.py                    everything behind the memory book: what Claude remembers per project
    rules.py                     house rules: what has been decided about working on a project
    preamble.py                  what every session on a project starts with, assembled once
    brief.py                     a new project's brief: kept out of CLAUDE.md, handed to its first session through a dialog
    design.py                    the notebook's Design view: a project's design language and pages, the prompts a session is pointed at, and docs/design-language.md written from them
    cilogs.py                    a project's CI on GitHub's own runners: its runs and the end of a failed job's log, read with the controller's token for `aerie ci-log`
    BbGlide.java                 a lent phone's glide as one held stroke: built on the node with javac and d8, run with app_process (R126)
    forgerelease.py              Release's forge half: the GitHub, Gitea or GitLab release beside a pushed tag, its notes the changelog's section and its builds attached
    ciwatch.py                   a project's CI watched once a day and at link: a moving runner label, an action a major behind, a red main branch and GitHub's notices on it, for the Git view, aerie catchup and the bell
    wiki.py                      the notebook's Wiki view: a project's wiki kept as a forge-shaped git repository of its own, exported as a zip and pushed to or pulled from the repository's wiki
    names.py                     what things are called: a project, a tmux session, a project's agent sessions
    agents.py                    the coding agents a session may run, one adapter each (R95): how each installs, signs in, is launched, briefed, guarded and read; page-agents.js is the page's copy
    projects.py                  new project / link and unlink a remote, the worker that clones and pushes, the locks and the pins Home shows
    forges.py                    which git host a remote is on, and the two things a host can be asked that git cannot
    forgeaccess.py               what an agent may do on a project's git host: the abilities, the token measured without changing anything, the project's Allow or Deny, and aerie forge's verbs on GitHub, GitLab and Gitea
    systems.py                   the systems a node can be: what Enroll node's pulldown offers, each with its provisioner family and its vetting (R204)
    ftp.py                       a project's file access over FTP and in an editor: the switches, the port, each account's access, and access_for, the one answer both doors give (R151, R159)
    wssync.py                    a node's projects as a synced copy: the index, state, since, get and put for its agent, and conflicts (R162)
    devices.py                   a person's devices: the token an app signs in for, the Devices list and Disconnect, and the device door an app syncs a project through as a node does (R270, R272)
    pcwork.py                    a person's PC lent to a project (R270): what the companion lends, a session's asks under Use a lent PC, the PC's long poll and its results
    apps.py                      the apps a person installs (R272): fetched from the release matching this controller, checked against their sha256, kept under /config/apps and served at /apps; the seed file read once
    snapshots.py                 each project's tree as it was each day, stored once by content, pruned to the project's days, and restored whole or a file at a time (R165)
    paths.py                     where the controller keeps what grows (snapshots, the git relay, logs), as the Settings page's Storage section sets it, and the move between two
    claudesync.py                a synced node's agents' conversations: the listing, get and put (whole, a tail, gone) for its agent's mirror (B613)
    fileexplorer.py              the Files page (R224): a machine's roots from its census, and each list, read, upload and change sent to its agent signed for that request
    files.py                     a project's files for a person's editor (R159): stat, list, read, write, rename, delete, search and changes, inside the project and never .git
    git.py                       the notebook's Git view: the repository read out, and its writes
    codebase.py                  the code base counted, by language, for the notebook's Overview
    logs.py                      what is kept, for how long, and the downloads behind the gear menu
    roadmap.py                   the roadmap; `aerie roadmap` drives the same file
    records.py                   the notebook's records whole as JSON, YAML or Markdown, and read back in (R167)
    bugs.py                      the bug tracker; `aerie bug` drives the same file
    notebook.py                  one batch over both of those, so half of one cannot exist
    pending.py                   what a session wants to add to the notebook, held for the operator
    ids.py                       one letter per notebook tab, so a number says which list it came from
    presence.py                  who else has a notebook open, in memory only
    overlap.py                   what each session is changing, and where two of them collide
    chat.py                      messages between accounts, and what each project's people are doing
    version.py                   one version identity per project, rendered for whatever is asking
    changelog.py                 the user-facing record beside it: categories, and the editor's writes
    artifacts.py                 what a project built: dist/, and what a row may offer
    signing.py                   a project's Android signing keys, kept by the controller, never a session's, and the sign-key jobs that work on them on the project's node (R106)
    releasesign.py               a release's unsigned APK from CI, signed on the project's node with its sideload key and attached, from a run that passed or one still going once its release exists (R106)
    releasefiles.py              a release checked against the files its project lists in .release-files as its CI ends, a short one said on the bell and a complete one said once (R190)
    membership.py                a project's owner, whether it is invite only, and the invitations to it
    registry.py                  projects by id (R154): each directory's permanent number and the name it is shown under, in projects.json; a directory is never handed out twice
    repos.py                     projects and their repositories (R138): which project each repository is in, in project-repos.json; create, add, move, detach for the trash, delete an empty one, and place one in no project
    busy.py                      whether a node is quiet enough to time anything on, and why not (R108)
    devapp.py                    a project's dev instance: built here, run here, driven from Artifacts
    devactions.py                the layer that runs and reports an instance: up, down, rebuild, test, remove, state and act, the compose plan and job runners, on the base devapp.py keeps
    relocate.py                  copying or moving a dev instance to another node, its volumes and data directory with it: three jobs, packed on the old node, unpacked on the new, then its rebuild
    containers.py                containers AerieOS did not build: the daemon's list and controls, ones written from a compose file, and whose each is; the Docker manager's view and verbs
    imagecheck.py                every container's registry images against what their registries serve (R195): a weekly check, Check for updates on the Containers page, Update on a row
    vms.py                       the VM manager (R91): each project's VMs on the nodes with VM host, the OS catalog matched by name, the limits, and the vm jobs
    gitcreds.py                  who gave a project a token, a line per person in /config/gitcreds naming their key store's entry, and the credential git work is handed: theirs while they are signed in (R135, R159)
    logins.py                    who is signed in now: a row per browser sign-in the cookie names, and a device signed in as the account, in /config/logins.json (R159)
    git-credential-bb            git's credential helper for that token: opened for the scheme and host it was written for, and nothing kept (R135)
    termws.py                    AerieOS's own terminal, the controller's half (R133): /termws in a pty here, or carried signed to a node's /term
    tokenkeys.py                 the controller's half of the sealed sign-ins (R126): each account's public key per node, made from the account's own key, and the keys a person's own terminal carries, each seal's by the key it names
    installkey.py                the install key the install made itself (R154): where it is kept, its fingerprint, shown to save, changed with everything kept under it sealed again
    accountkeys.py               each account's own key for its sign-ins on the nodes (R154), in account-keys.json sealed under the install key, changed from Profile
    router.py                    a model router on a node (R144): LiteLLM with the provider keys and Ollama as a written container, a key per allowed project, the models and the spend read at the router
    reach.py                     the bell's rows sent elsewhere per person (R149): email over SMTP, a webhook and its presets, each destination's kinds and quiet window, the minute loop holding a repeat while unchanged
    releasecheck.py              a newer AerieOS release for a bare-metal install (R90 step 5): asked of GitHub daily, said on the bell and under Controller settings, applied through the own node
    releasegaps.py               what a release owes the changelog (R217): the bugs fixed since the last release that it carried, with no Fixed line or answer
    checks.py                    update checks on one clock (R176): each check's cadence a setting under Controller settings, when it last ran, Check for updates
    firstboot.py                 a stick's prepared configuration at its first boot (R161 step 8): the owner and the people made, the setup page skipped where asked, the rest kept waiting, said on This machine
    adoptapps.py                 the containers another system ran, as compose files to import (R163 step 10): each written from the settings the read handed over (oldapps-put), its image, environment, ports, paths and network of fixed addresses, restarting with the machine where it did, what it will not do as written said at its top; a zip of them for an administrator, kept settings readable by the controller alone
    held.py                      a held start on a bare-metal install (R56 step 9): held after an unclean stop or when armed for the next restart, lifted by Start on This controller
    move.py                      moving this controller to another home (R90 step 12): the sealed bundle and its token, the nodes' challenges, the restore under the version gate, the old home marked moved
    backup.py                    the configuration backed up (R161 step 4): the move's bundle under a password's key, written onto the pools after every change, found and restored at a first run
    scanners.py                  AerieOS's own scanners on each node (R145): the compose project of Semgrep, Trivy and mobsfscan deployed and updated per node, one schedule for every node's runs, the SARIF each sends up, and the bell's rows
    nginxproxy.py                one nginx per node, AerieOS's own (R171): the routes and certificate kept here, the compose file generated from them, deployed and rebuilt through containers.py
    acme.py                      an ACME client on the cryptography library: Let's Encrypt certificates for the nginx page by HTTP-01 or DNS-01, renewed (R150)
    unlocks.py                   a person's tokens opened per use for the window they pick and logged, git's handout of an opened one, and a store under a key of the person's own opened only while unlocked (R158 step 5, R157)
    hardening.py                 the dashboard's process kept from core files and swap, not dumpable, and wipe() for a key let go (R158 step 6)
    csp.py                       the page's Content-Security-Policy, its inline blocks allowed by hash and its scripts by integrity, and what a browser refused under it, kept for the Doctor (R158 step 4)
    tls.py                       the dashboard's own TLS: one port serving https and http by the first byte, the install's own certificate or Let's Encrypt's, its key sealed under the install key (R158 step 2)
    phone.py                     a paired handset on a node: install, push, and the asking
    phonelease.py                a phone lent to a project (R113): the lease, and what its sessions may do on the phone without asking
    db.py                        the controller's store: the SQLite connection, the migrations, ids and the audit trail
    nodes.py                     the node registry, the job queue and the agent's channel (docs/nodes.md); the Nodes page's verbs; a build job from the controller
    channel.py                   the node agent's verbs behind /api/v1/agent/: enroll, hello, work, a job's files, log and result
    claudecode.py                Claude Code on each node: which version, checking for and installing an update
    agentcode.py                 the other coding agents on each node (Codex CLI, Copilot CLI): which version, the registry's latest, installing, updating and removing each (R95)
    claudegrant.py               which nodes each account is signed in to each agent on, as each node reported it
    mapping.py                   a new project's code map built in the background as it is created
    plugins.py                   the Claude Code plugins a project carries, listed and installed
    turns.py                     how many prompts a node lets run at once, and the queue when more ask
    workspace.py                 snapshots, the node bundle, and the artifact store
    jobs.py                      the controller's own job runner (exec here or over ssh) plus /healthz and /metrics
    vmtemplate.py                what a new sandbox VM is made from, with this one's identity in it
    idle.py                      ending sessions nobody has used for a while
    home.py                      Home's numbers across the install: nodes online, containers running, jobs running, failed today and the last ten
    notices.py                   what the page said to each account, kept per account (<state>/notices/UID.json, the newest 300): the Notifications page's history
    helpdocs.py                  AerieOS's own docs for the Help page: the docs README lists, one read by name, and a search across them
    projsessions.py              every account's sessions on a project, and an administrator ending one
    reports.py                   problems with AerieOS reported by any project's session (aerie report)
    diag.py                      the Diagnostics section of Controller settings: reports, images, errors, the audit trail, and the download
    featuresoff.py               the features an install switches off from its environment (FEATURES_OFF): the list, the sentence, and what the page and the routes read of it (R81)
    doctor.py                    `aerie doctor` run on a timer and cached, for the Doctor card
    runners.py                   a node's CI runners: the root-only token helper, and the Runner card's list
    findings.py                  the scanner's reports read and attributed, and what they used to say
    gitrelay.py                  a node session's push, fetch and pull, done in a repository of the controller's own
    pushscan.py                  what a push would send, read for secrets and private things before it goes, and the lines a person okayed (R219)
    bbrelay.py                   an aerie verb from a node's session, run here: which verbs travel, and what a session may push
    hooks.py                     what a node session's hooks post: overlap notes, the chat feed, the catch-up, the turn queue
    macros.py                    what the page may type into a terminal: the command and key tables, the pins, custom lists
    profiletab.py                an account's own settings, the Profile page
    mfa.py                       two-factor sign-in (R127): an authenticator app's codes, passkeys (WebAuthn, its CBOR and P-256 check), recovery codes, remembered browsers and wrong codes held, in two-factor.json
    qr.py                        a QR code as an SVG, for an authenticator app to scan (R127)
    transcripts.py               an account's conversations with each agent as a text to download, from a notebook's Sessions view
    fields.py                    one field out of a request body, read one way by the server and the modules it calls
    timing.py                    where a request's time went: named parts and its own CPU, for aerie dashboard trace
    share.py                     a part's share of what a session is sent: the rules, the roadmap and the bugs say less per row before they leave one out
    layout.py                    what the page keeps here: each account's tabs and panes, the dock's terminals among them
    bellseen.py                  what each account has dismissed from its bell: an update to one version, until a newer one is out
    migrations/                  numbered schema files for /config/builderbot.db, applied at boot
    labrecord.py                 the lab's own record: what each lab suite walked, on what and when, written by `aerie tests lab` into lab-record.json beside it, which a system's vetted line is read from
    lab-record.json              that record: the newest walks of each suite and subject, dated, with the build each ran against
    testreg.py                   the test registry: what each test protects, and
                                 what a run measured it costing
    notify.py                    getting a line into a running session, and knowing it landed
    signin.py                    each agent's sign-in and sign-out on one node, as jobs there
    test/                        its Playwright suite: `aerie dashboard test`, isolated; device-api.json in it pins what the released companion and VS Code extension read from the controller, each field's type, and deviceapi.mjs drives it (R79)
    unit/                        its python unit tier: `aerie tests unit`, the modules' rules without a server or a browser, run first by preflight (agentpkg.py loads the node agent for it)
    roottier/                    the root tier: what the root agent and the root helpers do in a folder an account controls, with a link planted where root works, seen as root (world.py is what its modules stand on)
  agent/builderbot-agent.py      the node agent's entry: runs the package beside it, and is the __main__.py of the zip a node runs
  agent/aerieos_agent/        the node agent, stdlib only, shipped to nodes by the dashboard as one zip
    __init__.py                  what the agent is and how it runs, and AGENT_VERSION
    base.py                      the constants naming the node's paths and tools, the log, own_path and own_digest
    bundle.py                    the zip a node runs, built the same on the controller and the node, so the digests agree
    controller.py                the connection to the controller, verified by pin
    stores.py                    the node's stores, a store's path rules, and node.json
    storage.py                   what the disks hold, by filesystem, store and project: an hourly walk on its own thread, for the Storage page (R169)
    backends.py                  the machine's package manager and network configuration backends
    vms.py                       the VMs a node runs (R91): the vm job's fixed table of virsh and qemu-img commands, cloud-init, the census of them, and their network's firewall
    vmhw.py                      a VM's hardware beyond size (R100): the host's CPUs and devices, pinning, the balloon, the network, a virtiofs folder, passthrough, the vBIOS dump
    lanbridge.py                 the wired LAN card in a bridge, br0, on AerieOS (R219), so a VM on it reaches its own host; once at a boot, put back without an address
    screen.py                    the node's one port for the controller's sockets, 7684, signed by the controller: the terminals (term.py) and a VM's screen for the dock (R99), relayed to its VNC on the loopback
    relaytls.py                  the relay port's TLS, loaded by both ends: the node's own certificate, the controller's pin on it, the pump between a TLS socket and the plain one each side's code keeps, and a signed request taken once
    term.py                      AerieOS's own terminal (R133): a pty per tab on the screen relay's port, running what its kind runs (rw, ro, ctr), signed by the controller
    toolchains.py                the toolchain store (R19): what is installed, who uses it, a session's environment
    gpu.py                       the NVIDIA card: its sample, its memory's holders, the driver and container toolkit
    sessnet.py                   each session kept to its own project's network (R79)
    scan.py                      the scan job (R145): each scanner run as compose with the node's project copies mounted read-only, its SARIF sent up as scan-put
    accounts.py                  each account a Unix user of its own on the node (R125): its user made, its home moved to it and back, the terminal's environment for bb-session tty
    tokenwatch.py                who opens an account's coding-agent token on the node (R125): the files held at 600, a reader that is neither the account nor the agent said on the next hello
    tokens.py                    the coding agents' sign-ins sealed on the node (R126): sealed where a login wrote them, opened into a tmpfs for a person's terminal, wiped after the last session
    tokenseal.py                 the sealing both ends load: an account's key pair per node, the seal, and the wrap a seal's key travels in to the agent
    names.py                     where a node keeps what is AerieOS's under its own name (R204): /etc/aerieos, /var/lib/aerieos and aerieos-agent where they are there, the names before where only those are, and the links and the command a starting agent adds so the new names answer before the Enroll script moves anything
    release.py                   whether an agent update is AerieOS's own release (R227): the Ed25519 release key a node pins at enrollment or at its console, the signature over the update's digest it then requires, and the console's word that unsigned builds are taken
    runners.py                   the CI runners: their slots and state, and Agent's runner verbs
    census.py                    the census and the sample every hello carries
    jobs.py                      Job: one piece of the controller's work, on its own thread
    ftp.py                       the file-access servers a project's settings open
    wssync.py                    keeps a node's synced copy of its projects in step with the controller's (R162)
    claudesync.py                keeps a synced node's agents' conversations and memories in step with the controller's (B613)
    sessions.py                  the session half (#24): what each terminal kind runs, tokens, firewall and upkeep, as Agent's methods
    workspace.py                 a job's source on disk, its artifacts, and the bundle of aerie
    work.py                      compose, toolchains, signing, images and system packages, as Agent's methods
    keyops.py                    the controller's signing key work on this node: a keystore checked, a key made or wrapped, a rotation's proof, a release's APK signed (R106)
    configplane.py               the configuration plane: the node's system, storage and network, as root
    osimage.py                   AerieOS on the machine (R160 step 4): the image, its slot and the next boot's for the census, and the os-update job that writes the other slot
    disks.py                     the machine's disks for the census (R162 step 1): lsblk's JSON and smartctl's, each whole disk with what its partitions hold
    shares.py                    the machine's SMB and NFS shares for the census and the storage-share job (R162 step 1): AerieOS's own two files, read and written whole
    pools.py                     the machine's ZFS pools for the census and the storage-pool job (R162 step 1): made, grown, scrubbed, a member replaced, exported, destroyed, each disk held to the census
    array.py                     the machine's array of mixed disks for the census and the storage-array job (R162 step 2): the record, snapraid.conf and the fstab lines rendered from it, made, a disk added or replaced, synced, scrubbed, checked, destroyed
    adopt.py                     another NAS's array and pools taken as they are for the census and the storage-adopt job (R163 step 8): each data disk found by its serial and mounted with the filesystem it holds, read-only unless writable is asked, parity left alone, the pools writable, the old paths and merged trees kept; never formatted or partitioned
    http80.py                    plain http://THE-MACHINE/ on a controller's own machine: a redirect to the dashboard on port 80, letting go for nginx and for a compose job (R202)
    console.py                   a way in at AerieOS's screen (R194): the admin account made with sudo from the console password's hash kept on the data partition, at every start, and the console job that sets or takes it
    power.py                     the machine's UPS through NUT and its own packages' updates for the census, and the host-update job (R164 step 3)
    files.py                     the Files page's requests on the screen relay's port (R224): list, read, write, mkdir, rename and delete into the trash, held inside a root that is never the system's own
    extmounts.py                 the other disks and shares the hello names (R162 step 4): each mounted at /mnt/other/NAME or unmounted as the record says, an SMB share's credentials root's alone, the census's rows
    packconfig.py                what each added pack is configured with here (R172): the hello's rows written as one env file per pack under the store's .bb/config, the session account's alone, which aerie tool reads into a verb's environment
    backups.py                   the storage-backup job (R162 step 5): rsync of a folder to another place, each run hard-linked to the one before, the oldest pruned, the last run for the census
    agent.py                     Agent: hello, the loop and self-update, made of the parts above
    cli.py                       enroll, run, status, sample
    coverage.py                  function coverage under aerie tests coverage only
  agent/ruff.toml                the linter's settings for the agent, pinned to the python a Rocky node carries
packs/                           the official packs (R169 step 1): every shipped toolchain and every coding agent as a pack in bbtool.json's format, tagged official and bundled for an install with no network, written by tools/packs-export.py from the tables and held to them by aerie lint
tools/catalog-mirror.py          makes the vetted catalog's mirror on a machine with the network: the signed index and a git bundle per repository at every commit it pins, for a controller that cannot reach the catalog (R169 step 6)
    official/                    one folder per shipped toolchain (a colon in its name a hyphen), its bbtool.json carrying the recipe config/toolchains.json has under shipped
    agents/                      one folder per coding agent, its bbtool.json carrying the adapter agents.py's table has under agent
    services/                    one folder per deployed thing of AerieOS's that is a pack (R172): the model router, its service block and its config block, what its Installed row asks for per node
apps/                            the companions a person installs (R98 step 1): the phone app, the editor extension and the
                                 Windows companion, each released by its own workflow and offered as a card in the Library
  android/                         the companion app: api-surface.json is its contract with the dashboard, each field's type pinned, app/ the Kotlin
  vscode/                          AerieOS for VS Code (R159): plain JavaScript, no build step and no dependencies
    package.json                   the extension's manifest: its commands, its settings, and aerieosApi, the Files API it speaks
    extension.js                   the builderbot: file system, the sign-in, open project, search and the session's terminal
    lib/client.js                  the controller as the extension speaks to it: sign-in through /login, the Files API, /term
    lib/ws.js                      a websocket client in Node's own modules, for the terminal
    lib/term.js                    AerieOS's own terminal on /termws, from VS Code: the frames the dashboard's dock speaks
    README.md                      what VS Code shows on the extension's page: setting it up, installing and using it
  windows/                         the Windows companion app (R270): a person's machine keeping a project's folder in step through the device door
    README.md                      what it does, signing in, picking a project and a folder, building it
    bbcompanion/__init__.py        the package: what the app is
    bbcompanion/__main__.py        its command line (sign in, add, remove, run, sign out) and the packaged app's start
    bbcompanion/core.py            the node agent's own sync on the device door: the projects picked, a long poll per project, what Windows cannot hold left out
    bbcompanion/names.py           Windows' rules for a file's name: device names, a trailing dot or space, the refused characters, two names one by case
    bbcompanion/creds.py           the device token in Windows' credential store, or a file only its owner reads elsewhere
    bbcompanion/settings.py        the projects kept and their folders, the controller's address
    bbcompanion/pc.py              this PC lent to a project: the verbs its person set up, run on a session's ask, the folder written as the project's path
    bbcompanion/update.py          kept current by its controller: what it holds asked at start and daily, a newer copy checked and swapped in at the next start
    bbcompanion/app.py             the window: sign in, the projects and each one's state, Add, Remove, Open folder, Conflicts
nodes/bb-session                    the root helper that runs a session in a view of its own project; the agent installs it
nodes/bb-netcut                     the root helper that runs a declared pack's install step as the job account with no network, where that account cannot make the namespace itself; the agent installs it
nodes/provision-macos.sh            a provisioner for macOS, not offered by default takes it away
nodes/provision-linux.sh                  turns a Linux machine into a node (the Docker sandbox, the stores, the session half) and enrolls it; Debian, RHEL, Arch and SUSE families, Alpine, Void, Gentoo
nodes/families/                           the provisioner's family files, one per package family (deb, rhel, arch, suse, alpine, void, gentoo): package names and verbs, where docker comes from; the enroll script carries the picked system's beside the core
nodes/install-controller.sh               installs the controller bare metal on the provisioner's core, lays the release out by the Dockerfile's COPY lines, and makes the machine a node of itself; --check, --update, --remove (R90)
nodes/unraid-vm.xml             the node as an Unraid VM: one file for every distribution; only the installer ISO line changes
nodes/vm/                        the same machine for the other six hypervisors: Proxmox, libvirt, QEMU, VMware, Hyper-V, VirtualBox
nodes/cloud-init/                the seed a cloud image boots from: meta-data and the user-data that runs the provisioner
config/skel/                     home directory skeleton
config/icon.png                  the icon the Unraid template shows
config/toolchains.json           the toolchains the Library offers, and how to install each
config/release-signers           the keys a release's SHA256SUMS.sig must verify against (R199), as ssh-keygen's allowed signers: what AerieOS's updater, the stick maker and the installer check a release by
config/catalog.pub               the catalog maintainers' Ed25519 public key (R169 step 2): what every install checks the catalog's index.sig against, with its spare on a second line (R232)
config/aerieos-release.pub       AerieOS's release key, public half (R227): what the Enroll script hands a node to pin, and what tools/sign-agent.py holds a build's key to; no key named until one is made; a second line names its spare (R232)
config/release-keys/README.md    where each publisher release key came from, and how one is refreshed (R137)
config/release-keys/node.asc     the Node.js release team keys that sign each release SHASUMS256.txt
config/release-keys/swift.asc    the Swift signing keys that sign each download
config/controller.env            a bare-metal install's env file as the installer first writes it: the paths compose mounts, the settings compose passes (R90)
config/controller-packages.tsv   what the controller needs installed, per provisioner family: the image and a bare-metal install read this one list (R90)
config/vm-images.json            the operating systems a VM is made from: each publisher's cloud image and its checksum file (R91)
config/templates/                briefing.md, assembled per session by preamble.py; nothing is copied into a project
tools/readme-shots.mjs           the README's pictures (dashboard, notebook, nodes, toolchains, the phone's dashboard and terminal) from a running dashboard, normally the dev instance: default scheme, addresses scrubbed, nothing saved
tools/sign-agent.py              the agent's release signature (R227): --keygen makes the key pair once, a release build signs the agent's digest into scripts/agent/agent.sig with the key from its secret, --check holds a signature to the committed public key
tools/bb-ref.sh                  writes the aerie block of docs/reference.md from aerie help; aerie lint holds the two equal
tools/aerieos-stick.py        the USB stick maker (R161 step 5): a release's stick image onto a removable disk on Windows, a Mac or Linux, checked and read back, Python's own library alone
tools/release-notes.py           a dev build's release notes: what the changelog's Unreleased gained since the last published release
tools/release-sign.py            makes the release key and signs a release's SHA256SUMS on the key holder's own machine (R199): never run in CI, the repository or a controller
tools/release-place.sh           where a release may be cut from: a dev build on its branch, a stable release or a candidate only on main (the tag's first check)
tools/root-tier.sh               the root tier as root in a throwaway container of the controller's image: the image's own copy, or a checkout's with --tree (the lint workflow's root job, the image workflow's upgrade job)
tools/release-attach.sh          one release per tag, found among the drafts and made once, each file uploaded to it by id: what a tag's last job makes the release with, and a job run again by hand attaches with
tools/release-missing.sh         the files .release-files names that a set of names lacks: one reading of the list for the last job and the rehearsal
tools/aerieos-usb-maker.py    the stick maker in a window (R198): which release, which stick, the first boot's settings and a last page naming the stick, each step aerieos-stick.py's own; built into a Windows .exe that asks for Administrator, attached to every release
tools/api-doc.py                 writes docs/api.md from server.py's route tables; aerie lint holds the two equal
tools/git-hosts-doc.py           writes docs/git-hosts.md from forgeaccess.ABILITIES; aerie lint holds the two equal
tools/packs-export.py            writes the official packs under packs/ from config/toolchains.json and agents.py's table; aerie lint's --check holds them to it (R169 step 1)
tools/check-sysdeps.py           checks every recipe's system packages, and with --controller the controller's own list, against each distribution's package index
tools/agent-version.sh           the lint check that the agent's version moved with its file
tools/no-em-dash.sh              the house rule voice's check: no em dash on a line this branch adds
test/nettest/compose.yml         the network probe (R178's proof): a container shipped to a node that tries what a project's container may and may not reach
test/nettest/Dockerfile          its image: alpine with curl, dig and nc, running probe.sh
test/nettest/probe.sh            the probe itself: DNS, the internet, the controller, the node's 80 and 443, and not its 22, the private ranges or IPv6; PASS/FAIL per line in the log
test/nettest/.env.example        the two addresses it needs: the controller's and the node's
tools/american-spelling.sh       the house rule spelling's check: no British spelling on a line this branch adds
tools/no-net-growth.sh           the everything-files against their ceilings in tools/ratchet.txt (R77)
tools/upgrade-snapshot.py        a lived-in /config made by this tree's controller through its API, written to scripts/dashboard/test/upgrade/VERSION/ for the upgrade suite, one taken at an older state kept beside it as VERSION-stateN; a release runs it
tools/upgrade-image.sh           the built image started on each release snapshot of /config through its own entrypoint: it answers, the stamp is the image's state, a copy was taken, the owner signs in (the image workflow's upgrade job)
tools/vscode-vsix.py             packages apps/vscode/ as a .vsix with python's zipfile, AerieOS's version inside (R159)
tools/companion-build.py         builds the Windows companion as one .pyz with the four agent modules its sync is (R270)
tools/app-schemes.py             writes the Android app's twelve color schemes, both halves, from the design record (aerie design json | tools/app-schemes.py)
tools/ratchet.txt                those ceilings, one per file
pyrightconfig.json               how pyright (the pyright-lsp plugin, or the CLI) reads this repo: each directory's imports and Python
                                 version, with the None checks off, since a module's configure() fills what it declares as None
tools/version-stamp              this repo's own stamp hook: a bump moves the compatibility
                                 window in the agent and the template with it, or refuses
docs/README.md                   the index of these docs, linked from the README
docs/release-notes/downloads.md  which download is for what, put at the top of every release's notes by the image workflow
docs/reference.md                the configuration reference, every aerie command (its aerie block written by tools/bb-ref.sh) and signing Android releases
docs/unraid.md                   step-by-step Unraid walkthrough
docs/image.md                    AerieOS, the appliance image: what it is, the disk and its slots, what persists, how it boots, how it is built
docs/install.md                  setup, start to finish: the checklist with the decisions each step needs
docs/architecture.md             the map: the seven parts, how they reach each other, where each is explained
docs/api.md                      every /api/ route with its method, handler, first sentence and what it refuses on, written by tools/api-doc.py
docs/git-hosts.md                what an agent can do on a git host and the token permission each needs, written by tools/git-hosts-doc.py
docs/how-it-works.md             the overview: what the image carries, its security model and hooks, and which doc explains each part
docs/dashboard.md                the dashboard: signing in, the rail, Home, the bell, color schemes, the dock and its terminals
docs/projects.md                 the Projects page: making, linking, archiving and deleting a project, and its repository's access
docs/notebook.md                 a project's page: its header and its views, from the roadmap and bugs to the wiki and design
docs/sessions.md                 each agent's sessions: starting one, the Sessions page, a session's view and network, its briefing and rules
docs/building.md                 builds, tests, CI runners and logs, the scanner's findings, dist/, signing and releases
docs/toolchains.md               the toolchain store, the Library, the Installed page's toolchains, the Emulator page, the NVIDIA card, Android, the Phone page
docs/agents.md                   the coding agents: the agent table, the Library and the Installed page, installing and signing in to each on a node (R95)
docs/tool-packs.md               tool packs: adding one, a project's Toolchains setting, and writing a bbtool.json
docs/submitting.md               submitting to the vetted catalog: a tool pack, a coding agent or a Docker app from writing it to a merged entry
docs/containers.md               the Containers page and nginx: dev instances, how one is reached, networks, image updates
docs/scanners.md                 the Scanners page: AerieOS's own scanners on each node, their schedule, and the reports
docs/versions.md                 versions and release lines: aerie version line, forward, backport, a patch line's rules
docs/vms.md                      the VMs page and aerie vm: VM host, the OS catalog, the dial, the limits, the network, snapshots, a VM made a node
docs/nas.md                      the installed edition's storage design (R56): Python the management plane and never the data path, the two storage profiles, what is not built
docs/machines.md                 Controller settings, Nodes, Storage, the logs, the Jobs page, a Mac as a node
docs/people.md                   the first account, Users and Roles, owners and invitations, the chat, your Profile
docs/aerie-command.md               the aerie verbs with more behind them: the test harness, the code map, capture, sound and documents
docs/privacy.md                  data and privacy: what an install keeps, what it contacts, how to remove it
docs/security.md                 the threat model: who is trusted for what, what each store protects and does not, and the line each hardening step closes (R158)
docs/features.md                 everything AerieOS does, by area, linked from each release's notes
docs/companion-app.md            the companion app for an Android phone: pairing, its lock, notifications, how it is built
docs/decisions.md                the design decisions, with their dates and reasons
docs/layout.md                   this list, held to the tree by aerie lint
docs/screenshots/                the README's pictures, regenerated by tools/readme-shots.mjs, and the mark at 512px (mark-512.png) a release's page shows
docs/start-here.md               the one page for somebody given an account on somebody else's AerieOS
docs/journeys.md                 what a person does with AerieOS, walked for real, dated
docs/sandbox-vm.md               the Docker sandbox VM: why, how, and pointing this at it
docs/nodes.md                    design: controller + nodes, homelab-default and enterprise-scalable
docs/users.md                    design: accounts, roles, and what each one may reach
docs/design-language.md          what the dashboard's surfaces owe each other: held by the
                                 house rule `design` and measured by test/uniform.mjs
.hadolint.yaml                   Dockerfile lint config, shared by CI and aerie lint
.release-files                   the files every release carries, which the controller checks each release against
.github/actionlint.yaml          this runner's labels, for workflow linting
.github/workflows/
  build-image.yml                GHCR publish: hosted, cached from :main, on a push to main that touches the image's inputs, the pushed image then started on each release's /config (tools/upgrade-image.sh); on a tag, the one run that builds everything the release carries (the image, the bundle, the apps, the OS image) behind the tag's checks, its last job making the release once with every file
  publish-release.yml            a release published: :dev, and for a stable one :latest and :MAJOR.MINOR, moved onto the version it built
  os-image.yml                   AerieOS built and booted under QEMU: called by build-image.yml to publish, and on its own for a branch push touching the image
  lint.yml                       aerie lint itself with nothing skipped, and the unit tier, on a pull request and before a release's tag publishes, on this runner; the root tier beside them, in a container on a hosted one
  dashboard.yml                  the dashboard's browser suites, on a pull request that changes what they test and before a release's tag publishes, on this runner
  android-app.yml                the companion app's build: on a push to main that touches it, as a job of a tag's run (the unsigned APK handed to the controller to sign), or by hand
  companion-app.yml              the Windows companion's .exe, the .pyz and the VS Code extension: as a job of a tag's run, its files handed to that run's last job, or by hand for a release that exists, attached to it
  release-rehearsal.yml          every build a release's tag runs and every check it is held to, on a branch by hand or aerie version rehearse, publishing nothing
  runner-smoke-test.yml          proves this runner picks up jobs, carries its toolchain and cannot see the shielded PAT (manual)
```
