import pytest
from fastapi.testclient import TestClient
from app.main import app

PNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6pAAAAABJRU5ErkJggg=='

def register(client,email):
    response=client.post('/api/v1/auth/register',json={'email':email,'password':'StrongPass123','name':'Original'})
    assert response.status_code==201

def test_profile_roundtrip_and_isolation():
    with TestClient(app) as first,TestClient(app) as second:
        register(first,'profile-first@example.com');register(second,'profile-second@example.com')
        data={'name':'Анна','last_name':'Иванова','job_title':'Инженер','timezone':'Asia/Tokyo','profile_status':'busy','contact_info':'Телефон: +7 000 000-00-00','avatar_data_url':PNG}
        saved=first.put('/api/v1/auth/profile',json=data)
        assert saved.status_code==200,saved.text
        loaded=first.get('/api/v1/auth/me').json()
        for key,value in data.items():assert loaded[key]==value
        assert loaded['email']=='profile-first@example.com'
        assert second.get('/api/v1/auth/me').json()['name']=='Original'
        assert first.put('/api/v1/auth/profile',json={**data,'avatar_data_url':''}).json()['avatar_data_url']==''

@pytest.mark.parametrize('field,value',[
    ('name','   '),('timezone','Not/AZone'),('profile_status','unknown'),
    ('avatar_data_url','https://example.com/avatar.png'),
    ('avatar_data_url','data:image/svg+xml;base64,PHN2Zz48L3N2Zz4='),
    ('avatar_data_url','data:image/png;base64,YmFk'),
    ('avatar_data_url','data:image/png;base64,%%%'),
    ('contact_info','x'*501),('email','change@example.com'),
])
def test_profile_validation(field,value):
    with TestClient(app) as client:
        register(client,f'profile-validation-{field}-{len(str(value))}@example.com')
        assert client.put('/api/v1/auth/profile',json={'name':'Valid',field:value}).status_code==422
        assert client.get('/api/v1/auth/me').json()['name']=='Original'

def test_profile_requires_login():
    with TestClient(app) as client:
        assert client.put('/api/v1/auth/profile',json={'name':'Unauthenticated'}).status_code==401
