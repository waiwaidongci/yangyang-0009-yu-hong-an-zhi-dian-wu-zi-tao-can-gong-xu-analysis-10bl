from datetime import datetime,timedelta,timezone

from fastapi import HTTPException


def plan_fefo(lots, item_id, units, arrival):
    needed=units
    chosen=[]
    for row in sorted(lots,key=lambda row:(row["use_by"],row["id"])):
        if row["item_id"]!=item_id or row["use_by"]<arrival or not row["balance"]:
            continue
        count=min(needed,row["balance"])
        chosen.append((row["id"],count))
        needed-=count
        if not needed:
            return chosen
    raise HTTPException(409,f"物资 {item_id} 的到点有效批号存量不足")


def warehouse_day():
    return datetime.now(timezone(timedelta(hours=8))).date()
