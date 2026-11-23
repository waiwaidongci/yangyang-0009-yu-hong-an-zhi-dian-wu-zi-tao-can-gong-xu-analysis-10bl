from fastapi import HTTPException


def swap_items(wanted, alternate):
    if wanted["survey_id"]!=alternate["survey_id"]:
        raise HTTPException(409,"替代搭配须来自同一次确认样本分析")
    before={wanted["id_a"]:wanted["case_a"],wanted["id_b"]:wanted["case_b"]}
    after={alternate["id_a"]:alternate["case_a"],alternate["id_b"]:alternate["case_b"]}
    removed,added=set(before)-set(after),set(after)-set(before)
    if len(removed)!=1 or len(added)!=1:
        raise HTTPException(409,"使用一个保留物资、一个替换物资的共需搭配")
    old,new=next(iter(removed)),next(iter(added))
    if before[old]!=after[new]:
        raise HTTPException(409,"换品箱规不等量，无法核抵原点位需求")
    return old,new
