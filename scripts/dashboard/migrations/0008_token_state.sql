-- 0008: what a token is, in a column of its own (R227 step 14). The revoked
-- column held four states as 0 (live), 1 (revoked), 2 (pending: handed to a
-- node that has not used it yet) and 3 (retired: replaced, still taken for
-- its grace), and a statement written for live and revoked passed over the
-- other two. A live node token carries no expiry: one that has one got it
-- from two calls racing on a rotation, which the check used to mend each
-- time it met it and now cannot produce.

ALTER TABLE tokens ADD COLUMN state TEXT NOT NULL DEFAULT 'live';

UPDATE tokens SET state = CASE revoked WHEN 0 THEN 'live' WHEN 2 THEN 'pending' WHEN 3 THEN 'retired' ELSE 'revoked' END;

UPDATE tokens SET expires = NULL WHERE kind = 'node' AND state = 'live';

ALTER TABLE tokens DROP COLUMN revoked;
