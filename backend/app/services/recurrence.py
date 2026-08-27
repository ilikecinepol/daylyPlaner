from datetime import datetime
from dateutil.rrule import rrulestr

ALIASES={"DAILY":"FREQ=DAILY","WEEKLY":"FREQ=WEEKLY","WEEKDAYS":"FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR","MONTHLY":"FREQ=MONTHLY","YEARLY":"FREQ=YEARLY"}

def normalize_rule(rule:str)->str:
    value=(rule or "").strip().upper()
    if value.startswith("RRULE:"):value=value[6:]
    return ALIASES.get(value,value)

def next_occurrence(value:datetime|None,rule:str)->datetime|None:
    if not value or not rule:return None
    parsed=rrulestr(normalize_rule(rule),dtstart=value)
    return parsed.after(value,inc=False)
