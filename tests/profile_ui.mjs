import assert from 'node:assert/strict';
import {profileCard,updateProfileAvatar} from '../frontend/js/profile.js';

const user={name:'Анна',last_name:'Иванова',job_title:'<script>alert(1)</script>',nickname:'anna',email:'anna@example.com',timezone:'Europe/Moscow',profile_status:'busy',contact_info:'Телефон',avatar_data_url:''};
const card=profileCard(user);
assert.ok(card.includes('Анна Иванова'));
assert.ok(card.includes('Занят'));
assert.ok(card.includes('&lt;script&gt;'));
assert.ok(!card.includes('<script>'));
assert.ok(card.includes('data-profile-edit'));
const button={setAttribute(name,value){this[name]=value}};
global.document={querySelector(){return button}};
updateProfileAvatar(user);
assert.equal(button.innerHTML,'АИ');
assert.equal(button['aria-label'],'Открыть профиль');
console.log('Profile renderer checks passed');
