# The threat model

What AerieOS protects, from whom, and what it does not. Written before
AerieOS ships as an operating system (R158), so that every hardening
step names the line here it closes, and so that whoever runs an install
can tell their own users what a copy of the disk, a person on the LAN or a
tampered page would and would not get. [privacy.md](privacy.md) says what
an install keeps; this page says who can reach it.

The short version: a secret lives in one place, sealed under a key that is
not beside it, and is handed to the one process that needs it for the one
moment it needs it. Root on the running controller reads everything the
controller can; nobody else reads anything whole.

## Who is trusted for what

| Who | Trusted to | Not trusted to |
|---|---|---|
| **The owner** | run the install: the controller's settings, every space, every account, the install key, maintenance mode | open another person's key store (their agent sign-ins, their git tokens): sealed under that person's key, which only the install key opens, which the owner holds, so this is a line of policy today and a line of cryptography once R157 lands |
| **An administrator** | spaces, nodes, people, the Keys page's inventory, purging a store | read a store's contents; sign in as another person |
| **A person** | their own spaces, their own key store, their own sign-ins | another person's sessions, store or sign-ins; the controller's settings |
| **A person's coding agent (a session)** | the space it runs in, the spaces it reads, `aerie` on its person's behalf under the space's dials | the controller's state, another space's tree, any token (it pushes and signs through AerieOS, which holds the credential), another account's home or tmux (R125), the dashboard's shell history (R155) |
| **Root on a node** | the machine: every session there, every token file on it | the controller: a node has no credential to the controller beyond its own enrollment, which reaches its own space's work and nothing of another node's |
| **Root on the controller** | everything the controller can read, the install key included | nothing is kept from root on the running controller; this is the host's own trust (`docker exec`, the machine's console) |
| **A copy of a disk** (a backup, a stolen drive, a copy of `/config`) | nothing | the sealed stores open without the install key (kept outside `/config`), the node's sealed sign-ins open without the controller, the signing keys and git tokens are ciphertext |
| **Someone on the LAN** | nothing | changing what the agent channel carries, or opening a terminal, a file request or a VM's screen on a node: each is signed with that node's own key, and a request to a node's relay is taken once. Reading what the relay carries (a shell's keys and output, a file, a VM's screen): it crosses in TLS to a certificate the node made for itself and reported over its channel, the only one the controller takes there; a node that could not make one (it has neither Python's cryptography library nor `openssl`) is served unencrypted and its page says so. The page's own traffic is theirs to read where the dashboard is served over http (step 2 below) |
| **The page's own code** | drawing what the controller answers and asking it to act | holding a key: the page never holds a key (a key of a person's own is a passkey's or a companion's, R157), keeps no secret in local or session storage, and under the CSP of step 4 runs no script it did not ship |

## What each store protects, and what it does not

**The install key** (`BB_SECRETS_DIR/install-key`, or `/config/.install-key`
where there is no secrets folder; made at the first start, changed from the
Keys page). The secrets folder is root's: the controller's account may pass
through it to its own key folder (mode 0710, the account's group), and may
not list it or read the `*.env` files and `ssh/` beside the key. On a stick
the whole secrets folder lives on the system pool once one is picked, so the
stick alone, lost or taken, carries the sealed state without the key that
opens it; while that pool is not mounted the folder is held empty and the
controller starts with nothing sealed or opened, then starts again when the
pool mounts. Everything the controller keeps sealed is sealed under a key
derived from it: the accounts' keys, the signing keys, two-factor secrets,
the deploy keys, a space's own git line from before 0.8.0.

- Protects against: a copy of `/config` (ciphertext alone), a move's
  bundle landed on another machine without the key ticked (what is sealed
  stays locked until the key is given), an operator of the share the state
  lives on.
- The configuration's own backup (Controller settings, Backup) carries the
  install key inside, sealed with the rest under the backup password, so
  the password alone restores a copy whole: a copy is a sealed file to
  whoever lacks the password, and everything the controller keeps to
  whoever has both. Choose that password as you would the owner's.
- Does not protect against: root on the running controller, who reads the
  key where the controller does; the stick and its pool's disks taken
  together; a secrets folder copied along with
  `/config`, which is why the key belongs in a folder the state is not in.

**An account's key** (`account-keys.json`, sealed under the install key).
Each person's own, made with their account, changed from Profile. Their
key store, their agent sign-ins on every node and the key pair each node
seals those under derive from it.

- Protects against: another person, an administrator and a copy of the
  disk reading the store; the install key changing (the account's key is
  sealed again, nothing on the nodes moves).
- Does not protect against: the owner, who holds the install key the
  account's key is sealed under. R157 closes this: a key of the person's
  own, held by a passkey or the companion, which the controller cannot
  open.

**A person's key store** (`account-secrets.json`: their git tokens, each
sealed under their account's key; the space's `gitcreds/NAME` names
entries and holds no token). A token is handed to git only for that
person's own work (their session's `aerie git`, their presses, the release
they cut) and only while they hold a live sign-in (`logins.json`); work
that is nobody's (watching CI) takes any signed-in giver's.

- Protects against: a token outliving its person's sign-in; a session
  pushing as somebody who is not there; a space carrying a token nobody
  gave it; a session reading the token (it never sees it: the helper hands
  it to git on the controller).
- Does not protect against: the controller itself while a person's store
  is open, which opens the token to hand it over. Step 5 bounds that: a
  token is opened per use for the window the person picks, the opened line
  is what the controller keeps (in memory, and in a handout file for git
  under `/run` for the window), and each use is on their Profile. With a
  key of their own (R157) the store opens only while they have unlocked it.

**The agent sign-ins on a node** (sealed by the node under a public key
whose secret only the controller derives; `tokenseal.py`). The node seals
and never holds what opens a seal; the controller hands the seal's key into
a terminal a signed-in person opened, wrapped to the agent's own key for
this boot.

- Protects against: a copy of the node's disk or of the share; the traffic
  captured and the disk copied together; another account's shell on the
  node (R125: each account is a Unix user of its own).
- Does not protect against: root on that node while the sign-in is open in
  a terminal there, which reads the process's memory; a controller that is
  itself compromised, which can derive any node's secret.

**The signing keys and the deploy keys** (`/config/signing`, `/config/deploy-keys`;
sealed, root-only). A signing is a job on the space's node handed the key
over the agent's channel for that job; a push with a deploy key goes
through the shielded ssh agent. A deploy key made or pasted in a space's
settings is kept by a root-only helper as `NAME.sealed`, sealed under the
install key, and is opened only into that agent: no private key file is on
the disk. One from before is sealed at the first start of a build that
seals them. An install with no install key keeps a deploy key as a plain
file and says so when it is made; a key an operator places by hand in the
secrets folder's `ssh/` is theirs, plain, and outside `/config`.

- Protects against: a session reading, printing or committing a key; a copy
  of `/config`, root's folders in it included.
- Does not protect against: root on the node during the job that holds the
  key; root on the running controller, which holds the install key.

**A share's password** (`users.json`, on a controller that serves shares).
Samba takes the NT hash of a password, MD4, which is far weaker than the
sign-in's own hash and opens the shares as the password does. It is kept
for an account an SMB share names and for nobody else: made as that person
next signs in or changes their password, taken away when no share names
them. A person may set a separate share password on Profile, which is then
the one kept.

- Protects against: every account's password being guessable from a copy of
  `users.json`, as it was while the hash was kept for all of them.
- Does not protect against: a copy of `users.json` for the people a share
  names: use a separate share password where that matters.

**The cryptography itself.** Every seal is ChaCha20-Poly1305 under a key
HKDF derives, and a node's key pair is X25519, from the `cryptography`
library; a passkey's signature and its point on P-256 are checked by the
same library. Where the library is missing the controller seals nothing
and says why, never with a cipher of its own. What is still written here:
MD4 for a share's NT hash on a machine whose OpenSSL withholds it (the
library has none; it is held to the RFC's answers), the reader for a
passkey's CBOR, which parses and decides nothing, and the seals of the
format before, which are opened and never made. A node that has not the
library seals a coding agent's sign-in the older way, which the controller
opens and seals again. Step 7 is the outside review.

## What an unlock gives up

A store is opened to be used. Each opening is a moment the controller holds
the plain token, and R158 step 5 makes each one a choice the person made:

- A person's git token is opened the first time git asks for it in a
  window, for the window they picked on their Profile (a quarter of an
  hour, an hour, eight hours, or while they are signed in), and the opened
  line is what the controller keeps: in its memory, and in a handout file
  of one line under `/run/bb-git` that `git-credential-bb` reads for that
  window, shredded when the window ends, the store is locked or the person
  signs out everywhere. The seal is opened once per window, not per use,
  and every opening is a line on their Profile: when, which token, on which
  space, for what (a push, a pull, CI watching, a release) and by whom.
  Lock on the Profile lets go of all of it at once.
- An agent sign-in is opened into the terminal that starts the session, on
  the node, and lives in that process for the session's life.
- The install key is in the controller's memory for as long as it runs:
  what root on the controller reads.

**A key of the person's own (R157).** Under the install key, the unlock
bounds how long an opened token stays in memory; the controller could open
the store at any time, since it holds the key. *Hold the key yourself* on
the Profile moves the store under a key the controller never holds: a
passkey's PRF secret (the authenticator derives it and the page only relays
it to the controller, over https and under the page's policy, for the one
request that unlocks), or a key the person keeps (64 hex characters shown
once; the Windows companion or a password manager holds it, and a device
signed in as them may unlock with it through the device door). The
controller keeps the X25519 public half of what the person holds and the
account key sealed to it; the account key is in its memory only while the
person has unlocked, and `Lock`, a restart or the window's end forgets it.
While it is shut: their pushes and pulls wait and the Git view says so, a
terminal they open on a node asks for the unlock first (that terminal is
what opens their sealed sign-ins there), and a login made on a node is
still sealed, to the node public halves the controller remembered while
the store was open. What it costs: a forgotten passkey or key means signing
in to every agent again and giving each space a token again; Purge
still works without it, an administrator's too. The tokens a space runs
background work with (CI watching, releases) go to the space's own
keeping at the move, listed before the person chooses, unless they keep
them under their key and accept that this work waits for their unlock.

## Memory and process

The dashboard and the node agent each do three things about the keys they
hold (R158 step 6, `hardening.py` and `aerieos_agent.base.harden`): no
core dump (the core limit is zero and the process is not dumpable, which
also keeps another process of the same user from reading its memory
through ptrace or `/proc/PID/mem`), no swap (the process locks its pages
in memory where the memlock limit lets it; `docker-compose.yml` and the
Unraid template raise that limit, and the Doctor says when it was too low),
and zeroing (`wipe`) of a bytes value that held a key or an opened sign-in
once it is let go. Root on the machine still reads a running process; what
the step closes is a core file, a swap partition and a neighbor of the same
user.

What sessions ask for never runs in either process: the controller runs
nothing, and on a node the agent that opens a seal is apart from the
sessions, which run as their account's own user in a view of their own
(R125, `bb-session`), so a session reaches no key the agent holds.

**Root's work in an account's folder is done as that account.** A node's
agent is root, and much of what it writes and reads is in folders an
account owns: a space's tree, a job's workspace, an account's
conversations. Root opening a path there follows whatever the account left
at that path, so the agent takes the account's file identity for that work
(for the calling thread alone: `setfsuid`, `setfsgid` and the thread's own
groups; `base.acting_as` in the agent). The kernel then checks every path
as that account, with none of root's file capabilities, and a planted link
leads nowhere the account could not have gone itself. The agent tries this
on the machine before relying on it and says in its log which it is; an
update's job says it too (`file work as the account: holds`). Where a
machine does not hold it, the work is root's as before and the log says so.
A folder the agent makes for an account above that account's own (a
space's top, an account's conversations folder) is still root's to make,
and nothing is made under a link on the way.

This is proved as root, where it is true or not: the root tier
(`scripts/dashboard/roottier`, `aerie tests root`) plants a link where the
agent downloads, syncs, writes a compose file, hands a folder over and
reads a job's artifacts, and where the session helper keeps its grants and
makes a worktree, and sees that a file only root reads and a folder only
root writes are as they were. It runs as root in a throwaway container, on
every pull request and on every release before anything is published: the
other suites run as an ordinary account, where acting as another changes
nothing.

## The lines the hardening closes

| Step of R158 | The line it closes |
|---|---|
| 2, TLS | someone on the LAN reading the page's traffic, a session cookie or a token typed into a form; http stays a choice for an install with no CA, said on the page with what then crosses in the clear |
| 3, vetted cryptography | the hand-built seal and key exchange, replaced with a library somebody else has reviewed |
| 4, the page hardened | a tampered or injected script on the page, a secret parked in the browser's storage, a cookie sent cross-site, a change posted with the cookie from another origin of the same site (an app this install routes): a cookie's POST is taken only from the dashboard's own page |
| 5, an unlock that gives up less | the controller holding a person's whole store open while they are signed in |
| 6, memory and process | a core dump, swap or a neighboring process reading a key the controller holds |
| 7, outside review | this page and the cryptography being right by their authors' word alone |
| 8, sign-in hardened | a stolen cookie used from another device; guessing a password at any way in (the sign-in page, the command line, the app, file access), where an address is held after 100 wrong in a quarter of an hour and an account only slowed, the address being each visitor's own behind the install's tunnel or a reverse proxy named in Settings and never the proxy's, which is everybody's; what was done to the host read back by person and machine |

What no step closes: root on the running controller, and a person's own
agent acting as them on their own spaces, which is what it is for. The
dials (Agents may) bound what it may do; the record (the audit, the
notebook's history, the forge's log under their own token) says what it did.

## What is held in one place

**Who may reach a route.** Every route of the dashboard's API is one line
of one record (`ROUTES` in `server.py`), and names there what it asks of
its caller (the dispatcher's `ROUTE_GATES`, read off the record), which the
dispatcher holds before the handler runs: the owner's alone, a person's own
sign-in and never a session's token, or the handler's own check where it
depends on what the request names (which space, which node, which action).
A route that names nothing is not served, and the auth suite fails on one,
so a new route cannot be reached before somebody has said who may reach it.
Most routes are still the handler's own; each one moved onto its line is
one fewer place to forget.

**What a session's token reaches.** A coding agent's session is not a
person with fewer rights: it is another kind of caller, and the dispatcher
refuses it on every route but the ones whose line of the same record says a
session's (`SESSION_ROUTES`, read off it too): the routes its own verbs and
hooks call, about forty of the hundred and eighty. A route in that table
still holds its own scope (the session's own space, the action, the space's
dials); a route outside it cannot be reached by a session whatever its
handler checks or forgets. So the accounts, the controller's settings, the
page's own reads, a person's chat, tabs and other sessions are not a
session's to ask for, and neither is the page: a session's token opens
none of the dashboard, its terminals, a VM's screen or the metrics, and
`aerie capture` sends that token to no page. The unit tier holds that
every path a session-side script names is in the table, and the auth
suite asks every other route with a session's token and expects the
refusal, so a new route is closed to sessions until somebody names it.
Where only some of a route's actions are a session's (asking for a phone
and not pairing one, installing a pack from the catalog and not removing
one), the same table names the actions and the dispatcher holds them once
the request is read. And a session carries no account's id and no role of
a person's: what the controller keeps by a caller's id (a layout, a key
store, a sign-in) it keeps nothing of for a session, and the routes that
do act for the person a session works for (their memories and
conversations on the space, their git token for a push, the phone lent to
them) ask for that person by name. What a session may ask of the
permissions at all is a list of four (read its space, work in it, write
to it, and the relayed verbs), each still held to the account behind it.

**A request from another site.** A change, and a read of `/api/`, sent with
the browser's cookie is taken from the dashboard's own page alone
(`Sec-Fetch-Site`), since some reads do things and another origin of the
same site is sent the cookie. The cookie is marked Secure where TLS ends
here or at a proxy in front that says so.

**What a node is told.** A node's word about the sessions it runs earns a
session's token only for a space that works on that node and an account
that may work on that space; it is handed nothing for a session it merely
names.

## What a node takes on its controller's word

**Its agent's updates, once it has pinned the release key, it does not.**
AerieOS has a release key (`config/aerieos-release.pub` names its public
half; the private half is the release build's secret and no controller's).
The Enroll script carries the public half and the agent pins it as the
node enrolls (`aerieos-agent release-key` shows it, and pins one on a
node enrolled before, at its console). Where the file names a spare on a
second line, the script carries both and the node pins both: an update
signed by either is taken ([the signing keys](#the-signing-keys-and-replacing-one)). From then on the node takes an agent
update only when the release build's signature over the update's digest
comes with it (`scripts/agent/agent.sig`, made by `tools/sign-agent.py` in
the release's builds and passed on by the controller, which checks nothing
itself). A controller built from a branch ships an unsigned agent, which a
pinned node refuses, saying so on the update's job; a machine its owner
uses for such builds says `sudo aerieos-agent unsigned on` at its own
console. Somebody who builds the controller themselves and signs those
builds with a key of their own adds its public half there instead (`sudo
aerieos-agent release-key add HEX`, four at most, and `release-key drop
HEX` takes one away): the node then takes what that key signed beside what
the release signed, and the update's job says which key it was. The key
is made once on the machine that builds (`tools/sign-agent.py
--builder-keygen FILE`, which prints the command for a node's console), and
each build is signed with it before its image is made (`tools/sign-agent.py
--builder FILE` writes `scripts/agent/agent.sig` for the tree as it
stands, which the image's build takes with the rest). It is kept on the
building machine, out of the repository and out of the container's reach:
a controller that could sign its own agent would make the nodes' check
worth nothing. These
choices are a person's at the machine: they take root and a
terminal, the running agent never writes over them, and nothing the
controller sends in the channel changes them. A pinned node that meets an
unsigned controller stays on the agent it has, and since a controller
sends a node whose agent is behind nothing but that update, it takes no
other job either until the controller runs a signed build or the node's
console allows unsigned ones: closed, on purpose, and said on the update's
job and on the node's row. A node's row says which it
is under Updates. The file is read one way (`scripts/lib/releasepub.py`), by
the Enroll script, the build's signer and `aerie lint`, which fails when it
does not name one key or two: a file that does not parse is a red build,
never a node that quietly pinned nothing.

**Nor the first agent, nor one a provisioner fetches later.** Every way of
enrolling carries the key: the Enroll script, the token-only commands the
Nodes page shows, a Mac's provisioner and the controller's own node on a
bare-metal install. With it they carry the digest of the agent the
controller shipped when the script or the command was made and, where its
build has one, the release's signature over that digest. The provisioner
holds the agent it fetches to the digest it was handed, where it had only
the digest the same answer named, and checks the signature under the key
before any of the agent runs (Python's cryptography library, OpenSSL 3, or
Swift's CryptoKit on a Mac); another agent, a signature that is not the
key's and one the machine cannot check are each refused with the reason,
and so is an answer with no digest at all. A build with no signature
enrolls on the digest alone and says so, with the key pinned for what
comes later. A script made before any of this, or a command somebody saved,
still enrolls, held to the digest the controller sends, and says what was
not checked. A provisioner run again on an enrolled node asks the installed
agent before it replaces it (`aerieos-agent check-update`, which decides as
an update is decided), and leaves it in place on a refusal; where the
installed agent is too old to answer, or is gone, a node that pinned a key
gets the newer one only when the provisioner itself can check the release's
signature under the key the node pinned, and a node that pinned none
updates as it did.

A node that has no key, one enrolled before there was one or by a script
that named none, takes what its controller sends, and the update's job says
that nothing was checked. It pins on its first signed update: the
controller names the release keys its own build carries beside every
update, and when the update's signature is under one of them the node
installs it and pins them, saying so on the job. That is trust on first
use, of a controller the node already took everything from, and it closes
the door behind a release rather than waiting for a person to run the
Enroll script again. An update with no signature, or one under another
key, is taken as before and pins nothing; a node that has any key, the
release's or one added at its console, is never offered one this way. Nor
is a node where a person dropped the release key (`sudo aerieos-agent
release-key none`): that choice is kept as the console's word, the node
takes what its controller sends and its updates' jobs say it was the
console's choice, and it pins no key by itself until a person pins one
there again (`release-key HEX`, or the Enroll script).

`aerieos-agent check-update FILE [SIG]` is the same rule, for whatever
replaces an agent from outside it (a provisioner run on a machine that has
one) to ask first: it says in one line whether this node would take that
file with that signature, exits 0 when it would and 77 when it refuses,
and writes nothing.

**The tools root installs from the bundle, it does not either.** The
provisioner with the machine's own helper in it, the helper that builds a
session's view and the one that cuts a pack's install off the network reach
a node in the bundle of `aerie` the controller serves, whose digest moves
with a person's tool packs and is the controller's word. A release's build
signs the list of those files, each with its digest, and a pinned node
keeps a copy of them for root only under that signature: otherwise root
goes on with the copy it has, the job saying why, and a machine whose
console allows unsigned builds takes them from a branch's build as it takes
that build's agent. A key added at the console counts here as it does for
the agent: root's tools signed by it are kept.

**Nor the other files a release ships in that bundle.** `aerie` itself and
its library (the toolchain installer and its checksum logic are in it, and a
script the agent runs as root to list sign-ins where accounts own their
homes), the shipped catalog, the publishers' keys a download is checked
against, the terminal's launcher and the hooks a session is handed all ride
in the same bundle. The bundle carries the list of them, a line a file with
its sha256 (`nodes/bundle.list`, made one way by
`scripts/lib/bundleparts.py` for the build's signer and the controller
alike), and the release's signature over that list (`nodes/bundle.sig`, the
third part of `scripts/agent/agent.sig`). A pinned node unpacks a bundle
only when that signature is under a key it trusts and every file in the
bundle is the one the list names: none changed, none missing, no link, and
none beside them except what a controller adds of its own. A bundle that
fails is unpacked nowhere, in the job account's store or in root's copies:
the node goes on with the bundle it has, names the first file that was
wrong in the job's log and its own, and does not fetch that bundle again
until its console's trust changes or the controller offers another. While
the refusal stands the node reports it with its hello, and whoever manages
nodes sees it: a row on the bell for that node, saying it refused this
controller's bundle and what was wrong in one phrase, and the same under
Sessions on the node's page; both leave when the node takes a bundle or the
controller serves another. Which keys the node takes, and the two commands
its console has for that (`release-key add`, `unsigned on`), are in the
job's log and the node's own, not on the page. A container's shell on such a node
opens from the bundle it kept, with no wait for one it will not take. A
machine whose console allows unsigned builds takes a branch's bundle as it
takes that build's agent, and a key added at the console counts as it does
there. A controller whose own files are not the ones its build signed (one
edited in place) says so once in its log, and one whose dashboard is served
from a checkout (`aerie dashboard dev`) packs that checkout's files, which
no build signed: either way its pinned nodes stay on the bundle they have.
To hold an install against a checkout, an administrator's
read of the Nodes page (`/api/v1/nodes`) carries the list's digest as `files`
with whether the build signed it as `files_signed`, and `tools/sign-agent.py
--digests` prints the same digest for a tree.

What a controller adds beside those files is still its word, and no
release can sign it: the tool packs a person added and the ones made on
that install (`config/toolpacks.json`, `config/toolpacks/NAME.bundle`), and
the vetted catalog's newer rows for the shipped toolchains
(`config/toolchains.catalog.json`, which a node reads in the shipped
catalog's place where the bundle carries it; the shipped file itself goes
as the release signed it). So whoever holds a controller can still hand a
pinned node a recipe of their own: what a recipe downloads and runs, it
runs as the jobs account, and the system packages it names are installed
by root from that machine's own repositories.

**The rest, it still does, unless its console says otherwise.** The agent
runs as root; a root command an administrator approves is run as given
(which, on a node provisioned as a sandbox, could also undo the pin); and
the jobs account's Docker is root's on a node that runs containers. So
whoever holds the controller (a copy of its state with the install key, an
administrator's sign-in) still holds those nodes: the signatures close the
update, root's own tools and the files a release ships in the bundle as
ways in, not the others. What bounds them
on the controller's side: **Lock system changes** on a node's row has the
controller refuse storage, network and root changes there, and every root
command is on the record with who approved it. Two things are held by the
node itself. On the controller's own machine the root agent runs docker for
the controller and nothing else under that mark. And a machine's own
console can switch root commands off: after `sudo aerieos-agent root-asks
off` there, that node refuses every root command the controller sends
(`aerie root run`, a schedule as root), whoever allowed it, and the
controller says so before anybody is asked; its row says it is off, and
only `sudo aerieos-agent root-asks on` at that machine turns it back on.
What AerieOS does as root by name (storage, updates, its own tools) goes
on, and where the machine runs containers, Docker there is still root's:
the switch closes the free-form command, which is the widest of them.

## The signing keys, and replacing one

What an install takes from outside is checked against a key it already
holds, never one that arrives with the thing itself:

| What is checked | The public half an install holds | Where the private half is |
|---|---|---|
| The catalog's index | `config/catalog.pub`, shipped in the release | the catalog repository's secret `CATALOG_SIGNING_KEY`, used by its `sign` workflow |
| A node's agent update, root's tools and the files of the bundle it fetches | `config/aerieos-release.pub`, pinned by the node when it enrolls | the release build's secret `AERIEOS_RELEASE_KEY`, read by two jobs on a `v*` tag alone ([versions.md](versions.md#the-release-key-on-github)) |
| A release's list of its files (`SHA256SUMS`), for a dev build | `config/release-signers`, its `aerieos-dev` lines: the release key and its spare again, as OpenSSH keys | the release build's secret `AERIEOS_RELEASE_KEY` |
| A release's list of its files, for a stable release | `config/release-signers`, its `aerieos-release` line | offline, on the stable key holder's own machine |

The third and fourth rows are one file, which the image carries and a
bare-metal release is laid out with, and one rule: every file an install
takes from a release (the controller's bundle, AerieOS's image, a stick's
image, the apps the Library offers) is held to the release's signed list,
and the release's tag says who may have signed it. A pre-release
(`vX.Y.Z-dev.N`, `-rc.N`) takes a list signed in either namespace; a stable
release (`vX.Y.Z`) takes `aerieos-release` alone, so the key CI holds, which
signs dev builds as they publish themselves, can never sign a stable
release, and a stable release waits for its holder's signature. A release
with no signed list, or one signed by somebody its tag may not have, is
refused with the reason; until a stable signer's line is in the file, a
stable release is refused in those words.

**What a changed key costs.** An install trusts only what a key it holds
signed, so a new key cuts off whatever still holds the old one. For the
catalog that is every install on an older release: it keeps the index it
last read and takes no newer one until it is updated; what a release
ships itself (the toolchains, the coding agents), what is installed and a
pack added by its own address go on working. For the release key it is
every node that pinned the old one: it takes no agent update, and so no
other job, until a person pins the new key at that machine (its Enroll
script again, or `aerieos-agent release-key` at its console). A key that
is lost costs the same as one that is changed.

**The spare.** So each of the first two files may name a second key, its
spare: a pair made the same way, whose private half is kept apart from
the first (never in the same secrets) and signs nothing while the first is
in use. An install reads an index signed by either, and a node that pinned
both takes an update signed by either. When the first key is lost or has
to go, the spare signs in its place and nothing is cut off; the next
release then names the spare as its first key and a new spare beside it.
Two is the most either file names: every key held is one more that can
sign. A node enrolled before a spare was named pins it the next time its
Enroll script is run, and its row says so under Updates until then.
`config/release-signers` was a list from the start, and its dev lines are
written from the release key and its spare (`tools/release-signers.py`,
held by `aerie lint`), so a build signed by either is taken.

