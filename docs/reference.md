# Reference

The settings the container is given, every `aerie` command a session has, the
apps a controller offers, and how Android releases are signed. What each part is for is
[how-it-works.md](how-it-works.md) and the docs it names; setting one up is [install.md](install.md).

## Configuration reference

Only what the container or the host has to know before AerieOS runs is a
variable; everything else is set in the dashboard: Controller settings (under
Machines) for the controller, a project's settings for the project, the
Nodes page for each machine. Tokens are never variables: git keys and publishing tokens go in the
root-only secrets folder ([unraid.md](unraid.md#shielding-secrets-pat--ssh-keys-from-sessions)),
a project's settings make its deploy key or hold its access token, and a
runner's token is typed on the CI runner page.

| Variable | Default | Purpose |
|---|---|---|
| `PUID` / `PGID` | `99` / `100` | File ownership (a NAS host's `nobody:users`) |
| `TZ` | `Etc/UTC` | The container's clock, for its log lines. Optional: the dashboard shows times in each browser's own zone, or the one picked under the gear in the header |
| `DASHBOARD_PORT` | `7680` | The one published port: page, API and terminals (websockets at `/termws`) |
| `FEATURES_OFF` | *(empty)* | Features switched off for the whole install, comma-separated: `tunnel`, `ftp`, `phone`, `devices`, `apps`, `image-updates`, `runner`, `enroll`, `shell` (a terminal on the controller itself; a node's stay), `vms` (virtual machines on nodes: the VMs page, `aerie vm` and installing VM host), `internet` (an install meant to run offline: apps, image updates, the tunnel and runners with it, and the Doctor skips asking the outside). Each one's controls are drawn dead with the sentence below under them, its requests are refused, and Settings lists them |
| `BANNER_TEXT` | *(empty)* | One line every visitor sees under the header, on every page and the sign-in page: a shared install's word to whoever is on it |
| `BANNER_LINK` | *(empty)* | A link at the banner's end, http(s) or a path on this site; anything else is dropped |
| `BANNER_LINK_LABEL` | *(empty)* | The link's words; "more" when empty |
| `FEATURES_OFF_WHY` | *(empty)* | The sentence a switched-off feature shows; "switched off on this install" when empty |
| `SCANNER_REPORTS_PATH` | `/mnt/user/appdata/scanners/reports` | deprecated in 0.9.0, removed in the release after: the directory a scanner on the host writes SARIF into, mounted read-only at `/reports` and still read by `aerie findings` and the Analysis view beside what the Scanners page's own scanners send up ([scanners.md](scanners.md)); empty where no host scanner runs |
| `AERIE_PULL` | `missing` | AerieOS's own dev instance only: compose's pull policy, `build` to build this checkout (with `AERIE_TAG=dev`); `BUILDERBOT_PULL` and `BUILDERBOT_TAG` are read too until 0.10 |

Mounts: the projects folder, the state directories (`home`, `config`), the
`/sdk` (the browsers `aerie capture shot` uses; a node keeps its own
toolchains), and three optional ones: `/secrets` (ro,
shielded credentials), `/reports` (ro, a scanner's output) and `/logs`
(the logs on a share of their own).

### A controller installed bare metal: its env file

A controller installed with `nodes/install-controller.sh` ([install.md](install.md#bare-metal))
reads `/etc/aerieos-controller/controller.env` at every start, in place of
compose's `.env`. It carries the same settings as the table above, under the
same names and with the same defaults (`TZ`, `DASHBOARD_PORT`,
`FEATURES_OFF`, `FEATURES_OFF_WHY`, `BANNER_TEXT`, `BANNER_LINK`,
`BANNER_LINK_LABEL`), but `PUID` and `PGID`, which are the container's alone:
the installer makes an account with ids of its own. In place of compose's
mounts it names the folders:

| Variable | Default | Purpose |
|---|---|---|
| `DASHBOARD_STATE` | `/var/lib/aerieos-controller/config` | The state, compose's `/config`: accounts, settings, notebooks, logs |
| `BUILDER_HOME` | `/var/lib/aerieos-controller/home` | The controller's own home, compose's `/home/builder` |
| `WORKSPACE` | `/srv/aerieos/projects` | The projects, compose's `/workspace` (the installer's `--workspace`); never `/workspace`, which is the machine's own node's synced copy |
| `SDK_ROOT` | `/var/lib/aerieos-controller/sdk` | The toolchain store, compose's `/sdk` |
| `BB_SECRETS_DIR` | `/etc/aerieos-controller/secrets` | The root-only secrets folder, compose's `/secrets`: `*.env` files and `ssh/` |
| `SSH_AUTH_SOCK` | `/run/aerieos-controller/ssh-agent.sock` | The deploy-key agent's socket, in a folder only the controller's account enters |
| `BB_ACCOUNT` | `builderbot` | The account the controller runs as, written by the installer (`--account`); change it by running the installer again |
| `BB_INSTALL` | `bare-metal` | What the install is, written by the installer and read by the controller, never guessed: on a bare-metal install the first run's node is the machine's own, set up by the installer, and Finish waits for it |

A value with spaces in it goes in double quotes. After an edit, `sudo
systemctl restart aerieos-controller`. The file is root's and readable by
the controller's account alone; a session on the machine's own node is kept
out of it, with the rest of the controller (the wall,
[decisions.md](decisions.md#a-controller-installed-bare-metal-and-its-own-node)).

### The install key

The install key seals at rest what AerieOS keeps that would let somebody
in: the settings' tokens, each project's signing keys, the git credentials a
project holds, the two-factor secrets, and each account's own key; the
sign-in cookies' key is made from it too.

An install makes its own at its first start, so there is nothing to set:
32 random bytes in an `install-key` folder only the controller's account
reads, inside the secrets folder (compose's `/secrets`, the template's
**Secrets directory**, a bare-metal install's `BB_SECRETS_DIR`) when that is
mounted read-write, and beside the state in `/config/.install-key` when
there is none. Kept beside the state, a copy of `/config` carries the key,
so the Keys page and `aerie doctor` say so; mount a secrets folder the
controller may write to and the next start moves the key into it. On
a NAS host that is the container's **Edit**, **Secrets directory** set to a
folder such as `/mnt/user/appdata/Aerie-Workshop/secrets` with access
**Read/Write**, then **Apply**: an install from a template before 0.8.0
keeps the read-only mount it was made with until it is changed there.

**Controller, Keys** (an administrator's) shows where the key is kept and
its fingerprint, which names it and opens nothing. **Show** puts the key on
the page to copy or download, and **I saved it** marks it saved: keep that
copy apart from `/config`, since a backup restored on a new install opens
nothing that was sealed without it. **Change** makes a new key, or takes one
pasted, and seals everything kept under the one before again under it at
once; people stay signed in until the next restart. The page also lists
everything kept under the key, each with what uses it and where it is
changed.

**Controller, Audit** (for an account that reads the controller's area) is
who did what to this install: every change since the first day, newest
first, a page at a time, each line when, who, what and on what (a machine
by its name where the change was to one); the bar's two pickers narrow it to
one person or one machine. Nothing on it changes anything.

Each account has a key of its own, kept by the controller under the install
key, for its coding agents' sign-ins sealed on the nodes; changing the
install key leaves those as they are. A person changes their own on
**Profile, Your key**. A sign-in sealed under a key before one that changed
opens with the old key the next time its person opens a terminal on that
node, and is sealed again under the new one; the old key is kept until then.

That key also seals the account's own **key store**, on **Profile, Your key
store**: a token the person gives a repository (an access token in its
settings, or one given when cloning it or linking it to a host) is kept
under their key, not the install's, and the project is linked to it; the
store holds any number for one host, each listed with the projects that use
it, never shown again and never downloaded. Their own git work uses it
ahead of a project's: a `aerie git` push or pull from their session, and their
presses in the Git view (one the view hands to a background job uses the
project's). A project's settings list the person's tokens for its remote's
host, with **Use for this project**; CI watching, releases and anybody
without a token of their own then use the one the project is linked to. A
token a project kept before goes into the project owner's store at the
first start that can seal it, AerieOS's owner taking those of a project
with none. **Purge**
empties the store after a plain confirmation: the key, every forge linked,
and the link of every project that used it, each of which then says on the
bell that its git access went with that account. Deleting the account does
the same, and an administrator can purge an account's store from the Users
page. Purging asks for no password or code, so a person who forgot theirs,
or fears it stolen, can still do it.

`INSTALL_KEY=` in a `*.env` file in the secrets folder (16 characters or
more; never in `.env` or the template's plain fields) sets the key instead,
and the install then makes none. With the secrets folder read-write, the
first start copies that key into its key folder (never beside the state),
and the Keys page says so: take `INSTALL_KEY` out and restart, and the
install carries on with the same key, changed on the page from then on.
Until it is copied, the Keys page says to change it there, with the old one as `INSTALL_KEY_PREVIOUS=` beside it until each
sign-in has moved. `SIGNING_SECRET=`, its name before 0.8.0, is read for one
release.

## The `aerie` helper

Bare `aerie` prints this list; `aerie status` is the tool-version wall.

```
aerie -p NAME VERB    any verb, about another space this one reads (its
                   settings name them): aerie -p NAME roadmap, aerie -p NAME map find X;
                   NAME is its shown name, its folder or its id (P3)
aerie status          tool versions, runner registration, the spaces here
aerie version         this space's version, and who is allowed to move it
aerie version --code  one form only: --code (Android versionCode), --quad (= --win:
                   manifest.json and Windows VERSIONINFO), --msi, --pep440,
                   --file, --semver, --json
aerie version bump major|minor|patch    move the target, if the policy allows it.
                   A bump decides the number and closes the changelog under
                   it; it does not release anything. It commits on the branch
                   the checkout is on and pushes nothing, and says so when
                   that is not the branch builds come from. **Release** on the
                   Artifacts view is the second gesture: an annotated tag
                   (vX.Y.Z, or DIR-vX.Y.Z for a component) on the commit you
                   are on, pushed to the remote. Until that tag exists every
                   build reads X.Y.Z-dev.N+sha, which sorts BEFORE X.Y.Z,
                   heading for it rather than at it; from the tag on, a build
                   of that commit is the bare number. Releasing is the
                   operator's whatever the policy says, and a pushed tag is
                   never moved or deleted from the dashboard.
                   A repo that carries its number somewhere else as well
                   (an agent's protocol number, a template's stamp) declares
                   that by carrying an executable `tools/version-stamp`, run
                   from the repo root with the new version and the part that
                   moved. Whatever it changes is committed with VERSION, so
                   the bump is one commit or none: a hook that fails refuses
                   the bump rather than leaving the number moved and its twin
                   behind. A repo without one is unaffected
aerie version init X.Y.Z  give this space (or --for DIR) its first VERSION
aerie version set X.Y.Z   straight to a later version in one commit, allowed
                   when the policy allows the largest part it moves; from a
                   number never released (no tag), its changelog section is
                   dated as the new one
aerie version unbump      take the last unreleased bump or set back; its
                   changelog section dissolves into Unreleased, the code
                   stays. Once: the bump before it is not taken back too.
                   A section dated under the wrong number is fixed with
                   unbump, then set to the number meant
aerie version release --why "..." [--without-apk] [--dev|--stable]
                   tag this commit and publish the release, as Release on the
                   Artifacts view does, on the controller with the space's own
                   credentials. The space's settings say whether an agent may
                   (Tag and publish a release): auto releases, ask waits for
                   the space's owner, with --why as the reason. A release
                   whose Android APK could not be signed is refused before the
                   tag, saying why; --without-apk goes on, and aerie sign release
                   signs it once that is put right. --dev tags the dev
                   build instead (vX.Y.Z-dev.N, no bump), which CI publishes as
                   a pre-release on the dev channel; --pre NAME a pre-release of
                   any other name (vX.Y.Z-rc.N, N the commit's as for dev). A pre-release
                   first moves Unreleased into its own changelog section,
                   committed and pushed, and is tagged on that commit; a stable
                   one gathers every pre-release section since the last stable
                   into its own. Refused while aerie changelog missing lists a
                   bug the last release carried with no Fixed line.
                   From a branch other than the one builds ship from it is a
                   dev release unless --stable says otherwise; the first line
                   printed names the channel it lands on
aerie version release --edit --why "..." [--tag TAG] [--notes FILE] [--attach FILE]...
                   change the published release under the same setting, each
                   edit its own ask: the notes replaced whole (- reads stdin),
                   a build in dist/ or a committed file attached (one of the
                   same name replaced), (asset:NAME) in the notes the address
                   of that file on the release, (file:PATH) a committed
                   picture shown from the repository at its pushed commit,
                   never a download: the way for a screenshot
aerie version release --remove NAME [--remove NAME]... --why "..." [--tag TAG]
                   take files off the published release, named as the forge
                   lists them: its own ask under the same setting, never part
                   of an edit, the names checked against the release first
aerie version release --withdraw TAG --why "..."
                   delete a published release and its tag together on the
                   forge, and the tag here, so the number can be cut again:
                   always the space owner's answer, whatever the setting
                   (deny refuses); a tag whose release is already gone goes
                   alone
aerie version rehearse  run every build a release's tag runs on this branch as it
                   is pushed (.github/workflows/release-rehearsal.yml),
                   publishing nothing; its summary lists what the release
                   would carry (.release-files). Tag once it is green
aerie version --list  every version this repo carries: its own, and any component
aerie version --for DIR   ask about a component: a directory with its own VERSION
aerie version line [X.Y.Z|none]   the release this branch works toward: a branch
                   named for one (claude/0.7.0) works toward it, or set it here;
                   a dev build heads for it (0.7.0-dev.N), a bump moves only
                   to it, and on a patch line aerie lint refuses a new migration
aerie version policy  what a session may move here, and who decides. A
                   person picks it in the space's settings (Agents may:
                   Move the version) or on the Artifacts view, before or after
                   there is a version: locked (theirs entirely), may start
                   one (a session writes the FIRST version and moves nothing
                   after), patch, patch and minor, or anything
aerie changelog       this space's user-facing changelog (--for DIR for a component)
aerie changelog add "..." --cat NAME   log what a change means for the person using
                   it; the next release or bump files them under its version. A
                   category is required, and the tool is where the rule lives:
                   Added (somebody can do something they could not), Changed
                   (already here, now different), Deprecated (going away),
                   Removed (gone), Fixed (was wrong in a released version,
                   now right; --bug N says which bug), Security (act on it
                   because of what it exposed). When two fit, the one a reader would look under;
                   something nobody using the product would notice gets no
                   entry, and neither does a fix to something no release has
                   carried yet (a published dev pre-release is a release:
                   a bug it carried gets a Fixed line): the changelog is
                   read by somebody upgrading from a release, who never met
                   that bug. Run without a category
                   and it prints this. A name that means one of the six is
                   spelled the one way (`fix` files under Fixed), the six keep
                   their usual order among themselves, and a space that
                   files its own way names its own category, kept as typed and
                   placed at the end: a default, which a house rule overrides.
                   What order the categories and their lines sit in is still
                   the operator's, on the Changelog editor beside the version
aerie changelog unreleased  the entries waiting for a bump, numbered straight
                   through the section by category, in the arranged order
aerie changelog edit N "..."  reword one of them: a change that tweaks something
                   already logged this cycle corrects its line rather than adding one,
                   and the line gains that commit. --cat NAME on its own moves it
                   and leaves the words, filing it at the end of that category the
                   way add --cat does, so re-filing a line into its own category
                   sends it to the bottom, which is the ordering a session has.
                   --no-stamp corrects a line without claiming a commit made it,
                   which is what a pass over the wording is
aerie changelog merge N M "..."   one line for several, carrying all their commits
aerie changelog split N     back into one line per commit it carries
aerie changelog rm N        drop one that stopped being true
aerie changelog missing [TAG]  the bugs fixed since the last release (or TAG)
                   that it carried, or may have, with no Fixed line and no
                   answer: a release is refused while there are any
aerie changelog skip N "why"   a fixed bug that needs no Fixed line, and why
                   (the release never had it, nobody using it meets it); kept
                   in the bug's notes, as add's --bug N is for the line itself
aerie projects        the space dirs here and their branches
aerie shell           login shell as the builder user
aerie login           Claude Code subscription auth flow, on the machine it is
                   run on. Nothing is copied anywhere: each node is signed in
                   for itself, from its row on the Nodes page or with this
aerie login --check   what THIS machine is signed in as, told to the controller.
                   The login itself never travels
aerie git push|fetch|pull|ls-remote [ARGS]
aerie git policy      what a session may push here (its own branches, main) from
                   the space's Git view; the controller enforces it on the
                   relay, against the refs the push would write: a name that is
                   only on the remote, a tag, --all and deleting a branch there
                   are the operator's whatever the two settings say
                   git's network half, run where the credential is: from a
                   session on a node it goes through the controller
aerie emu start [api] | stop | status | list | log [-p] | adopt
                   the space's own emulator: its phones are this space's
                   alone, made on the first start; adopt moves the account's
                   phones from before that into this space, once
aerie emu touch tap X Y | hold X Y --ms N | glide X Y X Y... [--hand NAME] [--seed N] [--pre MS] [--hold MS] [--mark FILE]
                   a timed touch on the running emulator, in screen pixels;
                   a glide moves like a hand (steady, normal, shaky, or
                   ruler for the straight even stroke), repeatable by seed,
                   at the pace asked whatever a move costs the device;
                   --mark FILE is made when the finger arrives to be held
aerie gpu             this node's NVIDIA card: how much of its memory is free, who is
                   computing on it, and whether this session may
aerie gpu run [--mem MB] -- CMD
                   CMD with a turn on the card: one heavy job at a time per node, waiting
                   for its turn and for MB of free memory rather than failing on a full card
aerie browser open --ext DIR [--firefox] [--url URL] [--headed]
                   Chrome (or Firefox) with an unpacked extension loaded, headless,
                   detached on a debugging port and a profile of its own: its id,
                   its port and the extension's id
aerie browser go|eval|shot ID ...
                   go ID URL (ext:PAGE for the extension's own), eval ID JS (the
                   value as JSON), shot ID FILE (a PNG of the page on show)
aerie browser list | stop ID|--all
                   the ones open; stop ends one by its process group and removes
                   its profile
aerie proc [PATTERN]  this account's processes with PATTERN in their command line, never
                   the call's own shell (which pgrep -f matches): pid, age, command
aerie proc stop PATTERN [--grace S]
                   end them: SIGTERM, then SIGKILL after S seconds (3)
aerie proc wait PATTERN [--timeout S]
                   wait until none is left (600s), saying what is left if some is
aerie tidy [--keep emulator|gpu|gradle|browser|server|tmp]... [--dry]
                   after a task or a batch of them, give back what it left holding:
                   this session's emulator (through aerie emu stop), anything else of
                   its own on the NVIDIA card, its Gradle and Kotlin daemons, the
                   headless browsers a test left behind, a server it put in the
                   background and left listening (a dev server, a preview), and its
                   own files in /tmp, which in a session is memory; and the quick-boot
                   snapshot of each of this space's phones not started for a week,
                   naming a phone that is not its default and has not run for two
                   (--keep emulator keeps them); --keep one, with the reason in your reply
aerie lint [path]     lint a repo's infrastructure files: shell scripts,
                   Dockerfiles, workflows, compose files, XML
aerie node busy [--json]
                   whether this node is quiet enough to time anything on: its load,
                   memory and card (what holds the card's memory, by kind), what
                   runs there by kind (emulators, Gradle, compilers, browsers,
                   other agents' sessions working, other spaces' jobs, counted
                   and never named) and a verdict: quiet, busy, saturated
aerie node wait-quiet [--level quiet|busy] [--timeout SECONDS]
                   wait until it is (quiet twice, ten seconds apart), before a
                   measurement; exits 1, saying how busy, if it never was
aerie nodes           the machines enrolled as nodes, each with the agent it runs,
                   read-only in a terminal; the Nodes page is where they are edited
aerie nodes show NAME one of them in full, by name or id: its agent against the one
                   this controller ships, and what Update agent would fix
aerie nodes enroll-token NAME [--user U] [--own]
                   a new node's enrollment token, printed once, from a shell on
                   the controller: Enroll node's Just a token, for a scripted setup;
                   --own is the controller's own machine, on a bare-metal install
aerie projects adopt FOLDER [--name NAME]
                   a folder already under the spaces share made a space, as
                   if AerieOS had made it, from a shell on the controller: a
                   folder made by hand is not one until this says so
aerie settings        this space's settings as the dashboard has them: node,
                   model, effort, build and test commands, lock. On a node
                   it is relayed from the controller, and it is what bb-tty
                   and aerie build read there. `set build|test|outputs VALUE`
                   is the one write: a session fills a field in for the
                   operator, under the space's gate (below). `node NODE`,
                   from a shell on the controller, sets the space's node as
                   its Settings page does, for a scripted setup.
aerie users           the dashboard's accounts. `passwd NAME` resets one from a
                   shell, which is the way back when the owner is locked out;
                   `claim NAME` makes the owner of a new install, as its first
                   page does, for a setup scripted from a shell
aerie work            who else is working this space, and which files two of
                   you have uncommitted at once: read-only
aerie jobs [-n N | ID]    the recent jobs: state, node, what ran, how it ended,
                   read-only; the Jobs page is where one is stopped. An id
                   prints that job's log, which is where a failed job says
                   what happened rather than only that it failed
aerie run [opts] -- CMD   snapshot this tree, run CMD on the space's node and
                   stream the log back; `--out GLOB` brings what matches into
                   dist/ with its provenance; `--node` names another node
aerie build           the space's build command on its node, with the outputs
                   it lists: all set in the space's settings dialog
aerie test [ARGS]     the same for its test command; ARGS are appended to it, so a
                   suite that takes file names runs only those. Where it runs is
                   "Tests run" in the space's settings: on the node, which is the
                   default; inside its dev instance when that is up, else on the
                   node; or only inside it, where a container that is down is a
                   refusal naming it and nothing runs on the node
aerie devapp          this space's dev instance: what it was built from, whether it is
                   running, and whether its daemon answers
aerie devapp probe [--port N] [--path /x]
                   whether it answers on its node's loopback: each published port
                   open or refused, and the HTTP status of a GET of the path; a read,
                   so no root ask; --container NAME for another of the space's
aerie devapp rebuild [--why "..."]
                   build it and bring it up. Only where the space has handed that
                   over: Agents may: Run its container, in its settings dialog and
                   the new-project dialog, reads deny (the default, refused with the
                   sentence that names it), ask (the reason goes to a person and the
                   command waits for Approve) or auto. Up, Down and a container of
                   any other shape stay the operator's. The build sees BB_BUILD_REV,
                   BB_BUILD_AT and BB_BUILD_VERSION, for a compose whose build.args
                   interpolate them, BB_BUILD_TAG, the version as an image tag
                   can carry it, and BB_DOCKER_GID, the node's docker group; its
                   other options are the compose file's own
aerie devapp new [NAME] [--branch REF] [--compose FILE] [--override FILE] [--node NODE] [--env FILE] [--why "..."]
                   send the space to Docker, as the Artifacts view's Send to Docker
                   manager does, under the same setting: a container made from its
                   own compose file on its node, then built and started, and this
                   waits for the verdict. Unnamed, it is the space's own container
                   while it has none, then another beside it named for the space
                   with -2, -3 and on; a second needs ports of its own, so give it
                   an env that sets them with --env. --branch builds it
                   from that branch; --compose names another of its compose
                   files (site/compose.yml), the root's own by default; --override
                   lays another compose file from the tree over it, for this one
                   container (its own ports, env or an extra service). --node
                   puts it on a hosting node ticked under the space's Also
                   works on (marked Hosting only): built on the space's own
                   node and shipped there. On ask, one request carries all of it and
                   Approve makes and builds it
aerie devapp remove [--why "..."]
                   take the container out of the manager, under the same setting;
                   its env and data stay for a remake, as the row's Remove leaves them
aerie devapp env [set FILE|-] [--why "..."]
                   print the container's env, or replace it, under the same setting;
                   on ask, Approve writes it and builds nothing, since the card said
                   env set, and the rebuild is the next ask.
                   AerieOS keeps it per container, never as a file in the space,
                   and points a compose line `env_file: .env` at it when it runs
aerie devapp override FILE|none
                   lay another compose file from the tree over the container's own
                   (compose's -f after -f), or none; the next rebuild takes it, and a
                   service it adds is asked about as any new one is. On ask it is a
                   person's, in the container's settings
aerie devapp ls       every container that belongs to this space, with the nginx routes to it, on every node it has one
aerie devapp log NAME one of those containers' log
aerie devapp start|stop|restart NAME [--why "..."]
                   one of those, under the same setting; --container NAME on the
                   other verbs reaches one written for this space
aerie sign FILE [--for play|sideload] [--why "..."]
                   sign a build in dist/ with one of the space's keys, on its
                   node, as a job this session cannot look inside: the key and
                   its password never reach the session. --for play is the Play
                   upload key (the default for an .aab), sideload the app signing
                   key (the default for an .apk). The space's settings say
                   whether an agent may (Sign a build): auto signs, ask waits for
                   the space's owner to allow it, with --why as the reason.
                   Arrives in dist/ as NAME-signed.apk or .aab. --key NAME signs
                   with that key; without it, the key the build's package is
                   mapped to, else the space's default
aerie sign keys       the space's keys by name, their fingerprints and which
                   package each signs (never a key or a password)
aerie sign key new NAME --for play|sideload --why "..."
aerie sign map PACKAGE KEY --why "..."
aerie sign rotate OLD NEW --why "..."
                   a new key made on the controller, or an app's package mapped
                   to a key (KEY "" unmaps it), under Agents may: Manage signing
                   keys: auto does it, ask waits for the space's owner. rotate
                   moves the apps OLD's sideload key signs to NEW's: builds go out
                   signed with both and a proof, Android 9 and newer take NEW,
                   older devices keep checking OLD, which is kept for good
aerie sign status [TAG]
                   whether a release's APK can be signed (the sideload key, the
                   node with its tools) and how the newest went: handed over,
                   signed and attached with the key's fingerprint, or what
                   stopped it, in the bell's words
aerie sign release --why "..."
                   look for unsigned release APKs now and sign a failed one
                   again, as the Signing view's Look for unsigned APKs now,
                   under Sign a build: auto starts it, ask waits for the owner;
                   then waits for the look and says what it found, run by run,
                   or why it found nothing
aerie emu create API  build the AVD for an API level, installing its image if missing
aerie emu install APK install an APK on the running emulator
aerie emu shot [FILE] screenshot the emulator into dist/emu/
aerie emu gfx PKG     a package's per-frame timings (gfxinfo framestats) into
                   dist/emu/, and every emu verb runs on the space's node
                   when it has one, its output coming back into dist/
aerie emu images [--available]
                   the system images on this machine's toolchain store, or
                   every one there is; `aerie emu flavors` says what each is for
aerie emu image add|remove ID
                   put a system image on this machine's store, or take one
                   off: a full id or a flavor's short name (tv, wear,
                   playstore). The operator's, like aerie toolchains install
aerie ci-labels       the runner labels the registry knows; this box's and every
                   node runner's; `--write` regenerates .github/actionlint.yaml
aerie findings        this space's scanner findings (--all for every space)
                   narrow with --level error|warning|note, --rule ID, --find TEXT
aerie findings history   what the scanner stopped and started saying here
                      (-n N, --since 7d, --find TEXT, as the other logs)
aerie findings sample [--remove]   write a clearly-fake report, so the Analysis
                      surfaces can be worked on where no scanner runs
aerie token keep      store BB_TOKEN where this account's sessions on this
                   machine read it; the agent runs it for an idle session
aerie roadmap            this space's roadmap: items are R1, R2, ...; bugs are B1, B2
aerie roadmap show N     one item in full: its details, its steps and theirs (N is R12 or 12)
aerie roadmap add "..."  put something on it; `done N` finished, `rm N [why]` abandoned
aerie roadmap restore N  put a dropped one back from the history, as it was
aerie roadmap reopen N   put back one finished since the last release, for the same goal
aerie roadmap shelve N   park one without dropping it; `mv N up|down` moves it
aerie roadmap unshelve N [WHY]   ask for one back: held for a person on the space to approve
aerie roadmap add "..." --step "..." --step "..."   an ordered group of steps
aerie roadmap edit N "..."               reword one; `step add|edit|rm|done` for one step
aerie roadmap info N [M] "..."           add the technical details to one, or step M,
                                      under what is there (--replace sets them)
aerie roadmap target N X.Y.Z             the release one is meant for (`none` clears); --target
                                      on add sets it, `aerie roadmap --target X.Y.Z` lists those;
                                      `target N.M X.Y.Z` (or N M) is step M's own, `none`
                                      sends it back to its item's, and --target lists an item
                                      for any step meant for that release
aerie roadmap step mv N M TO [POS]       step M of N moved whole to item TO (at POS); N says where
                                      it went, and `show N.M` finds it by its old number
aerie roadmap split N --into "TITLE" M...   N's steps M... moved to a new item, --into repeated
                                      for each; `fold N INTO M[.K]` makes N a step of M
                                      (its words on step K's details), N leaving the list
aerie roadmap refs       the R numbers and steps the list's own words name that find nothing
aerie roadmap --format json|yaml|markdown   the records whole, on list and show (--json for short),
                      as aerie bug, rules, wiki, design and map print theirs; `add --from FILE`
                      adds the records in a file, `apply FILE` writes an edited show back
aerie roadmap begin      work one out; `commit` records it as one change, `revert` undoes
aerie roadmap pending    what a session added that is waiting for your approval
aerie bug             the bug tracker: open bugs; `all`, `show N` for one in full
aerie bug find TEXT   search the reports themselves: area, repro and notes too
aerie bug begin       the same notebook batch `aerie roadmap begin` opens; `commit`, `revert`
aerie bug pending     reports a session filed that are waiting for your approval
aerie bug add "..."   report one (--sev, --area, --repro, ...); `note N`, `fix N`,
                   `wontfix N`, `na N`, `reopen N`, `rm N`, `history`. With
                   --repro, --reproduces always|sometimes|once|untried says how
                   often those steps showed it; --report N files diagnostics
                   report N with its words, area, repro and that answer
aerie tests run [ARGS]  run the space's test command, time it, and record the run: says first when it should
                   finish, and ends by NAMING what went wrong: the failed assertions per file, and for a file
                   that CRASHED the line it died on, the assertions that had already failed before it did,
                   and the fact that nothing after it ran. A crash prints no `FAIL` line and no totals, so a
                   run that only said "failures above" cost four whole runs to read once. ARGS go to the
                   command, so `aerie tests run auth cards` times and records those two files and nothing else
                   else. On the test node a repository's settings name (Tests run, under Build and test;
                   R151) the suites run there as a job, this tree snapshotted, with as
                   many workers as its cores and memory allow, the lines streamed here and the
                   run recorded as a local one; aerie dashboard test and the gate go there too

aerie tests last      that verdict again off the last run's log, running nothing
aerie tests log [-f]  the last run's output, whole; -f follows a run still going. The
                   Tests view's Open the run's output sends this into the space's shell
aerie devapp test [ARGS]  the space's test command inside its running dev instance, as a compose job on
                   its node: the whole log, and the job's exit code. `aerie test` takes this path on its own
                   where "Tests run" in the space's settings says the dev instance, so a suite that
                   tests AerieOS cannot disturb the AerieOS it runs on (roadmap R48). Only for an
                   image that carries its tests: one built to ship has none, and a run inside it finds
                   nothing and passes. Agents may: Run its container is not asked: a test runs in a
                   container that is already up
aerie tests unit      the python unit tier (scripts/dashboard/unit): the modules' rules without a server
                   or a browser, in under a second; preflight runs it before any suite
aerie tests lab       the lab suites (test/lab-*.mjs) against real services rather than stand-ins.
                   Each names what it needs and skips in one line without it, so a missing service
                   is never a failure, and nothing records them: a lab run is a proof, not a timing.
                   Two services are known. A Gitea: the `gitea` service of AerieOS's own dev
                   stack, under its compose file's `lab` profile, brought up from the Containers page
                   like any space's stack (`BB_LAB_GITEA`, the local one by default), and
                   a Forgejo beside it (`BB_LAB_FORGEJO`, port 3001), which the forge suite
                   runs against a second time under its own catalog entry. A real node,
                   through the controller it is enrolled on: `BB_LAB_CONTROLLER` (that dashboard's
                   address), `BB_LAB_TOKEN` (`user:password` for an administrator there, the lab's
                   own) and `BB_LAB_NODE` (the node by name or id). A job runs on that node, so name
                   one you are willing to have that happen to. A VM host there as well
                   (`BB_LAB_VMHOST`, with `BB_LAB_KEY` an ssh public key) walks every Linux
                   system Enroll node offers as a VM made a node, enrolled to Uninstall
                   (lab-systems, slow: each system takes its ten to twenty minutes);
                   with `BB_LAB_SSH` (that key's private half, a path on the VM host) and
                   `BB_LAB_REF` (a pushed ref) it installs a controller bare metal in a VM
                   and tries the wall around its own node (lab-baremetal)
aerie tests projection  when a run should finish, from what the last one took (--secs for the number)
aerie tests accept KEY "why"   the wait is the work: stop flagging it, saying why (--no undoes)
aerie rules           the house rules for this space: the operator's and yours
aerie rules show NAME one of them in full: what a conditional rule says
aerie rules add NAME "..." [--files ...] [--words ...] [--doc PATH] [--check CMD]   leave one of your own
                   [--refuse "CMD, CMD"]: commands it refuses outright when a session runs one
                   [--replaces RULE]: the global rule it takes the place of in this space
                   [--why "..."]: the reason behind it, kept for show and the tab, never sent
aerie rules edit NAME "..." | rm NAME ["why"]            change or drop yours
aerie rules check [NAME|--all]   run the checks of the rules whose files you changed
aerie rules history   what has changed them, by either of you
aerie rules pending   rules a session added that are waiting for your approval
aerie rules audit [DAYS]   your conversations here over DAYS (7): the commands a rule
                   refuses, run or tried, and the code map asked against grep
aerie preamble        what a session started here is handed: rules, roadmap, bugs (--json for its size)
aerie router-key      the model router's address, this space's own key and its models, for an Any model session
aerie help TOPIC      one topic of the session briefing in full (start, where, map, build, tidy,
                   speed, capture, asks, notebook, versions, git, android, gpu, containers);
                   aerie help topics lists them, aerie help VERB one verb's lines
aerie brief           the brief this space was started from: waiting for its first
                   session, whichever agent runs it, or kept after that session started
aerie design          what this space looks like, from the notebook's Design view:
                   its design language in a line, and its pages
aerie design show [ID|NAME]   the prompt for one page, or for the language alone:
                   the colors as tokens, the type, the shape, the layout
aerie design file [--from FILE]   docs/design-language.md as the notebook writes it;
                   --from renders it from a record (aerie design json, edited) instead
                   of the saved design, so a branch writes the file from its own
aerie design json     the record: the language, the pages, and the presets by key
aerie design schema   the record's shape with every limit, for a save that lands first time
aerie design save FILE   write a record of that shape back, whole: how a session
                   puts a design language it was given into the notebook
aerie wiki            the space's wiki, from the notebook's Wiki view: its pages,
                   who changed each last, and where it is pushed
aerie wiki show NAME [--rev]   one page's Markdown (--rev: the revision a save checks)
aerie wiki save NAME FILE|- [--why "..."]   write a page whole, new or rewritten,
                   under Agents may: Write the wiki: auto lands it, ask holds it
                   for the operator, deny refuses it, hidden keeps the whole
                   wiki from a session, reading included. A page changed since the
                   save began is refused rather than overwritten
aerie wiki rm NAME [--why "..."]   take a page out, under the same setting
aerie wiki mv OLD NEW   rename one; aerie wiki history: the last changes
aerie transcripts     your own conversations on this space, from every coding agent
                   you use, each marked with its agent, newest first, as the
                   Profile page lists them (aerie -p NAME for one it reads)
aerie transcripts show ID [--tz ZONE] [--all]   one of them as text: what was said,
                   every command it ran and what it answered; the newest
                   16 MB of a longer one, the whole of it with --all
aerie transcripts fetch ID [--into DIR]   the file itself into this machine's folder
                   for it: how a node holding its spaces as a synced copy
                   resumes a conversation it does not have (bb-tty runs it)
aerie memory          your memories on this repository, kept for every coding agent:
                   the index, newest first (aerie -p REPO for another repository
                   of the space, which keeps them when it moves)
aerie memory show NAME   one of them whole
aerie memory add NAME --type user|feedback|space|reference --about "one line" "what to remember"
                   save one, with its line in the index: a fact about one
                   repository on that repository
aerie memory forget NAME   take one out
aerie tests           the test registry: where the suite's time goes, slowest first
aerie tests show KEY  one test: what it protects, what it exercises, its history
aerie tests note KEY "..." [--how "..."]   what it protects, and what it really runs
aerie tests describe --from FILE.json      fill many at once, in one write
aerie tests ingest [LOG]  record a run's real durations (BB_TEST_TIMING=1 output)
aerie tests drift     what the runner reported that this list does not, and back
aerie tests flagged   the ones sitting on a round timeout rather than working
aerie history         one search over the notebook's logs: roadmap, bugs, memory
                   (`--find X`, `--since 7d`, `-n N`)
aerie roadmap history [-n N] [--since 7d] [--find TEXT]   what changed, narrowed
aerie phone           what phone is connected, and what is waiting on you
aerie phone run --why "..." -- adb args...
                   ask to reach it: the operator allows it on the dashboard
                   and the dashboard runs it, so a session never touches the
                   handset itself
aerie phone lease     whether the phone is lent to this space, for how long, and
                   which of its apps the lease covers. While lent, each of
                   these asks the phone's owner and runs on their Approve
                   (--why "..." is the sentence they read), or at once
                   once they allowed this session's commands:
aerie phone install dist/APP.apk   install one of this space's builds; its
                   package joins the lease
aerie phone start|stop|ime|log PKG   run, stop, pick as keyboard, or read the
                   logcat of a lease app
aerie phone shot      the screen, into dist/phone/
aerie phone record [SECONDS] | record start [SECONDS] | record stop
                   a video into dist/phone/, with its reel beside it (the
                   frames that changed, with their times, in one picture);
                   start leaves it running while touches work the phone,
                   stop collects it
aerie phone touch tap X Y | hold X Y [--ms N] | glide X Y X Y... [--hand NAME] [--seed N] |
                   text "..." | key back|enter|del|tab|space|up|down|left|right
                   only while a lease app is in front or is the keyboard;
                   --any-app asks the owner for that one touch on whatever is
                   in front (another space's keyboard), and Approve for this
                   session does not cover it; aerie phone ui prints the screen's
                   layout under the same rule
aerie vm [list]       this space's VMs (R91): state, OS, node, address, size, snapshots
aerie vm os           the operating systems a VM is made from
aerie vm new NAME --os OS [--vcpus N] [--mem 4G] [--disk 20] [--disks 100,500] [--node NODE] [--key FILE] [--pin 2,3] [--mem-max 8G] [--share PATH [--ro]] [--autostart] [--node-agent] --why "..."
                   a VM on one of the space's nodes with VM host installed,
                   letting in this session's ssh key (made when there is none);
                   the space's Make VMs setting decides: deny refuses, ask
                   waits for an administrator's Allow, auto makes it now.
                   --node-agent enrolls it as a node at its first boot, which
                   an administrator always allows; --disks gives it up to
                   three more, --pin, --mem-max and --share are as aerie vm
                   hardware says, --autostart starts it when its node boots
aerie vm start|stop|restart|rm NAME [--force]
                   one VM, under the same setting; stop asks it to shut down,
                   --force pulls the plug
aerie vm snapshot NAME SNAP [--note "..."] | revert NAME SNAP | snapshot-rm NAME SNAP
                   its state saved under a name and gone back to; a running
                   VM's memory is kept too, so a revert lands mid-program
aerie vm grow NAME [vda|vdb|vdc|vdd] GB | disk-add NAME GB | eject NAME
                   a stopped VM's disk made larger or another added, and an
                   installer's ISO taken out of its drive
aerie vm hardware NAME [--pin 2,3|none] [--share-cpus] [--mem-max 8G|none] [--share PATH|none] [--ro]
                   a stopped VM's hardware beyond its size (R100), what is
                   named and no more: its vCPUs pinned to host threads, the
                   memory it may balloon up to, a folder of the space seen
                   inside it by mount -t virtiofs space /mnt; the LAN and a
                   device passed through are a person's, on the VMs page
aerie vm autostart NAME on|off
                   whether it starts when its node boots
aerie vm devices [NODE]
                   the USB devices on the space's VM hosts (R116), each
                   with what holds it: the host, a VM, or nothing
aerie vm usb NAME give|take VENDOR:PRODUCT[:SERIAL] [--port 1-3]
                   a USB device to a VM, or back: a running VM has it now,
                   a stopped one from its next start; always held for a
                   person on the bell, since a device can be a disk or a key
aerie vm ip NAME | ssh NAME [COMMAND...]
                   its address, and ssh in as its account
aerie container       what container asks are waiting on an administrator
aerie container new --why "..." --name NAME --compose FILE [--env FILE] [--node NODE] [--for PROJECT]
                   a container built from a compose file the session wrote,
                   under the space's *Agents may: Run its container*: refused
                   at deny, asked at ask (an administrator reads the file on
                   the bell, and Approve registers it through the Containers page's own
                   New container path and starts its build), and at auto made
                   at once when it is this space's own on its own node; one
                   for another space or another node is always asked. A
                   published image is a compose naming it; a repository with a
                   Dockerfile is a compose with a build context on the spaces
                   share. Never a user's to approve
aerie root            what root commands are waiting on an administrator
aerie root run --why "..." [--node NAME] -- CMD...
                   ask for ONE command as root on this space's node (or, with --node
                   NAME, on a node it hosts containers on; the row's root-asks switch
                   decides): an
                   administrator allows or denies it on the Nodes page or the
                   bell, and the node runs that command and nothing else. Not
                   sudo: a second command is a second question. A node's
                   Sessions section can turn root asks off altogether, and
                   the ask is then refused with that said
aerie catchup         what has happened here lately: commits with the first line
                   of their bodies, what moved in the notebook, the builds this
                   box archived, and which image it is actually running
                   (`--since 7d`, `-n COMMITS`)
aerie ci-log          what CI printed on its last run here (`--list` for the runs
                   kept, a run id for one, `--project NAME` from elsewhere);
                   for a space on GitHub's own runners, its runs and the end
                   of each failed job's log, read by the controller from GitHub
aerie forge whoami    what this space's token may do on its git host (GitHub,
                   GitLab, Gitea), as measured, and what to ask for; `measure`
                   asks the host again
aerie forge pr|issue|run|release ACTION [ARGS]
                   the git host worked through the controller with the
                   space's token, which never reaches a session: pr list,
                   view N, create --title --head --base [--body] [--draft],
                   comment N --body, review N --approve|--request-changes|
                   --body, close N, merge N [--method merge|squash|rebase];
                   issue list, view N, create --title [--body] [--label a,b],
                   comment N --body, close N, label N NAME...; run list
                   [--branch B], view ID, log ID [--lines N] [--job], rerun
                   ID [--failed], dispatch WORKFLOW --ref B [-f NAME=VALUE];
                   release list, view TAG. --state open|closed|all on a list,
                   --json for the host's answer whole. Each needs what the
                   token allows and the space's Permissions, On the git
                   host, permit (docs/git-hosts.md)
aerie logs [-f] [N]   this boot's log
aerie logs -p [N]     a previous boot's log
aerie logs --list     the kept boot logs, newest first
aerie logs --node NAME [--agent|--runner|--nginx|--system|--kernel|--crash] [N]
                   a machine's own log: the agent's journal (its terminals'
                   among it), the CI runner's, its nginx's where the nginx
                   page put one, this boot's system journal, its kernel ring, and the
                   previous boot's last lines (--crash: what the box said
                   before it went). Root's on that box: the enrolled
                   account is in neither `adm` nor `systemd-journal`, so a
                   session cannot read them at all. Offered only while **debug
                   mode** is on in Controller settings, the session's space
                   has been granted that node's logs under **Debug** in its
                   settings, its own node included, and the session's account
                   has the **debug** grant, which is the owner's unless a role
                   names it. The space is the session's own, proved by its
                   token. What can be read is a table of three streams;
                   anything else is refused, not run
aerie diag [--json] [SECTION...]
                   the controller's diagnostics, read-only: its build and the
                   images it ran, its switches, the home tunnel (running,
                   registered, whether its name reaches here, its last lines),
                   the doctor's every check, each
                   node's agent and session half, the Claude plugins each
                   account installed on each node, the last day's jobs and the
                   failures, error lines from its own logs and the audit
                   trail, with anything shaped like a credential redacted. The
                   **debug** grant's: the owner's, or a role's that names it.
                   A session reads it only while **debug mode** is on, its
                   space is granted **the controller's diagnostics** on
                   the Debug page, and its account has the grant.
                   Its `reports` section is what sessions on any space
                   reported about AerieOS, kept until a person clears them
aerie report "..." [--area A] [--repro "..." --reproduces always|sometimes|once|untried]
                   a problem with AerieOS itself, from a session on any
                   space: it goes into the controller's diagnostics rather
                   than the space's tracker (the briefing's notebook section
                   says so), redacted like the diagnostics, and nothing comes
                   back to follow up. A `aerie bug add` whose words name
                   AerieOS or a `aerie` command is not filed but sent here,
                   unless `--here` says it is the space's own. *Agents may: Report
                   AerieOS bugs* in a space's settings turns all of it off
                   for that space, rule and nudge included: AerieOS's own
                   space, whose tracker those bugs belong in, has it off
aerie report conversation N   the conversation a person sent with a report (the
                   end of it, redacted), behind the same gate
aerie pc [VERB] [--why "..."]
                   a person's Windows PC lent to this space by the Windows
                   companion: bare, which PCs lend which verbs; a verb
                   (editor-start, editor-stop, game-start, game-stop, build,
                   shot, log, editor-call METHOD PATH) runs on the PC as its
                   person set it up there and waits for what it did, a
                   picture landing in dist/pc/. Under *Agents may: Use a lent
                   PC* (Deny by default; Ask puts each use in front of the
                   person at the PC); never a command string
aerie doctor          check everything that usually goes wrong

# developing AerieOS itself, from inside it
aerie dashboard test  browser-test the dashboard from this checkout, isolated
aerie dashboard dev   serve the live dashboard from ./scripts/dashboard (--off reverts)
aerie dashboard status  which copy of the dashboard is serving
aerie dashboard trace [SECONDS]  what the dashboard was asked over the last SECONDS, by endpoint and who asked, with how long each took
aerie drift           what this checkout changed that the container is not serving
aerie map VERB ...    the code map, which a session asks before grepping: find NAME,
                   who-calls NAME, calls NAME, defs FILE, draws ID|.class,
                   suites FILE..., state [FILE], sections FILE, unused [FILE],
                   addresses [FILE...], coverage, covered NAME, uncovered [FILE],
                   affected --base REF FILES..., languages (which files it
                   reads), build; aerie map help says what each does
aerie capture shot URL... [FILE|DIR] | --emu [PKG] [FILE] | --display :N [FILE]
                   one picture at rest: a page, the running emulator's screen,
                   or an X display (--drive F works the surface first). At rest
                   means shots a quarter second apart until a second of them
                   match, so a modal still arriving or a list still loading is
                   not the picture: the dashboard's own pages and the two other
                   sources settle by default, --settle asks it of any page, --now
                   takes the one shot at once. Into dist/shot/ for a page and
                   dist/emu/ for the emulator when no FILE is named.
                   A page that does not answer is no picture and exit 3; one
                   that answers 4xx or 5xx is shot, and the status said
aerie capture reel --video FILE|--url URL|--emu [PKG]|--display :N [--seconds N] [--drive F]
                   eyes on change over time: the frames of a recording that changed,
                   each stamped with its time, tiled into dist/reel/NAME/sheet.png
                   beside frames.json (when, and how much moved). From a video, a
                   page Playwright records while --drive FILE.mjs works it, the
                   running emulator's screenrecord (with gfxinfo framestats beside
                   it), or an X display grabbed while a shell script drives it with
                   xdotool; the provisioner installs Xvfb and xdotool for that.
                   Only the sheet and frames.json land in dist/: the recording
                   and the full-size frames are on this machine's disk, where
                   frames.json says
aerie capture ls      the captures in this space's dist/ (reels and emulator
                   shots), each with who asked and when: the Artifacts view's
                   Captures fold, in the terminal
aerie capture prune [--days N] [NAME...]
                   remove those named now, or every capture older than N days.
                   A capture is somebody's until the space's "captures kept"
                   days are up (7 unless its settings say otherwise), and the
                   controller sweeps them when the Artifacts view draws: name
                   yours here to let them go sooner
aerie tool            the tools toolchains add to a session, each under its own name
aerie tool search [WORDS...]  the vetted catalog's tool packs and apps, each with
                   its tier and what it is, and whether it is added here
aerie tool install NAME --why "..."  ask for a pack from the vetted catalog, as the
                   space's Install a tool pack setting says: refused, asked
                   of a person on the bell, or added now; a person installs
                   it on a node from the Library
aerie tool graphics CMD  pictures a session can make and then read back, with the
                   graphics toolchain on its node: info, resize, crop, compose,
                   annotate, diff, svg2png and optimize, into dist/img/, and
                   favicon SVG [DIR], a favicon set (ico + touch icon) from one mark
aerie tool diagrams render FILE...  PlantUML (.puml) and Mermaid (.mmd) rendered to
                   PNG and SVG in dist/diagrams/, with the diagrams toolchain
aerie tool docs read FILE...  a PDF, Word document, slide deck or spreadsheet as
                   Markdown on stdout, with the documents toolchain
aerie tool docs pages FILE [--pages N-M] [--dpi N]  its pages as pictures in
                   dist/docs/NAME/, for layout, charts and scans; a file that
                   is not a PDF is made one by the office toolchain first
aerie tool office convert FILE... [--to FORMAT]  LibreOffice with no window: a
                   document into pdf (the default), docx, xlsx, pptx or odt
aerie tool sound make PRESET [--seed N] [--name N] [--wav]  a sound effect for an
                   app from sfxr's presets (blip, pickup, jump, laser, hit,
                   powerup, explosion, bloop), into dist/sound/ as OGG, with a
                   waveform and a spectrogram beside it to check it by; tone
                   HZ [--ms N] [--to HZ] makes a beep or a sweep, look FILE
                   draws any sound, presets lists them; say "TEXT" speaks it
                   into a WAV (piper) and hear FILE writes down what a
                   recording says with its times (whisper), which need the
                   audio toolchain
aerie toolchains             SDKs kept outside the image: status, check, install X, update X, remove X
```

## The apps a person installs

The apps are built for every release and attached to it, each with a
`.sha256` file beside it. A controller offers the ones ticked
under **Apps** on its Controller settings page: a while after it starts and once a day it fetches each from
the release matching its own version (the newest release when none does,
and the section says so), keeps it only if it matches its sha256, and
serves it from `/config/apps`. A switch moved, or **Check for updates**, looks at
once.

| Where | What |
|---|---|
| Build, Apps | each offered app with its version, **Download**, and how to connect it |
| Settings, Profile | the browsers signed in as you, each with **Sign out**, and the devices, each with **Disconnect** |
| `GET /apps/NAME/FILE` | one file the controller holds (`android`), for anybody signed in |
| `GET /api/apps` | what is offered and held: each app's files, their sha256 and size, the release, when it last looked |
| `POST /api/v1/device/apps` | the same for a device's app (its own token), to update itself from; `GET /api/v1/device/app-file?app=NAME&file=FILE` fetches one |

A device's app sends the door it speaks as `X-BB-Door` (none means 1) and
which app and release it is as `X-BB-App`; one from
before the controller's window is answered 426 with the way to update, by
name. The device door's `projects` and `apps` answers say the controller's
`door` and `door_min`, so an app newer than its controller says so plainly.
What each released app reads is pinned with its types (the Android app's
in `apps/android/api-surface.json`): a field may be added at any time, and removed
only in the release after the apps that read it stopped, with the pin moved
in the same change and a changelog line.

### The seed file

A compose generator (the website's) writes `/config/seed.json` beside the
compose file to choose what a new controller offers before anybody signs in:

```json
{"version": 1, "apps": ["android", "companion"]}
```

Read once, on the first start that finds it: each app named is offered and
each one left out is not. It is then renamed `seed.json.applied`, and
Controller settings owns the choice from there. Nothing about it is in the
environment.

## Signing Android releases

A project keeps its Android keys on the controller, in the **Signing** view of
its page (under Ship), and a build is signed on its node as a job no session can look
inside: from the Artifacts view, or by a session with `aerie sign`, under the
project's **Agents may: Sign a build**. Everything that needs a jdk or the
build-tools happens on the project's node too, never on the controller:
checking an uploaded keystore, Generate, a wrapped backup, a rotation's proof
and a release's APK are each a job there, handed the key for that job alone.
So the node the project's settings choose needs the **jdk** and **Android SDK
Build-Tools** (with android-tools, which installs them) from its Toolchains,
and the Signing view says which node it is and what it lacks when it cannot.
No key is made or added until the
project's owner has set its **backup password**, which every download of a
key's backup asks for, AerieOS's owner included; a backup goes only to an
administrator who works on the project.

| Key | For | If it is lost or leaks |
|---|---|---|
| Play upload key | Google Play with Play App Signing: you sign the `.aab` with it, Google re-signs what users download with the key it holds | Play Console resets it |
| Sideload signing key | an APK you hand out yourself, or that F-Droid publishes from a reproducible build | gone for good: no update reaches an existing install, or anybody can ship one over it |

On the controller every key is sealed at rest under the **install key**
([The install key](#the-install-key)), which the install makes itself
unless `INSTALL_KEY=` sets one. Each keystore and its passwords under
`/config/signing` are ciphertext, so a copy of `/config`, or a backup of it,
opens no key; keys kept from before are sealed at the next start. Changing
the key on the Keys page seals them again under the new one. A key lost, or
replaced outside the page, leaves the sealed keys shut: the Signing view
says so, and each key comes back by **Import a backup**. Root on the running
controller can still read them.

So a sideload key is downloaded once with **Download backup** and kept
offline, with its password somewhere apart from it; its row says so in red
until it has been. A lost backup password is not reset from the dashboard:
signing goes on, and only somebody with a shell on the controller can clear
it, so keep it as carefully as the key. A signed build's Artifacts
row gives the certificate's whole fingerprint, with **Copy for F-Droid** for
its metadata. Using one key on Play, F-Droid and your own downloads (so users
can move between them) means giving Play that key when the app is first set
up there. A project can keep several named keys (one per app, or one shared),
generated on the project's node or uploaded, with each app's package mapped to its
key, and a sideload key can be **rotated** to another: builds then carry both
and a proof, Android 9 and newer move to the new key, and the old one is kept
for the devices before that. **Import a backup** takes what Download backup
gave, in this project or another, as the same key. [building.md](building.md#android-signing-keys)
has the rest.
