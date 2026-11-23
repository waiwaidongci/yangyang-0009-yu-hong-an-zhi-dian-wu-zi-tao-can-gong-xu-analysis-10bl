from fastapi import HTTPException


def differences(slip,received):
    delta_a=slip["units_a"]-received["counted_a"]
    delta_b=slip["units_b"]-received["counted_b"]
    if delta_a<0 or delta_b<0:
        raise HTTPException(409,"点收超过本次出库凭证件数，须另查箱号")
    return {"gap_a":delta_a,"gap_b":delta_b}


def audit_disposition(gaps, disposition):
    any_gap=any(gaps.values())
    if any_gap and disposition=="verified":
        raise HTTPException(409,"存在短少，须留存运输损失或待转运处置")
    if not any_gap and disposition!="verified":
        raise HTTPException(409,"全量签收不应标成损失或待转运")
