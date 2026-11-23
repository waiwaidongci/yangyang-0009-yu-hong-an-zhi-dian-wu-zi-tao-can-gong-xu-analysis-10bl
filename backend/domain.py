from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, enqueue, require
from dispatch import add_request, confirm_request, dispose, draft, inventory, mine, new_survey, requests_for, response_for, slips_for, survey_results

from alternate_routes import router as alternate_router
from handover_routes import router as handover_router
from lot_routes import router as lot_router

router = APIRouter(prefix="/api")
router.include_router(lot_router)
router.include_router(alternate_router)
router.include_router(handover_router)
any_role = require()
staff = require("operator", "reviewer")
reviewer = require("reviewer")
operator = require("operator")


class Line(BaseModel):
    item_id: int = Field(gt=0)
    units: int = Field(ge=1, le=3600)


class DemandSheet(BaseModel):
    slip: str = Field(pattern=r"^[A-Z0-9-]{3,28}$")
    shelter: str = Field(min_length=2, max_length=90)
    households: int = Field(ge=1, le=600)
    lines: list[Line] = Field(min_length=1, max_length=30)


class MiningRule(BaseModel):
    min_support_pct: int = Field(ge=1, le=100)
    min_lift: float = Field(ge=1, le=25)


class IssueDraft(BaseModel):
    request_id: int = Field(gt=0)
    pair_id: int = Field(gt=0)
    packs: int = Field(ge=1, le=200)


class Decision(BaseModel):
    note: str = Field(min_length=4, max_length=200)


@router.get("/flood-responses")
def responses(_=Depends(any_role)):
    with db() as cx:
        return cx.execute("SELECT * FROM flood_responses ORDER BY id").fetchall()


@router.get("/flood-responses/{incident}/requests")
def requests(incident: int, _=Depends(any_role)):
    with db() as cx:
        return {"incident": response_for(cx, incident), "stock": inventory(cx, incident),
                "requests": requests_for(cx, incident)}


@router.post("/flood-responses/{incident}/requests", status_code=201)
def create_request(incident: int, body: DemandSheet, _=Depends(operator)):
    with db() as cx:
        return add_request(cx, incident, body.model_dump())


@router.post("/flood-responses/{incident}/requests/{request_id}/confirm")
def confirm(incident: int, request_id: int, user=Depends(reviewer)):
    with db() as cx:
        return confirm_request(cx, incident, request_id, user["email"])


@router.get("/flood-responses/{incident}/surveys")
def surveys(incident: int, _=Depends(any_role)):
    with db() as cx:
        return {"incident": response_for(cx, incident), "surveys": survey_results(cx, incident)}


@router.post("/flood-responses/{incident}/surveys", status_code=202)
def launch_survey(incident: int, body: MiningRule, _=Depends(staff)):
    with db() as cx:
        row = new_survey(cx, incident, body.min_support_pct, body.min_lift)
        return {"survey": row, "job_id": enqueue(cx, "mine_relief_pairs", {"survey_id": row["id"]})}


@router.get("/flood-responses/{incident}/issue-slips")
def issue_slips(incident: int, _=Depends(any_role)):
    with db() as cx:
        return {"incident": response_for(cx, incident), "stock": inventory(cx, incident),
                "slips": slips_for(cx, incident)}


@router.post("/flood-responses/{incident}/issue-slips", status_code=201)
def stage_slip(incident: int, body: IssueDraft, user=Depends(operator)):
    with db() as cx:
        return draft(cx, incident, body.model_dump(), user["email"])


@router.post("/flood-responses/{incident}/issue-slips/{slip_id}/approve")
def approve(incident: int, slip_id: int, body: Decision, user=Depends(reviewer)):
    with db() as cx:
        return dispose(cx, incident, slip_id, "approved", body.note, user["email"])


@router.post("/flood-responses/{incident}/issue-slips/{slip_id}/shelve")
def shelve(incident: int, slip_id: int, body: Decision, user=Depends(staff)):
    with db() as cx:
        return dispose(cx, incident, slip_id, "shelved", body.note, user["email"])


def run_job(cx, kind, payload):
    if kind != "mine_relief_pairs":
        raise HTTPException(422, "不支持的安置点共需分析")
    return mine(cx, payload["survey_id"])


def seed(cx):
    row = cx.execute(
        """INSERT INTO flood_responses(response_code,river_sector,warehouse)
           VALUES ('F-1123','青堤河西岸','清桥应急中转库')
           ON CONFLICT (response_code) DO NOTHING RETURNING *""",
    ).fetchone()
    if row:
        incident = row["id"]
        supplies = [("MAT","隔潮睡垫",6,36,12), ("QUILT","保温毯",4,24,8),
                    ("LAMP","应急灯",4,32,4), ("WATER","饮用水",12,180,24), ("KIT","清洁包",5,70,10)]
        for item in supplies:
            cx.execute(
                "INSERT INTO depot_items(response_id,sku,name,case_size,on_hand,protected_units) "
                "VALUES (%s,%s,%s,%s,%s,%s)", (incident,*item),
            )
        stock = {item["sku"]: item["id"] for item in inventory(cx, incident)}
        baskets = [
            ("西河小学", {"MAT":24, "QUILT":20, "WATER":48}),
            ("运河礼堂", {"MAT":30, "QUILT":24}),
            ("桥头体育馆", {"MAT":18, "QUILT":16}),
            ("马场社区站", {"MAT":24, "QUILT":20}),
            ("前滩职校", {"MAT":24, "LAMP":12}),
            ("柳塘活动室", {"QUILT":16, "WATER":36}),
            ("江岸中学", {"LAMP":12, "KIT":20}),
            ("澄湾居委会", {"WATER":48, "KIT":25}),
        ]
        first = None
        for index, (site, goods) in enumerate(baskets, 1):
            need = add_request(cx, incident, {
                "slip": f"QA-W{index:02d}", "shelter": site, "households": 14 + index * 2,
                "lines": [{"item_id":stock[sku],"units":count} for sku,count in goods.items()],
            })
            confirm_request(cx, incident, need["id"], "seed@depot.local")
            if index == 1:
                first = need
        add_request(cx, incident, {
            "slip": "QA-W09", "shelter": "南堤文化站", "households": 20,
            "lines": [{"item_id": stock["WATER"], "units": 36}, {"item_id": stock["KIT"], "units": 15}],
        })
        survey = new_survey(cx, incident, 30, 1.10)
        mine(cx, survey["id"])
        pair = survey_results(cx, incident)[0]["pairs"][0]
        draft(cx, incident, {"request_id": first["id"], "pair_id": pair["id"], "packs": 2}, "seed@depot.local")
    return {table: cx.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in ("flood_responses","depot_items","shelter_requisitions","requisition_lines",
                          "co_demand_surveys","co_demand_pairs","issue_slips")}
