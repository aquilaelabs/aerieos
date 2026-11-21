"""Apps a NAS runs (R164 step 2, R238): none is shipped, each kept from
the catalog or added by a person; a compose file is held to the
catalog's rules before it is kept; an app from before pack format 4 asks
for the folders of the six blanks its compose reads, and one of format 4
for the fields its bbapp.json declares, beside AerieOS's own; rendering
holds each value to its kind and makes a secret once, never again on an
edit."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nasapps  # noqa: E402

COMPOSE = """services:
  notes:
    image: ghcr.io/example/notes:2.4.1
    ports:
      - "${PORT}:8080"
    volumes:
      - ${DATA}/notes:/data
"""

# An app of format 4: its own folders, a secret, a choice and a switch, and
# AerieOS's time zone and port.
LEDGER = """services:
  ledger:
    image: ghcr.io/example/ledger:3.1.0
    environment:
      TZ: ${TZ}
      DB_PASSWORD: ${DB_PASSWORD}
      CURRENCY: ${CURRENCY}
      SIGNUPS: ${SIGNUPS}
    ports:
      - "${PORT}:8020"
      - "${SYNC_PORT}:7070"
    volumes:
      - ${BOOKS}:/books
"""
FIELDS = [{"var": "BOOKS", "kind": "folder", "label": "Its books", "default": "ledger/books", "example": "/mnt/tank/ledger"},
          {"var": "SYNC_PORT", "kind": "port", "label": "Sync port", "default": 7070},
          {"var": "DB_PASSWORD", "kind": "secret", "label": "Database password"},
          {"var": "CURRENCY", "kind": "choice", "label": "Currency", "default": "USD",
           "choices": [{"value": "EUR", "label": "Euro"}, {"value": "USD", "label": "US dollar"}]},
          {"var": "SIGNUPS", "kind": "switch", "label": "Others may sign up"}]
META = {"format": 4, "framework": "4.2", "fields": FIELDS}


class Check(unittest.TestCase):
    """What every compose file is held to, a person's own or the catalog's."""

    def test_a_compose_is_pinned_pulled_and_names_only_the_blanks_it_may(self):
        self.assertIn("paste", nasapps.check("")["error"])
        self.assertIn("services mapping", nasapps.check("x: 1\n")["error"])
        self.assertIn("not pinned", nasapps.check("services:\n  a:\n    image: foo\n")["error"])
        self.assertIn("not pinned", nasapps.check("services:\n  a:\n    image: foo:latest\n")["error"])
        self.assertIn("never built", nasapps.check("services:\n  a:\n    image: foo:1\n    build: .\n")["error"])
        self.assertIn("a runs privileged", nasapps.check("services:\n  a:\n    image: foo:1\n    privileged: true\n")["error"])
        self.assertIn("unknown blank SECRET", nasapps.check("services:\n  a:\n    image: foo:1\n    environment:\n      K: ${SECRET}\n    ports: ['${PORT}:1']\n")["error"])
        self.assertIn("${PORT}", nasapps.check("services:\n  a:\n    image: foo:1\n")["error"])
        seen = nasapps.check(COMPOSE)
        self.assertEqual(seen["blanks"], ["DATA", "PORT"])
        self.assertFalse(seen["media"])
        self.assertEqual(seen["services"][0]["image"], "ghcr.io/example/notes:2.4.1")

    def test_a_compose_is_written_out_plainly_so_look_and_docker_read_the_same_file(self):
        # Each of these says one thing to the reader this check uses and
        # another to Docker: a merged key the check never sees, a service in
        # braces whose image no Update moves and no card's word counts.
        tail = "    ports:\n      - \"${PORT}:80\"\n"
        for what, text in (
                ("a merge key", "x-more: &more {privileged: true, pid: host}\nservices:\n  a:\n    image: x/y:1.0\n    <<: *more\n" + tail),
                ("an alias", "services:\n  a:\n    image: x/y:1.0\n    volumes: *v\n" + tail),
                ("an anchor", "services:\n  a: &a\n    image: x/y:1.0\n" + tail),
                ("a tag", "services:\n  a:\n    image: !!str x/y:1.0\n" + tail),
                ("a service in braces", "services:\n  a:\n    image: x/y:1.0\n" + tail + "  side: {image: \"evil/thing:1.0\"}\n")):
            self.assertIn("write it out plainly", nasapps.check(text).get("error", ""), what)
        # What only looks like one is taken: a comment, a quoted word, a
        # blank, a list in brackets, an address with an ampersand.
        plain = ("services:\n  a:\n    image: \"x/y:1.0\"   # the app & its *friends* {here}\n"
                 "    command: [\"--name\", \"${DATA}\", \"a&b\", \"*.txt\"]\n"
                 "    environment:\n      - A=b&c\n      - G=*.txt\n      - URL=http://h/?a=1&b=2\n" + tail)
        self.assertNotIn("error", nasapps.check(plain))
        self.assertEqual((nasapps.compose_marked(plain), nasapps.compose_plain(plain, {"a": {"image": "x/y:1.0"}})), ("", ""))
        self.assertIn("a line of its own", nasapps.compose_plain(plain, {"a": {"image": "x/y:1.0"}, "b": {"image": "z/w:2"}}))

    def test_what_reaches_the_host_is_refused_by_what_it_does_not_by_its_word(self):
        # Each passed the check that knew `privileged` alone, with Look
        # showing its image, ports and volumes and nothing of the rest.
        d = "sha256:" + "a" * 64
        head = f"services:\n  web:\n    image: nginx:1.27@{d}\n    ports:\n      - \"${{PORT}}:80\"\n"
        for what, extra, top, said in (
                ("every capability", "    cap_add: [ALL]\n    pid: host\n", "", "takes kernel capabilities: ALL"),
                ("the host's processes", "    pid: host\n", "", "host's process namespace"),
                ("a loosened profile", "    security_opt: [seccomp:unconfined]\n", "", "drops a security profile"),
                ("a profile by its label", "    security_opt:\n      - label:type:spc_t\n", "", "no-new-privileges is the one"),
                ("a disk", "    devices:\n      - /dev/sda:/dev/sda\n", "", "host devices: /dev/sda"),
                ("the controller's network", "    network_mode: container:aerie\n", "", "joins the network of container:aerie"),
                ("a network by its name", "    network_mode: aerie_default\n", "", "network_mode is host, bridge or none"),
                ("another container's volumes", "    volumes_from: [aerie]\n", "", "takes every volume of aerie"),
                ("a file Docker reads beside it", "", "include:\n  - /etc/other.yml\n", "include is not a key"),
                ("a service from another file", "    extends:\n      file: /x/y.yml\n      service: z\n", "", "extends is not a key"),
                ("a host file as its environment", "    env_file: /etc/shadow\n", "", "env_file is not a key"),
                ("a GPU by deploy", "    deploy:\n      resources:\n        limits:\n          cpus: \"1\"\n", "", "deploy is not a key"),
                ("another's volume", "    volumes:\n      - cfg:/c\n", "volumes:\n  cfg:\n    external: true\n", "external is not a key"),
                ("a host path as a volume", "    volumes:\n      - cfg:/c\n", "volumes:\n  cfg:\n    driver_opts:\n      o: bind\n      device: /\n",
                 "driver_opts is not a key"),
                ("a volume by another driver", "    volumes:\n      - cfg:/c\n", "volumes:\n  cfg:\n    driver: rclone\n", "its driver is local"),
                ("another's network", "", "networks:\n  outer:\n    external: true\n", "external is not a key"),
                ("secrets from a host file", "", "secrets:\n  k:\n    file: /etc/shadow\n", "secrets is not a key")):
            self.assertIn(said, nasapps.check(top + head + extra).get("error", ""), what)
        # What an app of its own writes stays its own to write.
        plain = ("version: \"3.8\"\nx-note: kept\n" + head + "    restart: unless-stopped\n    security_opt:\n      - no-new-privileges:true\n"
                 "    cap_drop: [ALL]\n    networks: [inner]\n    volumes:\n      - data:/data\n    healthcheck:\n      test: [\"CMD\", \"true\"]\n"
                 "volumes:\n  data:\nnetworks:\n  inner:\n    internal: true\n")
        self.assertNotIn("error", nasapps.check(plain))
        # The machine's own network, said in bbapp.json, is the app's to ask for.
        host = f"services:\n  web:\n    image: nginx:1.27@{d}\n    network_mode: host\n"
        self.assertNotIn("error", nasapps.check(host, [], "host"))

    def test_a_dev_instance_s_warnings_and_an_app_s_refusals_are_one_reader(self):
        import packformat
        import devapp
        sv = {"privileged": True, "cap_add": ["NET_ADMIN"], "network_mode": "container:db"}
        phrases = [p for _k, p in packformat.service_reach("app", sv)]
        with tempfile.TemporaryDirectory() as ws:
            old = devapp.WORKSPACE
            devapp.WORKSPACE = Path(ws)
            try:
                self.assertEqual(devapp.risks("web", {"services": {"app": sv}}), phrases)
            finally:
                devapp.WORKSPACE = old
        self.assertEqual(nasapps.check("services:\n  app:\n    image: x/y:1\n    cap_add: [NET_ADMIN]\n    ports: ['${PORT}:1']\n")["error"],
                         "service " + phrases[1])

    def test_an_image_may_carry_the_digest_it_is_pulled_by(self):
        d = "sha256:" + "4f" * 32

        def said(image):
            return nasapps.check(f"services:\n  a:\n    image: {image}\n    ports: ['${{PORT}}:1']\n")
        for held in (f"ghcr.io/example/notes:2.4.1@{d}", f"notes@{d}", f"notes:latest@{d}", f'"lscr.io/example/notes:2.4.1@{d}"'):
            seen = said(held)
            self.assertNotIn("error", seen, held)
            self.assertEqual(seen["services"][0]["image"], held.strip('"'), "the reference is kept whole: its digest is what is pulled")
        for loose, why in ((f"notes:1@sha256:{'4f' * 31}", "no image reference"), (f"notes:1@md5:{'4f' * 32}", "no image reference"),
                           (f"notes:1@sha256:{'4F' * 32}", "no image reference"), (f"notes:1@{d}@{d}", "no image reference"),
                           ("notes:1 extra", "no image reference"), ("notes:latest", "not pinned"), ("notes", "not pinned")):
            self.assertIn(why, said(loose).get("error", ""), loose)

    def test_a_format_5_app_names_every_image_by_digest_and_an_earlier_one_means_what_it_meant(self):
        d = "sha256:" + "4f" * 32
        both = f"services:\n  web:\n    image: ex/web:2@{d}\n    ports: ['${{PORT}}:1']\n  db:\n    image: ex/db:16\n"
        seen = nasapps.check_app({"format": 5}, both)
        self.assertIn("service db: ex/db:16 names no digest", seen["error"], "refused, with the image named")
        self.assertNotIn("error", nasapps.check_app({"format": 5}, both.replace("ex/db:16", f"ex/db:16@{d}")))
        for earlier in ({}, {"format": 4}, {"format": 3}):
            self.assertNotIn("error", nasapps.check_app(earlier, both), earlier)
        self.assertEqual(nasapps.held_of({"compose": both})["word"], "open", "an app reads pinned only when every image has a digest")
        self.assertIn("ex/db:16", nasapps.held_of({"compose": both})["why"])
        self.assertEqual(nasapps.held_of({"compose": both.replace("ex/db:16", f"ex/db:16@{d}")}),
                         {"word": "pinned", "why": "every image it runs is named by the digest its entry carries"})


class Fields(unittest.TestCase):
    """An app's own fields (pack format 4): declared in bbapp.json, each
    read by its compose, never one of AerieOS's own."""

    def test_each_kind_is_held_to_its_shape_and_given_its_default(self):
        errors = []
        got = {f["var"]: f for f in nasapps.fields_of(FIELDS, errors)}
        self.assertEqual(errors, [])
        self.assertEqual((got["BOOKS"]["default"], got["BOOKS"]["required"], got["BOOKS"]["example"]), ("ledger/books", True, "/mnt/tank/ledger"))
        self.assertEqual((got["SYNC_PORT"]["default"], got["SYNC_PORT"]["required"]), (7070, True))
        self.assertEqual((got["DB_PASSWORD"]["default"], got["DB_PASSWORD"]["required"]), ("", False), "a secret is made, never asked for")
        self.assertEqual(got["CURRENCY"]["default"], "USD")
        self.assertIs(got["SIGNUPS"]["default"], False)
        for bad, said in (({"var": "PORT", "kind": "port", "label": "p", "default": 1}, "one of AerieOS's own"),
                          ({"var": "lower", "kind": "text", "label": "x"}, "var is the variable"),
                          ({"var": "X", "kind": "file", "label": "x"}, "kind is one of"),
                          ({"var": "X", "kind": "text", "label": ""}, "label is what the form calls it"),
                          ({"var": "X", "kind": "folder", "label": "x", "default": "../etc"}, "a folder under the pool or share"),
                          ({"var": "X", "kind": "port", "label": "x", "default": 70000}, "1 to 65535"),
                          ({"var": "X", "kind": "choice", "label": "x", "choices": [{"value": "a"}]}, "choices lists 2 to 24"),
                          ({"var": "X", "kind": "text", "label": "x", "default": "a\nb"}, "one line")):
            errors = []
            nasapps.fields_of([bad], errors)
            self.assertTrue(errors and said in errors[0], (bad, errors))
        errors = []
        nasapps.fields_of([FIELDS[0], FIELDS[0]], errors)
        self.assertIn("and once", errors[0])
        for empty in ([], None, [{}] * 17):
            errors = []
            nasapps.fields_of(empty, errors)
            self.assertIn("a list of 1 to 16", errors[0])

    def test_a_manifest_says_format_4_for_what_came_with_it(self):
        self.assertEqual(nasapps.check_app({**META, "format": 3, "framework": "3.2"}, LEDGER)["error"],
                         'fields is pack format 4\'s: the manifest says "format": 4')
        self.assertIn("network is pack format 4's", nasapps.check_app({"network": "host"}, COMPOSE)["error"])
        self.assertIn("going is pack format 4's", nasapps.check_app({"going": "x"}, COMPOSE)["error"])
        seen = nasapps.check_app(META, LEDGER)
        self.assertNotIn("error", seen, seen)
        self.assertEqual([f["var"] for f in seen.get("fields", []) if isinstance(f, dict)], ["BOOKS", "SYNC_PORT", "DB_PASSWORD", "CURRENCY", "SIGNUPS"])
        self.assertEqual(nasapps.check_app({}, COMPOSE)["blanks"], ["DATA", "PORT"], "one with no fields keeps the six blanks")

    def test_every_blank_is_declared_or_aerieos_own_and_every_field_read(self):
        self.assertIn("unknown blank DATA", nasapps.check_app(META, LEDGER + "      - ${DATA}:/x\n")["error"])
        self.assertIn("field CURRENCY is declared and compose.yml never reads it",
                      nasapps.check_app(META, LEDGER.replace("      CURRENCY: ${CURRENCY}\n", ""))["error"])
        self.assertIn("${PORT}", nasapps.check_app(META, LEDGER.replace('      - "${PORT}:8020"\n', ""))["error"])

    def test_an_app_on_the_machine_s_own_network_says_so_and_publishes_nothing(self):
        host = "services:\n  ha:\n    image: ghcr.io/example/ha:2025.5.3\n    network_mode: host\n    volumes:\n      - ${CONFIG}:/config\n"
        conf = [{"var": "CONFIG", "kind": "folder", "label": "Its settings", "default": "apps/ha"}]
        self.assertEqual(nasapps.check_app({"format": 4, "network": "host", "fields": conf}, host).get("network"), "host")
        self.assertIn("said in bbapp.json too", nasapps.check_app({"format": 4, "fields": conf}, host)["error"])
        self.assertIn("publishes no ports", nasapps.check_app({"format": 4, "network": "host", "fields": conf},
                                                              host + "    ports:\n      - '8123:8123'\n")["error"])
        self.assertIn("answers on its own port", nasapps.check_app({"format": 4, "network": "host", "fields": conf},
                                                                   host.replace("/config\n", "/config\n    environment:\n      P: ${PORT}\n"))["error"])
        self.assertIn('network is "host"', nasapps.check_app({"format": 4, "network": "bridge", "fields": conf}, host)["error"])

    def test_a_router_field_names_the_variable_its_key_fills(self):
        rf = {"var": "LLM_URL", "kind": "router", "label": "Model router", "key": "LLM_KEY", "path": "/v1"}
        compose = LEDGER.replace("      SIGNUPS: ${SIGNUPS}\n", "      SIGNUPS: ${SIGNUPS}\n      LLM_BASE: ${LLM_URL}\n      LLM_API_KEY: ${LLM_KEY}\n")
        seen = nasapps.check_app({**META, "fields": FIELDS + [rf]}, compose)
        self.assertNotIn("error", seen, seen)
        self.assertEqual({k: seen["fields"][-1].get(k) for k in ("kind", "key", "path")}, {"kind": "router", "key": "LLM_KEY", "path": "/v1"})
        self.assertIn("unknown blank LLM_KEY", nasapps.check_app(META, compose.replace("      LLM_BASE: ${LLM_URL}\n", ""))["error"])
        for bad, said in (({**rf, "key": ""}, "names the variable its key fills"), ({**rf, "key": "PORT"}, "names the variable its key fills"),
                          ({**rf, "key": "LLM_URL"}, "names the variable its key fills"), ({**rf, "path": "v1"}, "path is what")):
            errors = []
            nasapps.fields_of([bad], errors)
            self.assertTrue(errors and said in errors[0], (bad, errors))
        a = {"id": "ledger", "port": 8020, "compose": compose, "fields": seen["fields"]}
        asked = []
        at = lambda nid: asked.append(nid) or ({"url": "http://10.0.0.5:4000", "key": "sk-own"} if nid == "n1" else {"error": "no router there"})  # noqa: E731
        env = nasapps.env_values(nasapps.render_with(a, {"BOOKS": "/mnt/a", "LLM_URL": "n1"}, router=at)["env"])
        self.assertEqual((env["LLM_URL"], env["LLM_KEY"], asked), ("http://10.0.0.5:4000/v1", "sk-own", ["n1"]))
        self.assertIn("Model router: no router there", nasapps.render_with(a, {"BOOKS": "/mnt/a", "LLM_URL": "n9"}, router=at)["error"])
        env = nasapps.env_values(nasapps.render_with(a, {"BOOKS": "/mnt/a", "LLM_URL": ""}, router=at)["env"])
        self.assertEqual((env["LLM_URL"], env["LLM_KEY"]), ("", ""), "none picked: both empty")
        a["fields"][-1]["required"] = True
        self.assertIn("pick the model router", nasapps.render_with(a, {"BOOKS": "/mnt/a", "LLM_URL": ""}, router=at)["error"])
        self.assertIn("LLM_KEY is set in", nasapps.extra_env(a, "LLM_KEY=x\n")[1])

    def test_a_going_app_says_what_takes_its_place(self):
        self.assertEqual(nasapps.check_app({"format": 4, "going": "  install  Sonarr  instead "}, COMPOSE)["going"], "install Sonarr instead")
        self.assertIn("going says", nasapps.check_app({"format": 4, "going": "x" * 201}, COMPOSE)["error"])

    def test_an_about_past_the_cards_200_is_said_to_its_author(self):
        # The card keeps 200 characters; past that it was cut mid-word with
        # nothing said to the catalog's author (B932).
        self.assertNotIn("error", nasapps.check_app({"about": "a word " * 28}, COMPOSE))
        self.assertIn("about says", nasapps.check_app({"about": "a word " * 29}, COMPOSE)["error"])


class NoneShipped(unittest.TestCase):
    """No app is shipped (R238 step 1): one is offered because the catalog's
    signed index lists it, or because a person added it, and for no other
    reason."""

    def test_with_nothing_kept_nothing_is_offered(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        nasapps.configure(state=d.name, write_json=lambda p, o: Path(p).write_text(json.dumps(o)))
        self.assertFalse(hasattr(nasapps, "APPS"), "the table is gone")
        self.assertEqual(nasapps.catalog(), [])
        self.assertIn("no app called jellyfin", nasapps.render("jellyfin", {})["error"])

    def test_an_id_a_shipped_app_had_is_anybody_s_now(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        nasapps.configure(state=d.name, write_json=lambda p, o: Path(p).write_text(json.dumps(o)))
        self.assertEqual(nasapps.add("jellyfin", "Jellyfin", "mine", 8096, COMPOSE).get("app"), "jellyfin")
        self.assertEqual([(a["id"], a["tier"]) for a in nasapps.catalog()], [("jellyfin", "sideloaded")])


class MadeBefore(unittest.TestCase):
    """A container made from an app while AerieOS shipped it keeps running
    and keeps its Configure: what it needs of its app is beside its own
    compose file (app.json), never in a table."""
    COMPOSE = ("services:\n  jellyfin:\n    image: jellyfin/jellyfin:10.10.7\n    restart: unless-stopped\n    user: \"${PUID}:${PGID}\"\n"
               "    environment:\n      TZ: ${TZ}\n    ports:\n      - \"${PORT}:8096\"\n    volumes:\n      - ${DATA}/config:/config\n"
               "      - ${DATA}/cache:/cache\n      - ${MEDIA}:/media:ro\n")
    # As New container kept it then (nasapps.snapshot of the shipped row).
    SNAP = {"id": "jellyfin", "name": "Jellyfin", "maker": "Jellyfin", "tier": "official", "own": ["PUID", "PGID", "TZ", "PORT"], "network": "",
            "port": 8096, "commit": "", "at": 0,
            "fields": [{"var": "DATA", "kind": "folder", "label": "Its settings and cache", "help": "its own folder", "required": True, "default": "apps/jellyfin"},
                       {"var": "MEDIA", "kind": "folder", "label": "Its media", "help": "what it serves", "required": True, "default": "", "example": "/mnt/tank/media"}]}
    ENV = "DATA=/mnt/tank/apps/jellyfin\nMEDIA=/mnt/tank/media\nPUID=1000\nPGID=1000\nTZ=Europe/Paris\nPORT=8096\nJELLYFIN_PUBLISHED_URL=https://tv.example.com\n"

    def setUp(self):
        import containers
        import devapp
        from unittest import mock
        self.containers = containers
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        nasapps.configure(state=self.tmp.name, write_json=lambda p, o: Path(p).write_text(json.dumps(o)))
        home = Path(self.tmp.name) / "containers" / "jellyfin"
        home.mkdir(parents=True)
        (home / "docker-compose.yml").write_text(self.COMPOSE)
        (home / "app.json").write_text(json.dumps(self.SNAP))
        for target, name, value in ((devapp, "containers_dir", lambda name: Path(self.tmp.name) / "containers" / name),
                                    (containers, "apps_held", lambda nid, but="": {"names": ["jellyfin"], "ports": [], "apps": []})):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_configure_opens_on_its_fields_with_nothing_in_the_library(self):
        self.assertEqual(nasapps.catalog(), [], "no app is shipped and none is kept")
        view = self.containers.app_view("jellyfin", self.ENV)
        self.assertEqual([f["var"] for f in view["fields"]], ["DATA", "MEDIA"])
        self.assertEqual(view["values"], {"DATA": "/mnt/tank/apps/jellyfin", "MEDIA": "/mnt/tank/media", "PUID": "1000", "PGID": "1000",
                                          "TZ": "Europe/Paris", "PORT": "8096"}, "each value read back from its environment")
        self.assertEqual(view["extra"], "JELLYFIN_PUBLISHED_URL=https://tv.example.com\n")
        self.assertIsNone(view["newer"], "nothing newer is offered where the Library holds no app of that name")

    def test_a_save_makes_its_environment_from_what_it_kept(self):
        snap = self.containers.app_of("jellyfin")
        req = {"values": {"DATA": "/mnt/tank/apps/jellyfin", "MEDIA": "/mnt/tank/films"}, "ids": "1000:1000", "tz": "Europe/Paris", "port": 8097,
               "env": "JELLYFIN_PUBLISHED_URL=https://tv.example.com\n"}
        made = self.containers.app_made(req, {**snap, "compose": self.containers._compose_of("jellyfin")}, "n1", nasapps.env_values(self.ENV), "jellyfin")
        self.assertNotIn("error", made)
        self.assertEqual(made["compose"], self.COMPOSE, "the file it was made with")
        env = nasapps.env_values(made["env"])
        self.assertEqual((env["MEDIA"], env["PORT"], env["JELLYFIN_PUBLISHED_URL"]), ("/mnt/tank/films", "8097", "https://tv.example.com"))
        self.assertEqual(made["app"]["id"], "jellyfin")


class Render(unittest.TestCase):
    """The environment New container makes from the panel: each value held
    to its field's kind, a secret made once and kept on every edit."""

    def app(self):
        return {"id": "ledger", "port": 8020, "compose": LEDGER, "fields": nasapps.check_app(META, LEDGER)["fields"]}

    def test_values_are_held_to_their_kinds(self):
        a, ok = self.app(), {"BOOKS": "/mnt/tank/ledger/"}
        r = nasapps.render_with(a, ok, tz="Europe/Paris")
        env = nasapps.env_values(r["env"])
        self.assertEqual({k: env[k] for k in ("BOOKS", "SYNC_PORT", "CURRENCY", "SIGNUPS", "TZ", "PORT")},
                         {"BOOKS": "/mnt/tank/ledger", "SYNC_PORT": "7070", "CURRENCY": "USD", "SIGNUPS": "false", "TZ": "Europe/Paris", "PORT": "8020"},
                         "a field the panel did not send takes its default; a folder loses its last slash")
        self.assertNotIn("PUID", env, "AerieOS's own are asked for only where the compose reads them")
        self.assertGreaterEqual(len(env["DB_PASSWORD"]), 20, "a secret not given is made")
        for values, said in (({}, "Its books is a folder"), ({"BOOKS": "/home/me"}, "Its books is a folder"),
                             ({**ok, "SYNC_PORT": "x"}, "Sync port is a port, a number"), ({**ok, "SYNC_PORT": 0}, "1 to 65535"),
                             ({**ok, "CURRENCY": "GBP"}, "Currency is one of Euro, US dollar"),
                             ({**ok, "DB_PASSWORD": "a$b"}, "Database password is one line")):
            self.assertIn(said, nasapps.render_with(a, values).get("error", ""), values)
        self.assertIn("Region/City", nasapps.render_with(a, ok, tz="not a zone!")["error"])
        self.assertIn("1 to 65535", nasapps.render_with(a, ok, port=70000)["error"])
        self.assertEqual(nasapps.env_values(nasapps.render_with(a, {**ok, "SIGNUPS": True})["env"])["SIGNUPS"], "true")

    def test_a_secret_is_made_once_and_kept_on_an_edit(self):
        a = self.app()
        first = nasapps.render_with(a, {"BOOKS": "/mnt/tank/ledger"})["values"]
        again = nasapps.render_with(a, {"BOOKS": "/mnt/tank/books2"}, keep=first)["values"]
        self.assertEqual((again["DB_PASSWORD"], again["BOOKS"]), (first["DB_PASSWORD"], "/mnt/tank/books2"))
        self.assertEqual(nasapps.render_with(a, {"BOOKS": "/mnt/a", "DB_PASSWORD": "chosen"})["values"]["DB_PASSWORD"], "chosen")

    def test_a_field_a_newer_definition_added_takes_its_default_on_an_edit(self):
        a = self.app()
        was = {"BOOKS": "/mnt/tank/ledger", "SYNC_PORT": "7171", "DB_PASSWORD": "s", "CURRENCY": "EUR", "SIGNUPS": "true", "TZ": "UTC", "PORT": "8020"}
        a["fields"] = a["fields"] + [{"var": "THEME", "kind": "text", "label": "Theme", "default": "dark", "help": "", "required": False}]
        got = nasapps.render_with(a, {}, keep=was)["values"]
        self.assertEqual((got["SYNC_PORT"], got["CURRENCY"], got["THEME"]), ("7171", "EUR", "dark"))

    def test_an_app_from_before_format_4_asks_for_the_folders_its_compose_reads(self):
        mine, own = nasapps.app_fields({"id": "notes", "compose": COMPOSE})
        self.assertEqual(([f["var"] for f in mine], own, mine[0]["default"]), (["DATA"], ["PORT"], "apps/notes"))
        both = COMPOSE.replace("/data\n", "/data\n      - ${MEDIA}:/media\n")
        self.assertEqual([f["var"] for f in nasapps.app_fields({"id": "x", "compose": both})[0]], ["DATA", "MEDIA"])
        r = nasapps.render_with({"id": "x", "port": 80, "compose": both, "secrets": ["DB_PASSWORD"]}, {"DATA": "/mnt/a", "MEDIA": "/mnt/m"}, port=81)
        self.assertEqual(r["env"].split("\n")[:3], ["DATA=/mnt/a", "MEDIA=/mnt/m", "PORT=81"])
        self.assertIn("DB_PASSWORD=", r["env"], "a secret a record from before names is made as a secret field is")

    def test_a_port_another_container_holds_is_taken_though_nothing_answers_on_it(self):
        a, was = self.app(), nasapps.answers_fn
        nasapps.answers_fn = lambda node, port: False
        try:
            values = nasapps.render_with(a, {"BOOKS": "/mnt/tank/ledger"})["values"]
            self.assertEqual(nasapps.ports_taken(a, values, "n_x"), [], "nothing answers and nothing holds it")
            self.assertEqual(nasapps.ports_taken(a, values, "n_x", held=[8020, 9000]), [8020],
                             "one still pulling its image holds its port all the same")
            self.assertEqual(nasapps.ports_taken(a, values, "n_x", keep=values, held=[8020]), [],
                             "its own port, on an edit, is its own")
        finally:
            nasapps.answers_fn = was

    def test_an_environment_file_reads_back_as_values(self):
        self.assertEqual(nasapps.env_values("A=1\n# no\nB=x=y\nlower=2\nA=3\n\n"), {"A": "3", "B": "x=y"})


class Another(unittest.TestCase):
    """A second container from the same app (each press on the Library
    makes another): refused only where it could not answer."""

    def test_a_second_on_the_machine_s_own_network_is_refused_on_that_node_alone(self):
        import containers
        from unittest import mock
        compose = "services:\n  beacon:\n    image: ghcr.io/example/beacon:1.0.0\n    network_mode: host\n    volumes:\n      - ${DATA}:/data\n"
        fields = [{"var": "DATA", "kind": "folder", "label": "Its data", "default": "apps/beacon", "help": "", "required": True}]
        a = {"id": "beacon", "name": "Beacon", "port": 8123, "network": "host", "compose": compose,
             "fields": nasapps.check_app({"format": 4, "framework": "4.2", "fields": fields, "network": "host"}, compose)["fields"]}
        req = {"values": {"DATA": "/mnt/tank/beacon"}}
        with mock.patch.object(containers, "apps_held", return_value={"names": ["beacon"], "ports": [], "apps": ["beacon"]}):
            said = containers.app_made(req, a, "n_x", name="beacon-2").get("error", "")
        self.assertIn("another on that node already does: make this one on another node", said)
        with mock.patch.object(containers, "apps_held", return_value={"names": ["beacon"], "ports": [], "apps": []}):
            self.assertNotIn("error", containers.app_made(req, a, "n_y", name="beacon-2"), "on a node without one it is made")


class Sideloaded(unittest.TestCase):
    """An app of a person's own (R170 step 3): checked before it is kept,
    kept at tier sideloaded, rendered as the catalog's are."""
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        nasapps.configure(state=self.d.name, write_json=lambda p, o: Path(p).write_text(json.dumps(o)))

    def tearDown(self):
        nasapps.configure(state="/nonexistent", write_json=None)
        self.d.cleanup()

    def test_added_kept_rendered_and_removed(self):
        self.assertIn("id is", nasapps.add("Notes!", "x", "y", 80, COMPOSE)["error"])
        self.assertIn("port", nasapps.add("notes", "Notes", "my notes", "x", COMPOSE)["error"])
        r = nasapps.add("notes", "Notes", "my notes", 8080, COMPOSE, by="ann")
        self.assertEqual(r["app"], "notes")
        self.assertIn("added already", nasapps.add("notes", "Notes", "my notes", 8080, COMPOSE)["error"])
        row = next(a for a in nasapps.catalog() if a["id"] == "notes")
        self.assertEqual((row["tier"], row["name"], row["port"], row["media"], row["by"]), ("sideloaded", "Notes", 8080, False, "ann"))
        self.assertEqual(([f["var"] for f in row["fields"]], row["own"], row["compose"]), (["DATA"], ["PORT"], COMPOSE))
        self.assertEqual(nasapps.source("notes")["compose"], COMPOSE)
        out = nasapps.render("notes", {"DATA": "/mnt/tank/apps/notes"}, port=8081)
        self.assertEqual(out["compose"], COMPOSE)
        self.assertEqual(out["env"], "DATA=/mnt/tank/apps/notes\nPORT=8081\n")
        self.assertIn("no app called", nasapps.render("nope", {})["error"])
        self.assertTrue(nasapps.add("notes", "Notes 2", "my notes", 8080, COMPOSE, replace=True)["replaced"])
        self.assertEqual(nasapps.source("notes")["name"], "Notes 2")
        self.assertEqual(nasapps.remove("notes"), {"ok": True})
        self.assertIn("error", nasapps.remove("notes"))
        self.assertFalse(any(a["id"] == "notes" for a in nasapps.catalog()))


if __name__ == "__main__":
    unittest.main()
