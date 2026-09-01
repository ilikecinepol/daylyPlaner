from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.database import SessionLocal
from app.models import Task, Project, ActivityLog
from app.ai.models import AIAccess, AIQuota, AIProposal, AIRequest
from app.ai.schemas import ModelAnswer

@pytest.fixture(autouse=True)
def demo(monkeypatch):
    monkeypatch.setenv('AI_ENABLED','1');monkeypatch.setenv('AI_PROVIDER','demo')
    monkeypatch.setenv('AI_DEMO_ACCESS','1');monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('AI_GLOBAL_DAILY_LIMIT','1000');monkeypatch.setenv('AI_USER_DAILY_LIMIT','20')

def account(c):
    r=c.post('/api/v1/auth/register',json={'email':f'{uuid4()}@example.com','password':'StrongPass123','name':'AI tester'})
    assert r.status_code==201
    return r.json()['id']

def conversation(c):
    r=c.post('/api/v1/ai/conversations');assert r.status_code==201,r.text
    return r.json()['id']

def chat(c,cid,message='Покажи задачи',**kwargs):
    return c.post(f'/api/v1/ai/conversations/{cid}/messages',json={'request_key':str(uuid4()),'message':message,**kwargs})

def decide(c,p,decision='confirm'):
    return c.post('/api/v1/ai/proposals/'+p['id']+'/decision',json={'decision':decision})

def test_ai_disabled_does_not_break_planner(monkeypatch):
    with TestClient(app) as c:
        account(c);monkeypatch.setenv('AI_ENABLED','0')
        assert c.get('/api/v1/ai/status').json()['access'] is False
        assert c.post('/api/v1/ai/conversations').status_code==403
        assert c.post('/api/v1/tasks',json={'title':'Normal task'}).status_code==201
        assert c.get('/api/v1/tasks').status_code==200

def test_production_requires_grant_and_expiry(monkeypatch):
    with TestClient(app) as c:
        uid=account(c);monkeypatch.setenv('AI_DEMO_ACCESS','0')
        assert c.get('/api/v1/ai/status').json()['access'] is False
        with SessionLocal() as db:
            grant=AIAccess(user_id=uid,enabled=True);db.add(grant);db.commit()
        assert c.get('/api/v1/ai/status').json()['access'] is True
        with SessionLocal() as db:
            db.get(AIAccess,uid).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
        assert c.post('/api/v1/ai/conversations').status_code==403

def test_local_access_never_bypasses_production(monkeypatch):
    with TestClient(app) as c:
        account(c);monkeypatch.setenv('AI_DEMO_ACCESS','0');monkeypatch.setenv('AI_LOCAL_ACCESS','1')
        assert c.get('/api/v1/ai/status').json()['access'] is True
        monkeypatch.setenv('APP_ENV','production')
        assert c.get('/api/v1/ai/status').json()['access'] is False

def test_private_context_and_history_isolation():
    with TestClient(app) as a,TestClient(app) as b:
        account(a);account(b)
        a.post('/api/v1/tasks',json={'title':'Visible task'})
        b.post('/api/v1/tasks',json={'title':'PRIVATE SECRET'})
        cid=conversation(a);result=chat(a,cid).json()
        assert result['status']=='completed' and 'Visible task' in result['answer']
        assert 'PRIVATE SECRET' not in str(result)
        assert b.get('/api/v1/ai/conversations/'+cid).status_code==404
        assert b.delete('/api/v1/ai/conversations/'+cid).status_code==404
        assert chat(b,cid).status_code==404

def test_create_confirmation_dedupe_and_reject():
    with TestClient(app) as c:
        uid=account(c);cid=conversation(c);key=str(uuid4())
        result=chat(c,cid,'Создай: Review',request_key=key).json()
        assert result['status']=='completed',result
        assert c.get('/api/v1/tasks').json()==[]
        again=chat(c,cid,'Создай: Review',request_key=key).json()
        assert again['id']==result['id']
        proposal=result['proposals'][0]
        first=decide(c,proposal);assert first.status_code==200,first.text
        assert first.json()['status']=='applied'
        assert decide(c,proposal).json()['result_task_id']==first.json()['result_task_id']
        assert len(c.get('/api/v1/tasks').json())==1
        second=chat(c,cid,'Создай: Rejected').json()['proposals'][0]
        assert decide(c,second,'reject').json()['status']=='rejected'
        assert decide(c,second).json()['status']=='rejected'
        assert len(c.get('/api/v1/tasks').json())==1
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.user_id==uid,ActivityLog.action=='ai_change_confirmed'))==1

def test_update_conflict_and_cross_user_confirm():
    with TestClient(app) as c,TestClient(app) as other:
        account(c);account(other);cid=conversation(c)
        task=c.post('/api/v1/tasks',json={'title':'Finish me'}).json()
        result=chat(c,cid,'Заверши: Finish me').json();proposal=result['proposals'][0]
        assert other.post('/api/v1/ai/proposals/'+proposal['id']+'/decision',json={'decision':'confirm'}).status_code==404
        c.patch('/api/v1/tasks/'+task['id'],json={'title':'Changed title','sync_version':task['sync_version']})
        assert decide(c,proposal).status_code==409
        assert c.get('/api/v1/tasks/'+task['id']).json()['status']=='planned'
        fresh=chat(c,cid,'Заверши: Changed title').json()['proposals'][0]
        assert decide(c,fresh).status_code==200
        assert c.get('/api/v1/tasks/'+task['id']).json()['status']=='completed'

def test_limits_and_no_refund_on_delete(monkeypatch):
    monkeypatch.setenv('AI_USER_DAILY_LIMIT','1')
    with TestClient(app) as c:
        account(c);cid=conversation(c)
        assert chat(c,cid).status_code==200
        assert chat(c,cid).status_code==429
        assert c.delete('/api/v1/ai/conversations/'+cid).status_code==204
        assert c.get('/api/v1/ai/status').json()['used']==1
        assert chat(c,conversation(c)).status_code==429

def test_deleting_history_preserves_created_tasks():
    with TestClient(app) as c:
        uid=account(c);cid=conversation(c)
        result=chat(c,cid,'Создай: Saved').json();decide(c,result['proposals'][0])
        c.delete('/api/v1/ai/conversations/'+cid)
        assert len(c.get('/api/v1/tasks').json())==1
        assert c.get('/api/v1/ai/conversations/'+cid).status_code==404
        with SessionLocal() as db:
            row=db.get(AIRequest,result['id'])
            assert row.prompt==row.answer=='' and row.sources==[]
            assert not db.scalar(select(AIProposal).where(AIProposal.request_id==row.id))

def test_provider_failure_does_not_expose_secrets(monkeypatch):
    async def fail(*args):raise RuntimeError('sk-secret sensitive prompt')
    monkeypatch.setattr('app.ai.provider.generate',fail)
    with TestClient(app) as c:
        account(c);result=chat(c,conversation(c)).json()
        assert result['status']=='failed' and 'sk-secret' not in str(result)
        assert c.get('/api/v1/tasks').json()==[]

def test_unknown_task_proposal_rejected(monkeypatch):
    async def malicious(*args):return ModelAnswer.model_validate({'answer':'Done','proposals':[{'kind':'update_task','task_id':'unknown','changes':{'title':'Injected'}}]}),1,1
    monkeypatch.setattr('app.ai.provider.generate',malicious)
    with TestClient(app) as c:
        account(c);result=chat(c,conversation(c)).json()
        assert result['status']=='failed' and result['proposals']==[]

def test_revoked_access_blocks_confirmation():
    with TestClient(app) as c:
        uid=account(c);cid=conversation(c);proposal=chat(c,cid,'Создай: No longer allowed').json()['proposals'][0]
        with SessionLocal() as db:db.add(AIAccess(user_id=uid,enabled=False));db.commit()
        assert decide(c,proposal).status_code==403
        assert c.get('/api/v1/ai/conversations/'+cid).status_code==200
        assert c.delete('/api/v1/ai/conversations/'+cid).status_code==204

def test_context_search_and_date():
    with TestClient(app) as c:
        account(c);cid=conversation(c)
        c.post('/api/v1/tasks',json={'title':'August item','start_at':'2030-08-01T07:00:00Z'})
        c.post('/api/v1/tasks',json={'title':'September item','start_at':'2030-09-01T07:00:00Z'})
        result=chat(c,cid,day='2030-08-01').json()
        assert len(result['sources'])==1 and result['sources'][0]['title']=='August item'
        assert chat(c,cid,search='September').json()['sources'][0]['title']=='September item'

def test_cancel_before_provider_returns(monkeypatch):
    async def cancelled(*args):
        with SessionLocal() as db:
            row=db.scalar(select(AIRequest).where(AIRequest.status=='running').order_by(AIRequest.created_at.desc()))
            row.status='cancelled';db.commit()
        return ModelAnswer(answer='Ignore me',proposals=[]),1,1
    monkeypatch.setattr('app.ai.provider.generate',cancelled)
    with TestClient(app) as c:
        account(c);result=chat(c,conversation(c)).json()
        assert result['status']=='cancelled' and not result['proposals']

def test_openai_adapter_without_network(monkeypatch):
    import asyncio, json, httpx
    from app.ai.provider import generate
    monkeypatch.setenv('OPENAI_API_KEY','test-placeholder-not-a-real-key')
    monkeypatch.setenv('AI_MODEL','explicit-test-model')
    observed={}
    class FakeClient:
        def __init__(self,**kwargs):observed['config']=kwargs
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            observed.update(url=url,**kwargs)
            return httpx.Response(200,request=httpx.Request('POST',url),json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'Ответ','proposals':[]})}]}],'usage':{'input_tokens':12,'output_tokens':5}})
    monkeypatch.setattr('app.ai.provider.httpx.AsyncClient',FakeClient)
    result,inputs,outputs=asyncio.run(generate('Вопрос',{'tasks':[]},'openai'))
    assert result.answer=='Ответ' and (inputs,outputs)==(12,5)
    assert observed['url']=='https://api.openai.com/v1/responses'
    assert observed['json']['store'] is False
    assert observed['json']['max_output_tokens']==2000
    assert observed['json']['text']['format']['strict'] is True
    assert observed['config']['follow_redirects'] is False

def test_replayed_confirmation_is_atomic_across_clients():
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(app) as c,TestClient(app) as duplicate:
        account(c);duplicate.cookies.update(c.cookies)
        proposal=chat(c,conversation(c),'Создай: Once only').json()['proposals'][0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda client:decide(client,proposal),[c,duplicate]))
        assert all(r.status_code==200 for r in results),[r.text for r in results]
        assert len(c.get('/api/v1/tasks').json())==1

def test_project_plan_can_be_edited_and_applied_atomically():
    with TestClient(app) as c:
        uid=account(c);proposal=chat(c,conversation(c),'План проекта: Запуск продукта').json()['proposals'][0]
        assert proposal['kind']=='project_plan' and len(proposal['plan']['stages'])==3
        assert c.get('/api/v1/projects').json()==[] and c.get('/api/v1/tasks').json()==[]
        plan=proposal['plan'];plan['project_name']='Запуск MVP';plan['stages'][0]['title']='Согласовать требования'
        edited=c.patch(f"/api/v1/ai/proposals/{proposal['id']}/project-plan",json={'plan':plan})
        assert edited.status_code==200,edited.text
        applied=decide(c,edited.json()).json()
        assert applied['status']=='applied' and applied['result']['project_name']=='Запуск MVP'
        projects=c.get('/api/v1/projects').json();tasks=c.get('/api/v1/tasks').json()
        assert len(projects)==1 and len(tasks)==3
        assert all(task['project_id']==projects[0]['id'] for task in tasks)
        assert any(task['title']=='Согласовать требования' for task in tasks)
        assert decide(c,proposal).json()['result']==applied['result']
        assert len(c.get('/api/v1/projects').json())==1 and len(c.get('/api/v1/tasks').json())==3
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(Project).where(Project.user_id==uid))==1
            assert db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.user_id==uid,ActivityLog.action=='ai_project_plan_confirmed'))==1

def test_project_plan_edit_is_private_and_locked_after_rejection():
    with TestClient(app) as c,TestClient(app) as other:
        account(c);account(other);proposal=chat(c,conversation(c),'План проекта: Private').json()['proposals'][0]
        assert other.patch(f"/api/v1/ai/proposals/{proposal['id']}/project-plan",json={'plan':proposal['plan']}).status_code==404
        assert decide(c,proposal,'reject').status_code==200
        assert c.patch(f"/api/v1/ai/proposals/{proposal['id']}/project-plan",json={'plan':proposal['plan']}).status_code==409

def test_recent_conversation_is_sent_as_context(monkeypatch):
    seen=[]
    async def capture(message,context,*args):
        seen.append(context.get('conversation'))
        return ModelAnswer(answer='Ответ',proposals=[]),1,1
    monkeypatch.setattr('app.ai.provider.generate',capture)
    with TestClient(app) as c:
        account(c);cid=conversation(c)
        assert chat(c,cid,'Первый вопрос').status_code==200
        assert chat(c,cid,'Уточни предыдущий ответ').status_code==200
    assert seen[0]==[]
    assert seen[1]==[{'user':'Первый вопрос','assistant':'Ответ'}]
