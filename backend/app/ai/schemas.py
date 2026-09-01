from typing import Literal
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: UUID
    message: str = Field(min_length=1, max_length=2000)
    search: str = Field(default="", max_length=100)
    day: date | None = None

class Change(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["idea", "planned", "in_progress", "completed", "cancelled"] | None = None
    priority: Literal["P1", "P2", "P3", "P4"] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    deadline_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=10080)

    @field_validator("start_at", "end_at", "deadline_at")
    @classmethod
    def aware_dates(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("У даты должен быть часовой пояс")
        return value

class PlanStage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"
    start_at: datetime | None = None
    end_at: datetime | None = None
    deadline_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=1, le=10080)

    @field_validator("start_at", "end_at", "deadline_at")
    @classmethod
    def aware_stage_dates(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("У даты должен быть часовой пояс")
        return value

class ProjectPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    project_name: str = Field(min_length=1, max_length=160)
    project_description: str = Field(default="", max_length=4000)
    color: str = Field(default="#5577e7", pattern="^#[0-9a-fA-F]{6}$")
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"
    goal_id: str | None = None
    stages: list[PlanStage] = Field(min_length=1, max_length=20)

class ProposalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["create_task", "update_task", "project_plan"]
    task_id: str | None = None
    changes: Change | None = None
    plan: ProjectPlan | None = None

class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=6000)
    proposals: list[ProposalOut] = Field(default_factory=list, max_length=5)

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["confirm", "reject"]

class ProjectPlanEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: ProjectPlan
