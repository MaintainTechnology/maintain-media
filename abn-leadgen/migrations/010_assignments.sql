CREATE TABLE worklist_assignment (
 worklist_id uuid NOT NULL REFERENCES worklist, actor_id text NOT NULL,
 assigned_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(worklist_id,actor_id)
);
