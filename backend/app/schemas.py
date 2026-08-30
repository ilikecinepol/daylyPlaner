from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
class Credentials(BaseModel):
    email: str = Field(min_length=3,max_length=320,pattern=r"^[^@\s]+@[^@\s]+$"); password: str = Field(min_length=8,max_length=128); name: str|None = Field(default=None,max_length=120); nickname:str|None=Field(default=None,min_length=3,max_length=40,pattern=r"^[\w.-]+$")
class ArchiveSettings(BaseModel):
    policy:str=Field(pattern="^(never|immediate|end_of_day|after_days)$"); days:int=Field(default=7,ge=1,le=365)
class NotificationRule(BaseModel):
    enabled:bool=True;channel:str=Field(default="bell",pattern="^(bell|sound|alarm)$");priority:str=Field(default="normal",pattern="^(normal|high|urgent)$")
class NotificationSettingsIn(BaseModel):
    rules:dict[str,NotificationRule]
class TaskIn(BaseModel):
    title:str=Field(min_length=1,max_length=500); description:str=""; priority:str=Field(default="P3",pattern="^P[1-4]$"); status:str=Field(default="planned",pattern="^(idea|planned|in_progress|completed|cancelled)$"); project_id:str|None=None; column_id:str|None=None; assigned_to_id:str|None=None; start_at:datetime|None=None; end_at:datetime|None=None; deadline_at:datetime|None=None; deadline_action:str=Field(default="none",pattern="^(none|mark_overdue|auto_complete)$"); due_at:datetime|None=None; duration_minutes:int=Field(default=60,ge=0,le=10080); all_day:bool=False; location:str=""; tags:list[str]=[]; mentions:list[str]=[]; recurrence_rule:str=""; reminder_offsets:list[int]=[]
class TaskPatch(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str|None=Field(default=None,min_length=1,max_length=500); description:str|None=None; priority:str|None=Field(default=None,pattern="^P[1-4]$"); status:str|None=Field(default=None,pattern="^(idea|planned|in_progress|completed|cancelled)$"); project_id:str|None=None; column_id:str|None=None; assigned_to_id:str|None=None; start_at:datetime|None=None; end_at:datetime|None=None; deadline_at:datetime|None=None; deadline_action:str|None=Field(default=None,pattern="^(none|mark_overdue|auto_complete)$"); due_at:datetime|None=None; duration_minutes:int|None=Field(default=None,ge=0,le=10080); all_day:bool|None=None; location:str|None=None; tags:list[str]|None=None; mentions:list[str]|None=None; recurrence_rule:str|None=None; reminder_offsets:list[int]|None=None; sync_version:int|None=None
class ProjectIn(BaseModel):
    name:str=Field(min_length=1,max_length=160); description:str=""; color:str=Field(default="#5577e7",pattern="^#[0-9a-fA-F]{6}$"); priority:str=Field(default="P3",pattern="^P[1-4]$"); team_label:str=Field(default="",max_length=100)
class ProjectDeleteIn(BaseModel):
    task_policy:str=Field(default="keep",pattern="^(keep|archive|delete)$")
class ColumnIn(BaseModel):
    name:str=Field(min_length=1,max_length=100); position:int|None=None
class TemplateIn(BaseModel):
    name:str=Field(min_length=1,max_length=160); icon:str="✦"; description:str=""; duration:int=60; priority:str="P3"; location:str=""; project_id:str|None=None; reminders:list[int]=[]; task_data:dict={}
class ContactIn(BaseModel):email:str|None=Field(default=None,max_length=320);user_nickname:str|None=Field(default=None,max_length=40);nickname:str="";tags:list[str]=[];role_ids:list[str]=[]
class FriendRoleIn(BaseModel):name:str=Field(min_length=1,max_length=80);color:str=Field(default="#5577e7",pattern="^#[0-9a-fA-F]{6}$")
class RoleRuleIn(BaseModel):role_id:str;denied_permissions:list[str]=[]
class RoleIn(BaseModel):name:str=Field(min_length=1,max_length=80);color:str="#7b818b";permissions:list[str]=[]
class MemberIn(BaseModel):email:str|None=Field(default=None,max_length=320);user_nickname:str|None=Field(default=None,max_length=40);role_id:str|None=None;role_ids:list[str]=[];channel_id:str|None=None
class ChannelIn(BaseModel):name:str=Field(min_length=1,max_length=100,pattern=r"^[\wа-яА-ЯёЁ-]+$");description:str="";contact_user_ids:list[str]=[]
class MessageIn(BaseModel):content:str=Field(default="",max_length=4000);attached_task_id:str|None=None
