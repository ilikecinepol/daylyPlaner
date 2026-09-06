const CACHE='plan-v6.9';
const ASSETS=['/','/index.html','/styles.css?v=3.2','/app.js?v=6.9','/frontend/js/api.js','/frontend/js/profile.js','/frontend/js/goals.js','/frontend/js/finance.js','/frontend/js/calendar.js','/frontend/js/ai.js','/manifest.webmanifest'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  if(event.request.method==='GET'&&!event.request.url.includes('/api/'))event.respondWith(fetch(event.request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));return response}).catch(()=>caches.match(event.request)));
});
