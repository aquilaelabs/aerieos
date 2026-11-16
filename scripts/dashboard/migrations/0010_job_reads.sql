-- 0010: the job reads use indexes (R228 step 4). Every read of the jobs
-- table but the active ones scanned it whole and sorted what it found: the
-- Jobs page, a node's last job of a kind, a space's compose jobs, and the
-- node list's last system job on every revisions poll. At 12,000 rows each
-- was 5 to 30 ms under the store's one lock.
--
-- In order: the Jobs page and Home (newest first, rowid breaking the tie); a
-- node's jobs of a kind (toolchains, images, agent updates); a node's jobs
-- still to finish, which without its own index were read through the one
-- before, every job the node ever ran; a space's jobs
-- of a kind (its containers' compose jobs); the newest job of a kind
-- anywhere; each node's last system job to end. One statement per paragraph,
-- as 0001 says.

CREATE INDEX jobs_queued ON jobs (queued);

CREATE INDEX jobs_node_type ON jobs (node, type, queued);

CREATE INDEX jobs_node_state ON jobs (node, state, queued);

CREATE INDEX jobs_project_type ON jobs (project, type, queued);

CREATE INDEX jobs_type_queued ON jobs (type, queued);

CREATE INDEX jobs_type_ended ON jobs (type, ended);
