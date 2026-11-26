"""The refusals every module says alike (R287 step 2, the operator's words
pass of 25 Nov): one sentence for each situation, so a person reads one
wording for one thing wherever it is met, and unit/test_refusals.py holds
every module to it. A missing space was said three ways (not a space,
unknown space, no such space) and a missing account two."""

NO_SPACE = "not a space"
NO_ACCOUNT = "not an account"


def no_space(name=""):
    """A space asked for that is not one, named where the asker named it."""
    return f"{NO_SPACE}: {name}" if name else NO_SPACE


def no_account(name=""):
    """An account asked for that is not one, named where it was named."""
    return f"{NO_ACCOUNT}: {name}" if name else NO_ACCOUNT
