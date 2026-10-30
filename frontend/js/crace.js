const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const raceDate=new Date('2026-12-05T09:00:00');
const step=(name,target,phase='station')=>({name,target,phase});

export const cracePlan=[
 {key:'baseline',date:'2026-10-27',title:'Контрольный комплекс',kind:'Контроль',duration:'75:21',rpe:'8/10',goal:'Исходная точка: 4 км бега и сокращённые 8 станций.',controls:'Средний пульс 160, максимум 184. 83% времени выше 151 уд/мин.',note:'Повторять такую интенсивность каждую тренировку не нужно.',steps:[step('Контрольный комплекс','Выполнено','run')]},
 {key:'w02',date:'2026-10-31',title:'Лёгкий бег + техника',kind:'Аэробная',duration:'45–55 мин',rpe:'3–4/10',goal:'Проверить непрерывный бег на обычной дорожке и восстановиться.',controls:'Дистанция каждого 8-минутного отрезка, разговорный тест, средний пульс и RPE.',note:'Если ноги не восстановились — убрать SkiErg и греблю. Если 8 минут много: 2 мин бег / 1 мин шаг.',steps:[step('Разминка','5 мин ходьбы + 5 мин лёгкого бега','run'),step('Бег 1','8 мин легко','run'),step('Ходьба','2 мин','run'),step('Бег 2','8 мин легко','run'),step('Ходьба','2 мин','run'),step('Бег 3','8 мин легко','run'),step('SkiErg','2 × 250 м, отдых 60–90 сек'),step('Гребля','2 × 250 м, отдых 60–90 сек'),step('Заминка','5 мин ходьбы','run')]},
 {key:'w03',date:'2026-11-03',title:'Километры + эрги',kind:'Аэробная',duration:'55–60 мин',rpe:'4–6/10',goal:'Увеличить продолжительность бега и отдельно развить циклические станции.',controls:'Время километров, разброс темпа, отсечки эргов, RPE последнего повтора.',note:'Если километр пока тяжёл: выполнить 3 × 8 минут или добавить короткий шаг.',steps:[step('Разминка','10 мин','run'),step('Бег','3 × 1 км; между отрезками 2 мин ходьбы','run'),step('SkiErg','3 × 250 м; отдых 60–90 сек'),step('Гребля','3 × 250 м; отдых 60–90 сек'),step('Заминка','5 мин','run')]},
 {key:'w04',date:'2026-11-07',title:'Бег после станций',kind:'Специфика',duration:'55–65 мин',rpe:'6–7/10',goal:'Возвращаться к бегу после силовых станций без резкого падения темпа.',controls:'Четыре беговые отсечки, станции и переходы на шаг. Цель — малый разброс, не рекорд.',note:'При необходимости 60–90 сек восстановления после пары «бег + станция».',steps:[step('Разминка','10 мин','run'),step('Бег 1','500 м','run'),step('Толкание саней','25 м'),step('Бег 2','500 м','run'),step('Тяга саней','25 м'),step('Бег 3','500 м','run'),step('Burpee broad jumps','20 м'),step('Бег 4','500 м','run'),step('Перенос гирь','100 м'),step('Заминка','5–8 мин','run')]},
 {key:'w05',date:'2026-11-10',title:'Аэробная база',kind:'Аэробная',duration:'55–65 мин',rpe:'3–6/10',goal:'Продлить спокойную работу и сохранять технику на эргах.',controls:'Дистанция, непрерывное время бега и падение темпа между повторами эргов.',note:'Короткий шаг допустим. Остановить бег на 30 мин при боли или ухудшении техники.',steps:[step('Разминка','10 мин','run'),step('Лёгкий бег','30–40 мин','run'),step('SkiErg','2 × 500 м, RPE 5–6'),step('Гребля','2 × 500 м, RPE 5–6'),step('Заминка','5 мин','run')]},
 {key:'w06',date:'2026-11-14',title:'Пять гоночных связок',kind:'Специфика',duration:'60–70 мин',rpe:'6–7/10',goal:'Стабилизировать бег на нарастающей усталости.',controls:'Время бега, переходы на шаг, SkiErg, wall balls и боль 0–10.',note:'750 м только после стабильной тренировки №4; иначе оставить 500 м.',steps:[step('Разминка','10 мин','run'),step('Бег 1','500–750 м','run'),step('SkiErg','500 м'),step('Бег 2','500–750 м','run'),step('Толкание саней','25 м'),step('Бег 3','500–750 м','run'),step('Burpee broad jumps','30 м'),step('Бег 4','500–750 м','run'),step('Выпады с мешком','25 м'),step('Бег 5','500–750 м','run'),step('Wall balls','30 повторений'),step('Заминка','5 мин','run')]},
 {key:'w07',date:'2026-11-17',title:'Подводка к симуляции',kind:'Восстановительная',duration:'45–55 мин',rpe:'3–4/10',goal:'Подготовиться к контрольной симуляции без накопления усталости.',controls:'Самочувствие сразу и на следующий день; боли быть не должно.',note:'Никаких рекордов.',steps:[step('Разминка','10 мин','run'),step('Лёгкий бег','25–30 мин','run'),step('Техника саней','2 × 12,5 м толкание и тяга'),step('Гребля','2 × 250 м спокойно'),step('Заминка','5 мин','run')]},
 {key:'w08',date:'2026-11-21',title:'Контрольная симуляция',kind:'Контроль',duration:'70–90 мин',rpe:'6–7/10',goal:'Главный тест цикла: восемь сокращённых связок ровно, без работы до отказа.',controls:'Общее время, все отсечки, средний/макс. пульс, RPE, шаг и самочувствие через 24/48 ч.',note:'Если предыдущие занятия нестабильны — выполнить 5–6 связок.',steps:[step('Разминка','10–12 мин','run'),step('Бег 1','750 м','run'),step('SkiErg','500 м'),step('Бег 2','750 м','run'),step('Толкание саней','25 м'),step('Бег 3','750 м','run'),step('Тяга саней','25 м'),step('Бег 4','750 м','run'),step('Burpee broad jumps','30–40 м'),step('Бег 5','750 м','run'),step('Гребля','500 м'),step('Бег 6','750 м','run'),step('Перенос гирь','100 м'),step('Бег 7','750 м','run'),step('Выпады с мешком','25 м'),step('Бег 8','750 м','run'),step('Wall balls','30 повторений'),step('Заминка','8–10 мин','run')]},
 {key:'w09',date:'2026-11-24',title:'Ровные километры',kind:'Аэробная',duration:'45–55 мин',rpe:'5–6/10',goal:'Закрепить ровный бег и начать снижение объёма.',controls:'Разброс километров, RPE последнего и восстановление дыхания.',note:'Три повтора достаточно, если после симуляции сохраняется усталость.',steps:[step('Разминка','10 мин','run'),step('Бег','3–4 × 1 км; 2 мин ходьбы','run'),step('SkiErg','2 × 250 м спокойно'),step('Заминка','5 мин','run')]},
 {key:'w10',date:'2026-11-28',title:'Гоночный ритм',kind:'Специфика',duration:'40–50 мин',rpe:'5–6/10',goal:'Сохранить ритм станций без тяжёлой мышечной усталости.',controls:'Ровные беговые отрезки, запас 2–3 повтора, лёгкие ноги на следующий день.',note:'Работа не до отказа.',steps:[step('Разминка','10 мин','run'),step('Бег 1','500 м','run'),step('Гребля','300 м'),step('Бег 2','500 м','run'),step('Burpee broad jumps','15–20 м'),step('Бег 3','500 м','run'),step('Перенос гирь','50 м'),step('Бег 4','500 м','run'),step('Wall balls','20 повторений'),step('Заминка','5 мин','run')]},
 {key:'w11',date:'2026-12-01',title:'Предстартовая активация',kind:'Подводка',duration:'25–35 мин',rpe:'3–4/10',goal:'Сохранить тонус и закончить тренировку свежим.',controls:'Только нормальное самочувствие; никаких рекордов и отказа.',note:'3–4 декабря — отдых или спокойная прогулка.',steps:[step('Лёгкий бег','10–15 мин','run'),step('Ускорения','3 × 20 сек, полное восстановление','run'),step('SkiErg','200 м спокойно'),step('Гребля','200 м спокойно'),step('Wall balls','10 повторений'),step('Заминка','5 мин','run')]},
 {key:'race',date:'2026-12-05',title:'CRACE Санкт-Петербург',kind:'Старт',duration:'Финиш',rpe:'Контроль',goal:'Пройти гонку с ровным началом и сохранить бег после последних станций.',controls:'Не выигрывать минуту в начале ценой десяти минут в конце.',note:'8 × 1 км + 8 станций. Категорию и соревновательные веса подтвердить заранее.',steps:[step('Старт','Первые 2 км контролируемо','run'),step('Гонка','8 × 1 км + 8 станций','run')]}
];

let ctx=null,activeTab='plan',activeKey='w02',bluetoothDevice=null,heartCharacteristic=null,liveHr=null,lastPromptAt=0;
let timer={running:false,elapsed:0,startedAt:0,step:0,stepStarted:0,laps:[],samples:[],startedIso:null};

const state=()=>ctx?.state?.crace||{profile:{max_hr:190,weight_kg:null},completed_sessions:{baseline:true},workouts:[]};
const session=()=>cracePlan.find(item=>item.key===activeKey)||cracePlan[1];
const totalElapsed=()=>timer.elapsed+(timer.running?(performance.now()-timer.startedAt)/1000:0);
const formatTime=value=>{const total=Math.max(0,value||0),minutes=Math.floor(total/60),seconds=total-minutes*60;return `${String(minutes).padStart(2,'0')}:${seconds.toFixed(1).padStart(4,'0')}`};
const dateLabel=value=>new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short'}).format(new Date(`${value}T12:00:00`));
const say=text=>{if(!('speechSynthesis'in window))return;window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))};

function header(){
 const days=Math.max(0,Math.ceil((raceDate-new Date())/86400000)),done=Object.values(state().completed_sessions||{}).filter(Boolean).length;
 return `<section class="crace-hero"><div><span class="eyebrow">CRACE · САНКТ-ПЕТЕРБУРГ</span><h1>Подготовка к старту</h1><p>5 декабря · Михайловский Манеж · HYROX</p></div><div class="crace-countdown"><strong>${days}</strong><span>дней до старта</span></div><div class="crace-hero-stat"><strong>${done}/12</strong><span>этапов плана</span></div></section>
 <nav class="crace-tabs">${[['plan','▦','План'],['wod','◷','WOD-таймер'],['charts','▥','Графики'],['nutrition','◆','Питание']].map(([key,icon,label])=>`<button class="${activeTab===key?'active':''}" data-crace-tab="${key}"><span>${icon}</span>${label}</button>`).join('')}</nav>`;
}

function planView(){
 const completed=state().completed_sessions||{},selected=session();
 return `<div class="crace-plan-layout"><section class="card crace-session-list"><div class="card-title"><span>План до 5 декабря</span><button class="secondary" data-crace-action="calendar">＋ В календарь</button></div>${cracePlan.map(item=>`<button class="crace-session-row ${item.key===activeKey?'selected':''}" data-crace-session="${item.key}"><span class="crace-session-status ${completed[item.key]?'done':''}">${completed[item.key]?'✓':'○'}</span><span><b>${esc(item.title)}</b><small>${dateLabel(item.date)} · ${esc(item.kind)} · RPE ${esc(item.rpe)}</small></span></button>`).join('')}</section>
 <section class="card crace-detail"><div class="crace-detail-head"><div><span class="eyebrow">${dateLabel(selected.date).toUpperCase()} · ${esc(selected.kind)}</span><h2>${esc(selected.title)}</h2><p>${esc(selected.duration)} · RPE ${esc(selected.rpe)}</p></div><button class="${completed[selected.key]?'secondary':'primary'}" data-crace-action="complete" data-key="${selected.key}">${completed[selected.key]?'Вернуть в план':'Отметить выполненной'}</button></div><div class="crace-callout"><b>Цель</b><p>${esc(selected.goal)}</p></div><ol class="crace-steps">${selected.steps.map(item=>`<li><span class="${item.phase}">${item.phase==='run'?'Бег':'Станция'}</span><div><b>${esc(item.name)}</b><small>${esc(item.target)}</small></div></li>`).join('')}</ol><div class="crace-guidance"><div><b>Контроль</b><p>${esc(selected.controls)}</p></div><div><b>Коррекция</b><p>${esc(selected.note)}</p></div></div>${!['baseline','race'].includes(selected.key)?`<button class="primary" data-crace-action="open-wod" data-key="${selected.key}">Открыть в WOD-таймере</button>`:''}</section></div>`;
}

function wodView(){
 const selected=session(),current=selected.steps[Math.min(timer.step,selected.steps.length-1)],connected=heartCharacteristic!==null;
 return `<section class="card crace-wod-toolbar"><label>Тренировка<select id="crace-wod-select">${cracePlan.filter(item=>!['baseline','race'].includes(item.key)).map(item=>`<option value="${item.key}" ${item.key===selected.key?'selected':''}>${dateLabel(item.date)} · ${esc(item.title)}</option>`).join('')}</select></label><button class="${connected?'secondary':'primary'}" data-crace-action="bluetooth">${connected?'♥ DexBee подключён':'♥ Подключить пульсометр'}</button><div class="crace-live-hr"><strong id="crace-live-hr">${liveHr||'—'}</strong><span>уд/мин</span></div></section>
 <div class="crace-wod-layout"><section class="card crace-timer-card"><span class="eyebrow">ОБЩЕЕ ВРЕМЯ</span><strong class="crace-timer" id="crace-timer">${formatTime(totalElapsed())}</strong><span class="crace-stage-time" id="crace-stage-time">Этап ${formatTime(totalElapsed()-timer.stepStarted)}</span><div class="crace-current-stage"><span>${current.phase==='run'?'БЕГ':'СТАНЦИЯ'}</span><h2>${esc(current.name)}</h2><p>${esc(current.target)}</p></div><div class="crace-timer-actions"><button class="primary" data-crace-action="timer">${timer.running?'Пауза':totalElapsed()?'Продолжить':'Старт'}</button><button class="secondary" data-crace-action="next">Следующий этап</button><button class="secondary" data-crace-action="reset">Сброс</button></div><label class="crace-rpe">RPE после финиша <select id="crace-rpe">${Array.from({length:10},(_,index)=>`<option value="${index+1}" ${index+1===5?'selected':''}>${index+1}/10</option>`).join('')}</select></label><small>Space — старт/пауза · Enter — следующий этап. Голосовые подсказки звучат через выбранные на телефоне наушники.</small></section>
 <section class="card crace-stage-list"><div class="card-title"><span>Этапы и отсечки</span><b>${timer.step+1}/${selected.steps.length}</b></div>${selected.steps.map((item,index)=>`<div class="crace-stage-row ${index===timer.step?'active':''} ${index<timer.step?'done':''}"><span>${index<timer.step?'✓':String(index+1).padStart(2,'0')}</span><div><b>${esc(item.name)}</b><small>${esc(item.target)}</small></div><time>${timer.laps[index]?formatTime(timer.laps[index].seconds):''}</time></div>`).join('')}</section></div>`;
}

function hrSvg(samples){
 if(!samples?.length)return '<div class="crace-empty-chart">График появится после тренировки с пульсометром</div>';
 const width=900,height=260,pad=28,maxT=Math.max(1,...samples.map(item=>item.t)),minHr=Math.min(90,...samples.map(item=>item.hr)),maxHr=Math.max(190,...samples.map(item=>item.hr));
 const points=samples.map(item=>`${pad+item.t/maxT*(width-pad*2)},${height-pad-(item.hr-minHr)/(maxHr-minHr)*(height-pad*2)}`).join(' ');
 return `<svg class="crace-hr-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Пульс последней тренировки"><line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}"/><polyline points="${points}"/><text x="${pad}" y="${height-7}">0 мин</text><text x="${width-pad}" y="${height-7}" text-anchor="end">${Math.round(maxT/60)} мин</text><text x="${pad}" y="20">${maxHr}</text></svg>`;
}

function chartsView(){
 const workouts=state().workouts||[],latest=workouts[0];
 return `<div class="crace-metrics"><article><span>ПЕРВАЯ ТРЕНИРОВКА</span><strong>75:21</strong><small>27 октября</small></article><article><span>СРЕДНИЙ ПУЛЬС</span><strong>160</strong><small>уд/мин</small></article><article><span>МАКС. ПУЛЬС</span><strong>184</strong><small>уд/мин</small></article><article><span>БЕГ</span><strong>4 км</strong><small>40 м бег / 10 м шаг</small></article></div><section class="card crace-chart-card"><div class="card-title"><span>${latest?`Последняя тренировка · ${esc(latest.title)}`:'Пульс тренировки'}</span>${latest?`<small>${latest.avg_hr||'—'} средний · ${latest.max_hr||'—'} максимум</small>`:''}</div>${hrSvg(latest?.samples)}</section><section class="card crace-zones"><div class="card-title">Первая тренировка · время в зонах</div>${[['170–188',32,'red'],['151–169',51,'yellow'],['132–150',8,'green'],['113–131',7,'blue'],['94–112',2,'gray']].map(([label,value,color])=>`<div><span>${label}</span><i><b class="${color}" style="width:${value/55*100}%"></b></i><strong>${value}%</strong></div>`).join('')}</section>${workouts.length?`<section class="card"><div class="card-title">История тренировок</div>${workouts.map(item=>`<div class="crace-workout-row"><div><b>${esc(item.title)}</b><small>${new Date(item.started_at).toLocaleString('ru-RU')}</small></div><span>${formatTime(item.duration_sec)}</span><span>${item.avg_hr||'—'} / ${item.max_hr||'—'} уд/мин</span><span>RPE ${item.rpe||'—'}</span></div>`).join('')}</section>`:''}`;
}

function nutritionView(){
 const profile=state().profile||{},weight=Number(profile.weight_kg)||0,day=document.querySelector('#crace-day-type')?.value||'hard',ranges={recovery:[3,4],easy:[3,5],hard:[5,7],pre:[5,7],race:[4,6]},range=ranges[day],carbs=weight?[Math.round(weight*range[0]),Math.round(weight*range[1])]:null,protein=weight?[Math.round(weight*1.4),Math.round(weight*1.8)]:null;
 return `<div class="crace-nutrition-layout"><section class="card"><span class="eyebrow">ПЕРСОНАЛЬНЫЙ РАСЧЁТ</span><h2>Топливо для тренировок</h2><p>Диапазоны зависят от нагрузки и массы тела. Это не жёсткая диета.</p><form id="crace-profile-form"><label>Масса тела, кг<input name="weight_kg" type="number" min="35" max="250" step="0.1" value="${esc(profile.weight_kg||'')}" required></label><label>Ориентир максимального пульса<input name="max_hr" type="number" min="100" max="230" value="${esc(profile.max_hr||190)}" required></label><label>Тип дня<select id="crace-day-type"><option value="recovery" ${day==='recovery'?'selected':''}>Восстановление</option><option value="easy" ${day==='easy'?'selected':''}>Лёгкая тренировка</option><option value="hard" ${day==='hard'?'selected':''}>Тяжёлая тренировка</option><option value="pre" ${day==='pre'?'selected':''}>День перед стартом</option><option value="race" ${day==='race'?'selected':''}>День старта</option></select></label><button class="primary">Рассчитать и сохранить</button></form>${weight?`<div class="crace-nutrition-result"><div><strong>${carbs[0]}–${carbs[1]} г</strong><span>углеводы за день</span></div><div><strong>${protein[0]}–${protein[1]} г</strong><span>белок за день</span></div><div><strong>≈ ${Math.round(weight*.3)} г</strong><span>белок после нагрузки</span></div></div>`:'<div class="empty">Укажите массу тела, чтобы получить диапазоны.</div>'}</section><section class="card crace-food-guide"><span class="eyebrow">ПРАКТИЧЕСКИЙ ПЛАН</span><h2>Без экспериментов в день гонки</h2><h3>Тренировочный день</h3><p>В основных приёмах пищи: источник углеводов, 25–40 г белка и овощи. За 2–3 часа до нагрузки — привычная еда, умеренно белка и мало тяжёлого жира.</p><h3>Симуляция 21 ноября</h3><p>Проверьте тот же завтрак, напиток и возможный гель, которые планируете на старт.</p><h3>Перед стартом</h3><p>За 1–4 часа — знакомая углеводная еда. Для нагрузки дольше часа: 30–60 г углеводов в час, только если ЖКТ уже это переносил.</p><h3>Примеры</h3><p>Каша + банан + йогурт; рис или гречка + птица или рыба; картофель + яйца; хлеб + творог; фрукты.</p><div class="crace-warning">При заболеваниях ЖКТ, диабете, заболеваниях почек или цели снижения веса нужен персональный план со специалистом.</div></section></div>`;
}

export function renderCRace(appState){
 if(appState)appState.crace=appState.crace||state();
 const views={plan:planView,wod:wodView,charts:chartsView,nutrition:nutritionView};
 return `<div class="crace-shell">${header()}${views[activeTab]()}</div>`;
}

function updateTimerDom(){
 const total=totalElapsed(),timerEl=document.querySelector('#crace-timer'),stageEl=document.querySelector('#crace-stage-time');
 if(timerEl)timerEl.textContent=formatTime(total);
 if(stageEl)stageEl.textContent=`Этап ${formatTime(total-timer.stepStarted)}`;
}
setInterval(updateTimerDom,100);

async function toggleCompleted(key){
 const current=Boolean(state().completed_sessions?.[key]),result=await ctx.api(`/crace/sessions/${key}`,{method:'PUT',body:JSON.stringify({completed:!current})});
 state().completed_sessions={...(state().completed_sessions||{}),[key]:result.completed};ctx.redraw();
}

async function addPlanToCalendar(){
 const existing=new Set((ctx.state.tasks||[]).flatMap(task=>task.tags||[]).filter(tag=>tag.startsWith('crace-session:')).map(tag=>tag.split(':')[1]));let added=0;
 for(const item of cracePlan.filter(item=>item.key!=='baseline'&&!existing.has(item.key))){
  const start=new Date(`${item.date}T18:00:00`),duration=item.key==='race'?180:60,end=new Date(start.getTime()+duration*60000);
  const task=await ctx.api('/tasks',{method:'POST',body:JSON.stringify({title:`CRACE · ${item.title}`,description:`${item.goal}\n\n${item.steps.map((part,index)=>`${index+1}. ${part.name} — ${part.target}`).join('\n')}`,priority:item.key==='race'?'P1':'P2',status:'planned',start_at:start.toISOString(),end_at:end.toISOString(),duration_minutes:duration,all_day:false,tags:['crace-2026',`crace-session:${item.key}`]})});ctx.state.tasks.push(task);added++;
 }
 ctx.toast(added?`Добавлено тренировок в календарь: ${added}`:'План уже находится в календаре');
}

async function connectBluetooth(){
 if(!navigator.bluetooth)throw new Error('Web Bluetooth доступен в Chrome или Edge на Android и Windows');
 bluetoothDevice=await navigator.bluetooth.requestDevice({filters:[{services:['heart_rate']}]});
 bluetoothDevice.addEventListener('gattserverdisconnected',()=>{heartCharacteristic=null;ctx.toast('Пульсометр отключён');ctx.redraw()});
 const server=await bluetoothDevice.gatt.connect(),service=await server.getPrimaryService('heart_rate');
 heartCharacteristic=await service.getCharacteristic('heart_rate_measurement');
 heartCharacteristic.addEventListener('characteristicvaluechanged',onHeartRate);await heartCharacteristic.startNotifications();ctx.toast(`Подключено: ${bluetoothDevice.name||'пульсометр'}`);ctx.redraw();
}

function onHeartRate(event){
 const data=event.target.value,flags=data.getUint8(0),hr=flags&1?data.getUint16(1,true):data.getUint8(1);liveHr=hr;
 const el=document.querySelector('#crace-live-hr');if(el)el.textContent=hr;
 if(!timer.running)return;const elapsed=totalElapsed(),last=timer.samples.at(-1);if(!last||elapsed-last.t>=.8)timer.samples.push({t:+elapsed.toFixed(1),hr,phase:session().steps[timer.step]?.phase||'station'});
 const max=Number(state().profile?.max_hr)||190,current=session().steps[timer.step],bounds=current?.phase==='run'?[.70,.82]:[.78,.88],low=Math.round(max*bounds[0]),high=Math.round(max*bounds[1]),now=Date.now();
 if(now-lastPromptAt<25000)return;if(hr>high){say('Сбавь темп');lastPromptAt=now}else if(hr<low){say(current?.phase==='run'?'Можно немного ускориться':'Можно добавить интенсивность');lastPromptAt=now}
}

function toggleTimer(){
 if(timer.running){timer.elapsed=totalElapsed();timer.running=false}else{if(!timer.elapsed){timer.startedIso=new Date().toISOString();timer.samples=[];timer.laps=[];timer.step=0;timer.stepStarted=0;say(`Начинаем. ${session().steps[0].name}`)}timer.startedAt=performance.now();timer.running=true}ctx.redraw();
}

async function nextStep(){
 if(totalElapsed()<=0)return;const selected=session(),total=totalElapsed(),current=selected.steps[timer.step];timer.laps[timer.step]={name:current.name,seconds:+(total-timer.stepStarted).toFixed(1)};
 if(timer.step<selected.steps.length-1){timer.step++;timer.stepStarted=total;say(`Следующий этап. ${selected.steps[timer.step].name}`);ctx.redraw();return}
 timer.elapsed=total;timer.running=false;const rpe=Number(document.querySelector('#crace-rpe')?.value)||5,workout=await ctx.api('/crace/workouts',{method:'POST',body:JSON.stringify({plan_key:selected.key,title:selected.title,started_at:timer.startedIso,duration_sec:Math.round(total),rpe,samples:timer.samples,laps:timer.laps})});state().workouts=[workout,...(state().workouts||[])];state().completed_sessions={...(state().completed_sessions||{}),[selected.key]:true};say('Тренировка завершена');ctx.toast('Тренировка и пульс сохранены');activeTab='charts';resetTimer(false);ctx.redraw();
}

function resetTimer(redraw=true){timer={running:false,elapsed:0,startedAt:0,step:0,stepStarted:0,laps:[],samples:[],startedIso:null};if(redraw)ctx.redraw()}

export function bindCRace(context){
 ctx=context;if(window.__craceBound)return;window.__craceBound=true;
 document.addEventListener('click',async event=>{const tab=event.target.closest('[data-crace-tab]');if(tab){activeTab=tab.dataset.craceTab;ctx.redraw();return}const row=event.target.closest('[data-crace-session]');if(row){activeKey=row.dataset.craceSession;ctx.redraw();return}const button=event.target.closest('[data-crace-action]');if(!button)return;try{const action=button.dataset.craceAction;if(action==='complete')await toggleCompleted(button.dataset.key);if(action==='calendar')await addPlanToCalendar();if(action==='open-wod'){activeKey=button.dataset.key;activeTab='wod';resetTimer(false);ctx.redraw()}if(action==='bluetooth')await connectBluetooth();if(action==='timer')toggleTimer();if(action==='next')await nextStep();if(action==='reset')resetTimer()}catch(error){ctx.toast(error.message||'Не удалось выполнить действие')}},true);
 document.addEventListener('change',event=>{if(event.target.id==='crace-wod-select'){activeKey=event.target.value;resetTimer()}if(event.target.id==='crace-day-type')ctx.redraw()});
 document.addEventListener('submit',async event=>{if(event.target.id!=='crace-profile-form')return;event.preventDefault();const data=Object.fromEntries(new FormData(event.target));try{const profile=await ctx.api('/crace/profile',{method:'PUT',body:JSON.stringify({weight_kg:Number(data.weight_kg),max_hr:Number(data.max_hr)})});state().profile=profile;ctx.toast('Параметры сохранены');ctx.redraw()}catch(error){ctx.toast(error.message)}},true);
 document.addEventListener('keydown',event=>{if(ctx.page()!=='crace'||activeTab!=='wod'||['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;if(event.code==='Space'){event.preventDefault();toggleTimer()}if(event.code==='Enter'){event.preventDefault();nextStep()}});
}
