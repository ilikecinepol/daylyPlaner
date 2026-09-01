import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ai import provider
from uuid import uuid4

def mock_client(monkeypatch, body, status=200):
    observed=[]
    class Client:
        def __init__(self,**kwargs): self.config=kwargs
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs):
            observed.append((url,kwargs,self.config))
            return httpx.Response(status,request=httpx.Request('POST',url),json=body)
    monkeypatch.setattr('app.ai.deepseek.httpx.AsyncClient',Client)
    monkeypatch.setenv('DEEPSEEK_API_KEY','deepseek-test-only')
    monkeypatch.delenv('DEEPSEEK_MODEL',raising=False)
    monkeypatch.setenv('OPENAI_API_KEY','must-not-be-used')
    return observed

def response(content=None,finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'content':content if content is not None else json.dumps({'answer':'Готово к обсуждению','proposals':[]})}}], 'usage':{'prompt_tokens':15,'completion_tokens':8}}

def test_deepseek_payload_and_key_isolation(monkeypatch):
    calls=mock_client(monkeypatch,response())
    result,inputs,outputs=asyncio.run(provider.generate('Тест',{'tasks':[]},'deepseek'))
    assert result.proposals==[] and (inputs,outputs)==(15,8)
    url,options,config=calls[0]
    assert url=='https://api.deepseek.com/chat/completions'
    assert options['headers']['Authorization']=='Bearer deepseek-test-only'
    assert options['json']['model']=='deepseek-v4-flash'
    assert options['json']['thinking']=={'type':'disabled'}
    assert options['json']['response_format']=={'type':'json_object'}
    assert options['json']['max_tokens']==2000 and not config['follow_redirects']
    monkeypatch.setenv('DEEPSEEK_MODEL','deepseek-v4-pro')
    asyncio.run(provider.generate('Тест',{},'deepseek'))
    assert calls[-1][1]['json']['model']=='deepseek-v4-pro'

@pytest.mark.parametrize('body,status',[
    (response('', 'stop'),200),(response('not json'),200),
    (response(finish='length'),200),({'choices':[]},200),
    (response(json.dumps({'answer':'Oops','proposals':[{'kind':'shell','changes':{}}]})),200),
    ({'error':{'message':'secret provider response'}},401),
])
def test_invalid_deepseek_answers_are_rejected(monkeypatch,body,status):
    calls=mock_client(monkeypatch,body,status)
    with pytest.raises(Exception):asyncio.run(provider.generate('Тест',{},'deepseek'))
    assert len(calls)==1 # no retries or provider fallback that could add cost

def test_missing_key_no_network_or_quota_charge(monkeypatch):
    calls=mock_client(monkeypatch,response())
    monkeypatch.delenv('DEEPSEEK_API_KEY')
    assert not provider.configured('deepseek')
    with pytest.raises(RuntimeError):asyncio.run(provider.generate('Тест',{},'deepseek'))
    assert calls==[]
    with TestClient(app) as client:
        uid=client.post('/api/v1/auth/register',json={'email':f'{uuid4()}@example.com','password':'StrongPass123','name':'Test'}).json()['id']
        monkeypatch.setenv('AI_ENABLED','1');monkeypatch.setenv('AI_PROVIDER','deepseek')
        from app.database import SessionLocal
        from app.ai.models import AIAccess
        with SessionLocal() as db:db.add(AIAccess(user_id=uid,enabled=True));db.commit()
        cid=client.post('/api/v1/ai/conversations').json()['id']
        result=client.post(f'/api/v1/ai/conversations/{cid}/messages',json={'request_key':str(uuid4()),'message':'Тест'})
        assert result.status_code==503
        state=client.get('/api/v1/ai/status').json()
        assert not state['ready'] and state['used']==0 and state['model']=='deepseek-v4-flash'
        assert 'must-not-be-used' not in str(state)
