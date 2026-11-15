-- 0009: the sessions a person asked to end on a node, kept until its
-- agent's next poll takes them (R227 step 13). They were held in memory, so
-- an End pressed just before the controller restarted was forgotten, and the
-- row it took off the page came back with its session still running.

CREATE TABLE kills (
    node_id TEXT NOT NULL,
    name    TEXT NOT NULL,
    at      REAL NOT NULL,
    PRIMARY KEY (node_id, name)
);
