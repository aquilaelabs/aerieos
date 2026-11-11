# Versions and release lines

A space's version is its `VERSION` file, moved by `aerie version bump` and
`aerie version set` where the space's policy lets a session move it, and
released with `aerie version release`. Between releases a build is
`X.Y.Z-dev.N`, where X.Y.Z is the release the work is heading for.

## Two releases at once

A branch has a *line*: the release it works toward. A branch named for a
release (`claude/0.7.0`) has that line by its name; any other takes one
with `aerie version line X.Y.Z` on it (kept in git's own config for the
branch, so it never travels in a commit), and `aerie version line none` goes
back to the name's. A build on a branch heads for its line, so work toward
0.7.0 builds as `0.7.0-dev.N` while a fix on `claude/0.6.2` builds as
`0.6.2-dev.N`, and the Artifacts view and the dashboard's version say which.

A roadmap item or one of its steps is meant for a release with `aerie roadmap
target N X.Y.Z` (or `N.M` for a step); `aerie roadmap --target X.Y.Z` lists
what is meant for one.

A *patch line* is one whose last number is above 0 (0.6.2). There a bump or
a release is refused for anything but the patch, and the gate holds the
space's own rules for what a patch may not change: a house rule named
`patch`, or `patch-` and a word, says in its files what that is (`aerie rules
add patch "A patch adds no migration and keeps the API." --files
"scripts/dashboard/statemigrations, docs/api.md"`), and `aerie tests
preflight` on a patch line fails on a changed file under one. AerieOS's
own lint refuses a new state migration on a patch line.

## Two channels

A controller installed bare metal (or the OS) updates from GitHub's
releases: the *normal* channel, which is every published release (`vX.Y.Z`)
and never a pre-release. A *dev* channel takes the pre-releases CI
publishes: a tag `vX.Y.Z-dev.N`, or a pre-release of another name
(`vX.Y.Z-rc.N`), built by the same workflow
as a release, marked a pre-release and never the latest, with the same
files (the controller bundle, the OS image, the stick disk, the APK). The
channel is picked under Controller settings, Updates, on any install, and a
dev build follows the dev channel until another is picked. Aerie Workshop
follows its image's tag instead: `:dev` for the dev builds, `:latest` for the
releases once there is one. Until AerieOS has a stable release, dev is the one
channel with anything on it.
On
the dev channel Check now, Update and the update window take the newest
of the releases and the dev builds by rank (a release stands above every
dev build heading for it, a dev build by its ordinal), so a dev build
moves to a later dev build or to the release it was heading for. A dev
build is not a release: it may not come up, and the OS image's slot
fallback is what brings the machine back. `aerie version release --dev` cuts
such a tag (no bump) and pushes it, which is what a session's release from a
branch other than main is unless `--stable` says otherwise; `--pre NAME`
cuts a pre-release of any other name, `vX.Y.Z-rc.N` or `-beta.N`, numbered by
the commit as a dev build is, so one number orders every pre-release whatever
it is called. The dev channel takes a pre-release of any name, Check now and
the stick maker's `--channel dev` alike, and Release makes its page on the
forge marked a pre-release, where the space's CI does not make it;
the stick maker's `--latest` takes the normal channel unless `--channel dev`
says otherwise, and `--release` names any tag.

## Drafts

Every release starts as a draft, a dev build and a stable release alike:
CI builds and attaches its files, but only the repository's own people see
it until its owner publishes it from the Artifacts view's **Drafts**, where
its notes are read and corrected first. Publishing is a person's press; a
coding agent's session cannot do it, whatever the space's dials say, and
it is refused while the release is short of a file `.release-files` names.
The tag and the code are public once pushed; the release's files and the
image tags people follow are not. A tag pushes the image under its exact
version alone (`:0.9.0`, `:0.9.0-dev.N`), and publishing it moves `:dev`,
and for a stable release `:latest` and `:0.9` too.

AerieOS's own dev builds are published by their build, not by a press: the
last job of the tag's build checks that every file `.release-files` names is
on the release and publishes it then, a pre-release and never the latest
(`tools/release-attach.sh --publish-when-whole`). A build whose image job
fails never reaches that step, so its release stays a draft; so does one
still short of a file after a quarter of an hour, with the file named in
the run. A stable release is not published this way: its owner reads it
first, as above.

A controller started for development, on the dev channel and holding a
token for AerieOS's repository, sees the drafts as well. Updating
AerieOS to one fetches the draft's files with that token and takes the
update from them, checked as an update from a folder is. A controller
installed on another system, and a container, take a draft only once it is
published.

## The changelog across releases

A published pre-release is a release: somebody ran it and met its bugs. So
the changelog keeps a section for each one, and Unreleased holds only what
no published build has carried. Cutting a pre-release first moves
Unreleased's lines under `## X.Y.Z-NAME.N: date`, commits that one file and
pushes the branch, then tags that commit; its notes are that section. A
stable release gathers every pre-release section since the last stable one,
with Unreleased, into `## X.Y.Z: date`, each category's lines in the order
they came, and leaves out a Fixed line about a bug the last stable release
never had, since nobody upgrading from it met that bug; its notes are that
section, the whole backlog since the last stable release. A bump to a stable
version gathers the same way.

A release is refused while the changelog owes a line: a bug fixed since the
last release (of any name) that the release carried, with no Fixed line and
no answer. A bug was carried when it was seen in a build of that release or
before it, or when its fix (a commit naming the bug, or the one it was closed
on) changes a line the release's own copy has; a fix touching only tests and
CI, or code that came after the release, owes nothing. `aerie changelog
missing` lists what is owed at any time; `aerie changelog add "..." --cat
Fixed --bug N` writes the line and ties it to the bug, and `aerie changelog
skip N "why"` answers for a bug that needs none. Both answers are kept in
the bug's notes. A line never names a bug's or a roadmap item's number: the
tool refuses one, since those are the notebook's and a reader of the
repository cannot open them.

## What a release upgrades from

Each release says how far back it reaches, in two numbers.

- **The state floor** is the oldest `/config` it reads (`SUPPORTED_FROM` in
  `scripts/dashboard/stateversion.py`). AerieOS starts at 0.9, and nothing
  upgrades from a build before it: an older `/config` is refused at start, and
  the way on is a fresh install.
- **The agent's window** is the minor of `AGENT_VERSION`. A node whose agent is
  from another window takes nothing but its own update, and its spaces'
  sessions wait until it has it. The controller keeps what the previous
  window's agents need to be updated and to hand over what they left on the
  node, and nothing older.

There is no downgrade. A container goes back by restoring the copy the
upgrade took (`backups/before-VERSION`) under the older image. A bare-metal
install goes back by itself only when a new release does not answer after an
update.

## Moving work between the lines

- **Forward.** Once a patch line is released, `aerie version forward
  claude/0.6.2` on the later line's branch merges it in: its fixes carried,
  the later line's `VERSION` kept, and the changelog stitched, the patch's
  dated section placed among the others by version and any entry it
  already released taken out of the later line's Unreleased, so a fix made
  on both lines is said once, under the release that shipped it. A patch
  line with changelog entries not yet released is refused until it is
  released. A conflict elsewhere is left in the tree, named, for a person.
- **Back.** A fix made on the later line first is carried back with `aerie
  version backport COMMIT` on the patch line's branch: cherry-picked with
  its origin named in the message, the patch line's `VERSION` kept, and the
  changelog entries the commit added put under the patch line's Unreleased
  in their own categories.
