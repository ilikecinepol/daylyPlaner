from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def register(c):
    return c.post("/api/v1/auth/register",json={"email":f"{uuid4()}@example.com","password":"StrongPass123","name":"Finance"}).json()
def account(c,name="Карта",opening="50000.00",currency="RUB"):
    r=c.post("/api/v1/finance/accounts",json={"name":name,"type":"bank_card","currency":currency,"opening_balance":opening,"is_archived":False});assert r.status_code==201;return r.json()
def tx(c,a,kind,amount,**extra):
    data={"type":kind,"amount":amount,"currency":a["currency"],"account_id":a["id"],"transaction_at":"2026-09-05T12:00:00Z","description":"test","destination_account_id":None,"category_id":None,"task_id":None,"project_id":None,"goal_id":None,"goal_contribution":False};data.update(extra);return c.post("/api/v1/finance/transactions",json=data)

def test_accounts_income_expense_transfer_and_analytics():
    with TestClient(app) as c:
        register(c);a=account(c);b=account(c,"Накопления","20000.00")
        assert tx(c,a,"income","70000").status_code==201
        assert tx(c,a,"expense","3000").status_code==201
        assert tx(c,a,"transfer","10000",destination_account_id=b["id"]).status_code==201
        balances={x["name"]:x["balance"] for x in c.get("/api/v1/finance/accounts").json()}
        assert balances=={"Карта":"107000.00","Накопления":"30000.00"}
        totals=c.get("/api/v1/finance/analytics?from=2026-09-01T00:00:00Z&to=2026-10-01T00:00:00Z").json()["totals"][0]
        assert (totals["income"],totals["expense"],totals["net"])==("70000.00","3000.00","67000.00")

def test_idor_and_user_isolation():
    with TestClient(app) as a,TestClient(app) as b:
        register(a);foreign=account(a);tx(a,foreign,"income","10")
        register(b);own=account(b,"Моя")
        assert tx(b,own,"expense","1",account_id=foreign["id"]).status_code==404
        assert b.get("/api/v1/finance/transactions").json()==[]
        assert all(x["id"]!=foreign["id"] for x in b.get("/api/v1/finance/accounts").json())

def test_planned_task_is_private_idempotent_and_recurs_without_transaction():
    with TestClient(app) as c:
        register(c);a=account(c);category=next(x for x in c.get("/api/v1/finance/categories").json() if x["type"]=="expense")
        task=c.post("/api/v1/tasks",json={"title":"Интернет","start_at":"2026-09-10T09:00:00Z","recurrence_rule":"MONTHLY","finance":{"type":"expense","amount":"3000","currency":"RUB","account_id":a["id"],"category_id":category["id"]}}).json()
        assert c.get("/api/v1/finance/accounts").json()[0]["balance"]=="50000.00"
        first=c.post(f'/api/v1/finance/tasks/{task["id"]}/execute').json();second=c.post(f'/api/v1/finance/tasks/{task["id"]}/execute').json()
        assert first["created"] is True and second["created"] is False
        assert len(c.get("/api/v1/finance/transactions").json())==1
        assert c.get("/api/v1/finance/accounts").json()[0]["balance"]=="47000.00"

def test_existing_goal_financial_progress_and_multicurrency_separation():
    with TestClient(app) as c:
        register(c);source=account(c);saving=account(c,"Накопления","0");account(c,"EUR","500","EUR")
        goal=c.post("/api/v1/goals",json={"title":"Компьютер","why":"Работа","period":"month","date":"2026-09-05","target_amount":"150000","currency":"RUB"}).json()
        assert tx(c,source,"transfer","10000",destination_account_id=saving["id"],goal_id=goal["id"],goal_contribution=True).status_code==201
        saved=c.get("/api/v1/goals").json()[0];assert saved["financial_current"]=="10000.00" and saved["financial_progress"]==7
        overview=c.get("/api/v1/finance/overview").json();assert {x["currency"] for x in overview["balances"]}=={"RUB","EUR"}
