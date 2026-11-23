CREATE TABLE IF NOT EXISTS site_handovers (
    slip_id bigint PRIMARY KEY REFERENCES issue_slips(id),
    counted_a integer NOT NULL CHECK(counted_a>=0),
    counted_b integer NOT NULL CHECK(counted_b>=0),
    proof_ref text NOT NULL,
    reported_by text NOT NULL,
    disposition text CHECK(disposition IN ('verified','record_loss','relay_pending')),
    reviewed_by text,
    reviewer_note text,
    reported_at timestamptz NOT NULL DEFAULT now()
);
