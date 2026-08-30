const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statuses={available:'Доступен',busy:'Занят',away:'Отошёл',offline:'Не беспокоить'};
const fullName=user=>[user.name,user.last_name].filter(Boolean).join(' ');
const initials=user=>fullName(user).split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();

export function updateProfileAvatar(user){
  const button=document.querySelector('header .avatar');
  if(!button||!user)return;
  button.innerHTML=user.avatar_data_url?`<img src="${esc(user.avatar_data_url)}" alt="Аватар">`:esc(initials(user));
  button.title=fullName(user);button.setAttribute('aria-label','Открыть профиль');
}

export function profileCard(user){
  return `<section class="card"><div class="card-title">Профиль</div><div class="profile-summary"><div class="profile-picture">${user.avatar_data_url?`<img src="${esc(user.avatar_data_url)}" alt="Аватар">`:esc(initials(user))}</div><div><strong>${esc(fullName(user))}</strong><div>${esc(user.job_title)}</div><small>${statuses[user.profile_status]||statuses.available}</small></div></div><p><span class="team-tag">@${esc(user.nickname)}</span><br><small>${esc(user.email)} · ${esc(user.timezone)}</small></p>${user.contact_info?`<p class="profile-contacts">${esc(user.contact_info)}</p>`:''}<button type="button" class="primary" data-profile-edit>Редактировать профиль</button> <button class="secondary" data-action="logout">Выйти</button></section>`;
}

export async function editProfile(user,uiDialog,api){
  const fields=`<div class="form-grid"><label>Имя<input name="name" required maxlength="120" value="${esc(user.name)}"></label><label>Фамилия<input name="last_name" maxlength="120" value="${esc(user.last_name)}"></label></div><label>Должность<input name="job_title" maxlength="160" value="${esc(user.job_title)}"></label><label>Часовой пояс IANA<input name="timezone" required maxlength="80" value="${esc(user.timezone)}" placeholder="Europe/Moscow"></label><label>Статус<select name="profile_status">${Object.entries(statuses).map(([key,label])=>`<option value="${key}" ${key===(user.profile_status||'available')?'selected':''}>${label}</option>`).join('')}</select><small>Это ручной статус профиля, а не автоматическое определение присутствия.</small></label><label>Контакты<textarea name="contact_info" maxlength="500" rows="3">${esc(user.contact_info)}</textarea></label><label>Аватар (PNG, JPEG, WebP; до 512 КБ)<input id="profile-avatar-file" type="file" accept="image/png,image/jpeg,image/webp"></label><div class="profile-picture" id="profile-avatar-preview">${user.avatar_data_url?`<img src="${esc(user.avatar_data_url)}" alt="Предпросмотр аватара">`:esc(initials(user))}</div><input name="avatar_data_url" type="hidden" value="${esc(user.avatar_data_url)}"><button type="button" class="secondary" id="profile-avatar-remove">Убрать аватар</button><p id="profile-avatar-error" role="alert"></p>`;
  const pending=uiDialog('Редактировать профиль',fields);
  const fileInput=document.querySelector('#profile-avatar-file'),form=fileInput.closest('form'),error=form.querySelector('#profile-avatar-error'),preview=form.querySelector('#profile-avatar-preview');
  let generation=0;
  fileInput.onchange=async()=>{
    const file=fileInput.files[0],version=++generation;if(!file)return;
    error.textContent='';
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>512*1024){error.textContent='Выберите PNG, JPEG или WebP не больше 512 КБ';fileInput.value='';return}
    const submit=form.querySelector('#ui-submit');submit.disabled=true;
    try{
      const value=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});
      const probe=new Image();probe.src=value;await probe.decode();
      if(version!==generation)return;
      form.elements.avatar_data_url.value=value;preview.innerHTML=`<img src="${esc(value)}" alt="Предпросмотр аватара">`;
    }catch{error.textContent='Не удалось прочитать изображение'}finally{submit.disabled=false}
  };
  form.querySelector('#profile-avatar-remove').onclick=()=>{generation++;fileInput.value='';form.elements.avatar_data_url.value='';preview.textContent=initials(user)};
  const data=await pending;generation++;
  if(!data)return null;
  delete data.checked;
  return api('/auth/profile',{method:'PUT',body:JSON.stringify(data)});
}
