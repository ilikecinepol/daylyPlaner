from datetime import datetime, timezone

from sqlalchemy import select

from ..models import ActivityLog, KanbanColumn, Task


def _aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def process_deadlines(db, now: datetime | None = None) -> dict[str, int]:
    """Apply each expired deadline action once and record the system change."""
    current = _aware(now) or datetime.now(timezone.utc)
    result = {"marked_overdue": 0, "auto_completed": 0}
    tasks = db.scalars(
        select(Task).where(
            Task.deleted_at == None,
            Task.completed_at == None,
            Task.status.notin_(["completed", "cancelled"]),
            Task.deadline_at != None,
            Task.deadline_at <= current,
            Task.deadline_processed_at == None,
            Task.deadline_action.in_(["mark_overdue", "auto_complete"]),
        )
    )
    for task in tasks:
        task.deadline_processed_at = current
        if task.deadline_action == "auto_complete":
            task.status = "completed"
            task.completed_at = current
            task.completed_by_id = None
            if task.project_id:
                column = db.scalar(
                    select(KanbanColumn).where(
                        KanbanColumn.project_id == task.project_id,
                        KanbanColumn.name.ilike("готово"),
                    )
                )
                if column:
                    task.column_id = column.id
            action = "task_auto_completed"
            result["auto_completed"] += 1
        else:
            action = "task_marked_overdue"
            result["marked_overdue"] += 1
        task.sync_version = (task.sync_version or 0) + 1
        db.add(ActivityLog(user_id=task.user_id, task_id=task.id, action=action, changes={"deadline_at": str(task.deadline_at)}))
    if result["marked_overdue"] or result["auto_completed"]:
        db.commit()
    return result
