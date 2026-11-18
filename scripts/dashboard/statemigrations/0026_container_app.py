"""State 25 to 26: a container made from an app keeps the app beside it.

New container from the Library keeps, beside a container's compose file,
which app it was made from, at which pin, and the fields that app declared
(containers/NAME/app.json), so its Configure opens on the app's panel with
each value read back from the container's environment. A container made
before has no such file and is edited as a written container, as it was.
Nothing is changed here: the state moves so that a copy of /config is taken
before the first one is written, and so that a build from before this one
refuses to start on a /config whose containers it would edit around their
app. Idempotent. Never edited once shipped (stateversion.py).
"""


def run(ctx):
    return
