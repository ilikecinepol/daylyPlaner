import csv, io
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from ..api.dependencies import current_user, iso_utc
from ..database import get_db
from ..models import FinanceAccount, FinanceCategory, FinanceTransaction, Goal, Project, ProjectMember, Task, TaskFinanceBinding
from .schemas import AccountIn, CategoryIn, TransactionIn
from .service import execute_task_finance

router=APIRouter(prefix="/api/v1/finance",tags=["finance"])
DEFAULTS={"expense":["Продукты","Транспорт","Жильё","Подписки","Здоровье","Спорт","Развлечения","Покупки","Образование","Другое"],"income":["Зарплата","Подработка","Продажи","Подарки","Другое"]}

def money(value):return format(Decimal(value or 0),".2f")
def owned(db,model,obj_id,user,label="Объект"):
    obj=db.get(model,obj_id)
    if not obj or obj.user_id!=user.id or getattr(obj,"deleted_at",None):raise HTTPException(404,f"{label} не найден")
    return obj
def account_balance(db,account):
    value=Decimal(account.opening_balance)
    for tx in db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id==account.user_id,FinanceTransaction.deleted_at==None,or_(FinanceTransaction.account_id==account.id,FinanceTransaction.destination_account_id==account.id))):
        amount=Decimal(tx.amount)
        if tx.type=="income" and tx.account_id==account.id:value+=amount
        elif tx.type=="expense" and tx.account_id==account.id:value-=amount
        elif tx.type=="transfer":value+=amount if tx.destination_account_id==account.id else -amount
    return value
def account_out(db,a):return {"id":a.id,"name":a.name,"type":a.type,"currency":a.currency,"opening_balance":money(a.opening_balance),"balance":money(account_balance(db,a)),"is_archived":a.is_archived,"created_at":iso_utc(a.created_at)}
def category_out(c):return {"id":c.id,"name":c.name,"type":c.type,"color":c.color,"is_default":c.is_default}
def transaction_out(t):return {"id":t.id,"type":t.type,"amount":money(t.amount),"currency":t.currency,"account_id":t.account_id,"destination_account_id":t.destination_account_id,"category_id":t.category_id,"transaction_at":iso_utc(t.transaction_at),"description":t.description,"task_id":t.task_id,"project_id":t.project_id,"goal_id":t.goal_id,"goal_contribution":t.goal_contribution}
def ensure_defaults(db,user):
    if db.scalar(select(FinanceCategory.id).where(FinanceCategory.user_id==user.id).limit(1)):return
    for kind,names in DEFAULTS.items():
        for name in names:db.add(FinanceCategory(user_id=user.id,name=name,type=kind,is_default=True))
    db.commit()
def validate_transaction(db,data,user,existing=None):
    source=owned(db,FinanceAccount,data.account_id,user,"Счёт")
    if source.currency!=data.currency:raise HTTPException(400,"Валюта операции не совпадает с валютой счёта")
    if data.destination_account_id:
        target=owned(db,FinanceAccount,data.destination_account_id,user,"Счёт назначения")
        if target.currency!=source.currency:raise HTTPException(400,"Переводы между разными валютами не поддерживаются в Finance v1")
    if data.category_id:
        category=owned(db,FinanceCategory,data.category_id,user,"Категория")
        if data.type!="transfer" and category.type!=data.type:raise HTTPException(400,"Тип категории не совпадает с операцией")
    if data.goal_id:
        goal=owned(db,Goal,data.goal_id,user,"Цель")
        if data.goal_contribution and (not goal.target_amount or goal.currency!=data.currency):raise HTTPException(400,"Вклад не соответствует финансовой цели")
    if data.task_id:owned(db,Task,data.task_id,user,"Задача")
    if data.project_id:
        p=db.get(Project,data.project_id)
        member=p and (p.user_id==user.id or db.scalar(select(ProjectMember.id).where(ProjectMember.project_id==p.id,ProjectMember.user_id==user.id)))
        if not p or p.deleted_at or not member:raise HTTPException(404,"Проект не найден")

@router.get("/accounts")
def accounts(db:Session=Depends(get_db),user=Depends(current_user)):return [account_out(db,a) for a in db.scalars(select(FinanceAccount).where(FinanceAccount.user_id==user.id,FinanceAccount.deleted_at==None).order_by(FinanceAccount.created_at))]
@router.post("/accounts",status_code=201)
def create_account(data:AccountIn,db:Session=Depends(get_db),user=Depends(current_user)):
    a=FinanceAccount(user_id=user.id,**data.model_dump());db.add(a);db.commit();return account_out(db,a)
@router.patch("/accounts/{item_id}")
def edit_account(item_id:str,data:AccountIn,db:Session=Depends(get_db),user=Depends(current_user)):
    a=owned(db,FinanceAccount,item_id,user,"Счёт")
    if a.currency!=data.currency and db.scalar(select(FinanceTransaction.id).where(FinanceTransaction.user_id==user.id,or_(FinanceTransaction.account_id==a.id,FinanceTransaction.destination_account_id==a.id),FinanceTransaction.deleted_at==None).limit(1)):raise HTTPException(409,"Нельзя менять валюту счёта с операциями")
    for k,v in data.model_dump().items():setattr(a,k,v)
    db.commit();return account_out(db,a)
@router.delete("/accounts/{item_id}",status_code=204)
def delete_account(item_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    a=owned(db,FinanceAccount,item_id,user,"Счёт");a.deleted_at=datetime.now(timezone.utc);db.commit()

@router.get("/categories")
def categories(db:Session=Depends(get_db),user=Depends(current_user)):
    ensure_defaults(db,user);return [category_out(c) for c in db.scalars(select(FinanceCategory).where(FinanceCategory.user_id==user.id,FinanceCategory.deleted_at==None).order_by(FinanceCategory.type,FinanceCategory.name))]
@router.post("/categories",status_code=201)
def create_category(data:CategoryIn,db:Session=Depends(get_db),user=Depends(current_user)):
    c=FinanceCategory(user_id=user.id,**data.model_dump());db.add(c);db.commit();return category_out(c)
@router.patch("/categories/{item_id}")
def edit_category(item_id:str,data:CategoryIn,db:Session=Depends(get_db),user=Depends(current_user)):
    c=owned(db,FinanceCategory,item_id,user,"Категория")
    for k,v in data.model_dump().items():setattr(c,k,v)
    db.commit();return category_out(c)

def transaction_query(user,from_,to,account,category,project,goal,type_):
    q=select(FinanceTransaction).where(FinanceTransaction.user_id==user.id,FinanceTransaction.deleted_at==None)
    if from_:q=q.where(FinanceTransaction.transaction_at>=from_)
    if to:q=q.where(FinanceTransaction.transaction_at<to)
    if account:q=q.where(or_(FinanceTransaction.account_id==account,FinanceTransaction.destination_account_id==account))
    if category:q=q.where(FinanceTransaction.category_id==category)
    if project:q=q.where(FinanceTransaction.project_id==project)
    if goal:q=q.where(FinanceTransaction.goal_id==goal)
    if type_:q=q.where(FinanceTransaction.type==type_)
    return q
@router.get("/transactions")
def transactions(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,account:str|None=None,category:str|None=None,project:str|None=None,goal:str|None=None,type_:str|None=Query(None,alias="type"),db:Session=Depends(get_db),user=Depends(current_user)):
    return [transaction_out(t) for t in db.scalars(transaction_query(user,from_,to,account,category,project,goal,type_).order_by(FinanceTransaction.transaction_at.desc()))]
@router.post("/transactions",status_code=201)
def create_transaction(data:TransactionIn,db:Session=Depends(get_db),user=Depends(current_user)):
    validate_transaction(db,data,user);t=FinanceTransaction(user_id=user.id,**data.model_dump());db.add(t);db.commit();return transaction_out(t)
@router.patch("/transactions/{item_id}")
def edit_transaction(item_id:str,data:TransactionIn,db:Session=Depends(get_db),user=Depends(current_user)):
    t=owned(db,FinanceTransaction,item_id,user,"Операция");validate_transaction(db,data,user,t)
    for k,v in data.model_dump().items():setattr(t,k,v)
    db.commit();return transaction_out(t)
@router.delete("/transactions/{item_id}",status_code=204)
def delete_transaction(item_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    t=owned(db,FinanceTransaction,item_id,user,"Операция");t.deleted_at=datetime.now(timezone.utc);binding=db.scalar(select(TaskFinanceBinding).where(TaskFinanceBinding.transaction_id==t.id));
    if binding:binding.transaction_id=None
    db.commit()

def analytics_data(db,user,from_,to,currency=None):
    txs=list(db.scalars(transaction_query(user,from_,to,None,None,None,None,None)))
    if currency:txs=[t for t in txs if t.currency==currency]
    totals=defaultdict(lambda:{"income":Decimal(0),"expense":Decimal(0)})
    by_category=defaultdict(Decimal);by_account=defaultdict(Decimal);by_project=defaultdict(Decimal);timeline=defaultdict(lambda:{"income":Decimal(0),"expense":Decimal(0)})
    for t in txs:
        if t.type=="transfer":continue
        amount=Decimal(t.amount);totals[t.currency][t.type]+=amount;timeline[str(t.transaction_at.date())][t.type]+=amount
        if t.type=="expense":
            if t.category_id:by_category[t.category_id]+=amount
            by_account[t.account_id]+=amount
            if t.project_id:by_project[t.project_id]+=amount
    planned=defaultdict(lambda:{"income":Decimal(0),"expense":Decimal(0)})
    q=select(TaskFinanceBinding).join(Task,Task.id==TaskFinanceBinding.task_id).where(TaskFinanceBinding.user_id==user.id,TaskFinanceBinding.transaction_id==None,Task.deleted_at==None,Task.status.notin_(["completed","cancelled"]))
    if from_:q=q.where(Task.start_at>=from_)
    if to:q=q.where(Task.start_at<to)
    for b in db.scalars(q):planned[b.currency][b.type]+=Decimal(b.amount)
    return {"period":{"from":iso_utc(from_),"to":iso_utc(to)},"totals":[{"currency":c,"income":money(v["income"]),"expense":money(v["expense"]),"net":money(v["income"]-v["expense"])} for c,v in totals.items()],"planned":[{"currency":c,"income":money(v["income"]),"expense":money(v["expense"]),"net":money(v["income"]-v["expense"])} for c,v in planned.items()],"by_category":[{"category_id":k,"amount":money(v)} for k,v in by_category.items()],"by_account":[{"account_id":k,"amount":money(v)} for k,v in by_account.items()],"by_project":[{"project_id":k,"amount":money(v)} for k,v in by_project.items()],"timeline":[{"date":k,"income":money(v["income"]),"expense":money(v["expense"])} for k,v in sorted(timeline.items())],"transaction_count":len(txs)}
@router.get("/analytics")
def analytics(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,currency:str|None=None,db:Session=Depends(get_db),user=Depends(current_user)):return analytics_data(db,user,from_,to,currency)
@router.get("/overview")
def overview(db:Session=Depends(get_db),user=Depends(current_user)):
    accts=[account_out(db,a) for a in db.scalars(select(FinanceAccount).where(FinanceAccount.user_id==user.id,FinanceAccount.deleted_at==None,FinanceAccount.is_archived==False))]
    return {"accounts":accts,"balances":[{"currency":c,"amount":money(sum(Decimal(a["balance"]) for a in accts if a["currency"]==c))} for c in sorted({a["currency"] for a in accts})],"latest":[transaction_out(t) for t in db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id==user.id,FinanceTransaction.deleted_at==None).order_by(FinanceTransaction.transaction_at.desc()).limit(8))]}
@router.get("/planned")
def planned(db:Session=Depends(get_db),user=Depends(current_user)):
    result=[]
    for b in db.scalars(select(TaskFinanceBinding).where(TaskFinanceBinding.user_id==user.id,TaskFinanceBinding.deleted_at==None)):
        task=db.get(Task,b.task_id)
        if task and not task.deleted_at:result.append({"task_id":task.id,"type":b.type,"amount":money(b.amount),"currency":b.currency,"account_id":b.account_id,"category_id":b.category_id,"transaction_id":b.transaction_id,"planned_at":iso_utc(task.start_at),"status":"actual" if b.transaction_id else "planned"})
    return result
@router.post("/tasks/{task_id}/execute")
def execute(task_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    task=owned(db,Task,task_id,user,"Задача")
    try:
        tx,created=execute_task_finance(db,task,user);db.commit()
    except Exception:
        db.rollback();raise
    return {"created":created,"transaction":transaction_out(tx),"task_id":task.id,"task_status":task.status}
@router.get("/report")
def report(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,format:str="json",db:Session=Depends(get_db),user=Depends(current_user)):
    txs=list(db.scalars(transaction_query(user,from_,to,None,None,None,None,None).order_by(FinanceTransaction.transaction_at.desc())))
    if format!="csv":return {"analytics":analytics_data(db,user,from_,to),"transactions":[transaction_out(t) for t in txs]}
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(["date","type","amount","currency","description","account_id","category_id","project_id","goal_id"])
    for t in txs:writer.writerow([iso_utc(t.transaction_at),t.type,money(t.amount),t.currency,t.description,t.account_id,t.category_id or "",t.project_id or "",t.goal_id or ""])
    return StreamingResponse(iter([stream.getvalue().encode("utf-8-sig")]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=finance-report.csv"})
