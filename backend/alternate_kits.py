from fastapi import HTTPException

from alternate_rules import swap_items


def offers(cx,incident):
    from dispatch import response_for
    response_for(cx,incident)
    return cx.execute(
        """SELECT k.*,a.name AS donor_name,b.name AS replacement_name,q.slip,q.shelter
           FROM kit_replacements k JOIN depot_items a ON a.id=k.donor_item
           JOIN depot_items b ON b.id=k.replacement_item JOIN shelter_requisitions q ON q.id=k.request_id
           WHERE q.response_id=%s ORDER BY k.id DESC""",(incident,),
    ).fetchall()


def propose(cx,incident,body,user):
    from dispatch import pair_for,requests_for,response_for
    response_for(cx,incident,lock=True)
    wanted=pair_for(cx,incident,body["wanted_pair"])
    alternate=pair_for(cx,incident,body["alternate_pair"])
    original,replacement=swap_items(wanted,alternate)
    request=next((r for r in requests_for(cx,incident) if r["id"]==body["request_id"] and r["phase"]=="confirmed"),None)
    if not request or not {wanted["id_a"],wanted["id_b"]}<={line["item_id"] for line in request["lines"]}:
        raise HTTPException(409,"原套餐须对应已确认点位的两项申报")
    return cx.execute(
        """INSERT INTO kit_replacements(request_id,wanted_pair,alternate_pair,donor_item,replacement_item,packs,explanation,opened_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (request["id"],wanted["id"],alternate["id"],original,replacement,body["packs"],body["explanation"],user),
    ).fetchone()


def admit(cx,incident,item_id,consent,user):
    from dispatch import pair_for,response_for,unit_checks
    response_for(cx,incident,lock=True)
    found=next((row for row in offers(cx,incident) if row["id"]==item_id),None)
    if not found or found["linked_slip"]:
        raise HTTPException(409,"仅待确认换品可登记安置点同意凭证")
    if found["revoked_reason"]:
        raise HTTPException(409,"原搭配已因需求更正停用，该换品同意不能再用于出库")
    pair=pair_for(cx,incident,found["alternate_pair"])
    a,b=pair["case_a"]*found["packs"],pair["case_b"]*found["packs"]
    mapping={found["replacement_item"]:found["donor_item"]}
    unit_checks(cx,incident,found["request_id"],pair,(a,b),mapping)
    slip=cx.execute(
        """INSERT INTO issue_slips(request_id,pair_id,packs,units_a,units_b,opened_by)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
        (found["request_id"],pair["id"],found["packs"],a,b,found["opened_by"]),
    ).fetchone()
    cx.execute(
        """UPDATE kit_replacements SET consent_ref=%s,accepted_by=%s,linked_slip=%s WHERE id=%s""",
        (consent,user,slip["id"],item_id),
    )
    return slip


def requested_mapping(cx,slip_id):
    row=cx.execute("SELECT donor_item,replacement_item FROM kit_replacements WHERE linked_slip=%s",(slip_id,)).fetchone()
    return {row["replacement_item"]:row["donor_item"]} if row else {}
