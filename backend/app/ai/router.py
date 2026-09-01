import json
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ActivityLog
from ..api.dependencies import current_user, iso_utc
from ..services.scheduling import normalize_schedule
from . import provider
from .access import allowed, require_access, provider_name
from .models import AIConversation, AIRequest, AIProposal, AIQuota
from .schemas import ChatIn, Decision, ProjectPlan, ProjectPlanEdit

def limit(name, default): return max(1,min(int(os.getenv(name,str(default))),1000))

def reserve(db,user):
    day=datetime.now(timezone.utc).date().isoformat()
    for scope, maximum in [("global",limit("AI_GLOBAL_DAILY_LIMIT",100)),(user.id,limit("AI_USER_DAILY_LIMIT",20))]:
        if not db.get(AIQuota,(scope,day)):
            try:
                with db.begin_nested():db.add(AIQuota(scope=scope,day=day,requests=0));db.flush()
            except IntegrityError:pass
        changed=db.execute(update(AIQuota).where(AIQuota.scope==scope,AIQuota.day==day,AIQuota.requests<maximum).values(requests=AIQuota.requests+1)).rowcount
        if not changed:
            db.rollback();raise HTTPException(429,"Дневной лимит AI исчерпан. Сброс — в 00:00 UTC.")

def conversation(db,user,conversation_id):
    item=db.get(AIConversation,conversation_id)
    if not item or item.user_id!=user.id:raise HTTPException(404,"Диалог не найден")
    return item

def proposal_out(p):
    return {"id":p.id,"kind":p.kind,"task_id":p.task_id,"before":p.before,
            "changes":{} if p.kind=="project_plan" else p.changes,
            "plan":p.changes if p.kind=="project_plan" else None,
            "status":p.status,"result_task_id":p.result_task_id,"result":p.result or {}}

def make_router(gateway):
    router=APIRouter(prefix="/api/v1/ai",tags=["AI module"])

    def request_out(db,user,row):
        for source in row.sources:
            try:gateway.task(db,user,source["id"])
            except HTTPException:
                return {"id":row.id,"prompt":row.prompt,"answer":"Доступ к данным этого ответа изменился. Задайте вопрос заново.","status":row.status,"sources":[],"proposals":[]}
        return {"id":row.id,"request_key":row.request_key,"prompt":row.prompt,"answer":row.answer,"status":row.status,"sources":row.sources,
                "proposals":[proposal_out(p) for p in db.scalars(select(AIProposal).where(AIProposal.request_id==row.id))]}

    @router.get("/status")
    def status(db:Session=Depends(get_db),user=Depends(current_user)):
        day=datetime.now(timezone.utc).date().isoformat();quota=db.get(AIQuota,(user.id,day))
        mode=provider_name()
        ready=provider.configured(mode)
        return {"enabled":os.getenv("AI_ENABLED","0")=="1","access":bool(allowed(db,user)),"provider":mode,"ready":ready,
                "model":provider.configured_model(mode),"used":quota.requests if quota else 0,"daily_limit":limit("AI_USER_DAILY_LIMIT",20),"reset_timezone":"UTC"}

    @router.get("/conversations")
    def conversations(db:Session=Depends(get_db),user=Depends(current_user)):
        return [{"id":c.id,"title":c.title} for c in db.scalars(select(AIConversation).where(AIConversation.user_id==user.id).order_by(AIConversation.created_at.desc()).limit(50))]

    @router.post("/conversations",status_code=201)
    def create_conversation(db:Session=Depends(get_db),user=Depends(current_user)):
        require_access(db,user)
        c=AIConversation(user_id=user.id);db.add(c);db.commit()
        return {"id":c.id,"title":c.title}

    @router.get("/conversations/{conversation_id}")
    def history(conversation_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
        conversation(db,user,conversation_id)
        rows=list(db.scalars(select(AIRequest).where(AIRequest.conversation_id==conversation_id).order_by(AIRequest.created_at.desc()).limit(50)))
        return [request_out(db,user,row) for row in reversed(rows)]

    @router.delete("/conversations/{conversation_id}",status_code=204)
    def erase(conversation_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
        c=conversation(db,user,conversation_id)
        ids=select(AIRequest.id).where(AIRequest.conversation_id==c.id)
        db.execute(delete(AIProposal).where(AIProposal.request_id.in_(ids)))
        # Keep only anonymous-content usage counters; erase prompts, answers and sources.
        db.execute(update(AIRequest).where(AIRequest.conversation_id==c.id).values(conversation_id=None,prompt="",answer="",sources=[],status="deleted"))
        db.delete(c);db.commit()

    @router.post("/conversations/{conversation_id}/messages")
    async def chat(conversation_id:str,data:ChatIn,db:Session=Depends(get_db),user=Depends(current_user)):
        require_access(db,user);c=conversation(db,user,conversation_id)
        old=db.scalar(select(AIRequest).where(AIRequest.user_id==user.id,AIRequest.request_key==str(data.request_key)))
        if old:
            if old.conversation_id!=conversation_id:raise HTTPException(409,"Ключ запроса уже использован")
            return request_out(db,user,old)
        context,snapshot=gateway.context(db,user,data)
        previous=list(db.scalars(select(AIRequest).where(AIRequest.conversation_id==c.id,AIRequest.status=="completed").order_by(AIRequest.created_at.desc()).limit(6)))
        context["conversation"]=[{"user":item.prompt[:2000],"assistant":item.answer[:4000]} for item in reversed(previous)]
        while len(json.dumps(context,ensure_ascii=False))>24000 and context["tasks"]:
            removed=context["tasks"].pop();snapshot.pop(removed["id"],None);context["truncated"]=True
        if len(json.dumps(context,ensure_ascii=False))>24000:raise HTTPException(400,"Уточните область поиска")
        sources=[{"id":t["id"],"title":t["title"]} for t in context["tasks"]]
        versions={key:task.sync_version for key,task in snapshot.items()}
        before={key:{field:getattr(task,field) for field in ["title","description","status","priority","start_at","end_at","deadline_at","duration_minutes"]} for key,task in snapshot.items()}
        mode=provider_name()
        if not provider.configured(mode):raise HTTPException(503,"AI-провайдер не настроен. Проверьте ключ и модель в окружении backend.")
        reserve(db,user)
        row=AIRequest(user_id=user.id,conversation_id=c.id,request_key=str(data.request_key),prompt=data.message,provider=mode,sources=sources)
        db.add(row);c.title=data.message[:120]
        try:db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,"Запрос уже обрабатывается")
        try:
            answer,input_tokens,output_tokens=await provider.generate(data.message,context,mode)
            db.expire_all();row=db.get(AIRequest,row.id)
            if row.status!="running":return request_out(db,user,row)
            if not db.execute(update(AIRequest).where(AIRequest.id==row.id,AIRequest.status=="running").values(status="finishing")).rowcount:
                db.rollback();db.refresh(row);return request_out(db,user,row)
            require_access(db,user)
            for source in sources:gateway.task(db,user,source["id"])
            for item in answer.proposals:
                if item.kind=="project_plan":
                    if item.task_id or item.changes is not None or item.plan is None:raise ValueError("Invalid project plan")
                    plan=item.plan.model_dump(mode="json")
                    known_goals={goal["id"] for goal in context["goals"]}
                    if plan.get("goal_id") and plan["goal_id"] not in known_goals:raise ValueError("Unknown goal")
                    plan["stages"]=[normalize_schedule(stage,None) for stage in plan["stages"]]
                    plan=ProjectPlan.model_validate(plan).model_dump(mode="json")
                    db.add(AIProposal(request_id=row.id,kind=item.kind,before={},changes=plan))
                    continue
                if item.plan is not None or item.changes is None:raise ValueError("Invalid task proposal")
                changes=item.changes.model_dump(exclude_none=True)
                if not changes:raise ValueError("Empty proposal")
                target=None
                if item.kind=="create_task":
                    if item.task_id or not changes.get("title"):raise ValueError("Invalid create")
                else:
                    if item.task_id not in versions:raise ValueError("Unknown task")
                    target=gateway.task(db,user,item.task_id,edit=True)
                    if target.sync_version!=versions[item.task_id]:raise ValueError("Task changed during generation")
                changes=normalize_schedule(changes,target)
                serialize=lambda value:iso_utc(value) if isinstance(value,datetime) else value
                fields={k:serialize(v) for k,v in changes.items()}
                previous={k:serialize(before[item.task_id].get(k)) for k in changes} if target else {}
                db.add(AIProposal(request_id=row.id,kind=item.kind,task_id=item.task_id,expected_version=versions.get(item.task_id),before=previous,changes=fields))
            row.answer=answer.answer;row.status="completed";row.input_tokens=input_tokens;row.output_tokens=output_tokens
            db.commit()
        except Exception:
            # Never expose provider errors, prompts, credentials or raw response bodies.
            db.rollback();row=db.get(AIRequest,row.id)
            if row and row.status in {"running","finishing"}:
                row.status="failed";row.answer="Не удалось подготовить ответ. Проверьте настройки AI или уточните запрос. Задачи не изменены.";db.commit()
        return request_out(db,user,row)

    @router.post("/requests/{request_id}/cancel")
    def cancel(request_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
        row=db.get(AIRequest,request_id)
        if not row or row.user_id!=user.id:raise HTTPException(404,"Запрос не найден")
        db.execute(update(AIRequest).where(AIRequest.id==row.id,AIRequest.status=="running").values(status="cancelled",answer="Запрос отменён. Задачи не изменены."))
        db.commit();db.refresh(row);return request_out(db,user,row)

    @router.post("/proposals/{proposal_id}/decision")
    def decide(proposal_id:str,data:Decision,db:Session=Depends(get_db),user=Depends(current_user)):
        require_access(db,user)
        proposal=db.get(AIProposal,proposal_id)
        row=db.get(AIRequest,proposal.request_id) if proposal else None
        if not row or row.user_id!=user.id or not row.conversation_id:raise HTTPException(404,"Предложение не найдено")
        if proposal.status!="pending":return proposal_out(proposal)
        if datetime.now(timezone.utc)-(proposal.created_at.replace(tzinfo=timezone.utc) if proposal.created_at.tzinfo is None else proposal.created_at)>timedelta(hours=1):
            raise HTTPException(409,"Предложение устарело. Задайте запрос заново.")
        if not db.execute(update(AIProposal).where(AIProposal.id==proposal.id,AIProposal.status=="pending").values(status="processing")).rowcount:
            db.rollback();db.refresh(proposal);return proposal_out(proposal)
        try:
            if data.decision=="reject":proposal.status="rejected"
            else:
                result=gateway.execute(db,user,proposal)
                if proposal.kind=="project_plan":
                    proposal.result=result;proposal.status="applied"
                    db.add(ActivityLog(user_id=user.id,action="ai_project_plan_confirmed",changes={"proposal_id":proposal.id,**result}))
                else:
                    proposal.result_task_id=result["id"];proposal.status="applied"
                    db.add(ActivityLog(user_id=user.id,task_id=result["id"],action="ai_change_confirmed",changes={"proposal_id":proposal.id,"kind":proposal.kind}))
            db.commit()
        except Exception:
            db.rollback();raise
        return proposal_out(proposal)

    @router.patch("/proposals/{proposal_id}/project-plan")
    def edit_project_plan(proposal_id:str,data:ProjectPlanEdit,db:Session=Depends(get_db),user=Depends(current_user)):
        require_access(db,user)
        proposal=db.get(AIProposal,proposal_id)
        row=db.get(AIRequest,proposal.request_id) if proposal else None
        if not row or row.user_id!=user.id or not row.conversation_id or proposal.kind!="project_plan":raise HTTPException(404,"План не найден")
        if proposal.status!="pending":raise HTTPException(409,"Можно изменять только ожидающий подтверждения план")
        if datetime.now(timezone.utc)-(proposal.created_at.replace(tzinfo=timezone.utc) if proposal.created_at.tzinfo is None else proposal.created_at)>timedelta(hours=1):raise HTTPException(409,"План устарел. Сформируйте его заново.")
        plan=data.plan.model_dump(mode="json")
        if plan.get("goal_id"):
            goals={goal["id"] for goal in gateway.context(db,user,ChatIn(request_key="00000000-0000-0000-0000-000000000000",message="проверка"))[0]["goals"]}
            if plan["goal_id"] not in goals:raise HTTPException(404,"Цель недоступна")
        plan["stages"]=[ProjectPlan.model_validate({**plan,"stages":[normalize_schedule(stage,None)]}).stages[0].model_dump(mode="json") for stage in plan["stages"]]
        proposal.changes=plan;db.commit();db.refresh(proposal);return proposal_out(proposal)

    return router
