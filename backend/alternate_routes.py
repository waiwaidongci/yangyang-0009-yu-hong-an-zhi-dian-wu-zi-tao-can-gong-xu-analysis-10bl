from fastapi import APIRouter,Depends
from alternate_kits import admit,offers,propose
from alternate_models import AlternateKit,SiteConsent
from core import db,require

router=APIRouter(prefix="/flood-responses/{incident}/alternates")


@router.get("")
def offer_sheet(incident:int,_=Depends(require())):
    with db() as cx:
        return offers(cx,incident)


@router.post("",status_code=201)
def alternative(incident:int,body:AlternateKit,user=Depends(require("operator"))):
    with db() as cx:
        return propose(cx,incident,body.model_dump(),user["email"])


@router.post("/{offer_id}/consent",status_code=201)
def consent(incident:int,offer_id:int,body:SiteConsent,user=Depends(require("reviewer"))):
    with db() as cx:
        return admit(cx,incident,offer_id,body.consent_ref,user["email"])
