from calendar import monthrange
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Goal, Task
from ..schemas import GoalIn
from .dependencies import current_user

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])
RANK = {"day": 0, "week": 1, "month": 2}

def owned_goal(db, goal_id, user):
    goal = db.get(Goal, goal_id)
    if not goal or goal.deleted_at or goal.user_id != user.id:
        raise HTTPException(404, "Цель не найдена")
    return goal

def assign_values(db, goal, data, user):
    if data.parent_id:
        parent = owned_goal(db, data.parent_id, user)
        if parent.id == goal.id or RANK[parent.period] <= RANK[data.period]:
            raise HTTPException(400, "Родительская цель должна быть более длительного периода")
    if goal.id:
        children = db.scalars(select(Goal).where(Goal.parent_id == goal.id, Goal.deleted_at == None))
        if any(RANK[child.period] >= RANK[data.period] for child in children):
            raise HTTPException(400, "Сначала измените привязку дочерних целей")
    start = data.date
    if data.period == "week": start -= timedelta(days=start.weekday())
    if data.period == "month": start = start.replace(day=1)
    end = start + timedelta(days=6) if data.period == "week" else start.replace(day=monthrange(start.year, start.month)[1]) if data.period == "month" else start
    goal.title, goal.why, goal.period = data.title, data.why, data.period
    goal.period_start, goal.period_end, goal.parent_id = start, end, data.parent_id

def output(db, goal):
    tasks = list(db.scalars(select(Task).where(Task.goal_id == goal.id, Task.deleted_at == None)))
    counted = [t for t in tasks if t.status != "cancelled"]
    completed = sum(t.status == "completed" for t in counted)
    return dict(id=goal.id, title=goal.title, why=goal.why, period=goal.period,
                period_start=goal.period_start, period_end=goal.period_end, parent_id=goal.parent_id,
                total=len(counted), completed=completed,
                progress=round(100 * completed / len(counted)) if counted else 0)

@router.get("")
def list_goals(db: Session = Depends(get_db), user=Depends(current_user)):
    return [output(db, goal) for goal in db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.deleted_at == None).order_by(Goal.period_start.desc(), Goal.created_at))]

@router.post("", status_code=201)
def create_goal(data: GoalIn, db: Session = Depends(get_db), user=Depends(current_user)):
    goal = Goal(user_id=user.id)
    assign_values(db, goal, data, user)
    db.add(goal); db.commit()
    return output(db, goal)

@router.put("/{goal_id}")
def edit_goal(goal_id: str, data: GoalIn, db: Session = Depends(get_db), user=Depends(current_user)):
    goal = owned_goal(db, goal_id, user)
    assign_values(db, goal, data, user); db.commit()
    return output(db, goal)

@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    goal = owned_goal(db, goal_id, user)
    goal.deleted_at = datetime.now(timezone.utc)
    for task in db.scalars(select(Task).where(Task.goal_id == goal.id)):
        task.goal_id = None
        task.sync_version = (task.sync_version or 0) + 1
    for child in db.scalars(select(Goal).where(Goal.parent_id == goal.id)):
        child.parent_id = None
    db.commit()
