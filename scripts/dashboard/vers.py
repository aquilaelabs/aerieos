"""A dotted version as something that sorts: one function, on its own so
that any module may import it."""


def vkey(v):
    """A version as a tuple that sorts as versions do: 1.10.0 above 1.9.3.
    Every part must be a number, so a caller matches the shape first."""
    return tuple(int(x) for x in v.split("."))
