# The dashboard's API

Written from `scripts/dashboard/server.py` by `tools/api-doc.py`; `aerie lint` holds this page equal to it.
Every request carries the account's credential (a session's token, or the person's cookie or
basic auth). The last column is the route's gate in the route record: what the dispatcher holds
before the handler runs (and after `then`, what the handler asks of that person besides), or the
names of everything the handler itself asks: a permission (of the
install, or of the space the request names), `space` for a space the account sees, `unlocked` for
one not locked against it, `node:` and `instance:` for a permission asked of one node or one
cluster, `dial:` for a session's ask under the space's Agents may, `own` for the account's own
things, and `seen` or `open` where the handler refuses nobody signed in (`seen`: the answer holds
what the asker may see). A name is everything the handler consults, so a permission read only to
draw a dead button is named too. A `prefix` route takes every path it prefixes, in the order
listed; an `exact` one takes its path alone. The companion app's own contract is
`apps/android/api-surface.json`.

| Method | Path | Match | Handler | What it does | Asks |
|---|---|---|---|---|---|
| GET | `/api/revs` | prefix | `_get_revs` | GET /api/revs. | `seen` |
| GET | `/api/live` | exact | `_get_live` | GET /api/live: who has a Claude session on each project this account sees, which of them are working and which asking, the maps the status payload also carries (projsessions.maps), alone and cheap. | `seen` |
| GET | `/api/audit` | exact | `_get_audit` | GET /api/audit: who did what to this install (db.audit_page) for the Audit page, newest first, a page at a time (before=TIME), by one person (person=NAME) or one machine (machine=NODE_ID); with the people and the machine | `controller-read` |
| GET | `/api/trace` | prefix | `_get_trace` | GET /api/trace?since=T: what this server was asked since T, grouped by endpoint. | `admin`, `debug` |
| GET | `/api/status` | prefix | `_get_status` | GET /api/status. | `seen` |
| GET | `/api/reset` | exact | `_get_reset` | GET /api/reset: how a Reset that un-enrolls its nodes first is getting on: each node, done or why not, and the error that stopped it. | `controller-read` |
| GET | `/api/move` | exact | `_get_move` | GET /api/move: a move armed here (and, asked with ?pieces=1, what a bundle may carry with each piece's size), or this controller moved, or this state arrived by a move with the nodes not yet here; an administrator's. | an administrator's, held by the dispatcher; then `owner` |
| GET | `/api/move-bundle` | exact | `_get_move_bundle` | GET /api/move-bundle[?name=]: the bundle as a download, packed fresh under the armed move's key at this moment, or the one just packed by name; the owner's. | the owner's alone, held by the dispatcher |
| GET | `/api/move-backup` | exact | `_get_move_backup` | GET /api/move-backup?name=: the controller's backup packed under a token of its own, as a download; the owner's. | the owner's alone, held by the dispatcher |
| GET | `/api/backup` | exact | `_get_backup` | GET /api/backup: the password set or not, the last copy, where the copies go and the copies found; an administrator's. | an administrator's, held by the dispatcher; then `owner` |
| GET | `/api/backup-file` | exact | `_get_backup_file` | GET /api/backup-file?name=NAME: a copy under the state as a download, the owner's; sealed, so a download is only ever a sealed file. | the owner's alone, held by the dispatcher |
| GET | `/api/findings` | prefix | `_get_findings` | GET /api/findings: findings.view, scoped to the projects this account sees. | `seen` |
| GET | `/api/profile` | prefix | `_profile` | The signed-in account's own settings (the Profile page): read on GET, saved on POST, by profiletab.py. | `own`, `admin`, `node`, `space` |
| GET | `/api/transcripts` | prefix | `_get_transcripts` | GET /api/transcripts?project=NAME: the signed-in account's own conversations with Claude on that project, newest first (transcripts.mine); with audit=DAYS, what they did against the house rules that can be counted instea | `own`, `space` |
| GET | `/api/snapshots` | prefix | `_get_snapshots` | GET /api/snapshots?project=NAME: the days kept of the project's tree (snapshots.py), newest first, and how many it keeps. | a person's own sign-in, never a session's token, held by the dispatcher; then `settings`, `space` |
| GET | `/api/transcript` | prefix | `_get_transcript` | GET /api/transcript?project=NAME&id=SESSION: one of the signed-in account's own conversations with Claude on that project as a text file, every command and answer in it (transcripts.render); as JSON with as=json, which i | `own`, `space` |
| GET | `/api/git` | prefix | `_get_git` | GET /api/git: the notebook's Git view (gitview.view), for a project this account may see. | `space` |
| GET | `/api/forge-access` | exact | `_get_forge_access` | GET /api/forge-access: what an agent may do on this project's git host, each ability with what its token says and the project's own override, from the kept measure; for a project this account sees. | `space` |
| GET | `/api/project-sessions` | prefix | `_get_project_sessions` | GET /api/project-sessions?project=NAME: every account's sessions on the project, for its settings dialog. | `settings`, `space` |
| GET | `/api/changelog` | prefix | `_get_changelog` | GET /api/changelog: changelog.reading, for a project this account sees. | `space` |
| GET | `/api/version` | prefix | `_get_version` | GET /api/version. | `space` |
| GET | `/api/tls` | prefix | `_get_tls` | GET /api/tls: what the dashboard is served over (tls.status), for an account that reads the controller; with download=1 the certificate itself, for a phone or the companion to pin. | `controller-read` |
| GET | `/api/artifacts` | prefix | `_get_artifacts` | GET /api/artifacts: artifacts.tab_view, for a project this account sees. | `space` |
| GET | `/api/artifact` | prefix | `_get_artifact` | GET /api/artifact: one file of a project's, as a download (artifacts.download). | `space` |
| GET | `/api/signing-backup` | prefix | `_get_signing_backup` | GET /api/signing-backup: a project's keystore for an administrator's own copy (signing.backup), which marks it backed up. | `space`, `signing` |
| GET | `/api/node-busy` | prefix | `_get_node_busy` | GET /api/node-busy: whether one of a project's nodes is quiet enough to time anything on (busy.report). | `space` |
| GET | `/api/meta` | prefix | `_get_meta` | GET /api/meta. | `seen` |
| GET | `/api/welcome` | prefix | `_get_welcome` | GET /api/welcome: AerieOS's own changelog for the welcome panel (changelog.welcome), and where this account last looked. | `seen` |
| GET | `/api/source` | prefix | `_get_source` | GET /api/source: the code base as a zip, from the Artifacts view (artifacts.source_download). | a person's own sign-in, never a session's token, held by the dispatcher; then `space` |
| GET | `/logs/download` | prefix | `_get_logs_download` | GET /logs/download: the container's own log, every project's traffic in it, or the diagnostics whole (logs.download): Controller settings' to read, the diagnostics with them, since they hold the bug reports a person read | `controller-read` |
| GET | `/api/phone/wait` | prefix | `_get_phone_wait` | GET /api/phone/wait?since=T: the companion app's live connection. | `admin` |
| GET | `/api/phone` | prefix | `_get_phone` | GET /api/phone. | `admin`, `node`, `space` |
| GET | `/api/toolchains` | prefix | `_get_toolchains` | GET /api/toolchains. | `node:read`, `admin`, `node`, `space` |
| GET | `/api/agents` | prefix | `_get_agents` | GET /api/agents?node=ID: the coding agents on one node (the Library's): each agent's row, the version against the latest and any job of its own, and the asking account's own plugins and MCP servers there. | `node:read`, `admin`, `node`, `space` |
| GET | `/api/emulator` | prefix | `_get_emulator` | GET /api/emulator?node=ID: that node's system images, what could be added, and the image job there. | `node:read`, `admin`, `node`, `space` |
| GET | `/api/roles` | prefix | `_get_roles` | GET /api/roles: the Roles page: the areas, every role, and each account with its Global roles, the roles it holds on each project and the projects it is on. | `admin`, `space` |
| GET | `/api/users` | prefix | `_get_users` | GET /api/users. | `admin`, `space` |
| GET | `/api/nginx` | prefix | `_get_nginx` | The nginx page (nginxproxy.view): every node's nginx, for an account that may read the Nodes page; never a session's. | `admin`, `node:configure`, `node:configure-read`, `node:nodes-read` |
| GET | `/api/scanners` | exact | `_get_scanners` | The Scanners page (scanners.view): every node's scanners, the schedule, the versions and what nothing covers, for an account that reads a node's services (_service_may); never a session's. | a person's own sign-in, never a session's token, held by the dispatcher; then `admin`, `node:configure`, `node:configure-read`, `node:nodes-read`, `instance:configure` |
| GET | `/api/router` | exact | `_get_router` | GET /api/router?node=ID: a node's model router (router.status) and the projects it may be offered to, for an account that reads the Nodes page, on that node; never a session's. | a person's own sign-in, never a session's token, held by the dispatcher; then `node:configure`, `node:configure-read`, `node:nodes-read`, `space` |
| GET | `/api/router-key` | exact | `_get_router_key` | GET /api/router-key?project=NAME: the router address and the project's own key, for a session of that project at its start (bb-tty's launcher) or a person who may work on it; {} where no router allows the project. | `space`, `work` |
| GET | `/api/storage` | prefix | `_get_storage` | The Storage page (storage.view): every node this account holds the Storage area on, what its disks hold, by project where the account sees the project and as one line otherwise. | `admin` |
| GET | `/api/history` | prefix | `_get_history` | GET /api/history?node=ID&span=6h\\|day\\|week\\|month: the controller's own machine's CPU, memory, network, disk I/O and temperatures over the span, at the resolution kept for it (five minutes for a day, an hour for a month). | `node:nodes-read` |
| GET | `/api/schedules` | exact | `_get_schedules` | GET /api/schedules: every schedule, its words, its next run and its last run's state, and the nodes it may run on. | `schedules-read`, `schedules` |
| GET | `/api/extmounts` | exact | `_get_extmounts` | GET /api/extmounts: the other disks and shares the controller's own machine mounts, as recorded, never a password. | an administrator's, held by the dispatcher |
| GET | `/api/nasapps` | exact | `_get_nasapps` | GET /api/nasapps: the catalog of ready apps the New container dialog offers, each with what it is and the blanks it takes. | `docker-write`, `node:read`, `admin`, `node`, `space` |
| GET | `/api/catalog` | prefix | `_get_catalog` | GET /api/catalog[?fresh=1]: the vetted catalog's index as kept (fetched again when older than an hour, or on fresh), verified against the key this install ships; with the reason when the newest could not be taken. | `toolchains-write` |
| GET | `/api/library` | prefix | `_get_library` | GET /api/library?node=ID: everything an AerieOS installs or runs as one list for one node (library.rows): the toolchains and packs with what the node's store holds, the coding agents, the apps a NAS runs, the vetted cata | `node:read`, `admin`, `node`, `space`, `toolchains-write`, `docker-write`, `node:configure`, `work`, `node:toolchains-write`, `curate` |
| GET | `/api/pack-icon` | prefix | `_get_pack_icon` | GET /api/pack-icon?name=PACK or ?app=ID: a pack's or an app's own icon, as the image its file is and nothing else: its type set here and never sniffed, and a policy that runs no script and sandboxes it, so an SVG opened  | `seen` |
| GET | `/api/storebackups` | exact | `_get_storebackups` | GET /api/storebackups: the backups the controller's own machine copies, as recorded. | an administrator's, held by the dispatcher |
| GET | `/api/root-hooks` | exact | `_get_root_hooks` | GET /api/root-hooks: every root startup hook in the state's startup.d, what it says, and whether the start runs it (approved, changed since, new). | `controller-read` |
| GET | `/api/connections` | exact | `_get_connections` | GET /api/connections: Connected services, every credential the install holds for an outside service with who added it, its last use and its expiry, and how many people keep connections of their own, which are theirs alon | `controller-read` |
| GET | `/api/clusters` | exact | `_get_clusters` | GET /api/clusters: the Kubernetes clusters this install may deploy to, each with its facts as last asked; never a credential. | `clusters-read`, `instance:clusters-read`, `instance:clusters`, `node:configure` |
| GET | `/api/deploy` | exact | `_get_deploy` | GET /api/deploy?project=: the space's environments, each with its cluster's name, and the clusters this account may pick one from (Clusters Read; none, with why, otherwise). | `space`, `deploy-read`, `instance:clusters-read`, `clusters-read`, `settings`, `write`, `unlocked`, `deploy` |
| GET | `/api/discord` | exact | `_get_discord` | GET /api/discord?project=: the space's Discord connection (never its token), its last plans, and whether this account changes it: whoever sees the space looks, Space settings Write connects and applies. | `space`, `settings`, `unlocked` |
| GET | `/api/kubernetes` | exact | `_get_kubernetes` | GET /api/kubernetes?project=&env=: what runs in one of the space's environments, read with its own deployer, so nothing outside its namespace: each workload with ready of desired, its version, its pods and where it answe | `space`, `deploy-read` |
| GET | `/api/old-compose` | exact | `_get_old_compose` | GET /api/old-compose: the old system's containers as compose files in a zip, one each, to import from New container (adoptapps.export_zip). | `admin` |
| GET | `/api/v1/nodes` | prefix | `_get_nodes` | GET /api/v1/nodes: the Nodes page's read (nodes.tab_view), scoped to this account. | `admin`, `node`, `space`, `instance:nodes-write`, `instance:runner` |
| GET | `/api/v1/jobs` | prefix | `_get_jobs` | GET /api/v1/jobs: nodes.jobs_view, narrowed to the projects this account may see unless it administers. | `admin`, `space`, `debug`, `node:jobs`, `work` |
| GET | `/api/home` | prefix | `_get_home` | GET /api/home: home.read, the overview's numbers. | `admin`, `space`, `clusters-read`, `instance:clusters-read` |
| GET | `/api/apps` | prefix | `_get_apps` | GET /api/apps: the apps this controller offers and holds (apps.view), for the Library's companion cards and the Settings section. | `open` |
| GET | `/api/notices` | prefix | `_get_notices` | GET /api/notices: notices.listing, this account's own. | `own` |
| GET | `/api/help` | prefix | `_get_help` | GET /api/help: the docs on the Help page (helpdocs.py): the listing, ?doc=NAME one of them, ?q=WORDS a search across them. | `open` |
| GET | `/api/docker` | prefix | `_get_docker` | GET /api/docker: the manager's whole page, containers.manager_view, for the node this account may read; with a space and one of the nodes its containers may be on, that node as the space's, naming every such node. | `space`, `read`, `node:read`, `admin`, `node`, `containers-read` |
| GET | `/api/containers` | prefix | `_get_containers` | GET /api/containers. | `containers-read` |
| GET | `/api/vms` | exact | `_get_vms` | GET /api/vms: the VMs of the projects this account may read them on (a session: its own), the OS catalog and the VM hosts. | `space`, `admin` |
| GET | `/api/node-files` | exact | `_get_node_files` | GET /api/node-files?node=&root=&path=: the node's roots, and with a root the folder's listing; an administrator's. | `admin` |
| GET | `/api/node-files/read` | exact | `_get_node_files_read` | GET /api/node-files/read?node=&root=&path=[&dl=1]: a file's bytes streamed from its node, a download or shown in the page; nothing it holds runs here (a page or a script is sent as text). | `admin` |
| GET | `/api/project-job` | prefix | `_get_project_job` | GET /api/project-job. | `create` |
| GET | `/api/trash` | prefix | `_get_trash` | GET /api/trash: what in the bin this account may manage, each item asked of the space it was in (Space settings Write on any space listed, restored and purged every space's). | `trash`, `trash-any` |
| GET | `/api/claude-now` | prefix | `_get_claude_now` | GET /api/claude-now. | `space` |
| GET | `/api/roadmap` | prefix | `_get_todo` | GET /api/roadmap. | `space` |
| GET | `/api/rules` | prefix | `_get_rules` | GET /api/rules. | `space`, `admin` |
| GET | `/api/global-rules` | prefix | `_get_global_rules` | GET /api/global-rules. | `open` |
| GET | `/api/preamble` | prefix | `_get_preamble` | GET /api/preamble. | `space` |
| GET | `/api/brief` | prefix | `_get_brief` | GET /api/brief: brief.view, the brief waiting in a project's tree and the one kept after it left, for a project this account sees. | `space` |
| GET | `/api/design` | prefix | `_get_design` | GET /api/design: design.view, a project's design language, its pages and the vocabulary they are drawn from, for a project this account sees; a session reads it too, through aerie design. | `space` |
| GET | `/api/wiki-export` | prefix | `_get_wiki_export` | GET /api/wiki-export: the wiki as a zip of its Markdown pages, whether or not the project has a remote. | `space` |
| GET | `/api/wiki` | prefix | `_get_wiki` | GET /api/wiki: the project's wiki (wiki.view), or one page of it with ?page=, for an account that sees the project; a session reads it too, through aerie wiki. | `space` |
| GET | `/api/ci-runs` | prefix | `_get_ci_runs` | GET /api/ci-runs: a project's runs on GitHub's own runners, or with ?run=N (0 the newest finished) that run's jobs and the end of each failed job's log (cilogs), for an account that sees the project; a session reads it t | `space` |
| GET | `/api/ci-watch` | prefix | `_get_ci_watch` | GET /api/ci-watch: what the last look at a project's CI found (ciwatch.read), for an account that sees the project. | `space` |
| GET | `/api/codebase` | prefix | `_get_codebase` | GET /api/codebase. | `space` |
| GET | `/api/pending` | prefix | `_get_pending` | GET /api/pending. | `space` |
| GET | `/api/memory` | prefix | `_get_memory` | GET /api/memory. | `space` |
| GET | `/api/tests` | prefix | `_get_tests` | GET /api/tests. | `space` |
| GET | `/api/bugs` | prefix | `_get_bugs` | GET /api/bugs. | `space` |
| GET | `/api/pubkeys` | prefix | `_get_pubkeys` | GET /api/pubkeys. | `create` |
| POST | `/api/v1/nodes` | prefix | `_nodes` | The Nodes page's verbs. | `instance:runner`, `instance:nodes-write` |
| POST | `/api/v1/jobs` | prefix | `_jobs` | The Jobs page's one verb, and where `aerie run`, `aerie build`, `aerie test` and `aerie emu` land from the controller (nodes.run_job). | `jobs`, `space`, `node:jobs`, `admin`, `work` |
| POST | `/api/v1/bb` | exact | `_bb_relay` | A bb verb from a session on a NODE, run here (roadmap #24). | `bb` |
| POST | `/api/v1/claude-login` | exact | `_claude_login` | A node saying what this account is signed in to Claude, or another coding agent, AS there, or that it is not: never the login itself, which stays on the machine that made it (claudegrant.py says why). | `seen` |
| POST | `/api/v1/hook` | exact | `_hook` | What a session's hooks have to say, from a NODE (roadmap #24): hooks.py says what each kind means. | `seen` |
| POST | `/api/v1/tty-grant` | exact | `_tty_grant` | Whose terminal a node's bb-tty is about to start, answered here. | `admin`, `write`, `terminal`, `vms-write`, `claude`, `terminal-any`, `own` |
| POST | `/api/lock` | prefix | `_lock` | Lock or unlock a project, never a session's. | `space`, `admin` |
| POST | `/api/archive` | prefix | `_archive` | Archive or unarchive a space for the account asking: folded away under Archived on their own Spaces page and nothing else, as their favorites are theirs; anybody signed in, never a session. | `space` |
| POST | `/api/repos` | prefix | `_repos` | Projects and their repositories: create (a project with a name and nothing in it), rename, move (a repository into another project) with move-check (what it changes, asked first: the nodes, containers and VMs it touches  | `admin`, `create`, `space`, `unlocked`, `node:node` |
| POST | `/api/project-pin` | prefix | `_project_pin` | A space made one of this account's favorites or not, kept as its pin: whether Home shows it and the Spaces page's Favorites chip finds it (projects.pin). | a person's own sign-in, never a session's token, held by the dispatcher |
| POST | `/api/project-group` | prefix | `_project_group` | Put a project in one of this account's groups, take it out, or rename a group (projects.set_group, rename_group), or delete one (delete_group): a label for the Projects page, nothing more. | a person's own sign-in, never a session's token, held by the dispatcher; then `space` |
| POST | `/api/apps` | prefix | `_apps` | POST /api/apps: look at the release again now (apps.check_now). | `controller` |
| POST | `/api/pc` | prefix | `_pc` | POST /api/pc: a session's word with a PC lent to its project (pcwork.py, aerie pc): lent (which PCs lend which verbs), run (ask one, under the project's Agents may: Use a lent PC) and result (an ask's answer, held a whil | `seen` |
| POST | `/api/project-color` | prefix | `_project_color` | Give a project one of the colors for this account alone, or none (projects.set_mark): worn by its card, its tabs and its bar. | a person's own sign-in, never a session's token, held by the dispatcher; then `space` |
| POST | `/api/project-auth` | prefix | `_project_auth` | What credential this project's remote uses, and what else it could: projects.auth_answer. | `space`, `git-auth` |
| POST | `/api/project-ftp` | exact | `_project_ftp` | A project's file access over FTP (ftp.py): what it is, for whoever sees the project, and a change, for an account with File access Write on it (users.may's ftp). | `space`, `ftp` |
| POST | `/api/container` | prefix | `_container` | A container from a compose file written here, with no project: containers.tab_verb. | `node:configure`, `docker-write`, `docker-any`, `space` |
| POST | `/api/vms` | exact | `_vms` | POST /api/vms: new, start, stop, restart, remove, snapshot, revert, snapshot-rm. | `admin`, `node:nodes-write`, `vms-write`, `space` |
| POST | `/api/dockerctl` | prefix | `_docker_ctl` | Start, stop, restart or read the log of ONE container on a node. | `read`, `docker-read`, `docker-write`, `node:read`, `admin`, `node`, `space`, `node:nodes-write`, `instance:configure`, `node:configure`, `docker-any` |
| POST | `/api/rename` | prefix | `_rename` | Rename a project: projects.rename. | `space`, `rename`, `git-auth` |
| POST | `/api/trash-restore` | prefix | `_trash_restore` | A repository out of the bin, back into the project it was in, or into the one named (`project`) where that one is gone or another is wanted; one from before projects into a project of its own. | `trash`, `trash-any`, `space` |
| POST | `/api/trash-purge` | prefix | `_trash_purge` | Delete a trashed project for good. | `trash`, `trash-any` |
| POST | `/api/trash` | prefix | `_trash` | Move a project out of the workspace: projects.trash, once project_busy says nothing holds it (the same guards as renaming). | `trash` |
| POST | `/api/session` | prefix | `_session` | Kill a session, or say whether one asked to end has. | `theirs`, `own` |
| POST | `/api/send` | prefix | `_send` | Type a macro's command lines into a shell session of the caller's and press Enter: macros.send. | `theirs`, `own` |
| POST | `/api/say` | prefix | `_say` | Type a message into a CLAUDE session and press Enter. | `space`, `claude` |
| POST | `/api/chat` | prefix | `_chat` | Read a conversation, send into one, or mark one seen: chat.converse. | `own`, `space` |
| POST | `/api/layout` | prefix | `_layout` | Store this account's open tabs: layout.save_tabs. | `own` |
| POST | `/api/bell` | exact | `_bell` | Put a bell note away for this account, bring every one back (bellseen.py), or resume a session an outage held. | `own` |
| POST | `/api/notices` | exact | `_notices` | Keep, delete or clear what the page said to this account: notices.act. | `own` |
| POST | `/api/nginx` | exact | `_nginx` | Deploy, save, certificate, remove, check and update on one node's nginx (nginxproxy.py): writing a compose file and building it on a node, a service's, so Configure on that node, and on every node for the hostname list e | a person's own sign-in, never a session's token, held by the dispatcher; then `node:configure` |
| POST | `/api/scanners` | exact | `_scanners` | Deploy, update, remove, run now, the schedule and a version check (scanners.py): compose and scan jobs on a node, a service's, so Configure on that node, or on every node for what reaches them all (deploy-all, a run with | a person's own sign-in, never a session's token, held by the dispatcher; then `node:configure` |
| POST | `/api/router` | exact | `_router` | POST /api/router: a node's model router (router.py): its keys and endpoints saved, Deploy, Save and Remove as a written container's compose jobs, Ollama's models pulled and removed, a project allowed or not, the models a | a person's own sign-in, never a session's token, held by the dispatcher; then `node:configure` |
| POST | `/api/library` | exact | `_library` | POST /api/library: a card's Configure, Install and Remove for a service (the model router, router.py's own verbs, docker-write as the nginx page), the router's models, spend and Ollama's pulls, and Configure for an added | `node:configure`, `admin`, `work` |
| POST | `/api/images` | exact | `_images` | Check for updates on the Containers page (imagecheck.py): every container's registry images on one node, or all, asked now. | a person's own sign-in, never a session's token, held by the dispatcher; then `docker-write` |
| POST | `/api/storage` | exact | `_storage` | Measure now on the Storage page: a node's disks walked at once (nodes.node_storage_measure). | `admin` |
| POST | `/api/schedules` | exact | `_schedules` | POST /api/schedules: save (add or change, turning one on or off among them), remove, or run now. | `schedules` |
| POST | `/api/extmounts` | exact | `_extmounts` | POST /api/extmounts: set (add or change), remove, or on and off (Eject is off: the agent unmounts within a minute). | an administrator's, held by the dispatcher |
| POST | `/api/nasapps` | exact | `_nasapps` | POST /api/nasapps: one app's compose and environment with its blanks filled (its data folder, its media folder, the user it runs as, the time zone, its port), for the dialog to show before Create makes it as any containe | `docker-write`, `curate` |
| POST | `/api/storebackups` | exact | `_storebackups` | POST /api/storebackups: set (add or change) or remove a backup's record; Run now is the nodes verb storage-backup. | an administrator's, held by the dispatcher |
| POST | `/api/root-hooks` | exact | `_root_hooks` | POST /api/root-hooks {action: approve, name, sha} or {action: revoke, name}: a root hook approved as it was shown, or its approval taken back, through the root-only helper. | `controller` |
| POST | `/api/connections` | exact | `_connections` | POST /api/connections {action: forget, kind, ref}: a credential forgotten at once (a leak, a person gone), where its kind keeps it. | `admin` |
| POST | `/api/clusters` | exact | `_clusters` | POST /api/clusters {action: add, name, kubeconfig} \\| {action: from-k3s, node, name} \\| {action: test\\|rename\\|forget, id}: a cluster added once its API answers (from a kubeconfig, or the k3s a node runs, which is Configure  | `instance:clusters`, `node:configure` |
| POST | `/api/deploy` | exact | `_deploy` | POST /api/deploy {project, action: save, env, was} \\| {project, action: remove, name}: an environment added or changed once its namespace is ready on its cluster, or taken off the space's list (its namespace stays on the  | `space`, `unlocked`, `deploy`, `write`, `settings`, `instance:clusters-read` |
| POST | `/api/kubernetes` | exact | `_kubernetes` | POST /api/kubernetes {project, env, action: restart\\|scale, kind, name, replicas}: a workload in one of the space's environments restarted or scaled, with its own deployer. | `space`, `unlocked`, `deploy` |
| POST | `/api/k8s` | exact | `_k8s` | POST /api/k8s {project, action: status\\|logs\\|deploy\\|rollback, env, ref, pod, container, tail, why}: aerie k8s, from a session as from a person, relayed by the controller, which holds every credential; a session never hold | `deploy-read`, `space`, `unlocked`, `deploy`, `dial:kube` |
| POST | `/api/discord` | exact | `_discord` | POST /api/discord {project, action: connect\\|forget\\|pull\\|plan\\|apply, token, guild, text, write, why}. | `space`, `unlocked`, `settings`, `write`, `dial:discord` |
| POST | `/api/pin` | prefix | `_pin` | Pin or unpin a command: macros.pin. | `command-pin` |
| POST | `/api/reset` | exact | `_reset` | POST /api/reset: start over at onboarding (settings.reset), and the dashboard re-executes itself so the next page is Create the owner. | `controller` |
| POST | `/api/move` | exact | `_move` | POST /api/move: prepare (the move armed, the token answered once, a bundle packed), forget (withdrawn), moved (this controller marked moved to the new one, read-only from here on), ask (the new address asked now whether  | the owner's alone, held by the dispatcher |
| POST | `/api/node-files` | exact | `_node_files` | POST /api/node-files: mkdir, rename or delete (into the root's trash) on a node's root; an administrator's, audited. | `admin` |
| POST | `/api/backup` | exact | `_backup` | POST /api/backup {action: now}: a copy written now, the owner's. | the owner's alone, held by the dispatcher |
| POST | `/api/create` | prefix | `_create` | New project: a fresh local repo, a clone or a link, and what the dialog chose besides (projects.create_from_dialog). | `create`, `space`, `admin`, `unlocked`, `node` |
| POST | `/api/profile` | prefix | `_profile` | The signed-in account's own settings (the Profile page): read on GET, saved on POST, by profiletab.py. | `own`, `admin`, `node`, `space` |
| POST | `/api/git` | prefix | `_git_act` | The Git view's actions: fixed git commands on the project's tree on the controller, under the acting account's author and the project's own credentials (gitview.verb). | `space`, `unlocked`, `admin` |
| POST | `/api/forge-access` | exact | `_forge_access_post` | POST /api/forge-access {project, action: measure}: the token measured again, for the Permissions section's Measure; an account's on a project it may change. | a person's own sign-in, never a session's token, held by the dispatcher; then `space`, `unlocked` |
| POST | `/api/forge` | exact | `_forge` | POST /api/forge {project, verb, args}: one aerie forge verb, run here with the project's own token under what the token allows and the project's override, for a session on its own project or an account that may change it. | `work`, `space`, `unlocked` |
| POST | `/api/project-sessions` | prefix | `_project_sessions` | POST /api/project-sessions {project, action: "end", session, node}: an administrator ending one of them (projsessions.py). | `settings`, `space` |
| POST | `/api/unlink` | prefix | `_unlink` | Take the remote off a project, with the credential and the push grant that came with it. | `git-auth` |
| POST | `/api/link` | prefix | `_link` | Link an existing local repo to an empty repo on a host. | `git-auth` |
| POST | `/api/project-job` | prefix | `_project_job` | Stop the running project job, or clear the last one's outcome. | `create` |
| POST | `/api/roadmap` | prefix | `_roadmap` | Add, send, edit or drop one item on a project's list: roadmap.verb says what each action means. | `space`, `unlocked`, `settings` |
| POST | `/api/roles` | prefix | `_roles` | POST /api/roles: assign (an account's Everywhere roles and its roles on each project, as far as the asker may), set (make or change a role: its scope, its areas and note) or remove one; owner and admin are built in and r | `admin` |
| POST | `/api/users` | prefix | `_users` | The Users page's verbs. | `own`, `admin`, `space` |
| POST | `/api/toolchains` | prefix | `_toolchains` | Queue installs or removals of the toolchains the Tools card offers: an administrator's, and toolchains.verb says what each action does with which names. | `node:toolchains-write` |
| POST | `/api/agents` | exact | `_agents` | POST /api/agents: install (or update), remove or check one coding agent on one node (agentcode.verb), the one way an agent is managed: whoever may install toolchains there. | `node:toolchains-write` |
| POST | `/api/toolpacks` | exact | `_toolpacks` | POST /api/toolpacks: look at a tool pack by its repository's address, or at one made here from a pasted manifest or an uploaded archive (/api/upload-archive's id); add it as it was shown; read a pack made here's manifest | `toolchains-write`, `curate`, `admin` |
| POST | `/api/emulator` | prefix | `_emulator` | Add system images to a node, or remove one: a job there, against its toolchain store. | `toolchains-write`, `node:toolchains-write`, `admin`, `space` |
| POST | `/api/logs` | prefix | `_logs` | The log policy, and the two things that can be done to the pile: logs.verb. | `controller` |
| POST | `/api/idle` | prefix | `_idle` | The idle rule for every agent's sessions (idle.py): minutes, 0 for never. | `controller` |
| POST | `/api/paths` | prefix | `_paths` | Where the controller keeps one kind of what grows (paths.py), and what is there moved across. | a person's own sign-in, never a session's token, held by the dispatcher; then `controller` |
| POST | `/api/snapshots` | prefix | `_snapshots` | POST /api/snapshots: take one now, or restore the whole tree as of a day or one file of it (snapshots.restore, which snapshots the tree first so it can be undone). | a person's own sign-in, never a session's token, held by the dispatcher; then `settings`, `space` |
| POST | `/api/transcripts` | exact | `_transcripts` | POST /api/transcripts {project, id, action}: one of the signed-in person's own conversations deleted, or made visible to every session on the project (share) or private again (unshare): a person's, from the notebook's Se | `own`, `space` |
| POST | `/api/settings` | prefix | `_settings_post` | POST /api/settings. | `controller`, `debug`, `owner` |
| POST | `/api/checks` | exact | `_checks_post` | POST /api/checks {kind}: Check for updates, for one of the update checks under Controller settings (checks.py). | `controller` |
| POST | `/api/catalog-mirror` | exact | `_catalog_mirror_post` | POST /api/catalog-mirror {action: import, archive} or {action: forget}: the vetted catalog's mirror under Controller settings, its archive taken through /api/upload-archive. | `controller` |
| POST | `/api/rules` | prefix | `_rules` | The operator's house rules for one project: the whole list, saved (rules.verb). | `space`, `unlocked`, `rules` |
| POST | `/api/global-rules` | prefix | `_global_rules` | The rules that apply to EVERY project: rules.global_verb. | `controller` |
| POST | `/api/pending` | prefix | `_pending` | Approve or deny what a session has waiting (roadmap #27): pending.verb. | `space`, `unlocked`, `pending` |
| POST | `/api/memory` | prefix | `_memory` | Edit, create or delete one of this project's memories, rewrite their index, or read the history: memory.verb, behind the gates here. | `space`, `unlocked` |
| POST | `/api/prefs` | prefix | `_prefs_post` | POST /api/prefs: a project's settings dialog, saved by prefs.dialog_save behind the gates here. | a person's own sign-in, never a session's token, held by the dispatcher; then `space`, `unlocked`, `node:node`, `nodes-write`, `debug`, `docker-write`, `curate`, `vms-write`, `deploy`, `settings` |
| POST | `/api/brief` | prefix | `_brief` | POST /api/brief: the first Claude press's Build it and Start without it, and a session's take as it starts: brief.verb, behind the gates here. | `space`, `unlocked` |
| POST | `/api/design` | prefix | `_design` | POST /api/design: a Design section's Save of the language and the pages, and the file written into the tree: design.verb, for an account that works on the project. | `space`, `unlocked` |
| POST | `/api/wiki` | exact | `_wiki` | POST /api/wiki: a page saved, removed or renamed, and the wiki pushed to or pulled from the forge's (wiki.verb), for an account that works on the project. | `space`, `unlocked` |
| POST | `/api/ci-watch` | exact | `_ci_watch` | POST /api/ci-watch: look at a project's CI now (ciwatch.look), for an account that sees the project; the answer is what it found. | `space` |
| POST | `/api/devapp` | prefix | `_devapp` | The dev-instance controls: the Containers page's buttons, and `aerie devapp` from a session. | `space`, `admin`, `read`, `docker-write`, `node:configure`, `docker-read`, `work`, `docker-any`, `unlocked`, `node` |
| POST | `/api/changelog` | prefix | `_changelog` | Write back the Unreleased section a person rearranged: changelog.editor_verb. | a person's own sign-in, never a session's token, held by the dispatcher; then `space`, `unlocked` |
| POST | `/api/version` | prefix | `_version` | Move a project's version, or change who is allowed to: version.verb, behind the gates here. | `space`, `version`, `dial:release` |
| POST | `/api/tls` | prefix | `_tls` | POST /api/tls {action: issue}: a Let's Encrypt certificate for the Connection section's hostname asked for now, by DNS-01 through the Cloudflare API token (nginxproxy's hooks), for an account that changes the controller' | `controller` |
| POST | `/api/signing` | exact | `_signing` | A project's Android signing keys (signing.verb). | `dial:sign`, `dial:keys`, `space`, `unlocked`, `signing` |
| POST | `/api/keys` | exact | `_keys` | POST /api/keys: the install key and everything kept under it for an administrator (status, show, saved, change), and the account's own key for its sign-ins on the nodes (mine, change-mine). | `controller` |
| POST | `/api/members` | exact | `_members` | A project's owner, whether it is invite only, its people and its invitations, and an invitee's answer (membership.verb). | a person's own sign-in, never a session's token, held by the dispatcher; then `space` |
| POST | `/api/signing-backup` | exact | `_post_signing_backup` | POST /api/signing-backup: the same, with the project's backup password in the body, never in a URL that lands in a log. | `space`, `signing` |
| POST | `/api/artifacts` | prefix | `_artifacts` | Push an .xpi from a project's dist/ to the paired phone, install an .apk there, or stop a push: phone.artifact_verb, behind the gates here. | `space`, `unlocked` |
| POST | `/api/nodelog` | prefix | `_nodelog` | A machine's own log, for a session that has been granted it. | `space`, `debug` |
| POST | `/api/diag` | exact | `_diag` | The controller's diagnostics (diag.py). | `debug` |
| POST | `/api/reports` | exact | `_reports` | Problems with AerieOS itself, reported by any project's session (reports.py, aerie report). | `space`, `controller`, `controller-read`, `debug` |
| POST | `/api/v1/files` | exact | `_files` | A project's files for a person's own editor (files.py): the account this request proved, a project it sees, and the file access its settings give it through the editor's door, asked on this request (ftp.access_for), so t | a person's own sign-in, never a session's token, held by the dispatcher; then `space` |
| POST | `/api/phone` | prefix | `_phone` | Pair, connect, and push an extension, and the asking: a session's ask for adb, root or a container, and a person's answer. | `admin`, `node`, `space` |
| POST | `/api/findings` | prefix | `_findings_log` | The Analysis view's log. | `space` |
| POST | `/api/tests` | prefix | `_tests` | The hand-written half of the registry: testreg.verb. | `space`, `unlocked` |
| POST | `/api/presence` | prefix | `_presence` | This browser is in a project's notebook, and who else is (roadmap #26): presence.heartbeat, for a signed-in account on a project it sees. | `space` |
| POST | `/api/bugs` | prefix | `_bugs` | Report, edit, or close one bug: bugs.verb, behind the gates here. | `space`, `unlocked` |
| POST | `/api/custom` | prefix | `_custom` | Save or delete one of the operator's own command lists: macros.custom_edit. | `command-pin` |
| POST | `/api/doctor` | prefix | `_doctor` | Re-run aerie doctor now and answer with the fresh verdict. | `controller` |
| POST | `/api/signout` | prefix | `_signout` | Sign this account out of a coding agent on one node (signin.sign_out): the login is that machine's, so that machine lets go of it. | `node:read` |
| POST | `/api/login-code` | prefix | `_login_code` | Hand the code from the browser to the sign-in flow: signin.take_code, for the person whose flow it is. | a person's own sign-in, never a session's token, held by the dispatcher |
| POST | `/api/signin` | prefix | `_signin` | Start a sign-in on one node, or stop the one that is running: signin.verb. | `node:read` |
