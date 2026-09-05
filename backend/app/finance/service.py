from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from ..models import FinanceAccount, FinanceCategory, FinanceTransaction, Task, TaskFinanceBinding

def set_task_finance(db,task,user,data):
    binding=db.scalar(select(TaskFinanceBinding).where(TaskFinanceBinding.task_id==task.id,TaskFinanceBinding.user_id==user.id))
    if data is None:
        if binding and not binding.transaction_id:db.delete(binding)
        elif binding:raise HTTPException(409,"Проведённую финансовую настройку нельзя удалить из задачи")
        return None
    account=db.get(FinanceAccount,data.account_id)
    if not account or account.user_id!=user.id or account.deleted_at:raise HTTPException(404,"Счёт не найден")
    if account.currency!=data.currency:raise HTTPException(400,"Валюта задачи не совпадает с валютой счёта")
    if data.category_id:
        category=db.get(FinanceCategory,data.category_id)
        if not category or category.user_id!=user.id or category.deleted_at:raise HTTPException(404,"Категория не найдена")
        if category.type!=data.type:raise HTTPException(400,"Тип категории не совпадает с платежом")
    if binding and binding.transaction_id:raise HTTPException(409,"Проведённую финансовую задачу нельзя изменить")
    if not binding:binding=TaskFinanceBinding(task_id=task.id,user_id=user.id);db.add(binding)
    for key,value in data.model_dump().items():setattr(binding,key,value)
    return binding

def clone_task_finance(db,source,child):
    binding=db.scalar(select(TaskFinanceBinding).where(TaskFinanceBinding.task_id==source.id,TaskFinanceBinding.user_id==source.user_id))
    if binding:db.add(TaskFinanceBinding(task_id=child.id,user_id=binding.user_id,type=binding.type,amount=binding.amount,currency=binding.currency,account_id=binding.account_id,category_id=binding.category_id))

def execute_task_finance(db,task,user):
    binding=db.scalar(select(TaskFinanceBinding).where(TaskFinanceBinding.task_id==task.id,TaskFinanceBinding.user_id==user.id).with_for_update())
    if not binding:raise HTTPException(404,"У задачи нет личных финансовых настроек")
    if binding.transaction_id:return db.get(FinanceTransaction,binding.transaction_id),False
    tx=FinanceTransaction(user_id=user.id,type=binding.type,amount=binding.amount,currency=binding.currency,account_id=binding.account_id,category_id=binding.category_id,transaction_at=datetime.now(timezone.utc),description=task.title,task_id=task.id,project_id=task.project_id,goal_id=task.goal_id)
    db.add(tx);db.flush();binding.transaction_id=tx.id
    task.status="completed";task.completed_at=datetime.now(timezone.utc);task.completed_by_id=user.id;task.sync_version=(task.sync_version or 0)+1
    return tx,True
