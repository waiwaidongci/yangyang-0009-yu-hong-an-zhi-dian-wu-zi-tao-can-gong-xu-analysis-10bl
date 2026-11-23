from fastapi import APIRouter, Depends
from core import db,require
from lot_book import lot_book,manifest,receive
from lot_models import ArrivalDay,IntakeLot

router=APIRouter(prefix="/flood-responses/{incident}/lots")
operator=require("operator")


@router.get("")
def lots(incident:int,_=Depends(require())):
    with db() as cx:
        return lot_book(cx,incident)


@router.post("",status_code=201)
def intake(incident:int,body:IntakeLot,user=Depends(operator)):
    with db() as cx:
        return receive(cx,incident,body.model_dump(),user["email"])


@router.post("/manifest/{slip_id}")
def assign(incident:int,slip_id:int,body:ArrivalDay,user=Depends(operator)):
    with db() as cx:
        return manifest(cx,incident,slip_id,body.arrival_day,user["email"])
