ALTER TABLE shelter_requisitions ADD COLUMN IF NOT EXISTS revision bigint NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS requisition_corrections (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id bigint NOT NULL REFERENCES shelter_requisitions(id),
    previous_lines jsonb NOT NULL,
    corrected_lines jsonb NOT NULL,
    reason text NOT NULL,
    corrected_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS requisition_corrections_request
    ON requisition_corrections(request_id,id);

ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS sample_revisions jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS job_id bigint;
ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS voided_reason text;
ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS voided_at timestamptz;
ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS voided_correction bigint REFERENCES requisition_corrections(id);
ALTER TABLE co_demand_surveys ADD COLUMN IF NOT EXISTS superseded_by bigint REFERENCES co_demand_surveys(id);

ALTER TABLE co_demand_surveys DROP CONSTRAINT IF EXISTS co_demand_surveys_status_check;
ALTER TABLE co_demand_surveys ADD CONSTRAINT co_demand_surveys_status_check
    CHECK (status IN ('queued','ready','voided'));
ALTER TABLE co_demand_surveys DROP CONSTRAINT IF EXISTS co_demand_surveys_voided_check;
ALTER TABLE co_demand_surveys ADD CONSTRAINT co_demand_surveys_voided_check
    CHECK ((status='voided') = (voided_reason IS NOT NULL));

ALTER TABLE issue_slips ADD COLUMN IF NOT EXISTS voided_reason text;
ALTER TABLE issue_slips ADD COLUMN IF NOT EXISTS voided_at timestamptz;
ALTER TABLE issue_slips DROP CONSTRAINT IF EXISTS issue_slips_phase_check;
ALTER TABLE issue_slips ADD CONSTRAINT issue_slips_phase_check
    CHECK (phase IN ('draft','approved','shelved','voided'));

ALTER TABLE kit_replacements ADD COLUMN IF NOT EXISTS revoked_reason text;
ALTER TABLE kit_replacements ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
