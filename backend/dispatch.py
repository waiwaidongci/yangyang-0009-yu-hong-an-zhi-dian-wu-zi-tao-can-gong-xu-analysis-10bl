from fastapi import HTTPException
from psycopg.types.json import Jsonb

from alternate_kits import requested_mapping
from core import enqueue
from eclat import overlap_pairs
from lot_book import draw_lots
from lot_selection import warehouse_day


def response_for(cx, incident_id, *, lock=False):
    row = cx.execute("SELECT * FROM flood_responses WHERE id=%s" + (" FOR UPDATE" if lock else ""),
                     (incident_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "找不到雨洪响应")
    return row


def inventory(cx, incident_id):
    return cx.execute(
        """SELECT i.*,COALESCE(l.expired,0) AS expired_units,
                  GREATEST(0,i.on_hand-i.protected_units-COALESCE(l.expired,0)) AS available_units,
                  GREATEST(0,i.on_hand-i.protected_units-COALESCE(l.expired,0))/i.case_size AS available_cases
           FROM depot_items i LEFT JOIN LATERAL (
              SELECT sum(balance) AS expired FROM depot_lots WHERE item_id=i.id AND use_by<%s
           ) l ON true WHERE i.response_id=%s ORDER BY i.id""", (warehouse_day(),incident_id),
    ).fetchall()


def requests_for(cx, incident_id):
    headers = cx.execute("SELECT * FROM shelter_requisitions WHERE response_id=%s ORDER BY id DESC",
                         (incident_id,)).fetchall()
    goods = cx.execute(
        """SELECT l.*,i.sku,i.name FROM requisition_lines l
           JOIN depot_items i ON i.id=l.item_id
           JOIN shelter_requisitions r ON r.id=l.request_id
           WHERE r.response_id=%s ORDER BY i.id""", (incident_id,),
    ).fetchall()
    corrections = cx.execute(
        """SELECT c.* FROM requisition_corrections c
           JOIN shelter_requisitions r ON r.id=c.request_id
           WHERE r.response_id=%s ORDER BY c.id""", (incident_id,),
    ).fetchall()
    for row in headers:
        row["lines"] = [item for item in goods if item["request_id"] == row["id"]]
        row["corrections"] = [item for item in corrections if item["request_id"] == row["id"]]
    return headers


def add_request(cx, incident_id, body):
    response_for(cx, incident_id, lock=True)
    items = {line["item_id"] for line in body["lines"]}
    if len(items) != len(body["lines"]):
        raise HTTPException(409, "同一需求单的物资不可重复")
    if not items <= {item["id"] for item in inventory(cx, incident_id)}:
        raise HTTPException(409, "需求物资须来自本次响应的库房目录")
    row = cx.execute(
        """INSERT INTO shelter_requisitions(response_id,slip,shelter,households)
           VALUES (%s,%s,%s,%s) ON CONFLICT(response_id,slip) DO NOTHING RETURNING *""",
        (incident_id, body["slip"], body["shelter"], body["households"]),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "需求单号与当前响应已有凭证重复")
    with cx.cursor() as cursor:
        cursor.executemany("INSERT INTO requisition_lines(request_id,item_id,units) VALUES (%s,%s,%s)",
                           [(row["id"], line["item_id"], line["units"]) for line in body["lines"]])
    return row


def confirm_request(cx, incident_id, request_id, email):
    response_for(cx, incident_id, lock=True)
    row = cx.execute(
        """UPDATE shelter_requisitions SET phase='confirmed',confirm_by=%s
           WHERE id=%s AND response_id=%s AND phase='submitted' RETURNING *""",
        (email, request_id, incident_id),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "只有本次响应的待审需求单可以确认")
    return row


def new_survey(cx, incident_id, support, lift):
    response_for(cx, incident_id, lock=True)
    samples = cx.execute(
        "SELECT id,revision FROM shelter_requisitions WHERE response_id=%s AND phase='confirmed' ORDER BY id",
        (incident_id,),
    ).fetchall()
    if len(samples) < 4:
        raise HTTPException(409, "至少需要四个已审核安置点需求单")
    revisions = {str(sample["id"]): sample["revision"] for sample in samples}
    return cx.execute(
        """INSERT INTO co_demand_surveys(response_id,sample_ids,min_support_pct,min_lift,sample_revisions)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",
        (incident_id, [sample["id"] for sample in samples], support, lift, Jsonb(revisions)),
    ).fetchone()


def survey_results(cx, incident_id):
    runs = cx.execute(
        """SELECT s.*,j.status AS job_status,j.error AS job_error
           FROM co_demand_surveys s LEFT JOIN app_jobs j ON j.id=s.job_id
           WHERE s.response_id=%s ORDER BY s.id DESC""",
        (incident_id,),
    ).fetchall()
    pairs = cx.execute(
        """
        SELECT p.*, a.sku AS sku_a, b.sku AS sku_b, a.name AS name_a, b.name AS name_b
        FROM co_demand_pairs p JOIN co_demand_surveys s ON s.id=p.survey_id
        JOIN depot_items a ON a.id=p.id_a JOIN depot_items b ON b.id=p.id_b
        WHERE s.response_id=%s ORDER BY p.lift DESC,p.intersection DESC,p.id
        """, (incident_id,),
    ).fetchall()
    for survey in runs:
        survey["pairs"] = [pair for pair in pairs if pair["survey_id"] == survey["id"]]
    return runs


def sample_revisions(cx, sample_ids):
    """Snapshot the correction revision of every frozen sample request."""
    if not sample_ids:
        return {}
    rows = cx.execute(
        "SELECT id,revision FROM shelter_requisitions WHERE id=ANY(%s)", (sample_ids,),
    ).fetchall()
    return {str(row["id"]): row["revision"] for row in rows}


def _normalised_revisions(value):
    return {str(key): int(number) for key, number in (value or {}).items()}


def mine(cx, survey_id):
    # Serialise against corrections, which lock the response then rewrite samples.
    existing = cx.execute("SELECT response_id FROM co_demand_surveys WHERE id=%s", (survey_id,)).fetchone()
    if existing is None:
        raise HTTPException(404, "找不到已冻结的需求样本")
    response_for(cx, existing["response_id"], lock=True)
    survey = cx.execute("SELECT * FROM co_demand_surveys WHERE id=%s FOR UPDATE", (survey_id,)).fetchone()
    if survey["status"] == "voided":
        return {"survey_id": survey_id, "skipped": "场次已停用，不再启用该次结果"}
    if survey["status"] == "ready":
        return {"survey_id": survey_id, "sample_count": len(survey["sample_ids"])}
    expected = _normalised_revisions(survey["sample_revisions"])
    current = sample_revisions(cx, survey["sample_ids"])
    if not expected:
        # Legacy frozen run with no snapshot; adopt the revisions it is about to read.
        cx.execute("UPDATE co_demand_surveys SET sample_revisions=%s WHERE id=%s",
                   (Jsonb(current), survey_id))
        expected = current
    if expected != current:
        # A newer correction landed after this run was frozen; keep it disabled.
        reason = "样本已有更新更正，旧任务结果不再启用"
        void_survey(cx, survey, None, reason, "system")
        return {"survey_id": survey_id, "skipped": reason}
    rows = cx.execute("SELECT request_id,item_id FROM requisition_lines WHERE request_id=ANY(%s)",
                      (survey["sample_ids"],)).fetchall()
    baskets = {request: set() for request in survey["sample_ids"]}
    for row in rows:
        baskets[row["request_id"]].add(row["item_id"])
    pairs = overlap_pairs(baskets, survey["min_support_pct"], float(survey["min_lift"]))
    with cx.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO co_demand_pairs
               (survey_id,id_a,id_b,count_a,count_b,intersection,support,conf_ab,conf_ba,lift)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(survey_id, *row) for row in pairs],
        )
    cx.execute("UPDATE co_demand_surveys SET status='ready' WHERE id=%s", (survey_id,))
    return {"survey_id": survey_id, "sample_count": len(baskets), "pairs": len(pairs)}


def void_survey(cx, survey, correction_id, reason, email):
    """Disable a frozen run while keeping its old result queryable."""
    cx.execute(
        """UPDATE co_demand_surveys
           SET status='voided',voided_reason=%s,voided_at=now(),voided_correction=%s
           WHERE id=%s""", (reason, correction_id, survey["id"]),
    )
    pair_ids = [row["id"] for row in cx.execute(
        "SELECT id FROM co_demand_pairs WHERE survey_id=%s", (survey["id"],)).fetchall()]
    if not pair_ids:
        return []
    voided = [row["id"] for row in cx.execute(
        """UPDATE issue_slips
           SET phase='voided',voided_reason=%s,voided_at=now(),disposition_by=%s,disposition_note=%s
           WHERE phase='draft' AND pair_id=ANY(%s) RETURNING id""",
        (reason, email, reason, pair_ids),
    ).fetchall()]
    # Replacement agreements from the old pair can no longer produce an outbound slip.
    if voided:
        cx.execute(
            """UPDATE kit_replacements SET revoked_reason=%s,revoked_at=now()
               WHERE revoked_reason IS NULL
                 AND (wanted_pair=ANY(%s) OR alternate_pair=ANY(%s))
                 AND (linked_slip IS NULL OR linked_slip=ANY(%s))""",
            (reason, pair_ids, pair_ids, voided),
        )
    else:
        cx.execute(
            """UPDATE kit_replacements SET revoked_reason=%s,revoked_at=now()
               WHERE revoked_reason IS NULL AND linked_slip IS NULL
                 AND (wanted_pair=ANY(%s) OR alternate_pair=ANY(%s))""",
            (reason, pair_ids, pair_ids),
        )
    return voided


def replacement_survey(cx, survey, email):
    """Create the run that repeats the voided survey at its original thresholds."""
    revisions = sample_revisions(cx, survey["sample_ids"])
    fresh = cx.execute(
        """INSERT INTO co_demand_surveys(response_id,sample_ids,min_support_pct,min_lift,sample_revisions)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",
        (survey["response_id"], survey["sample_ids"], survey["min_support_pct"],
         survey["min_lift"], Jsonb(revisions)),
    ).fetchone()
    cx.execute("UPDATE co_demand_surveys SET superseded_by=%s WHERE id=%s",
               (fresh["id"], survey["id"]))
    job_id = enqueue(cx, "mine_relief_pairs", {"survey_id": fresh["id"]})
    return cx.execute("UPDATE co_demand_surveys SET job_id=%s WHERE id=%s RETURNING *",
                      (job_id, fresh["id"])).fetchone()


def correct_request(cx, incident_id, request_id, body, email):
    """Reviewer rewrites a confirmed request's materials, keeping an audit trail."""
    response_for(cx, incident_id, lock=True)
    request = cx.execute(
        "SELECT * FROM shelter_requisitions WHERE id=%s AND response_id=%s FOR UPDATE",
        (request_id, incident_id),
    ).fetchone()
    if request is None:
        raise HTTPException(404, "找不到本次响应的需求单")
    if request["phase"] != "confirmed":
        raise HTTPException(409, "只有已核需求单可以留更正记录")
    items = {line["item_id"] for line in body["lines"]}
    if len(items) != len(body["lines"]):
        raise HTTPException(409, "同一需求单的物资不可重复")
    if not items <= {item["id"] for item in inventory(cx, incident_id)}:
        raise HTTPException(409, "需求物资须来自本次响应的库房目录")
    previous = [{"item_id": line["item_id"], "units": line["units"]}
                for line in cx.execute(
                    "SELECT item_id,units FROM requisition_lines WHERE request_id=%s ORDER BY item_id",
                    (request_id,)).fetchall()]
    corrected = [{"item_id": line["item_id"], "units": line["units"]} for line in body["lines"]]
    if previous == sorted(corrected, key=lambda line: line["item_id"]):
        raise HTTPException(409, "更正后的物资与原件一致，无需留记录")
    cx.execute("DELETE FROM requisition_lines WHERE request_id=%s", (request_id,))
    with cx.cursor() as cursor:
        cursor.executemany("INSERT INTO requisition_lines(request_id,item_id,units) VALUES (%s,%s,%s)",
                           [(request_id, line["item_id"], line["units"]) for line in body["lines"]])
    revision = cx.execute(
        "UPDATE shelter_requisitions SET revision=revision+1 WHERE id=%s RETURNING revision",
        (request_id,),
    ).fetchone()["revision"]
    correction = cx.execute(
        """INSERT INTO requisition_corrections
           (request_id,previous_lines,corrected_lines,reason,corrected_by)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",
        (request_id, Jsonb(previous), Jsonb(corrected), body["reason"], email),
    ).fetchone()
    reason = f"需求单 {request['slip']} 已更正，原搭配停用"
    affected = cx.execute(
        """SELECT * FROM co_demand_surveys
           WHERE response_id=%s AND status IN ('queued','ready') AND %s=ANY(sample_ids)
           ORDER BY id FOR UPDATE""", (incident_id, request_id),
    ).fetchall()
    disabled = []
    replacements = []
    for survey in affected:
        void_survey(cx, survey, correction["id"], reason, email)
        disabled.append(survey["id"])
        replacements.append(replacement_survey(cx, survey, email)["id"])
    return {**correction, "revision": revision,
            "disabled_surveys": disabled, "replacement_surveys": replacements}


def retry_survey(cx, incident_id, survey_id):
    """Re-enqueue a run whose background job failed, keeping it disabled if voided."""
    response_for(cx, incident_id, lock=True)
    survey = cx.execute(
        "SELECT * FROM co_demand_surveys WHERE id=%s AND response_id=%s FOR UPDATE",
        (survey_id, incident_id),
    ).fetchone()
    if survey is None:
        raise HTTPException(404, "找不到这次共需分析")
    if survey["status"] == "voided":
        raise HTTPException(409, "已停用的场次不能重试，请查看替代场次")
    if survey["status"] == "ready":
        raise HTTPException(409, "该场次已有结果，无需重试")
    job = cx.execute("SELECT * FROM app_jobs WHERE id=%s", (survey["job_id"],)).fetchone()
    if job and job["status"] in ("queued", "running"):
        raise HTTPException(409, "该场次仍在计算，请稍后刷新")
    job_id = enqueue(cx, "mine_relief_pairs", {"survey_id": survey_id})
    return cx.execute("UPDATE co_demand_surveys SET job_id=%s WHERE id=%s RETURNING *",
                      (job_id, survey_id)).fetchone()


def pair_for(cx, incident_id, pair_id):
    row = cx.execute(
        """
        SELECT p.*,a.name AS name_a,b.name AS name_b,
               a.case_size AS case_a, b.case_size AS case_b
        FROM co_demand_pairs p JOIN co_demand_surveys s ON s.id=p.survey_id
        JOIN depot_items a ON a.id=p.id_a JOIN depot_items b ON b.id=p.id_b
        WHERE s.response_id=%s AND p.id=%s AND s.status='ready'
        """, (incident_id, pair_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "找不到本库房的共需搭配")
    return row


def unit_checks(cx, incident_id, request_id, pair, units, substitution=None):
    request = next((row for row in requests_for(cx, incident_id) if row["id"] == request_id), None)
    if not request or request["phase"] != "confirmed":
        raise HTTPException(409, "只有经审核的安置点需求单可配发")
    requested = {line["item_id"]: line["units"] for line in request["lines"]}
    substitution = substitution or {}
    awarded = {row["item_id"]: row["awarded"] for row in cx.execute(
        """SELECT COALESCE(k.donor_item,x.item_id) AS item_id, sum(x.units) AS awarded FROM issue_slips i
           JOIN co_demand_pairs p ON p.id=i.pair_id
           CROSS JOIN LATERAL (VALUES (p.id_a,i.units_a),(p.id_b,i.units_b)) x(item_id,units)
           LEFT JOIN kit_replacements k ON k.linked_slip=i.id AND k.replacement_item=x.item_id
           WHERE i.request_id=%s AND i.phase='approved' GROUP BY COALESCE(k.donor_item,x.item_id)""", (request_id,),
    ).fetchall()}
    available = {row["id"]: row for row in inventory(cx, incident_id)}
    for item_id, quantity in zip((pair["id_a"], pair["id_b"]), units):
        stock = available[item_id]
        demand_id = substitution.get(item_id,item_id)
        if demand_id not in requested:
            raise HTTPException(409, f"该安置点未申报{stock['name']}，不可整配")
        if quantity + awarded.get(demand_id, 0) > requested[demand_id]:
            raise HTTPException(409, f"{stock['name']}超出该点未配发的申报数量")
        if quantity > stock["available_units"]:
            raise HTTPException(409, f"{stock['name']}可用整箱不足，保留库存不得占用")


def draft(cx, incident_id, data, email):
    response_for(cx, incident_id, lock=True)
    pair = pair_for(cx, incident_id, data["pair_id"])
    units = data["packs"] * pair["case_a"], data["packs"] * pair["case_b"]
    unit_checks(cx, incident_id, data["request_id"], pair, units)
    return cx.execute(
        """INSERT INTO issue_slips(request_id,pair_id,packs,units_a,units_b,opened_by)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
        (data["request_id"], data["pair_id"], data["packs"], *units, email),
    ).fetchone()


def slips_for(cx, incident_id):
    return cx.execute(
        """SELECT i.*,r.slip,r.shelter,a.name AS name_a,b.name AS name_b
           FROM issue_slips i JOIN shelter_requisitions r ON r.id=i.request_id
           JOIN co_demand_pairs p ON p.id=i.pair_id
           JOIN depot_items a ON a.id=p.id_a JOIN depot_items b ON b.id=p.id_b
           WHERE r.response_id=%s ORDER BY i.id DESC""", (incident_id,),
    ).fetchall()


def dispose(cx, incident_id, slip_id, phase, note, email):
    response_for(cx, incident_id, lock=True)
    row = next((item for item in slips_for(cx, incident_id) if item["id"] == slip_id), None)
    if not row or row["phase"] != "draft":
        raise HTTPException(409, "只可处置本库房待审核的配发草案")
    if phase == "approved":
        pair = pair_for(cx, incident_id, row["pair_id"])
        quantities = row["units_a"], row["units_b"]
        unit_checks(cx, incident_id, row["request_id"], pair, quantities, requested_mapping(cx,slip_id))
        draw_lots(cx,row,pair)
        for item_id, quantity in zip((pair["id_a"], pair["id_b"]), quantities):
            cx.execute("UPDATE depot_items SET on_hand=on_hand-%s WHERE id=%s", (quantity,item_id))
    return cx.execute(
        """UPDATE issue_slips SET phase=%s,disposition_note=%s,disposition_by=%s
           WHERE id=%s RETURNING *""", (phase,note,email,slip_id),
    ).fetchone()
