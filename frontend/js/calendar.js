const pad=value=>String(value).padStart(2,'0');

export function localTime(value){
  if(!value)return'';
  const normalized=/Z$|[+-]\d\d:\d\d$/.test(value)?value:value+'Z',date=new Date(normalized);
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function replaceScheduledTimeInTitle(title,oldTime,newTime){
  if(!oldTime||!newTime||oldTime===newTime)return title;
  const escaped=oldTime.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return title.replace(new RegExp(`(^|[^\\d])${escaped}(?!\\d)`),(_,prefix)=>prefix+newTime);
}

export function calendarMovePatch(task,date,targetTime){
  const oldTime=task.all_day?'':localTime(task.start_at),time=targetTime||oldTime;
  if(!time)return {start_at:`${date}T00:00:00Z`,end_at:null,all_day:true,title:task.title};
  const start=new Date(`${date}T${time}:00`),duration=Math.max(0,task.duration_minutes||0),end=new Date(start.getTime()+duration*60000);
  return {start_at:start.toISOString(),end_at:end.toISOString(),all_day:false,title:replaceScheduledTimeInTitle(task.title,oldTime,time)};
}
