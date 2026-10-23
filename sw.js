// Service worker แบบเบา: ไม่เก็บแคช จึงไม่มีปัญหาไฟล์เก่าค้าง ใช้เพื่อให้ Chrome ติดตั้งเป็นแอปได้
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{
  if(e.request.mode==='navigate'){
    e.respondWith(fetch(e.request).catch(()=>new Response('ออฟไลน์อยู่ กรุณาเชื่อมต่ออินเทอร์เน็ต',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}})));
  }
});
