from fastapi import HTTPException

from lot_selection import plan_fefo,warehouse_day


def stock_lots(cx,incident):
    return cx.execute(
        """SELECT l.*,i.sku,i.name FROM depot_lots l JOIN depot_items i ON i.id=l.item_id
           WHERE i.response_id=%s ORDER BY l.use_by,l.id""",(incident,),
    ).fetchall()


def lot_book(cx,incident):
    from dispatch import response_for
    response_for(cx,incident)
    manifests=cx.execute(
        """SELECT m.*,r.lot_id,r.units,l.label,l.use_by
           FROM slip_lot_manifests m JOIN reserved_lot_lines r ON r.slip_id=m.slip_id
           JOIN depot_lots l ON l.id=r.lot_id JOIN issue_slips s ON s.id=m.slip_id
           JOIN shelter_requisitions q ON q.id=s.request_id WHERE q.response_id=%s
           ORDER BY m.slip_id, l.use_by,l.id""",(incident,),
    ).fetchall()
    return {"lots":stock_lots(cx,incident),"manifests":manifests}


def receive(cx,incident,body,user):
    from dispatch import response_for
    response_for(cx,incident,lock=True)
    if not cx.execute("SELECT id FROM depot_items WHERE id=%s AND response_id=%s",
                      (body["item_id"],incident)).fetchone():
        raise HTTPException(409,"批号须对应本库目录物料")
    lot=cx.execute(
        """INSERT INTO depot_lots(item_id,label,use_by,balance,received_by)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",(body["item_id"],body["label"],body["use_by"],body["units"],user),
    ).fetchone()
    cx.execute("UPDATE depot_items SET on_hand=on_hand+%s WHERE id=%s",(body["units"],body["item_id"]))
    return lot


def manifest(cx,incident,slip_id,arrival,user):
    from dispatch import pair_for,response_for,slips_for
    response_for(cx,incident,lock=True)
    slip=next((row for row in slips_for(cx,incident) if row["id"]==slip_id),None)
    if not slip or slip["phase"]!="draft":
        raise HTTPException(409,"仅待批草案可绑定到点批号")
    if arrival < warehouse_day():
        raise HTTPException(409,"到点日不能早于当前日期")
    pair=pair_for(cx,incident,slip["pair_id"])
    lots=stock_lots(cx,incident)
    picks=plan_fefo(lots,pair["id_a"],slip["units_a"],arrival)+plan_fefo(lots,pair["id_b"],slip["units_b"],arrival)
    cx.execute(
        """INSERT INTO slip_lot_manifests VALUES (%s,%s,%s)
           ON CONFLICT(slip_id) DO UPDATE SET arrival_day=excluded.arrival_day,packed_by=excluded.packed_by""",
        (slip_id,arrival,user),
    )
    cx.execute("DELETE FROM reserved_lot_lines WHERE slip_id=%s",(slip_id,))
    with cx.cursor() as cursor:
        cursor.executemany("INSERT INTO reserved_lot_lines VALUES (%s,%s,%s)",[(slip_id,*pick) for pick in picks])
    return {"slip_id":slip_id,"arrival_day":arrival,"picks":[{"lot_id":lot,"units":units} for lot,units in picks]}


def draw_lots(cx,slip,pair):
    picks=cx.execute(
        """SELECT r.*,l.item_id,l.balance,l.use_by,m.arrival_day FROM reserved_lot_lines r
           JOIN depot_lots l ON l.id=r.lot_id JOIN slip_lot_manifests m ON m.slip_id=r.slip_id
           WHERE r.slip_id=%s""",(slip["id"],),
    ).fetchall()
    if not picks:
        physical=cx.execute(
            """SELECT i.id,i.on_hand-COALESCE(sum(l.balance),0) AS loose
                FROM depot_items i LEFT JOIN depot_lots l ON l.item_id=i.id
                WHERE i.id IN (%s,%s) GROUP BY i.id""",(pair["id_a"],pair["id_b"]),
        ).fetchall()
        stock={row["id"]:row["loose"] for row in physical}
        if stock[pair["id_a"]]<slip["units_a"] or stock[pair["id_b"]]<slip["units_b"]:
            raise HTTPException(409,"非批号散存不足，先在批次拣配生成有效批号单")
        return
    cutoff = max(warehouse_day(),picks[0]["arrival_day"])
    available = cx.execute(
        """SELECT i.id,i.on_hand-i.protected_units-COALESCE(sum(l.balance) FILTER (WHERE l.use_by<%s),0) AS eligible
           FROM depot_items i LEFT JOIN depot_lots l ON l.item_id=i.id
           WHERE i.id IN (%s,%s) GROUP BY i.id""",(cutoff,pair["id_a"],pair["id_b"]),
    ).fetchall()
    physical = {row["id"]:row["eligible"] for row in available}
    if physical[pair["id_a"]]<slip["units_a"] or physical[pair["id_b"]]<slip["units_b"]:
        raise HTTPException(409,"到点日有效的保留库存不足，不能批准")
    for pick in picks:
        if pick["balance"]<pick["units"] or pick["use_by"]<max(warehouse_day(),pick["arrival_day"]):
            raise HTTPException(409,"候选批号已不足或过期，请重新拣配")
    for pick in picks:
        cx.execute("UPDATE depot_lots SET balance=balance-%s WHERE id=%s",(pick["units"],pick["lot_id"]))
