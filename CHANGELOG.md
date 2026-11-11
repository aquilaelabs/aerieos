# Changelog

## 0.9.0-dev.5221: 2026-11-11

### Changed

- How each coding agent is installed is now a recipe in its catalog pack, so when a vendor changes its installer (as OpenCode's did) the fix reaches every install through the catalog with no new release of AerieOS; an update's first line says when the catalog's recipe is the one used. Takes effect on a node once its agent has updated (24f3a37)

### Fixed

- Updating OpenCode works again: it failed with 'installed, but no opencode to run' since OpenCode's installer moved where it puts the program. Takes effect once a node's agent has updated (fb6049b)
- An agent's update, sign-in and sign-out jobs say what they are on the Jobs page and in aerie jobs, where OpenCode's (and in aerie jobs every agent's) read 'exec' (fb6049b)

## 0.9.0-dev.5214: 2026-11-11

### Changed

- A coding agent no longer second-guesses the aerie commands AerieOS itself decides: a release, a push or a roadmap change that the space's Agents may allows is not refused or asked about again by the agent's own permission check, which could differ from one day to the next. Claude Code, Codex, Copilot and Grok are each told in their own way, and a pack's agent can say how in its manifest (agent.allow). A session picks this up when it starts, so restart running sessions after the update (d0297ee)

## 0.9.0-dev.5211: 2026-11-11

### Added

- aerie diag has a tunnel section: whether the home tunnel is running and registered, whether its name reaches this controller, and its last lines; a secret that is set says so in the settings section, where it printed as empty (03d106d)

### Changed

- Only one controller can run on a configuration folder at a time: a second one started on the same /config stops with the reason, rather than writing over the first (e303494)
- A backup and a move's bundle copy the configuration at one moment, rather than file by file while it is being written; the copies kept before an upgrade no longer carry the install key (e303494)
- With Run its container on auto, a session's build still runs at once, unless its compose file asks for more than its own folder (the host's files, privileges, the Docker socket): then you are asked once, with the list, and your Allow covers that file from then on (0c4735d)
- A node locked out because a token it had replaced came back now says it may be a machine restored from a snapshot or a backup, and that Enroll script on its row brings it back (ac7e5dc)
- A node keeps its files in /etc/aerieos and /var/lib/aerieos and runs the service aerieos-agent, under AerieOS's own name. A node from before changes over when its Enroll script is run on it: the folders are renamed with the old names left as links, and builderbot-agent still works as a command. Until then it runs as it did, and both names answer (c850175)
- A page already loaded once in a browser opens without asking the controller about each of its scripts again: a repeat load was 82 requests and is one (8add20a)
- An open page no longer reads the whole status every two seconds while a coding session is working: the turning mark in a working session's title is no longer taken for a change (b53ac75)
- A coding session's tool calls no longer wait about two seconds in every twenty while their gate asked the controller for its whole status, and every aerie command starts about 50 ms sooner (873e79e)
- A command that acts on a space's tree right after an edit there (aerie git push after a commit, aerie version) no longer waits up to half a minute for the node's own change to come back to it. Takes effect on a node once its agent has updated (fe36377)
- The Jobs page and Home read a short form of each job rather than the script or configuration it carried: a hundred jobs were over a megabyte, read again whenever any job moved (89a91dd)

### Removed

- The ISO is no longer an installer: its boot menu offers no Install, and a new machine is set up from the USB edition (the stick's image also serves as a VM's disk). The ISO stays on each release as the file a running AerieOS machine updates from. An installer on the machine's own screen is being built. The ISOs up to 0.9.0-dev.5173 could not install on a blank machine in any case (f725a42)

### Fixed

- Installs and space clones that were queued behind another job when the controller restarted are picked up again, or named on the Spaces page as not started, rather than dropped without a word (e303494)
- aerie changelog missing, and a release's own check for bugs owed a Fixed line, no longer run past three minutes and end with nothing said on a space with hundreds of fixed bugs (879e7c2)
- The Enroll script's last lines say the machine's address again, where they printed 'my_ip: command not found' (874b4d1)
- Home's updates due counts updates only: a failing disk, a hot one or a restart owed is no longer one (874b4d1)

### Security

- A node is handed a session's credential only for a space that works on that node and a person who may work on that space. Before, a node that merely named another space's session was handed its credential, so one node taken over reached every space (e9502c6)
- An accounts file that cannot be read no longer opens the make-the-first-account page to whoever reaches the dashboard: nobody signs in until it is mended or put back from a backup, and nothing is written over it. State files are now synced to disk as they are written, so a power cut does not leave one cut short (e303494)
- A coding agent's session can no longer change its person's Profile: where their notifications go, their browser sign-ins, their second factor (e9502c6)
- A CI runner registered to a public repository says on its row that a pull request from anybody can run on that node, and which setting on the git host to change (61a3651)
- A container's compose file is checked for more ways of reaching the host before it is built: the host's other namespaces, another container's volumes, a volume bound to a host folder under another name, a build that uses the host's network or ssh agent, and a folder that is a link to the system (35f094d)
- A node can pin AerieOS's release key and then takes only agent updates the release signed, whatever its controller sends. Nothing changes until a release names the key; a node's row says which it is under Updates (ac7e5dc)

## 0.9.0-dev.5173: 2026-11-10

### Changed

- A job pressed while another is running is queued behind it rather than refused, on the Library, the Installed page, a container's row, a node's system changes, Reboot and Shut down, and a new space's clone; the card or row says it is queued, and pressing the same thing again does not queue it twice. What still cannot happen during a job, such as renaming a container or disabling a node with sessions on it, is ghosted with the reason on its row (3d75e07)
- Two people can sign in to a coding agent at the same time, and a sign-in left open no longer holds up a build on that node, nor waits behind one (b757ee1)
- Restart on a session, the tests panel's output, and a container's shell right after an update now wait until they can go through, rather than asking you to press again in a moment (b757ee1)

### Fixed

- A node that reached a move's new home and then came back to the old controller is taken back by itself, rather than refused every five minutes until it is enrolled again (5640b84)
- The bell and the doctor's buttons no longer show a loading ring under their icon when pressed, and any other icon-only button that is still waiting shows its ring in place of the icon (ae30aba)
- A certificate through Cloudflare's DNS waits until the record can be seen before asking Let's Encrypt, and says so when it never appears, rather than waiting a fixed time and failing with Let's Encrypt's words (b757ee1)
- A node enrolled at the public hostname of Reach from outside follows a move to a controller on the local network: it is told that hostname rather than the new home's local address, and Prepare to move no longer warns about it (6dd5554)
- A machine's first boot no longer fails to make the machine its own node when its dashboard answers the agent's download with an error in its first moments: the download is tried again (101fb59)
- The bell no longer loses its whole list while a node is being turned away or has shown a retired token (7e481f5)
- A node no longer restarts its CI runner in the middle of a job when the runner has updated itself, which canceled the run (d047877)
- The Analysis page shows its findings once they arrive, rather than loading until something else on the page moved, and its filters redraw it (273b47b)
- On a phone the Files page's filter shares a line with New folder and Upload rather than spanning the page above them (ea6e923)
- After a controller update its nodes are back within seconds, rather than showing quiet for a minute or two while their agents waited to ask again (ed35650)

## 0.9.0-dev.5146: 2026-11-10

### Added

- Prepare to move names any node that dials in from outside the local network when the new home's address is a local one it cannot reach (133a1ba)
- New container's Compose pane has Import a compose file, which fills it from a file on your computer and names the container after the file (16a8572)

### Changed

- The move token given on the first page is not asked for again when the move lands, and where the old controller ran on the same machine the landing asks for the bundle alone (133a1ba)
- The old system's containers and VMs are brought back from the machine's Containers page, and are found where they usually are when the stick was made without the old system's backup (133a1ba)
- New container offers a ready app only when the Library's New container opened it on that app; apps are picked on the Library (133a1ba)
- The old system's containers come back as compose files: Download compose files saves a zip of them, each with the image, settings, ports and paths it ran with and what it will not do as written said at its top, to import with New container; Make the network makes a network the old Docker kept for its own containers as a bridge of its own (16a8572)

### Removed

- Make and start for the old system's containers. Upgrading: once this machine's agent is updated, press Read again on its Containers page, under Containers and VMs from the old system, then download their compose files and import each one (16a8572)

### Fixed

- Moving here's pool and folder picks and its After it lands step no longer squeeze long sentences into a grid, and each pick's button sits beside its field (133a1ba)
- A move from a container install onto a machine no longer risks retiring one of its nodes and moving that node's spaces onto the new machine (133a1ba)
- The old system's VMs on this machine's page say each defined VM's name once with its buttons beside it, Define the VMs sits under the VMs it defines rather than under another's buttons, and whether one starts with the machine is a tick (f4e0613)

## 0.9.0-dev.5138: 2026-11-09

### Added

- A controller's own machine now runs containers: the Containers page, the Library's apps and Make and start under Containers and VMs from the old system all work there. A session's build on that machine waits for a person, and a container there has no Shell (0da04aa)

### Changed

- Moving a controller here asks only for its move token on the first page, not for an account the move then replaces (4cc9d2c)
- A controller's own machine is now a node like any other: it is on the Nodes page and in the picker of the Library, Installed, the Emulator, the Phone and the CI runner, so toolchains and coding agents install on it; its name, disks, console password, restart and shut down moved to its row on the Nodes page, and the Controller group's page, now This controller, keeps its release, updates and older versions (4cc9d2c)
- The first-run page has Generate console login and Shut down at its top, in place of a step asking for a console password (4cc9d2c)

### Fixed

- On a stick the data partition now grows to fill the stick at boot, as it was meant to; it had stayed at 2 GB on a stick of any size, which filled up and left no room for an update (c783e0f)
- An OS update no longer loses the machine's ZFS pools at its first boot, which took the spaces, the sign-ins and the secrets with them (e914d08)

## 0.9.0-dev.5128: 2026-11-08

### Added

- While a machine is first set up, its screen or a KVM logs in as admin with no password, even if the dashboard or the agent has stopped, and the first-run page offers a password to keep a way in after setup ends (cf50004)

## 0.9.0-dev.5123: 2026-11-08

### Added

- The bell says when an adopted array is writable with no parity yet, with This machine on the row, and when a stick's own partition is running out of room; This machine shows that partition's room (80b84fe)

### Changed

- Taking the array over no longer holds the machine for the hours the first parity sync takes: the job ends once the parity disk is ready and the sync runs in the background, as Sync now and Scrub do too, its progress on This machine and the Storage page; the first-run walk no longer offers the takeover, which comes after it from This machine (80b84fe)
- A bar shows how far a sync, scrub or parity check is, and how much of a bundle has been sent when a move lands; a first-run step held behind a job says the job's step and how long it has run (80b84fe)

### Fixed

- On a stick, SnapRAID's content file (a catalogue of every block of the array, gigabytes for a large one, rewritten whole as a sync goes) no longer goes on the stick's own partition, which it filled during a first sync, taking the controller down with it; it lives on the data disks (80b84fe)

## 0.9.0-dev.5119: 2026-11-08

### Changed

- A new Unraid or compose install keeps its state in /mnt/user/appdata/Aerie-Workshop, and the template's hostname is aerie-workshop; an install already running keeps its own folders. Upgrading: a compose install that never set APPDATA_PATH must set APPDATA_PATH=/mnt/user/appdata/BuilderBot in its .env before it updates, or it starts on an empty folder (9c94749)
- Every button that starts something shows it was taken: one still working after a moment wears a spinner, and Download the bundle says Packing until the file is ready, a failure said on the page rather than as a page of its own (56f8685)
- The first-run walk takes its steps in order: a step that needs the one before waits, saying which, and while the machine runs a job (adopting the disks, moving to a pool) the steps that would start another wait for it, the page saying what runs, where a press used to fail with 'one at a time' (56f8685)

### Deprecated

- BUILDERBOT_TAG and BUILDERBOT_PULL in a compose .env are now AERIE_TAG and AERIE_PULL; the old names are read until 0.10 (9c94749)

## 0.9.0-dev.5114: 2026-11-08

### Added

- A stick offered a pool that holds another AerieOS install's folder now offers to set that folder aside (renamed to aerieos-system.old, then .old-2 and on, untouched) and use the pool, where it only refused; the picker says so before you press (ee21eac)
- A Files page under Machines: browse, preview, upload, download, rename, move and delete files on a node's pools, array, shares and mounted disks, for administrators, every change in the audit log; a delete goes to that disk's .aerieos-trash folder. A node's agent serves it once updated (8458483)

### Fixed

- Downloading a move's bundle needs only the bundle's own size free on the old controller's disk, where it needed up to three times that and could end in a bare "No space left on device"; a full disk is now said with what to do (95cc75d)
- A stick that goes back to the configuration from before an update keeps its logs in memory as before, instead of writing them to the stick (510d31c)

## 0.9.0-dev.5096: 2026-11-07

### Changed

- On a stick, the secrets folder with the install key moves to the system pool along with docker, the VMs, the toolchains and the spaces, so the stick alone opens nothing the controller sealed; a stick whose pool was picked before carries them over at its next boot (ee7e020, 5fb699a)
- Pages open faster: the status read every page waits on takes about a third of the time it did (the newest conversations and the roles are no longer read again on every poll), Controller settings measures what a move would carry side by side, the Library reads once when it opens, and a pointer resting on Containers or Build reads ahead what that page shows first (5897793, 31e5ea6, 2b03cbc, dee915b)
- Profile waits with every section it always has, and a person's roles on the Users page wait in their places, so nothing grows in after the page has drawn (e3d8adb)
- On a phone, a space's Docker view keeps its view toggle and buttons on one line and its status under them, where the status was squeezed between them (bf59b20, e610c71)

### Fixed

- A controller whose secrets folder is root's alone (every install on a machine of its own, a stick included, and a container whose secrets folder is closed as the install guide says) could not reach the install key it made there, so it sealed nothing and a move carrying the old controller's key stopped at landing with permission denied; the boot now says so if the controller's account cannot read its key (ee7e020, f957998)
- A move landing on a stick keeps the accounts the stick made from the old system's share users, with their SMB passwords, so shares already served to them keep their people; a name the moved controller already has is its account, and the landing says so (275cfe6)
- A landing whose spaces cannot be copied says so with what it set aside, instead of stopping with those lines lost; secrets the new home cannot write no longer stop a landing, which lands the rest and says to copy them by hand (2b4bef3)
- A bundle's secrets piece says when the secrets folder is root's alone and the bundle carries none of it, instead of packing it as empty without a word (1114a0b)
- A session's commit after a command the controller ran for it (a release's changelog section, a pull) no longer carries the old files back over what the controller committed (e9c1fef)
- A release keeps a changelog line's commit when the line was committed on its own right after its change (4108ed5)
- aerie settings names the hosting-only nodes ticked under Also works on (2daf041)
- The dock's tab on show, pressed, puts the dock down on the first press, also after a click in the page above (42d145c)
- An OS update takes the configuration's copy before anything else and stops when it cannot; a slot whose write was cut short reads as empty rather than as its old version, which the next update would have kept in place of the good copy; and the older slot picked by hand from the boot menu takes back its own configuration when a newer build wrote the one there, where its controller sat refusing to start (7c9c50c)
- A new OS image's boot menu goes on only once the health check marks its slot good, so a release with a broken menu cannot take away the way back to the slot before (6659f2a)
- Visiting an older version is refused while an update is on trial, which the visit would have spent a boot of or ended (84e5f03)

### Security

- A move or backup bundle's outer details (its kind, origin and versions) are held to its sealed body, and a bundle changed after it was made is refused before anything changes; bundles made before still land (679ccaf)
- The audit's digest of a change's parameters is keyed by the install's own key, so a short secret in a request cannot be guessed from the audit (808926d)
- A session's aerie nodes reads its space's own nodes, as the Nodes page narrows them; an owner's or an administrator's seat reads every node (6c75b33)

### Upgrading

- A controller that could not reach its install key (under Fixed) seals what it kept open at its first start on this release; nothing is asked of you (ee7e020)

## 0.9.0-dev.5065: 2026-11-07

### Changed

- A row on the Installed page that says an update is available has its Update button there, as the Library's card does (760de66)

### Fixed

- The mover moves nothing to or from a pool or the data disks that is not mounted, never overwrites a copy already on the other side, never follows a linked share folder and leaves a file a program holds open; a sync, scrub or check is refused while any disk of the array is not mounted, and the merged share tree is mounted only over disks that are (3c90807)
- A move lands one at a time, and a landing cut midway lands again from Controller settings; the database in a bundle is a whole copy however busy the controller is while it is made (2a693f3)
- A node whose controller came back from an older backup is taken back by any of its last month's credentials, not only its newest 200 (2a693f3)
- aerie version release run from a session no longer stops after three minutes with nothing printed, leaving the release half made (1653df6)

### Security

- Taking an adopted array over finds the old parity disk by its serial before giving it a filesystem: a reboot or a stick plugged in that moved the disks' names could have put another disk under it, and the takeover now asks for the confirmation on the machine itself and checks every data disk is mounted first (3c90807)
- Let it go no longer runs a spaces folder's give-back script from inside the folder as root, and a system pool is never a folder in memory (047ccd5)
- A move or backup bundle carries the install key only when its box is ticked, also on an install that keeps the key beside its configuration (2a693f3)
- A change made with the browser's sign-in is taken only from the dashboard's own page, never from another app on the same domain; wrong passwords are counted at every way in (the sign-in page, the command line, the app, file access): one address is held after 100 in a quarter of an hour (2a693f3)

### Upgrading

- A disk array adopted before this release is released and adopted again (Read only) before Take the array over, which now finds its parity disk by the serial the adoption keeps (3c90807)

## 0.9.0-dev.5053: 2026-11-07

### Fixed

- A controller moves onto a new AerieOS stick whose old system had share users; the landing was refused as the stick having other accounts (3a1d38e)

## 0.9.0-dev.5049: 2026-11-06

### Changed

- Each of a space's settings is changed in one place: what every repository shares (people, what sessions reach, toolchains, coding agents, its nodes) on the space's own settings, shown read-only on a repository's with a button to them; a repository may still keep its containers off some of the space's hosting nodes, pick its own test node, and set any Agents may dial apart, and the space's settings name each repository that does (64b2b7d)
- Fewer controls: where a repository's tests run is one choice under Build and test; the daily snapshot switch is gone (0 days kept takes none); terminal colors are Profile's for every space; Move the version is set on the Permissions view; Its VMs may hold shows only where VMs may be made (64b2b7d)
- On a phone a space's Manage agent, Shell and its menu sit on the name's row, and a notebook's view tabs stay pinned at the top as its page scrolls (f862844)
- Good, warning and error colors are the same in every theme, one shade for dark themes and one for light; the warning is a warmer amber (f862844)

### Fixed

- A space's session can rebuild a container one of its repositories has on a hosting node the space or the repository uses, however it got there; one made there before the repository joined the space was still refused (8bb4415)

### Upgrading

- Terminal colors set for one space are dropped: set them on Profile, under Your terminal, for every space. A repository whose daily snapshots were switched off keeps 0 days of them. (2aca16a)

## 0.9.0-dev.5037: 2026-11-06

### Added

- A controller restored from a backup takes back every node still there by itself, even one whose credential changed since the copy was made; a node that is gone simply never comes back (3a99086)
- Backup copies can also go to a disk or share under Other disks and shares, so a copy of the controller is off the machine; the section says plainly that it holds the controller, not the files on your pools (3a99086)

### Fixed

- A space's session can rebuild a container that one of the space's repositories sent to a hosting node; it was refused as left behind on another node (f24c5b1)

## 0.9.0-dev.5030: 2026-11-06

### Added

- A VM can have a TPM 2.0, ticked in New VM or its Hardware dialog, so Windows 11 installs; VM host now installs swtpm for it (fb8b5c7)
- Check parity on the Storage page's array reads every block back against the parity, says how far it has got, and corrects what differs only when you ask; its result lands on the bell, and it can run monthly (b4a2f62)
- A VM AerieOS did not make, such as one made in virt-manager, can be cloned into a space from the VMs page: its disks are copied and the original is left as it was (b88ad6f)
- A ZFS pool made on another machine, such as a TrueNAS box, can be imported from the Storage page as it is, and comes back after every restart until it is exported (d9db7ae)
- Download a backup under Move this controller keeps a copy of the controller, its spaces and their repositories under a token of its own, without arming a move: record the token, since it is shown once; the file and token never expire, and land on a new controller's first setup the way a move does (0ab205e)

### Changed

- A share's name and its folder may have spaces between words, such as TV Shows (8f2aa14)
- Moving a controller in is part of a new controller's first setup only: once its setup is finished, Move a controller here is gone from Controller settings and a landing is refused, so a controller in use is never replaced or merged into (0b40d0d)
- A reinstall never takes the data an earlier AerieOS left on a pool (its containers, VMs, spaces and the accounts' sign-ins): naming that pool as the system pool is refused, and a move token from the old controller is the way to bring it over (424c90f)

### Fixed

- Turning the IOMMU on under This machine's Features, or in the installer, works on an AerieOS machine; it stopped saying no bootloader was found (b656a35)
- An array made after another was destroyed syncs; its first sync stopped saying too many disks had changed (e5deabf)
- A node whose agent is turned away because the controller has no record of its credential, as after restoring the controller's settings from a backup older than the node's last check-in, says so on the Nodes page with Enroll again as the way back, where it said only that the agent had not dialed in lately (837ac48)
- aerie tidy ends the test servers a test run left behind when it was stopped early; it said nothing was running and left them for hours (2335ff2)
- A session can search for the word exited in its files again; only waiting on a background run's log in a loop is refused (3a6e6e2)
- Landing a move on a controller that already has a space of the same name keeps that space's folder whole in the workspace's trash and says so; the two repositories' files were mixed in one folder (a3a2949)

## 0.9.0-dev.4980: 2026-11-06

### Added

- Pre-releases of any name and a changelog that knows what each release carried: aerie version release --pre NAME cuts vX.Y.Z-NAME.N beside --dev, each pre-release takes Unreleased as its own changelog section and its notes, a stable release gathers every pre-release since the last stable into its own section, the fixes to what only they had left out, and a release is refused while a bug the last release carried has no Fixed line (aerie changelog missing, add --bug N, skip N) (3df9934)
- A pre-release of any name gets its page on the forge, marked a pre-release, where the space's CI does not make one, and AerieOS's dev channel and the stick maker take an rc or beta as they take a dev build; every pre-release is numbered by its commit, as a dev build is (c01abbf)
- On AerieOS the wired network card is a port of a bridge, br0, which keeps the card's MAC and the machine's address, so a VM on the LAN reaches its own host: a node VM on the controller's machine dials in, and one a move brings back finds its controller; the bridge is made once at a boot and put back if it gets no address, and VMs on the card move to it (238dbfd)
- A VM's Hardware dialog picks its network source (its space's network, the LAN, a bridge on the host or a libvirt network), its network model and its MAC, with Regenerate (7940597)

### Changed

- A move's bundle downloads as aerieos-move-DATE.aeriemove; a .bbmove from an older install still lands (ccf6e14)

### Fixed

- aerie changelog add named the current commit as well on a line that already named its own (0b19d80)
- A session's aerie output past 200 KB came back with its start cut off and no word of it, so a bug list printed as JSON on a node did not parse (61b68be)
- Editing a draft release's notes, or attaching its signed APK, could take its tag off on GitHub, so Publish and the next edit could not find it (028a05c)
- Restarting a session right after the controller was updated could end the new session as its terminal opened (2a4fc8e)

### Upgrading

- On AerieOS, the first boot after this update puts the wired network card in a bridge, br0, with the card's MAC: an address the router reserves for that card stays the machine's. Where the machine's address is set on the Network page, it moves to br0 by itself (238dbfd)

## 0.9.0-dev.4951: 2026-11-06

### Changed

- Projects are called spaces, since a space can hold code or only containers and VMs: every page, dialog and message says space, the Spaces page is at #/spaces, and a link to #/projects still opens it (da5e87e, e6e48f0)

### Fixed

- A dashboard page no longer reloads by itself when the machine's clock is corrected, which took what was being typed or pressed with it (ce458a5)
- A console password could not be set: the job always failed, so the screen could never be logged in to (39118b2)
- A machine with no NVIDIA card started with a failed unit at every boot (795590f)
- The Installed page and the Library offered Remove on the NVIDIA driver and container toolkit the AerieOS image carries, and drew them on a machine with no card (ac2ce10)
- The first-run page lost what was being typed each time it read the disks again (0b47c38)
- A move could not land from the first-run walk or Controller settings: the controller's own machine counted as another node, so it never read as fresh (c7feb1d)
- After a move onto a machine of its own, the spaces that ran on the old controller's machine still pointed at the old machine, which stayed on the Nodes page as one still to come (52c971a)
- The dock's line jumped back to its start whenever it redrew (1e941bf)
- On a phone the terminal's Keys and Commands buttons were different widths (b4b7e9d)
- Analysis with no scanner reports showed a red message that stayed over the pages opened after it (788484c)
- A home made by a BuilderBot image still greeted with BuilderBot at every start (5da10c0)
- The move walk's Land card said more than the walk needs, and the space folder's card had two primary buttons (4b6302d)
- aerie map could answer with a copy of a file left in a folder git ignores, ahead of the file itself (cd35f35)
- The sessions doc said each session's own network was a switch on a node's page; it is always on, with no switch, and fails closed (fc1e749)

### Upgrading

- Nothing to do for the rename to spaces: aerie's verbs and --project, the API's paths and fields and what an install stores keep their names, and old #/projects links open the new page (da5e87e, e6e48f0)

## 0.9.0-dev.4922: 2026-11-05

### Changed

- A share works as a NAS's does: a folder on a pool, internal until you turn Export on, then Private, Secure or Public, with each person read/write, read-only or no access, and editable after it is made. A share has no password of its own: each person signs in with their name and their sign-in password, or a separate one set on Profile (099ceeb)
- One rule for fields on every page: a label over its field, fields in a grid with room between them, a long form in groups; and the control fits the answer, so the time zone is a pulldown and a store's path suggests the node's mounts (e96124a)
- The first run on a machine of its own makes the disks, then gives the projects and containers a place by itself, with Shares as an optional step (d2859ed)

### Fixed

- An AerieOS machine lost its own node at every reboot: the agent and each account's home were kept in memory, and the page waited for ever. They now last, and a machine that lost them takes them back at its next boot (873803c)
- A first run on blank disks could not make anything: every blank disk read as holding data and Make it stayed dead, a machine with an SSD got half its storage, and the shares could not be made (d2859ed)
- Nothing could reach a share: Samba was never told of the shares file, a person's name was not mapped to their user, every imported password read as expired, and a file could not be saved over (099ceeb)
- The console password could never log in, since the image had no login program (873803c)
- VMs had no host after a reboot: libvirtd failed at every boot after the first (873803c)
- A new project left a stray folder beside it (78c7d97)
- This machine's Features said Storage and Shares were not installed on an AerieOS machine whose pools and shares worked, and its count said 1 installed above three (0ff1a80, 741c2d7)
- Home's containers tile said an unknown count as last seen on a fresh machine instead of 0 of 0 (95e19b2)
- The Containers page on the controller's own machine said to install Docker, which is already there, instead of saying containers do not run there yet and to enroll another machine (8687f19)
- The console password, the move landing and Storage's new pool, schedule and array forms were laid out unlike every other form, with pulldowns too long to read (ce9bfe3)

## 0.9.0-dev.4909: 2026-11-04

### Changed

- The first page asks whether you are moving a controller here, and yes opens a walk through it on the next page: what to have with you, the disks, where the projects and containers go, landing the controller, what comes after and the way back, in the order they have to happen and each done on that page. Every install takes it with the steps it has (b3d345a, ce7cd9e)
- This machine reads as one page: every section a card, each fact said once, labels lined up and the words cut down. Its sections about the stick are now Pool and projects, First boot and The old system's disks (d83bc4e)

### Fixed

- Move a controller here was never drawn on Controller settings, on any install, so a move onto a stick had no form to land on; Back up now stayed dead for the owner too, and a kept copy had no Download (1e5c2d6, 9cd0b52)
- Naming a projects folder took it from the system that had it, with no way back: that system could no longer read it. Who had it is now kept in the folder, Let it go gives it back, and root on the other system can run `.aerieos-give-back.sh` there (70ff89e)
- A pool adopted from another system can be a stick's system pool whatever its filesystem: a btrfs or XFS one was not offered, which left Docker and the VMs waiting (095dce1)
- The first-run page's links to This machine and the Storage page, and the held band's press, led nowhere while the page stood (b3d345a)

## 0.9.0-dev.4895: 2026-11-04

### Changed

- A store pointed at a folder that already is one is used as it is: AerieOS's marker in it, the node's own toolchain folder inside it, or the folder the page nested for the node before; nothing is nested inside and nothing brought across (c99eafc); the agent asks the same at apply time, so a setting saved before the controller could tell applies without a second save (f386579)

### Fixed

- A mount's state on the Storage section was cut off at a desk when it carried a fix (a stale handle, a mount that did not come up): the whole reason now sits under the mount's row, and the cell keeps its first words (bdad714)
- Enrolling a node again had moved its stores back onto the default paths, so the runner lost its JDK, the project's FTP server was not found and every toolchain read as not installed; the script carries the node's store paths and the agent keeps the ones its record has (88a2736)

## 0.9.0-dev.4885: 2026-11-03

### Added

- The doctor warns while /config sits on a FUSE share (a /mnt/user path): the state database there can come back older after a restart, and the line says what to map instead (25b29f0)

### Changed

- Enroll script on an enrolled node's row downloads the script at once, built from what the node was enrolled with (the system it runs included); the Features section's Enroll again is where an answer is changed (3d5f350)

### Fixed

- An enroll script run again on a node with a cloudflared door left the door restarting under the ssh session running it, which ended the session and the script with it; a door up on its token is left running (615323d)
- Just a token in an enrolled node's Enroll again dialog was refused as a second node with the row's name; it mints on the row (0b67ee1)
- A node whose newest token the controller does not know tries the one it was handed before, and takes a fresh one from there: a controller back from a restart with an older record had kept its nodes refused until each was re-enrolled by hand (ef2656d)
- The controller folds its write-ahead log into the database every minute and on a clean stop, so a restart has nothing to recover: with /config on a FUSE share (a /mnt/user path) a container re-created had come back with the state of the last fold, 25 minutes before, and turned every node away as unknown until re-enrolled (f80e647)
- Home's Getting started card stays put away once a node has dialed in: a node whose agent is quiet is still the first node, and Claude Code on it still installed; the card had come back at 2 of 4 whenever the nodes went quiet (46119a7)

## 0.9.0-dev.4875: 2026-11-03

### Changed

- Controller settings' Update checks is the clocks alone: when each check last looked and how often it runs; Check for updates stays on each thing's own page (Containers, nginx, Scanners, the Library) (801c19e)
- Move this controller reads as facts (new home, armed, nodes heard, last packed, what is in the bundle, the ask) with one line under them, and a dozen dense hints across the pages say their one thing in a line with the rest behind a help mark (1f42d65)

### Fixed

- Move this controller on Controller settings fills in after a reload and after Forget it, and keeps itself current while a move is armed (68851b8, be70d12, 1db8d53)
- The Update window is offered only on an install that updates itself (bare metal and AerieOS), and its boot-menu field only on AerieOS; the container edition's image is pulled by whatever runs it (5f020a1, 1db8d53)
- The color scheme picker's chosen tile shows its scheme's own colors; the page's pressed-button fill had painted the Default tile copper (df0f1c7)
- AerieOS printed 'No changes allowed in reconfigure' on the console at every boot (2d67d9e)

## 0.9.0-dev.4858: 2026-11-03

### Added

- A project with no repository is a place to run an agent that builds containers and VMs: Start agent on an empty project's card starts a session in a plain folder of the project's own, with no git and no notebook, briefed that its work is containers (aerie container new) and VMs (aerie vm); git, the build, test and notebook verbs are refused there with why, and the card's Settings opens the project's own settings as a dialog, with each repository's git, build, files and snapshots left to its notebook (1619322)
- A project's Agents may dials are the defaults for every repository in it: a notebook's Permissions view starts each dial on 'as the project' and sets one apart only when picked, so a new repository takes the project's permissions until somebody says otherwise (52d4ee9)

### Fixed

- The dashboard could answer an error while a project was being deleted, if a status read was going on at the same moment (6b7a26f)

## 0.9.0-dev.4852: 2026-11-03

### Added

- A node's Features section marks an NVIDIA card for a VM: from the next boot vfio-pci holds it, one VM takes it under Hardware, and the machine and its containers do without it until it is unmarked (9a90fa8)
- A container is given the machine's GPU from its settings on the Containers page: an NVIDIA card through the container toolkit, an AMD card or APU through its render devices, for every service of it from the next build (946f98d)

### Fixed

- The first run's Your disks step leaves the disks a stick's plan adopts alone: each is listed as the old system's, with no box, and Make it never sees them; with every disk theirs the step points at This machine's Disks from the stick (565fc4b)
- AerieOS carries the Realtek and Broadcom network firmware, so a board with one of those chips no longer boots saying its firmware could not be loaded (565fc4b)
- Install on IOMMU, Storage, Shares or UPS in a node's Features section lands: the agent refused every feature but VM host and the firewall as 'not a feature verb' (9a90fa8)
- This machine's From the stick section marks the array, the pools and the shares done once they are adopted or served, instead of saying they are waiting for good (f0d0d47)
- On an AerieOS machine the Nodes page says the machine is its own node and where its page is, instead of 'No node yet' (f0d0d47)
- A move's landing cut midway (a power loss between its steps) is said on the bell, with where what was there is kept and that landing the same bundle again finishes it (f0d0d47)
- A landing says when the carried install key could not be taken because the new home's key is set in its environment, and what to set (f0d0d47)
- A moved controller's band says the way back: its bundle still downloads and lands on a fresh install (f0d0d47)
- A cache disk an old system kept in its array's cache slot is offered for adoption as a pool (f0d0d47)
- Four refusals on the adoption path say what to do: a disk with no filesystem UUID, a pool's name that cannot be mounted here, a prepared configuration that could not be read, and a stick with no room for a static address (f0d0d47)
- Forge measure asks the git door whether a project's token may push, so a fine-grained token an organization has not approved no longer reads as able to push until the push itself is refused (b0be3a2)
- On the first run's disks step a disk's checkbox sat on a line of its own above the disk's name instead of before it (46ee70b)
- On Windows the USB maker's write could stop at 'access denied' after the stick's partitions were cleared: it now opens and locks the stick again and goes on where it was (401400a)

## 0.9.0-dev.4818: 2026-11-02

### Fixed

- The USB maker and the installer take the newest published build that carries their file, by its exact name: a dev build from before the name carries builderbot-os and builderbot-controller files, and the maker took one, asked for an aerieos-os image that was not there and stopped (84604c8)
- On Windows the USB maker's first write after the stick's partitions are cleared no longer stops at 'the device is not ready': the write waits for the stick for up to thirty seconds, and a Windows refusal is said in Windows' own words (84604c8)
- A stick's first boot sets the hostname and the time zone its prepared configuration names; they were left at aerieos and UTC, with both under failed on This machine (84604c8)
- The Storage page shows a disk as mounted as soon as Disks from the stick has adopted it, instead of 'not mounted' until the hourly walk or Measure now (84604c8)
- Serve the shares on This machine no longer refuses a share for a person who has not signed in yet: their user is made on the machine when the share names them, and they reach it over SMB once their password is set on Profile (84604c8)
- A release is no longer refused for 'uncommitted changes' over files git does not track; a changed tracked file still refuses it, named (84604c8)
- A dev build's files all land on one release: the apps, the controller bundle and the OS image each found the tag's draft among the drafts, where two drafts had been made for one tag (84604c8)

## 0.9.0-dev.4809: 2026-11-02

### Added

- The roadmap's steps move between items without losing anything: aerie roadmap step mv takes a step to another item whole, split makes new items from an item's steps, fold makes an item a step of another, and each step keeps the number it was first given, so aerie roadmap show finds it by that number wherever it is now; on the page a step has Move to, an item Split and Fold into, and in reorder mode a step drags onto another item (3b4d293)
- AerieOS has a way in at its screen: a console password set on This machine logs in as admin with sudo, and the boot menu's Rescue entry opens a root shell at the screen when nothing else answers (6e8e123)
- An installed AerieOS takes over the disks another NAS made as they are: each data disk found by its serial and mounted with its own filesystem at its old path (read-only by default, writing nothing at all), the parity disk left alone, the pools writable, the merged folders made again, the shares served as they were, and the containers and VMs that ran brought back with the exact images they ran and started with the machine where they were (This machine, Disks from the stick)
- The image is tagged :dev when a release or dev build is published, so an install can follow the dev channel by its compose file or template (1b8ce1d)
- aerie version release --withdraw TAG deletes a published release and its tag together, and the tag in the project's copy, so the number can be cut again; it is always the project owner's answer on the bell, and a tag whose release is already gone goes alone (7a8e367)
- aerie version rehearse runs every build a release's tag runs on the pushed branch, publishing nothing, with a summary of the files the release would carry, so a release is tagged once it is green (7a8e367)
- A release can be signed with an offline release key (tools/release-sign.py): AerieOS's updater, the stick maker and the installer refuse a release the install's own config/release-signers does not verify, so a change to the repository or its CI cannot hand an install an update (7f98d53)
- AerieOS keeps the versions an update replaces, the three newest by default: each is on the boot menu under Older versions and on This machine, a visit lasting one boot with the configuration as it was (300599f)
- On a bare-metal or USB install, plain http://the-machine/ finds the dashboard: a redirect on port 80 until nginx or anything else takes the port (2a102c2)
- An agent works the project's git host through `aerie forge`: pull requests (list, view, create, comment, review, close, merge), issues, CI runs with their logs, reruns and dispatches, and releases, one set of verbs on GitHub, GitLab, Gitea and Forgejo, each run on the controller with the project's access token, which never reaches a session. The token is measured on the host without changing anything; the project's Permissions view gains On the git host, each ability with what the token allows and an Allow or Deny over it (merging starts at Deny); every session is told at its start what it may do there and what to ask for; and *Which permissions?* beside the token field opens the new git hosts page, the table of what to enable on each host. (3113eeb)
- A machine that is its own controller sets up its disks in its first run: you say how many disks may fail, it picks a ZFS layout or an array with parity from the disks there and says how much you can use and how it grows, names every disk it erases before it writes, and makes the Media, Backups and Projects shares after. (386d43e)
- AerieOS's console shows AerieOS's logo above the login prompt at every boot, with the release it runs and the address to open the dashboard at; the installer opens on the same logo. (68ba427)
- A tool pack or a catalog app can carry its own icon: `icon` in `bbtool.json` or `bbapp.json` names a PNG, WebP or SVG file in it (64 KB at most), which its Library card shows in place of its kind's glyph. It is read at the commit the pack is pinned to and shown only as an image, so an SVG's scripts never run. (fe8d6df)
- Two release channels: the releases as published, and a dev channel of the pre-releases CI publishes from a dev build (a vX.Y.Z-dev.N tag, the same files, never the latest), picked under Controller settings, Updates, where an install offers it; aerie version release --dev cuts and pushes such a tag (8228751)
- Moving a controller to another home without losing its nodes: Prepare to move under Controller settings arms the move and shows a move token once, with no life on it, so a controller is prepared days ahead; every node hears the new address and a challenge of its own on each hello from then on, and the section says how many have; the bundle (the state, the deploy key, each store, the repositories and the install key as ticked, each with its size) is packed fresh each time it is downloaded; the new install's first page (Moving a controller here?) takes the token with the old controller's address and pulls the bundle from it, or with a downloaded bundle, holds it to the version gate, restores it and restarts; the landing is told both ways under the move key, so the old controller marks itself moved whichever side was up; it is read-only after, saying where it went, and tells a node that comes late its own challenge, so it knocks and follows like the others; the new controller's Nodes page lists the nodes not yet here with one line each (builderbot-agent follow) for a node that outlived the old controller, never enrolled again (72d59c6)
- Power under Controller settings on a bare-metal install and AerieOS: Restart and Shut down for the machine the controller runs on, the same verbs This machine has (72d59c6)
- A held start on a bare-metal install: after a shutdown that was not clean, or when hold the next start was ticked beside Restart and Shut down before a restart, the install comes up with the dashboard, its agent and the network and nothing else (no agent session starts; a shell still opens) until Start is pressed on This machine, a band on every page saying it is held and why (0a822e8)
- This machine: on a controller installed bare metal the computer it runs on has a page of its own, first in the rail's Controller group, with what the machine is, the Updates section and everything a node's page draws (health, projects, sessions, features, storage, network, reboot and power off); it is no longer a row on the Nodes page or in its picker, and a project's node picker names it This machine (ae919d3)
- A bare-metal install updates from the page: a newer release is a line on the bell and an Updates section under Controller settings, Update runs the installer through the machine's own node (its root agent, never the controller's account), the release's controller bundle is fetched from the release and checked against its sha256 and its build attestation, and a new release that does not answer is rolled back by itself; each release now publishes builderbot-controller-X.Y.Z.tar.gz with its sha256 and attestation (2df7ee8)
- Tests run on a node picked for them: a project's settings gain a Test node beside its nodes, and with one named aerie tests run, aerie dashboard test and the gate's suites run there as a job (this tree snapshotted, as a build travels), with as many workers as that node's cores and memory allow, the lines streamed back, the run recorded and a covered run's counters merged here as a local run's are; a run behind another there says how many jobs are ahead (725635f)
- USB devices to VMs: a VM host's node page gains a USB section listing each device the machine has (name, vendor and product, serial, port, speed, the driver holding it) with what holds it, Give to a VM attaches it live to a running VM and writes it into its definition (a stopped one has it from its next start), Take back detaches it, a device is found again by its serial after a replug or a reboot and by its port when two are alike, a device the host boots from, serves storage on or has in a pool stays the host's with why, the VM's row names what it holds, and aerie vm devices and aerie vm usb let a session list and ask, held for an administrator on the bell; the section's Controllers list each USB controller with what hangs off it and its IOMMU group, given whole through the VM's Hardware dialog unless something the host needs shares the group; the Features section's IOMMU puts intel_iommu=on or amd_iommu=on with iommu=pt on the kernel's command line and asks for a restart (afbb962)
- Every notebook record prints whole as JSON, YAML or Markdown (--format, or --json) on aerie roadmap, bug, rules, wiki, design and map, from one serializer with a format number in each document, and the same formats come back in: aerie roadmap add --from FILE and aerie bug add --from FILE add the records in a file, and aerie roadmap apply FILE writes an edited show back, refused when the list moved since it was printed; the code map reads data files too, so aerie map find DASHBOARD_PORT names every file a setting lands in and aerie map who-calls DASHBOARD_PORT where the code reads it (3b4d293)
- A model router on a node: a node's page gains a Model router section that deploys LiteLLM there with the provider keys you give it (Anthropic, OpenAI, Google, OpenRouter, xAI, and any OpenAI-compatible endpoint under a name of its own), kept sealed on the controller and never in a session's view, Ollama beside it where you turn it on with its models pulled and removed from the section, and the projects allowed to use it, each handed the router's address and a key of its own at a session's start so its spend is its own; the models the router knows, with their context and price, and each project's spend are read from the section (a82d20e)
- Any model as a fifth coding agent: OpenCode, pointed at a node's model router rather than signed in to anybody, offered by Start as Any model with the router's models (their context and price where known) and started with a config of its own (the router as its provider, the briefing as its instructions), its guards a plugin of AerieOS's calling the same hooks as the other agents', its conversations exported into the transcripts; the Library installs and updates it as the others; the picker marks the models walked with it and says when one's context cannot hold the briefing, and its tab on the dock says the project's spend through the router and a local model's tokens per second (a196894)
- The bell reaches you elsewhere: Profile's Where the bell reaches you takes email (through the SMTP server under Controller settings, Mail), a webhook, ntfy, Gotify, Pushover, Telegram, Discord or Slack, each with the kinds it takes (an ask waiting on you, what a node needs, a red CI run, an invitation, a file changed in two places) and a quiet window; a row goes once and not again while unchanged, Test checks the way, and a token or address is sealed under the install key (c41c804)
- A Scanners page in the Containers group beside nginx: AerieOS's own static analysis scanners (Semgrep, Trivy, mobsfscan) deployed to each node that holds projects as a compose project with their versions pinned, run there on one schedule (daily, weekly, monthly or a timetable of your own, and Run now) over the projects whose node it is, each node sending its SARIF up to the controller so nothing is mounted for it; the page says each node's state, Update when newer versions are out (checked weekly), the last run with its log, and the projects nothing covers with why; a failed run and versions behind are on the bell (12af2fa)
- The threat model is written down in docs/security.md: who is trusted for what, what each store protects and does not, what an unlock gives up, and the line each hardening step closes (1493a5c)
- A person's key store opens less at a time: a token is opened per use for the window picked on Profile, Your key store (a quarter of an hour, an hour, eight hours, or while signed in), Lock lets go of everything opened, and Uses of your tokens lists each opening with what it was for; git is handed an opened token for that window and never opens the store itself (da2e647)
- A key of the person's own: Hold the key yourself on Profile moves the key store under a passkey (one that answers PRF; a new passkey asks for it) or a key the person keeps, which this AerieOS never holds, so not even its owner opens what is in it; it opens only while they unlock it, their pushes and pulls say when it is locked, a terminal on a node asks for the unlock first, the tokens projects run CI watching and releases with go to each project's own keeping at the move unless kept, and Give the key back moves it under the install key again; a device signed in as the person may unlock with the key they keep (da2e647)
- A browser's sign-in is bound to the browser it was made in: its cookie presented from another browser is refused, Profile's Signed in as you lists each browser signed in as you (its system and the address it came from) with Sign out, and Controller, Audit is who did what to this install, newest first, narrowed to a person or a machine (75aaf5f)
- The nginx page gets certificates from Let's Encrypt: Get one from Let's Encrypt asks for a hostname's pair by an HTTP-01 challenge the node's nginx answers or a DNS-01 record written through the Cloudflare API token, keeps it like a pasted pair and renews it thirty days before it ends, with the result on the bell (ccb1e29)
- AerieOS, the appliance image the installed editions are made from: Debian stable pinned to a dated snapshot with ZFS built against its kernel, the controller staged in as a bare-metal install lays it out, a read-only root in two slots so an update is a whole image and a bad one falls back, GRUB for UEFI and BIOS, /var and the changes to /etc the only things that persist, and the machine its controller's own node at its first boot; built by image/build.sh, in CI on every release tag (docs/image.md) (03d24cd)
- VMs on the controller's own machine: VM host installs on a bare-metal controller's machine too, its VMs run through the node's root agent with the jobs account kept out of libvirt's group there, and the VMs page lists for an administrator the domains a node's libvirt has that AerieOS did not make, under Not AerieOS's, read-only (c641b4b)
- AerieOS in a VM: a VM installs from the ISO as a machine does, so a hypervisor is the easiest place to try it; a release carries the OS as two files, the ISO and the USB stick's image (14f007e)
- AerieOS updates from the page: on a machine running the image, Update under Controller settings fetches the release's ISO, checks it against its sha256 and its build attestation, takes the root, kernel and initrd out of it, writes the slot not in use and names it for the next boot, the restart yours from This machine and the slot running now kept to fall back to; an offline machine takes the same files from a folder; an Update window under Controller settings applies a newer release by itself at an hour, daily or one weekday, off by default (b583bae)
- AerieOS installs from an ISO: it boots the same root live with an installer on the console that asks for the disk (everything on it lost, said first) and the features to turn on at the first boot, lays the disk out with the very script that made the image, the data partition grown to the disk, and restarts into the machine as its own controller and node; the ISO's second entry boots the live system without installing (b2cab06)
- AerieOS on a stick runs from memory: with the switch set in GRUB's environment the slot is copied into memory at boot, exactly its bytes, and the system runs from the copy while the stick keeps the configuration apart from both slots; the slot tool reads and sets the switch (e0d7654)
- An AerieOS update boots on trial: the slot an update wrote boots as a trial, the health check marks it good once the dashboard answers and the agent runs, and a second boot without that word goes back to the slot before by itself, said on This machine; the boot menu names each slot's version and offers Safe mode, which brings up the dashboard and the shares and starts nothing else (the start is held); the controller's configuration is copied before an update, kept beside the old slot (668715b)
- This machine sets the machine's name and time zone: a Name and time section on the controller's own machine, each set on the machine by its root agent, the zones offered as a list to type into; the first-run page's This machine card says the name, the address and the clock's zone, and where to change them (b18d6fe)
- The Storage page lists the controller's own machine's disks: each by name, model, size, serial, spinning or solid state and what each partition holds, with SMART's health, temperature and hours where the machine has smartctl, the system disk marked; read before anything is written to one (c56141b)
- Storage and shares are features of the controller's own machine: its Features section installs ZFS, mergerfs, SnapRAID and SMART as Storage and Samba and NFS as Shares, each with exactly its packages, removed with them and refused while a pool or a share stands; the row says which tools answer (6c8a995)
- Shares on the Storage page: the controller's own machine's SMB and NFS shares, each a folder on a pool given to the machine's users or to everybody as a guest over SMB and to named clients over NFS, read-only or not, with Remove; every press a job the machine's root agent runs, which writes AerieOS's own share files whole and tells Samba and NFS to read again (a041fd2)
- The configuration backed up onto the machine and found again: with a backup password set under Controller settings, a sealed copy of the state (the same bundle a move carries) is written onto every pool of the controller's own machine and under the state after every change, the five newest kept and each downloadable, and a fresh install's first page offers Restoring a saved configuration: a copy found on its disks or one you kept, and the password, and it becomes the controller as it was (c86dcfe)
- The USB stick maker: tools/builderbot-stick.py writes a release's stick image onto a USB stick on Windows, a Mac or Linux with nothing but Python's own library, lists the removable disks and never writes the system disk, fetches the image with its sha256 and checks it, says what is on the stick is lost, writes the disk whole and reads it back; the release carries the stick's disk beside the ISO, the slot loaded into memory at boot (6a559f9); it writes the newest release when none is named, and `--set KEY=VALUE` puts a line in the stick's builderbot.env as it writes: TZ, BB_RELEASE_LINE, and the network settings BB_HOSTNAME and a static address (BB_NET_ADDRESS, BB_NET_MASK, BB_NET_GATEWAY, BB_NET_DNS) the machine takes at each boot in place of DHCP; each boot grows the stick's data partition to the stick's size, `BB_DATA_MAX` capping it; on a stick boot the logs and the journal are kept in memory and docker, the VMs, the toolchains and the projects write to a system pool picked under This machine's The stick, which also says what the stick has written; `--config FILE` puts a prepared configuration on the stick (the machine's name and time zone, the owner, the people), which the first boot applies before anyone signs in and says on This machine (c014595)
- ZFS pools on the Storage page: the controller's own machine's pools as zpool says them (size and what is used, health, the members by layout, the last scrub), each with Scrub, Export and Destroy, and a new pool made from a name, a layout and the disks it takes, each named by model, size and serial and said again before anything is written; every press a job the machine's root agent runs, the system disk never offered (0cae2c5)
- Snapshots of the controller's own pools: the Storage page's Snapshots section counts each ZFS pool's snapshots by kind, takes one now, rolls a dataset back to one (its name typed again) or deletes one, and saves a schedule per pool (hourly, daily or weekly, with how many of that kind to keep; the oldest past that goes as the next is taken), each a row on the Schedules page that runs as one of the machine's own jobs rather than a script (b25236b)
- People on shares: a share on the controller's own machine is given to AerieOS accounts and roles by name (a role names everybody holding it now), each person sets an SMB password of their own on Profile, where Your shares lists the shares named to them with the address to map each by on Windows and a Mac, and a share can be a Mac's Time Machine target (e9c5e12)
- An array of mixed disks on the controller's own machine: the Storage page's Array section makes one of data disks of any sizes (each its own xfs or btrfs filesystem, pooled into one tree by mergerfs with the policy picked for where new files land) and one or two parity disks kept by SnapRAID, adds a disk, replaces a slot's disk with its files rebuilt from parity, runs a sync, scrub or check now and schedules the sync and the scrub as rows on the Schedules page; parity is periodic, which the page says, and destroying the array leaves every disk's files readable on any Linux (14f007e)
- Disk health on the bell, and disks spun down: a disk SMART calls failing, a disk running hot, a pool not online or an array disk gone on the controller's own machine is a row on the bell (a kind of its own under Where the bell reaches you, so it can go out by email or a push) that leaves when it stops being true, and This machine's Name and time gains Spin down disks, which stops the spinning disks but the system's after the idle time picked and sets it again after every boot (5d14606)
- A UPS and the system's own updates on This machine: the UPS feature installs NUT for a USB UPS, the Power section shows its charge, the minutes left and the load, the bell says when the machine runs on battery or the battery is low (sendable by email or a push), and NUT shuts the machine down cleanly on a low battery; on a bare-metal install that is not AerieOS, Updates under Controller settings also counts the system's own package updates once an hour, says which are security ones and whether a restart is needed, and applies them with apt from the page, restarting after when asked (7918b2d)
- Reporting on This machine: the controller's own machine's CPU, memory, network in and out, disk reads and writes and the CPU's and disks' temperatures are kept for weeks at falling resolution (five-minute means for two days, hourly for two months) and drawn in a Reporting section over six hours, a day, a week or a month, the hour's charts unchanged (0778cbf)
- Other disks and shares on the Storage page: a USB or eSATA disk plugged into the controller's own machine, or an SMB share or NFS export on another machine, is mounted at /mnt/other by name as a backup target or a source to copy in, never pooled, with Eject unmounting a disk so it is safe to pull; the record is the controller's, a share's password sealed under the install key, and the machine's agent follows it within a minute (8aa403b)
- Backups off the machine: the Storage page's Backups section copies a folder on the controller's own machine (a pool, the array, the controller's state) to another place (another pool, the array, a disk or a share under Other disks and shares) with rsync, each run a dated folder sharing what did not change with the run before and the oldest pruned past the runs kept, run now or on a daily or weekly schedule that is a row on the Schedules page; the last good run is a tile on Home, and a run that failed or a scheduled backup two days without one is a row on the bell (4df8513)
- Pools by purpose: a new share picks the pool or the array it lives on and names its folder there, and a pool of one disk (an SSD holding the hot data) gets a one-press nightly backup to the array under Backups, so a dead disk is restored from last night's run; no cache tier and no mover: writes go to the pool a share names (f8f7751)
- Encrypted pools: a new pool can be made with ZFS native encryption under a passphrase, its key either kept on the machine sealed under the install key (the pool unlocks at every boot, the disks unreadable pulled from it) or asked for on the Storage page after every boot (the whole machine taken is covered too), the choice said with what each protects against and changeable later; a locked pool is a row on the bell and its shares say so rather than vanishing, and Safe mode boots with every pool locked (3c6c521)
- Apps a NAS runs: New container on the Containers page offers a catalog of ready apps (Jellyfin, Plex, the arr stack, qBittorrent, Immich, Nextcloud, Home Assistant, Syncthing), each filled in from a few blanks (its data folder, its media or files folder, the user it runs as, the time zone, its port) into a compose file pinned to a tag and an environment the Create makes as any container, reached on its port on the node and put behind a hostname and a certificate on that node's nginx page (1fc3563)
- A VM may belong to the machine rather than a project: Belongs to on New VM offers This machine's own to an administrator, for the NAS's own apps and desktops (a Home Assistant VM, a Windows desktop), grouped as such on the VMs page, administrators' alone and never a session's (04c0799)
- One manifest for everything: every shipped toolchain and every coding agent is a pack in bbtool.json's format under packs/, tagged official and bundled with the release for an install with no network, a toolchain's recipe under shipped and an agent's adapter (how it installs, updates and signs in, how it takes the briefing and AerieOS's guards, where its conversations are) under agent; an agent that cannot take the guards is not listed, and aerie lint holds the packs to the tables they are written from (3aa2613)
- The vetted catalog's signed index: AerieOS reads the catalog's index.json and index.sig from the address under Controller settings (the public builderbot-catalog by default), checks the signature against the maintainers' public key the install ships before reading an entry, refuses a tampered or re-signed index and keeps the one before, and puts a pack the catalog withdrew on the bell for every install that holds it; each entry pins a pack to an exact commit and its archive's sha256, never latest (c9eebb7)
- Install from the vetted catalog: the Library lists the index's packs with their tier, each Install opening the Add tool pack dialog on the commit the index pins with the archive's sha256 checked on the way in, Look before Add as always; every pack's row says its tier (vetted, or by URL), and a withdrawn pack is said and not offered (a196894)
- A project's FTP access can be kept on for an hour, a day or a week, then turns itself off
- A controller moved onto a bare-metal machine keeps the node that machine already is and a stick's plan of disks to adopt (a94c440)
- A project can list the files each release must carry in .release-files; the controller checks every release against it once CI has had three hours, and a release short of a file is a red row on the bell naming the file and why (7a8e367)
- On a USB stick, This machine can name a folder already on the machine's disks as the projects folder, so a controller moved there works on its projects where they are, with nothing copied (7c24926)
- On a USB stick the projects are never kept on the stick: until a system pool or a projects folder on the disks is named, no project is made, cloned or moved in (7c24926)
- A move onto a USB stick lands from Controller settings, Move a controller here, once the disks hold the projects, spooled and unpacked there; a landing without room says so before it takes the bundle (7c24926)
- Every release starts as a draft: the Artifacts view's Drafts shows its notes to read and correct, and Publish makes it public once its files are all there (c4879b7)

### Changed

- Any install picks its update channel under Controller settings, Updates, and a dev build follows the dev builds until another is picked
- The default theme is blue and copper: navy surfaces, a cerulean accent, blue words and warm copper on what is pressed, and the mark with them; a check that passed stays green
- BuilderBot is now AerieOS, at aerieos.org, with a new mark: a raptor with its wings swept back, which is also the letter A
- The command is aerie, in every shell and session
- The container edition is called Aerie Workshop: it is the AI workshop alone, and the storage comes with AerieOS on a machine of its own
- A session's aerie version release from a branch other than main makes a dev pre-release unless --stable is said, and its first line names the channel the release lands on (7a8e367)
- aerie sign release waits for its look and says what it found, run by run, or why it found nothing to sign (7a8e367)
- A dev build's release notes list only what changed since the last published release (37e8e97)
- Every page's top reads in one order: a notice, the page's head, its number tiles, then the search with the page's buttons at its right, the filter chips under it and the small jump chips over the sections they lead to; a notebook view the same, its tiles first. A single action sits in its head's top-right corner or beside the words it belongs with, never on a line of its own, and on a phone the search keeps its buttons on its line while they fit. (61c8237)
- The Machines, Build and Containers headers keep one node for every one of their pages, and no page names that node again under the header. (61c8237)
- A page's state reads as a state pill, an update check is Check for updates everywhere, Users and Roles have a head with their counts, empty lists say so in one quiet line, and the Phone page is two plain steps, Connect and Pair a new phone. (61c8237)
- AerieOS's mark is the robot head in isometric line work, in the mark's greens: the big mark at the top of the README and the About screen, the solid small one as the favicon, the top bar's mark (in the theme's color, red while the controller is away) and the phone app's launcher and status icons (a5fe690)
- The Machines, Build and Containers groups each wear one header over their pages, in a project's shape: the node picked once where a project's name is, with when it was seen, where it dials in from and its agent beside it, the group's sub-nav under it with the group's own actions at its right (Machines: Create sandbox VM and Enroll node); every page of the group follows that one pick and carries no picker of its own, the Containers page's search growing into the picker's room, and a sub-tab says not here when the picked node lacks what it needs (nginx not deployed, no Docker, no Android tools or adb, no CI runner yet); a notebook's restart note is a band between its header and its view strip, put away with its x for as long as it says the same (05dd7bb)
- A Network page in the Controller group says how the controller is reached (its address and port, what it is served over, which nodes dial in and from where), and Connection and Reach from outside live there now rather than under Controller settings (0602655)
- The repository is laid out by what each part is: the companions a person installs live under apps/ (apps/android the phone app, apps/vscode the editor extension, apps/windows the Windows companion) and each place the container edition installs under platforms/ (platforms/unraid/builderbot.xml, the Unraid template, which moved there with no copy at the old path: a template installed from the old raw URL is pointed at the new one by hand, once); the installed edition's own parts land beside them as they are built; release assets keep their names (e4bacde)
- Every git action is a person's, with their own token: each person gives a project their own token for their pushes, pulls and releases, used only while they are signed in on a browser or a device, and the project keeps none of its own; its settings list who has given one, the Git view says whose token a press would use, a session whose person is signed out everywhere is told that aerie git waits for them, and watching CI pauses, said on the project, while nobody who gave a token is signed in (46493b1)
- Update checks under Controller settings: each check AerieOS makes by itself (a newer AerieOS, the container images, nginx, the scanners, the Library's versions and catalog) daily, weekly, monthly or off, with when it last ran and Check now; a node's own version check is its row's Version check. A newer AerieOS is now looked for weekly rather than daily, like the rest (b0eb924)
- The Library: one page under Build for everything an AerieOS installs or runs on a node (the coding agents, the toolchains, the tool packs, the apps a NAS runs and the companions for your own machines), each a card with its tier (official, vetted or sideloaded), what it is and one Install, Update, Remove or Download; a card opens on its whole description; a search box and chips by kind and tier; Add your own takes a tool pack or an app's compose file of yours, looked at before it is kept. The Toolchains, Agents and Apps pages are this page now, and are gone: the Library offers, the Installed page under Machines holds, a companion's download is a Library card, and an address naming one of the old pages opens the Build group. (2083e35)
- A tool pack may name the AerieOS release lines it works with: one that does not name this install's is not added, and one held that stops fitting after an upgrade is said on the bell (a05dda7)
- A tool pack says what it touches (the hosts its install fetches from, and whether it needs root), shown on Look; one that needs root is added by an administrator alone (e3e4592)
- A session can look through the vetted catalog with aerie tool search and ask for a tool pack with aerie tool install, as a new Install a tool pack setting under Agents may says (ask by default: a person who may curate the catalog answers on the bell) (ef5b215)
- A tool pack names its system packages for each package manager (apt, dnf, pacman, zypper, apk), as the shipped toolchains do; a node whose manager it names none for is told so on the pack's card and its Install there is refused, and Look lists them (8aed56e)
- A mirror of the vetted catalog for a controller without the network: tools/catalog-mirror.py makes one on a machine that has it, and Controller settings' new Vetted catalog group imports it (refused unless the index is the maintainers' and complete), the Library then reading its index and installing its packs and apps with nothing fetched; the same group sets the catalog's address, and the stick maker's --mirror carries one on a USB stick, imported as the controller starts (30d91f3)
- Catalog update: a tool pack kept from the vetted catalog offers the newer commit a later index pins on its Library card, the dialog showing what it changes before Update keeps it, its tier kept (9e48fd2)
- Docker apps in the vetted catalog: an app entry is an Apps card on the Library, and Install fetches it at the commit the signed index pins, keeps it and opens New container with it picked on the Library's node (25ae3ea)
- A pack's setting may be each person's own: a config field with `"scope": "person"` is set under Yours on the Installed page's row by anyone who works on that node's projects, sealed under their own key and read by their own sessions' verbs (8f2fabf)
- Configure on the card: a tool pack says in its manifest what it asks for on a node (keys, choices, a list of endpoints, a switch, the projects allowed), a new Installed page under Machines, with the node picked, lists what the Library put there and draws that form on each row, keeps the answers sealed and hands them to that node for the pack's verbs; an agent's sign-in, a toolchain's system packages and Remove live there too, the Library's cards showing the catalog's entry alone; the Model router is installed from the Library and configured on Installed, and its section leaves the node's page (5155820)
- A person keeps one token for each git host and sign-in: a new one replaces the one before in place, every project using it moves to the new one, and the older tokens an install already kept for the same host are let go at the upgrade (fb7bd4d)
- A chip that narrows a list moves it: what stays slides to its new place, what the chip leaves out fades away and what it brings fades in, on the Library's cards and every page with chips (3279319)
- On the Library the source chips count within the kind picked, so picking Apps says how many apps each source has (4330d70)
- The NVIDIA driver's card and row say installed and in use where they said running the card, and an installed card or row says so in green (bc71c74)
- A project's Agents may says what each of its parts is for: Coding agents says Claude always may and an unticked agent does not start there, Start opens and Sessions each carry a line under them, and each agent's guards fold under How each agent is guarded (6ae825f)
- Pages read alike: sizes say their unit after a space and in TB past a terabyte, a list narrowed two ways shows one All with the second row starting at Any source or Any version, a view's status line is a note unless it says what stops a press, the Wiki view's controls are one row, Commit all and the Design view's new page sit on one line, and where any coding agent is meant the page says agent (56bc704)
- A project's Permissions, On the git host: Change CI workflow files set to Deny now refuses a session's push that changes a workflow file (a workflow runs with the repository's secrets); Push branches, Read the code and Publish and edit releases have no switch there any more, each showing the setting that governs it (Pushing, or Agents may: Tag and publish a release), since a Deny on them was told to sessions but never enforced (30cba84)
- The :latest image is now the newest published release, moved when one is published, where it followed every push to main; :main follows main, and :dev and :X.Y move when a release is published (c4879b7)

### Security

- Every seal is on vetted cryptography: what the controller keeps sealed (the accounts' keys and key stores, the signing keys, the settings' secrets, two-factor secrets) is ChaCha20-Poly1305 under a key HKDF derives from the install key or the account's, and a node seals the coding agents' sign-ins with X25519 and ChaCha20-Poly1305, all from the cryptography library in the image and on every node; what was sealed the way before is sealed again at the next start, and on a node the next time its person opens a terminal there, and the old format is still read this release (1e534c6)
- The dashboard is served over https where it can be had: Controller settings' Connection section picks http, the install's own certificate (made at the switch, its fingerprint shown for the phone and the companion to pin, its private key sealed under the install key and listed on the Keys page) or a Let's Encrypt certificate for the controller's hostname by a DNS-01 record through the Cloudflare API token; one port serves both, so a node keeps dialing http while a browser gets https; a fresh install starts on http, and the Doctor and the section say so until https is on (e6d74b8)
- The page runs only what it ships: a Content-Security-Policy allows the page's own scripts and styles and nothing inline that is not in the file by its hash, each script tag names its file's integrity, cookies are SameSite=Strict, and what a browser refuses under the policy is kept and said by bb doctor (41d8fe9)
- The dashboard and the node agent keep the keys they hold out of core files and swap: neither writes a core dump or can be read by another process of its user, each locks its memory where the memlock limit allows (docker-compose.yml, the Unraid template and the agent's unit raise it, and bb doctor says when it could not), and a key or an opened sign-in is zeroed once let go (b2635de)

### Upgrading

- AerieOS starts here. Nothing upgrades from BuilderBot 0.8 or earlier: install fresh, and add your projects again from their repositories
- The command is aerie, and bb is gone
- The image is ghcr.io/aquilaelabs/aerieos, the repositories are github.com/aquilaelabs/aerieos and aerieos-catalog, and every download is named aerieos-*
- The Android app is org.aerieos.app and the VS Code extension aquilaelabs.aerieos: install them new and pair or sign in again
