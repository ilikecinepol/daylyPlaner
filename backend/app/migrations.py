from sqlalchemy import inspect, text
from .database import engine

SQLITE_COLUMNS={
 "users":{"updated_at":"DATETIME","deleted_at":"DATETIME","nickname":"VARCHAR(40)"},
 "projects":{"updated_at":"DATETIME","deleted_at":"DATETIME","team_label":"VARCHAR(100) DEFAULT ''"},
 "tasks":{"column_id":"VARCHAR(36)","start_at":"DATETIME","due_at":"DATETIME","duration_minutes":"INTEGER DEFAULT 60","all_day":"BOOLEAN DEFAULT 0","mentions":"JSON DEFAULT '[]'","recurrence_rule":"VARCHAR(300) DEFAULT ''","completed_at":"DATETIME","sync_version":"INTEGER DEFAULT 1"},
 "task_templates":{"project_id":"VARCHAR(36)","reminders":"JSON DEFAULT '[]'","created_at":"DATETIME","updated_at":"DATETIME","deleted_at":"DATETIME"},
 "contacts":{"tags":"JSON DEFAULT '[]'"}
}
def migrate_legacy():
    if engine.dialect.name!="sqlite": return
    inspector=inspect(engine); tables=set(inspector.get_table_names())
    with engine.begin() as conn:
        for table,columns in SQLITE_COLUMNS.items():
            if table not in tables: continue
            existing={c["name"] for c in inspector.get_columns(table)}
            for name,definition in columns.items():
                if name not in existing: conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))
        if "tasks" in tables:
            conn.execute(text("UPDATE tasks SET duration_minutes=duration WHERE duration_minutes IS NULL"))
            conn.execute(text("UPDATE tasks SET completed_at=CURRENT_TIMESTAMP WHERE completed=1 AND completed_at IS NULL"))
