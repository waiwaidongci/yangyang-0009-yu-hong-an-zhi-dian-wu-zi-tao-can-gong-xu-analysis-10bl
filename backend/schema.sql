CREATE TABLE IF NOT EXISTS flood_responses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_code text NOT NULL UNIQUE,
    river_sector text NOT NULL,
    warehouse text NOT NULL
);

CREATE TABLE IF NOT EXISTS depot_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id bigint NOT NULL REFERENCES flood_responses(id),
    sku text NOT NULL,
    name text NOT NULL,
    case_size integer NOT NULL CHECK (case_size > 0),
    on_hand integer NOT NULL CHECK (on_hand >= 0),
    protected_units integer NOT NULL CHECK (protected_units BETWEEN 0 AND on_hand),
    UNIQUE (response_id, sku)
);

CREATE TABLE IF NOT EXISTS shelter_requisitions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id bigint NOT NULL REFERENCES flood_responses(id),
    slip text NOT NULL,
    shelter text NOT NULL,
    households integer NOT NULL CHECK (households BETWEEN 1 AND 600),
    phase text NOT NULL CHECK (phase IN ('submitted','confirmed')) DEFAULT 'submitted',
    confirm_by text,
    revision bigint NOT NULL DEFAULT 0,
    UNIQUE(response_id,slip),
    CHECK ((phase = 'confirmed') = (confirm_by IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS requisition_lines (
    request_id bigint NOT NULL REFERENCES shelter_requisitions(id),
    item_id bigint NOT NULL REFERENCES depot_items(id),
    units integer NOT NULL CHECK (units BETWEEN 1 AND 3600),
    PRIMARY KEY (request_id,item_id)
);

CREATE TABLE IF NOT EXISTS co_demand_surveys (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id bigint NOT NULL REFERENCES flood_responses(id),
    sample_ids bigint[] NOT NULL CHECK (cardinality(sample_ids) >= 4),
    min_support_pct integer NOT NULL CHECK (min_support_pct BETWEEN 1 AND 100),
    min_lift numeric(5,2) NOT NULL CHECK (min_lift BETWEEN 1 AND 25),
    status text NOT NULL CHECK (status IN ('queued','ready','voided')) DEFAULT 'queued'
);

CREATE TABLE IF NOT EXISTS co_demand_pairs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    survey_id bigint NOT NULL REFERENCES co_demand_surveys(id),
    id_a bigint NOT NULL REFERENCES depot_items(id),
    id_b bigint NOT NULL REFERENCES depot_items(id),
    count_a integer NOT NULL CHECK (count_a > 0),
    count_b integer NOT NULL CHECK (count_b > 0),
    intersection integer NOT NULL CHECK (intersection BETWEEN 1 AND LEAST(count_a,count_b)),
    support double precision NOT NULL CHECK (support BETWEEN 0 AND 1),
    conf_ab double precision NOT NULL CHECK (conf_ab BETWEEN 0 AND 1),
    conf_ba double precision NOT NULL CHECK (conf_ba BETWEEN 0 AND 1),
    lift double precision NOT NULL CHECK (lift > 0),
    CHECK(id_a < id_b),
    UNIQUE(survey_id,id_a,id_b)
);

CREATE TABLE IF NOT EXISTS issue_slips (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id bigint NOT NULL REFERENCES shelter_requisitions(id),
    pair_id bigint NOT NULL REFERENCES co_demand_pairs(id),
    packs integer NOT NULL CHECK (packs BETWEEN 1 AND 200),
    units_a integer NOT NULL CHECK (units_a > 0),
    units_b integer NOT NULL CHECK (units_b > 0),
    phase text NOT NULL CHECK (phase IN ('draft','approved','shelved','voided')) DEFAULT 'draft',
    opened_by text NOT NULL,
    disposition_by text,
    disposition_note text,
    CHECK ((phase='draft') = (disposition_by IS NULL)),
    CHECK ((phase='draft') = (disposition_note IS NULL))
);
