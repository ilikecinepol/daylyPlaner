from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class AccountIn(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=160);type:str=Field(pattern="^(bank_card|bank_account|cash|savings|other)$")
    currency:str=Field(pattern="^[A-Z]{3}$");opening_balance:Decimal=Field(default=Decimal("0"),max_digits=18,decimal_places=2);is_archived:bool=False

class CategoryIn(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=100);type:str=Field(pattern="^(income|expense)$");color:str=Field(default="#5577e7",pattern="^#[0-9a-fA-F]{6}$")

class TransactionIn(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    type:str=Field(pattern="^(income|expense|transfer)$");amount:Decimal=Field(gt=0,max_digits=18,decimal_places=2);currency:str=Field(pattern="^[A-Z]{3}$")
    account_id:str;destination_account_id:str|None=None;category_id:str|None=None;transaction_at:datetime;description:str=Field(default="",max_length=4000)
    task_id:str|None=None;project_id:str|None=None;goal_id:str|None=None;goal_contribution:bool=False
    @model_validator(mode="after")
    def rules(self):
        if self.type=="transfer" and (not self.destination_account_id or self.destination_account_id==self.account_id):raise ValueError("Для перевода нужны разные счета")
        if self.type!="transfer" and self.destination_account_id:raise ValueError("Счёт назначения допустим только для перевода")
        if self.goal_contribution and self.type!="transfer":raise ValueError("Вкладом в накопительную цель может быть только перевод")
        return self
