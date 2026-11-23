CREATE TABLE IF NOT EXISTS kit_replacements (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id bigint NOT NULL REFERENCES shelter_requisitions(id),
    wanted_pair bigint NOT NULL REFERENCES co_demand_pairs(id),
    alternate_pair bigint NOT NULL REFERENCES co_demand_pairs(id),
    donor_item bigint NOT NULL REFERENCES depot_items(id),
    replacement_item bigint NOT NULL REFERENCES depot_items(id),
    packs integer NOT NULL CHECK(packs BETWEEN 1 AND 200),
    explanation text NOT NULL,
    opened_by text NOT NULL,
    accepted_by text,
    consent_ref text,
    linked_slip bigint UNIQUE REFERENCES issue_slips(id),
    CHECK ((linked_slip IS NULL)=(consent_ref IS NULL)),
    CHECK (wanted_pair <> alternate_pair)
);
