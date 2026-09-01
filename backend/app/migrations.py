from sqlalchemy import inspect, text
from .database import engine

SQLITE_COLUMNS={
 "users":{"updated_at":"DATETIME","deleted_at":"DATETIME","nickname":"VARCHAR(40)","completed_task_archive_policy":"VARCHAR(30) DEFAULT 'never'","completed_task_archive_days":"INTEGER DEFAULT 7","notification_settings":"JSON DEFAULT '{}'","notifications_cleared_at":"DATETIME"},
 "projects":{"updated_at":"DATETIME","deleted_at":"DATETIME","team_label":"VARCHAR(100) DEFAULT ''","priority":"VARCHAR(2) DEFAULT 'P3'"},
 "tasks":{"column_id":"VARCHAR(36)","start_at":"DATETIME","due_at":"DATETIME","end_at":"DATETIME","postponed_at":"DATETIME","deadline_at":"DATETIME","deadline_action":"VARCHAR(30) DEFAULT 'none'","deadline_processed_at":"DATETIME","duration_minutes":"INTEGER DEFAULT 60","all_day":"BOOLEAN DEFAULT 0","mentions":"JSON DEFAULT '[]'","recurrence_rule":"VARCHAR(300) DEFAULT ''","completed_at":"DATETIME","archived_at":"DATETIME","sync_version":"INTEGER DEFAULT 1"},
 "task_templates":{"project_id":"VARCHAR(36)","reminders":"JSON DEFAULT '[]'","task_data":"JSON DEFAULT '{}'","created_at":"DATETIME","updated_at":"DATETIME","deleted_at":"DATETIME"},
 "contacts":{"tags":"JSON DEFAULT '[]'"}
}
SQLITE_COLUMNS["users"].update({"last_name":"VARCHAR(120) DEFAULT ''","job_title":"VARCHAR(160) DEFAULT ''","profile_status":"VARCHAR(20) DEFAULT 'available'","contact_info":"VARCHAR(500) DEFAULT ''","avatar_data_url":"TEXT DEFAULT ''"})
SQLITE_COLUMNS["tasks"]["goal_id"]="VARCHAR(36)"

def migrate_legacy():
    if engine.dialect.name!="sqlite": return
    inspector=inspect(engine); tables=set(inspector.get_table_names())
    with engine.begin() as conn:
        for table,columns in SQLITE_COLUMNS.items():
            if table not in tables: continue
            existing={c["name"] for c in inspector.get_columns(table)}
            for name,definition in columns.items():
                if name not in existing: conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))
