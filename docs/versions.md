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

AerieOS's own dev builds are published by CI, not by a press, and in two
runs. The tag's own run builds every file it can, attests each one, and
its last job makes the draft with them: the controller bundle, the OS
image and the stick's, the companion's files, and one line naming the
container image the tag pushed by its digest (`aerieos-image-VER.digest`).
The Android app is not among them: that run hands it over unsigned, and the
controller signs it with the app's own key and attaches it afterwards,
minutes to hours later. Once it has, the controller starts the second run,
`seal-release.yml`, for the tag and on the tag. That run makes the
release's signed list of its files, which can only be made over every
file: it checks that the release carries all of them, that the tag still
names the commit it runs on, that each file's bytes match the sha256
beside it and its build attestation by the workflow that builds it, and
that the Android app, which no build attests, is signed by a certificate
`config/apk-signers` names; then it signs `SHA256SUMS` with the release
build's key, attaches it with `SHA256SUMS.sig`, and publishes the release,
a pre-release and never the latest (`tools/release-attach.sh
--publish-when-whole`). A release short of a file, or with a file nothing
vouches for, is not sealed and stays a draft, with the reason in the run.
A build whose image job fails makes no release at all. A stable release is
not sealed or published this way: its key's holder signs its list on their
own machine and its owner reads it first, as above.

When the controller was down, or could not start the run (the bell says so,
and the Signing view), a person starts it: the repository's Actions page,
**seal release**, **Run workflow**, from the tag, with the tag typed as its
input. Run again for a release that is sealed and published, it makes the
same list and changes nothing. Run after a file was replaced (the Android
app signed again with `aerie sign release --again`), it says what changed
in a warning on the run and replaces the list.

Two things the controller's start of it needs, as `aerie version rehearse`
does: the space's token allowed to start workflows (Actions, write), and
`seal-release.yml` on the repository's default branch, since GitHub starts
a workflow by its file's name only once the default branch carries it. A
dev build tagged on a branch before the file has reached main waits, a
draft, until it has, and is then sealed from the Actions page.

### The release key on GitHub

The key CI signs with (the agent's signature and a dev build's list) is
the repository's secret `AERIEOS_RELEASE_KEY`. Two jobs read it: `signature`
in the tag's run, which signs the agent once for the image, the bundle and
the OS image, and `seal` in `seal-release.yml`. A push to main, the weekly
rebuild, a run by hand and a branch's OS image build do not read it and
ship the agent unsigned, as a branch always did; a tag whose agent does not
carry the committed key's signature fails. Both jobs name the environment
`release`, and the library they use the key with is installed from
`tools/release-requirements.txt`, each file held to its hash, in a step
that holds no secret.

**What the workflow files hold, and what only GitHub's settings do.** A
tag's run uses the tag's own copy of every workflow file, so whoever may
push a `v*` tag writes the job that reads the key. The files hold what a
file can: the job that holds the key asks, before the step that reads it,
where the tag's commit is, by the default branch's copy of the rule
(`tools/release-place.sh` and `tools/release-branches`: a dev build on
`main` or a release's working branch, each a pattern a branch's whole name
matches, a stable release or a candidate on `main` alone), so a tag on a
stray commit signs nothing, and a default branch that does not carry the
two files signs nothing at all, the tag's own copy never asked in their
place (the rehearsal says when `main` lacks them or holds other copies);
a release's files
are attested on hosted runners, and the seal holds each attestation to the
tag's commit and to a hosted runner (`tools/release-sign.py`); the Android
app a release carries is built on a hosted runner, not on the machine a
pull request's checks run on; and the image tags people follow move only
onto the digest a published, sealed release's signed list names. None of
that stops a tag that rewrites the workflow itself. These settings do,
each made once on GitHub, and until they are made the key is as open as
the widest of them leaves it:

- **The key in the environment alone.** Settings, Environments, `release`:
  add `AERIEOS_RELEASE_KEY` as an environment secret, then delete it under
  Settings, Secrets and variables, Actions, Repository secrets. A
  repository secret is handed to any workflow of any branch that names it;
  an environment's only to a job the environment admits.
- **Which refs the environment admits.** The same page, **Deployment
  branches and tags**: Selected branches and tags, one rule, the tag
  pattern `v*`. A job on any other ref is refused before a step starts.
- **Who approves a run that reads it.** The same page, **Required
  reviewers**: the owner, with **Prevent self-review** left off where the
  owner is the only maintainer. Each tag's `signature` job and each seal
  then waits for a press, which is the one check a rewritten workflow
  cannot remove. This is a step for a person at every release, and the
  reason it stays is that it is the only one a tag's author cannot write
  around; without it the next setting carries the whole weight.
- **Who may push a `v*` tag.** Settings, Rules, Rulesets, New tag
  ruleset: target `v*`, restrict creations, updates and deletions, bypass
  for whoever cuts releases. A tag that cannot be moved is also what the
  seal's commit check rests on.
- **The branches a release is cut from.** Settings, Rules, Rulesets, a
  branch ruleset for `main` and the release branches
  (`tools/release-branches`, `claude/*` for the working branches): restrict
  creations, deletions and force pushes, bypass for whoever cuts releases,
  and require a pull request on `main`. The place check trusts what those
  branches hold, and a release branch's name is one anybody who may push
  could otherwise make.
- **Pull requests from forks.** Settings, Actions, General, **Approval for
  running fork pull request workflows from contributors**: Require approval
  for all external contributors. The self-hosted runner is a machine on
  its owner's network; `lint.yml` and `dashboard.yml` refuse a fork's
  request, but a request that edits the workflow runs its own copy, so
  this setting, and reading a request's workflow changes before approving
  its run, is the protection.
- **What a workflow's token may do by default.** Settings, Actions,
  General, **Workflow permissions**: Read repository contents and packages
  permissions, and "Allow GitHub Actions to create and approve pull
  requests" off. Each workflow here names what its jobs need.
- **The Windows certificate.** `BB_WIN_CERT_PFX_B64` and
  `BB_WIN_CERT_PASSWORD` are read by the tag's run alone (a rehearsal is
  handed neither): move them into an environment limited to `v*` tags too,
  and name it on the companion's `build` job when they are.

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
Fixed --bug N` writes the line, ties it to the bug (several by repeating
`--bug`) and names the commits that fixed it rather than whatever HEAD is
then, `aerie changelog link N BUG...` ties a line already written to the
bugs it answers, and `aerie changelog skip N "why"` answers for a bug that
needs none. A bug that names the commit that fixed it (recorded when it is
closed, or set with `aerie bug fixed-in`) is answered by any line naming that
commit too. A tie is kept in the notebook, on the bug's row, which shows the
line and the release that carried it, and in the changelog editor, where
each line shows its bugs and the ones the next release owes are listed over
the lines; an edit, a merge or the editor's Save keeps a line's bugs tied. A
repository's Settings, Releases, says whether what is owed holds a release
or goes out with it said.

## What each file is for

Every release AerieOS makes, and every draft published from Drafts, opens with
a table of its files: each one's name and what it is for, from the list in the
repository's Settings, Releases, where a name may hold `@VER@` for the version
and `*` for anything. Checksums and signatures share one row, and a file the
list says nothing of is listed by its name, which the draft's row says before
it is published. A repository holding `docs/release-notes/downloads.md` has
that file put over its notes instead, `@TAG@`, `@VER@` and `@REPO@` filled in;
the same switch turns either off. A line never names a bug's or a roadmap item's number: the
tool refuses one, since those are the notebook's and a reader of the
repository cannot open them.

## What a release upgrades from

Each release says how far back it reaches, in two numbers.

- **The state floor** is the oldest `/config` it reads (`SUPPORTED_FROM` in
  `scripts/dashboard/stateversion.py`). Nothing updates from
  `0.9.0-dev.5641` or earlier: such a `/config` is refused at start, and
  the way on is a fresh install.
- **The agent's window** is the minor of `AGENT_VERSION`. A node whose agent is
  from another window takes nothing but its own update, and its spaces'
  sessions wait until it has it. The controller keeps what an older agent
  needs to take that update, and sends it no other job until it has.

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
