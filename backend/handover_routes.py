from fastapi import APIRouter,Depends
from core import db,require
from handover_models import HandoverCount,SignHandover
from handover_service import close,packing_receipts,submit

router=APIRouter(prefix="/flood-responses/{incident}/handovers")


@router.get("")
def in_transit(incident:int,_=Depends(require())):
    with db() as cx:
        return packing_receipts(cx,incident)


@router.post("/{slip_id}",status_code=201)
def count_at_shelter(incident:int,slip_id:int,body:HandoverCount,user=Depends(require("operator"))):
    with db() as cx:
        return submit(cx,incident,slip_id,body.model_dump(),user["email"])


@router.post("/{slip_id}/verify")
def review_at_shelter(incident:int,slip_id:int,body:SignHandover,user=Depends(require("reviewer"))):
    with db() as cx:
        return close(cx,incident,slip_id,body.model_dump(),user["email"])
