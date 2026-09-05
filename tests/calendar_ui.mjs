import assert from 'node:assert/strict';
import {calendarMovePatch,localTime,replaceScheduledTimeInTitle} from '../frontend/js/calendar.js';

const start='2026-09-05T07:30:00Z',oldTime=localTime(start);
const original={title:`Созвон в ${oldTime}`,start_at:start,duration_minutes:60,all_day:false};
const moved=calendarMovePatch(original,'2026-09-06','14:15');
assert.equal(moved.title,'Созвон в 14:15');
assert.equal(moved.all_day,false);
assert.equal(new Date(moved.end_at)-new Date(moved.start_at),60*60*1000);
assert.equal(replaceScheduledTimeInTitle('Версия 10:30.2','10:30','11:00'),'Версия 11:00.2');
assert.equal(calendarMovePatch({title:'Выходной',start_at:'2026-09-05T00:00:00Z',duration_minutes:60,all_day:true},'2026-09-08','').start_at,'2026-09-08T00:00:00Z');

console.log('calendar ui helpers: ok');
