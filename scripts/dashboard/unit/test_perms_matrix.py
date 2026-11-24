"""Every action against every area at every level (R277, the operator, 24 Nov:
'there's been a lot of changes and I'm worried it's drifted').

A role holding one area at one level, on a space or Everywhere, is asked
about every action the server checks (roles.CAP_AREA), on its own space,
on another and on none, and each answer is held to what the areas say: an
action is its area's, Write holds Read, a role given on a space holds
there and nowhere else, a global area is an Everywhere role's alone, and
an area held node by node holds on the nodes named. A new action, or an
area moved, shows here as the cell that changed."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import roles  # noqa: E402


def on_project(u, name):
    return name in (u.get("projects") or [])


class Matrix(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        roles.configure(state=self.tmp, write_json=lambda p, d: __import__("pathlib").Path(p).write_text(json.dumps(d)))

    def g(self, u, action, project=None, **kw):
        return bool(roles.granted(u, action, project, on_project, **kw))

    @staticmethod
    def expected(action, area, level, scope, project):
        """What the areas promise: the action's own area, at its level or
        Write, held on the space the role is given on, a global area only
        Everywhere, and an action reaching every space at once only from an
        Everywhere role."""
        want_area, need = roles.CAP_AREA[action]
        if want_area != area or (need == "write" and level != "write"):
            return False
        if scope == "global":
            return True
        if area not in roles.PROJECT_AREAS or action in roles.EVERYWHERE_ONLY:
            return False
        return project in ("alpha", None)

    def test_every_action_follows_its_area_level_and_scope(self):
        wrong = []
        for area in roles.AREA_KEYS:
            for level in roles.LEVELS:
                for scope in roles.ROLE_SCOPES:
                    if scope == "projects" and area not in roles.PROJECT_AREAS:
                        # A global area is not one a role on a space may hold.
                        continue
                    name = f"m {area} {level} {scope}"[:40]
                    self.assertNotIn("error", roles.set_role(name, scope=scope, perms={area: level}), name)
                    u = ({"name": "x", "role": "user", "roles": [name], "projects": ["alpha"]} if scope == "global"
                         else {"name": "x", "role": "user", "roles": [], "projects": ["alpha"], "project_roles": {"alpha": [name]}})
                    for action in roles.CAP_AREA:
                        for project in ("alpha", "beta", None):
                            got, want = self.g(u, action, project), self.expected(action, area, level, scope, project)
                            if got != want:
                                wrong.append(f"{name} / {action} on {project}: got {got}, want {want}")
                    roles.remove(name)
        self.assertEqual(wrong, [], "\n".join(wrong[:40]))

    def test_a_role_on_a_space_holds_no_global_area(self):
        # Set with one, it keeps none of it: a global area is only ever an
        # Everywhere role's (the areas' rule since R152).
        roles.set_role("sneak", scope="projects", perms={"projects": "read", "controller": "write", "accounts": "write"})
        u = {"name": "x", "role": "user", "roles": [], "projects": ["alpha"], "project_roles": {"alpha": ["sneak"]}}
        for action in ("controller", "admin", "debug", "command-pin"):
            self.assertFalse(self.g(u, action, "alpha") or self.g(u, action), action)

    def test_an_area_held_node_by_node_holds_on_the_nodes_named(self):
        self.assertNotIn("error", roles.set_role("n1", scope="global", perms={"nodes": "write", "install": "write", "jobs": "read"},
                                                 only={"nodes": {"n_1": "write"}, "install": {"n_1": "read"}}))
        u = {"name": "x", "role": "user", "roles": ["n1"], "projects": []}
        self.assertTrue(self.g(u, "nodes-write", node="n_1"))
        self.assertFalse(self.g(u, "nodes-write", node="n_2"))
        self.assertFalse(self.g(u, "toolchains-write", node="n_1"), "Read on n_1 is not Write")
        self.assertFalse(self.g(u, "toolchains-write", node="n_2"))
        self.assertFalse(self.g(u, "jobs", node="n_1"), "jobs Read is not running one")

    def test_an_action_of_no_area_of_its_own_is_work_on_the_space(self):
        # roadmap, bugs, pending and the rest: Spaces Write on the space.
        roles.set_role("rd", scope="projects", perms={"projects": "read"})
        roles.set_role("wr", scope="projects", perms={"projects": "write"})
        rd = {"name": "r", "role": "user", "roles": [], "projects": ["alpha"], "project_roles": {"alpha": ["rd"]}}
        wr = {"name": "w", "role": "user", "roles": [], "projects": ["alpha"], "project_roles": {"alpha": ["wr"]}}
        for action in ("roadmap", "bugs", "pending", "rules", "wiki"):
            self.assertNotIn(action, roles.CAP_AREA, action)
            self.assertFalse(self.g(rd, action, "alpha"), action)
            self.assertTrue(self.g(wr, action, "alpha"), action)
            self.assertFalse(self.g(wr, action, "beta"), action)

    def test_every_action_names_a_real_area_and_level(self):
        for action, (area, level) in roles.CAP_AREA.items():
            self.assertIn(area, roles.AREA_KEYS, action)
            self.assertIn(level, roles.LEVELS, action)


if __name__ == "__main__":
    unittest.main()
