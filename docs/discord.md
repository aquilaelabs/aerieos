# Discord

A space can run a Discord server: its channels, roles and rules kept as a
file in the space's repository, built out and changed from there by a person
or by an agent session, with a person's Allow on anything that removes,
changes a permission or reaches people.

## Connecting a server

Discord is a space's connection, made in the space's settings under
**Discord**, beside its git host:

1. On Discord's developer portal, make an application and its bot, and on
   the bot's page **Reset Token** to see its token.
2. Invite the bot to the server. Connecting with a bot that is in no server
   yet gives the invite link, asking for the permissions AerieOS's verbs
   need and no more: view channels, manage channels, manage roles, manage
   the server (for AutoMod), send and manage messages (for pins) and read
   their history.
3. Paste the token under **Bot token** and press **Connect**. Where the bot
   is in several servers, give the one's ID under **Server ID**.

The token is checked as a bot's, kept sealed under the install key, never
shown again and never handed to a session: the controller calls Discord's
API itself. A user account's token is refused, as Discord's terms refuse it.
**Forget** takes the token off this install; the bot stays in the server
until it is kicked there. The connection is on Controller settings'
**Connected services** with every other credential the install holds.

Connecting and forgetting are Space settings Write on the space, as is
applying a layout; anybody who sees the space may read its Discord view.

## The layout: deploy/discord.yml

The server as code, in the repository, committed like the rest of it:

```yaml
roles:
  - name: "@everyone"
    permissions: [view_channel, send_messages]
  - name: Moderators
    color: "#e67e22"
    hoist: true
    permissions: [manage_messages, kick_members]
categories:
  - name: Welcome
    channels:
      - name: rules
        topic: Read this first
        overwrites:
          - role: "@everyone"
            deny: [send_messages]
      - name: introductions
channels:
  - name: general
automod:
  - name: No invites
    keywords: ["discord.gg/*"]
pins:
  rules:
    - Be kind. No spam.
```

- **roles**: each by its name, with its color, whether it is shown apart
  (`hoist`) and mentionable, and its permissions by Discord's own names
  (`manage_messages`, `kick_members` and the rest). `@everyone` takes
  permissions alone. A bot's or an integration's own role is left alone.
- **categories** and **channels**: a channel's `kind` is `text` (the
  default), `voice`, `announcement`, `stage` or `forum`; a text channel's
  name is kept as Discord keeps it, in lower case with dashes. `overwrites`
  allow and deny permissions for a role in that channel or category.
- **automod**: keyword rules that block a message, each by its name.
- **pins**: messages the bot posts and pins in a channel. Only the bot's own
  pins are the layout's; a pin a person made is left as it is.

A field left out is its default: no topic, no overwrites, no permissions.

## Pull, Plan and Apply

The notebook's **Discord** view, in Ship, names the server and has three
presses:

- **Pull** writes the server as it stands into `deploy/discord.yml`,
  uncommitted, so a server that exists already is adopted rather than
  rebuilt. Over a file already there it asks first.
- **Plan** says what applying the file would change: each role, category,
  channel, AutoMod rule and pin added, changed or removed. A change that
  removes something, or grants or takes a permission (a role's, an
  overwrite's), is marked **asks**: a session's apply waits on a person for
  it, whatever its dial says.
- **Apply** makes every change in the plan, in order: roles first, then
  categories, channels and their permissions, AutoMod and pins, and what the
  file no longer names last. A person's Apply is all of it, after one
  question. Each change is on the audit log; Discord's rate limits are
  waited out.

The view keeps the space's last plans, who made each and whether it was
applied. A change Discord cannot make, a channel's kind, is said in the plan
and left: remove the channel and add it again.

## From a session

A session reaches its own space's server with `aerie discord`, relayed by
the controller:

- `aerie discord` says the server connected and the last plans;
- `aerie discord pull` writes the server into `deploy/discord.yml` in the
  session's tree;
- `aerie discord plan` prints what applying the tree's file would change,
  each change a person allows marked `!`;
- `aerie discord apply --why "..."` makes it so, under the space's **Agents
  may: Manage Discord**, deny by default: at ask the whole apply waits on the
  space's owner (or any administrator) on the bell, at auto the changes that
  ask nobody are made and the rest wait on a person; what removes, changes a
  permission or reaches members always waits. The bell's row lists every
  change, each that asks marked, for the person to read before Allow.

A session never connects or forgets a server, and never holds its token.
