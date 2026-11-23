from typing import Literal
from pydantic import BaseModel,Field


class HandoverCount(BaseModel):
    counted_a:int=Field(ge=0,le=720000)
    counted_b:int=Field(ge=0,le=720000)
    proof_ref:str=Field(min_length=4,max_length=180)


class SignHandover(BaseModel):
    disposition:Literal["verified","record_loss","relay_pending"]
    note:str=Field(min_length=4,max_length=180)
