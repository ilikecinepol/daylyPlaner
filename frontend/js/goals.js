const esc = value => String(value ?? "").replace(/[&<>"\x27]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","\x27":"&#39;"}[c]));
const labels = {day:"День",week:"Неделя",month:"Месяц"};
const rank = {day:0,week:1,month:2};
export const goalOptions = (goals, selected="") => '<option value="">Без цели</option>'+goals.map(g=>`<option value="${g.id}" ${g.id===selected?"selected":""}>${labels[g.period]} · ${esc(g.title)} (${g.period_start})</option>`).join("");
export function renderGoals(state, taskRow, period, date) {
  const goals=(state.goals||[]).filter(g=>g.period===period && g.period_start<=date && g.period_end>=date);
  return `<div class="page-head"><h1>Цели и задачи</h1><button class="primary" data-goal-action="create">+ Цель</button></div>
    <p>Помните, зачем вы это делаете. Задачи здесь — те же задачи из календаря и проектов.</p>
    <div class="goal-toolbar"><label>Период<select id="goal-period">${Object.entries(labels).map(([key,label])=>`<option value="${key}" ${key===period?"selected":""}>${label}</option>`).join("")}</select></label><label>Дата<input id="goal-date" type="date" value="${date}"></label></div>
    ${goals.map(g=>{const tasks=[...state.tasks,...state.archived].filter(t=>t.goal_id===g.id),counted=tasks.filter(t=>t.status!=="cancelled"),done=counted.filter(t=>t.status==="completed").length,progress=counted.length?Math.round(done/counted.length*100):0,parent=state.goals.find(p=>p.id===g.parent_id);return `<section class="goal-card"><h2>${esc(g.title)}</h2><div class="meta">${g.period_start} — ${g.period_end}${parent?` · Цель: ${esc(parent.title)}`:""}</div><p class="goal-why">${esc(g.why||"Добавьте, зачем вам эта цель")}</p><progress max="100" value="${progress}" aria-label="Прогресс цели"></progress><span> ${done} из ${counted.length} · ${progress}%</span><div class="goal-actions">${[["newtask","+ Задача"],["attach","Привязать задачу"],["edit","Изменить цель"],["delete","Удалить цель"]].map(([action,label])=>`<button class="secondary" data-goal-action="${action}" data-goal-id="${g.id}">${label}</button>`).join("")}</div>${tasks.map(t=>`<div>${taskRow(t)}<button class="secondary" data-goal-action="unlink" data-task-id="${t.id}">Убрать из цели</button></div>`).join("")||"<p>Пока нет задач</p>"}</section>`}).join("")||'<div class="empty">На этот период целей пока нет. Создайте первую.</div>'}`;
}
export async function handleGoalAction(button, ctx) {
  const {state,dialog,api,openTask,refresh,period,date}=ctx,action=button.dataset.goalAction;
  const goal=state.goals.find(g=>g.id===button.dataset.goalId);
  if(action==="newtask"){openTask({}, {goal_id:goal.id});return;}
  if(action==="create"||action==="edit") {
    const g=goal||{title:"",why:"",period,period_start:date};
    const parents=state.goals.filter(p=>p.id!==g.id&&rank[p.period]>rank[g.period]);
    const data=await dialog(goal?"Изменить цель":"Новая цель",`<label>Название<input name="title" maxlength="300" required value="${esc(g.title)}"></label><label>Зачем это важно<textarea name="why" maxlength="4000">${esc(g.why)}</textarea></label><p>Период: ${labels[g.period]}</p><label>Дата внутри периода<input name="date" type="date" required value="${g.period_start}"></label><label>Родительская цель<select name="parent_id">${goalOptions(parents,g.parent_id)}</select></label>`);
    if(!data)return;
    await api("/goals"+(goal?"/"+goal.id:""),{method:goal?"PUT":"POST",body:JSON.stringify({title:data.title,why:data.why,date:data.date,period:g.period,parent_id:data.parent_id||null})});
  } else if(action==="delete") {
    if(!await dialog("Удалить цель?", "<p>Все задачи сохранятся. Удалится только их связь с этой целью.</p>","Удалить"))return;
    await api("/goals/"+goal.id,{method:"DELETE"});
  } else {
    let task;
    if(action==="attach") {
      const available=state.tasks.filter(t=>t.user_id===state.user.id&&t.goal_id!==goal.id);
      if(!available.length)throw new Error("Нет доступных задач для привязки");
      const data=await dialog("Привязать обычную задачу",`<p>Если задача уже связана с другой целью, она будет перенесена в эту цель.</p><label>Задача<select name="task_id">${available.map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join("")}</select></label>`);
      if(!data)return;task=available.find(t=>t.id===data.task_id);
    } else task=[...state.tasks,...state.archived].find(t=>t.id===button.dataset.taskId);
    if(!task)return;
    await api("/tasks/"+task.id,{method:"PATCH",body:JSON.stringify({goal_id:action==="attach"?goal.id:null,sync_version:task.sync_version})});
  }
  await refresh();
}
