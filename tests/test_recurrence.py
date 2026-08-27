from datetime import datetime,timezone
from app.services.recurrence import next_occurrence

START=datetime(2024,1,31,9,tzinfo=timezone.utc)

def test_daily_and_weekdays():
    assert next_occurrence(START,"FREQ=DAILY").day==1
    assert next_occurrence(datetime(2024,3,1,9,tzinfo=timezone.utc),"FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR").weekday()==0

def test_selected_days_interval_until_and_count():
    assert next_occurrence(datetime(2024,1,1,9,tzinfo=timezone.utc),"FREQ=WEEKLY;BYDAY=WE,FR").weekday()==2
    assert next_occurrence(START,"FREQ=DAILY;INTERVAL=2").day==2
    assert next_occurrence(START,"FREQ=DAILY;COUNT=1") is None

def test_month_end_and_leap_year():
    assert next_occurrence(START,"FREQ=MONTHLY;BYMONTHDAY=31").month==3
    leap=next_occurrence(datetime(2020,2,29,9,tzinfo=timezone.utc),"FREQ=YEARLY")
    assert (leap.year,leap.month,leap.day)==(2024,2,29)
