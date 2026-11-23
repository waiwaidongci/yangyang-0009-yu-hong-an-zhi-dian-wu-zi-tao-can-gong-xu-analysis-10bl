from fastapi import HTTPException
from handover_deltas import audit_disposition,differences


def approved(cx,incident,slip_id):
    from dispatch import response_for,slips_for
    response_for(cx,incident,lock=True)
    row=next((r for r in slips_for(cx,incident) if r["id"]==slip_id),None)
    if not row or row["phase"]!="approved":
        raise HTTPException(409,"已批准出库的箱件才可录入安置点点收")
    return row


def packing_receipts(cx,incident):
    from dispatch import response_for,slips_for
    response_for(cx,incident)
    counted=cx.execute(
        """SELECT h.* FROM site_handovers h JOIN issue_slips i ON i.id=h.slip_id
           JOIN shelter_requisitions r ON r.id=i.request_id WHERE r.response_id=%s""",(incident,),
    ).fetchall()
    reports={r["slip_id"]:r for r in counted}
    output=[]
    for slip in slips_for(cx,incident):
        if slip["phase"]=="approved":
            record=reports.get(slip["id"])
            output.append({"slip":slip,"receipt":({**record,**differences(slip,record)} if record else None)})
    return output


def submit(cx,incident,slip_id,body,user):
    slip=approved(cx,incident,slip_id)
    gaps=differences(slip,body)
    row=cx.execute(
        """INSERT INTO site_handovers(slip_id,counted_a,counted_b,proof_ref,reported_by)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",(slip_id,body["counted_a"],body["counted_b"],body["proof_ref"],user),
    ).fetchone()
    return {**row,**gaps}


def close(cx,incident,slip_id,body,user):
    slip=approved(cx,incident,slip_id)
    row=cx.execute("SELECT * FROM site_handovers WHERE slip_id=%s FOR UPDATE",(slip_id,)).fetchone()
    if not row or row["disposition"]:
        raise HTTPException(409,"仅待签核的点收凭证可以处置")
    audit_disposition(differences(slip,row),body["disposition"])
    return cx.execute(
        """UPDATE site_handovers SET disposition=%s,reviewed_by=%s,reviewer_note=%s
           WHERE slip_id=%s RETURNING *""",(body["disposition"],user,body["note"],slip_id),
    ).fetchone()
