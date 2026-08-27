export async function api(path,options={}){
  const response=await fetch('/api/v1'+path,{credentials:'include',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  if(response.status===204)return null;
  const body=await response.json().catch(()=>({}));
  if(!response.ok){
    let detail=body.detail;
    if(Array.isArray(detail))detail=detail.map(item=>{const field=item.loc?.at(-1);if(field==='password')return'Пароль должен содержать не менее 8 символов';if(field==='email')return'Введите корректный email';return item.msg}).join('. ');
    throw Error(detail||`Ошибка сервера (${response.status})`);
  }
  return body;
}
