from pydantic import BaseModel,Field


class AlternateKit(BaseModel):
    request_id:int=Field(gt=0)
    wanted_pair:int=Field(gt=0)
    alternate_pair:int=Field(gt=0)
    packs:int=Field(ge=1,le=200)
    explanation:str=Field(min_length=4,max_length=180)


class SiteConsent(BaseModel):
    consent_ref:str=Field(min_length=4,max_length=180)
