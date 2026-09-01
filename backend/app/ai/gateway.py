"""Narrow boundary between the assistant and existing planner services."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, or_
from ..models import Task, Project, ProjectMember, Goal
from ..schemas import TaskIn, TaskPatch, ProjectIn

class PlannerGateway:
    def __init__(self, membership, create, patch, create_project):
        self.membership, self.create, self.patch, self.create_project = membership, create, patch, create_project

    def task(self, db, user, task_id, edit=False):
        task=db.get(Task,task_id)
        if not task or task.deleted_at: raise HTTPException(404,"Задача недоступна")
        if task.project_id:
            self.membership(db,task.project_id,user,"edit_tasks" if edit else "view")
        elif task.user_id!=user.id: raise HTTPException(404,"Задача недоступна")
        return task

    def context(self, db, user, data):
        candidates=db.scalars(select(Project).where(Project.deleted_at==None,or_(Project.user_id==user.id,Project.id.in_(select(ProjectMember.project_id).where(ProjectMember.user_id==user.id)))))
        projects=[]
        for project in candidates:
            try: self.membership(db,project.id,user,"view")
            except HTTPException: continue
            projects.append(project)
        project_ids=[p.id for p in projects]
        query=select(Task).where(Task.deleted_at==None,Task.archived_at==None,or_((Task.user_id==user.id)&(Task.project_id==None),Task.project_id.in_(project_ids)))
        if data.search: query=query.where(or_(Task.title.icontains(data.search,autoescape=True),Task.description.icontains(data.search,autoescape=True)))
        if data.day:
            start=datetime.combine(data.day,datetime.min.time(),ZoneInfo(user.timezone))
            end=start+timedelta(days=1)
            query=query.where(or_((Task.start_at>=start)&(Task.start_at<end),(Task.deadline_at>=start)&(Task.deadline_at<end)))
        tasks=list(db.scalars(query.order_by(Task.updated_at.desc()).limit(51)))
        truncated=len(tasks)>50
        tasks=tasks[:50]
        def stamp(value):
            if not value:return None
            return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
        records=[dict(id=t.id,title=t.title,description=t.description[:300],status=t.status,priority=t.priority,start_at=stamp(t.start_at),end_at=stamp(t.end_at),deadline_at=stamp(t.deadline_at),duration_minutes=t.duration_minutes,project_id=t.project_id) for t in tasks]
        goals=list(db.scalars(select(Goal).where(Goal.user_id==user.id,Goal.deleted_at==None).order_by(Goal.period_start.desc()).limit(11)))
        context={"now":datetime.now(timezone.utc).isoformat(),"timezone":user.timezone,"tasks":records,
                 "projects":[{"id":p.id,"name":p.name} for p in projects[:20]],
                 "goals":[{"id":g.id,"title":g.title,"why":g.why[:200],"period_start":str(g.period_start),"period_end":str(g.period_end)} for g in goals[:10]],
                 "truncated":truncated or len(projects)>20 or len(goals)>10,
                 "scope":"Доступные неархивные задачи и их календарные даты; проекты и личные цели. Внешние календари не включены."}
        return context,{t.id:t for t in tasks}

    def execute(self, db, user, proposal):
        if proposal.kind=="create_task":
            return self.create(TaskIn(**proposal.changes),user,db,commit=False)
        if proposal.kind=="project_plan":
            plan=proposal.changes
            goal_id=plan.get("goal_id")
            if goal_id:
                goal=db.get(Goal,goal_id)
                if not goal or goal.user_id!=user.id or goal.deleted_at:raise HTTPException(404,"Цель недоступна")
            project=self.create_project(ProjectIn(name=plan["project_name"],description=plan.get("project_description",""),color=plan.get("color","#5577e7"),priority=plan.get("priority","P3")),user,db,commit=False)
            tasks=[]
            for stage in plan["stages"]:
                tasks.append(self.create(TaskIn(**stage,project_id=project["id"],goal_id=goal_id),user,db,commit=False))
            return {"project_id":project["id"],"project_name":project["name"],"task_ids":[task["id"] for task in tasks]}
        self.task(db,user,proposal.task_id,edit=True)
        return self.patch(proposal.task_id,TaskPatch(**proposal.changes,sync_version=proposal.expected_version),user,db,commit=False)
