CREATE TABLE IF NOT EXISTS depot_lots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES depot_items(id),
    label text NOT NULL,
    use_by date NOT NULL,
    balance integer NOT NULL CHECK(balance>=0),
    received_by text NOT NULL,
    UNIQUE(item_id,label)
);
CREATE TABLE IF NOT EXISTS slip_lot_manifests (
    slip_id bigint PRIMARY KEY REFERENCES issue_slips(id),
    arrival_day date NOT NULL,
    packed_by text NOT NULL
);
CREATE TABLE IF NOT EXISTS reserved_lot_lines (
    slip_id bigint REFERENCES slip_lot_manifests(slip_id),
    lot_id bigint REFERENCES depot_lots(id),
    units integer NOT NULL CHECK(units>0),
    PRIMARY KEY(slip_id,lot_id)
);
