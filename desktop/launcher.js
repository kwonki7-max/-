'use strict';
const $=selector=>document.querySelector(selector);
for(const action of ['minimize','maximize','close'])$('#'+action).onclick=()=>window.desktop[action]();
let busy=false;
async function connect(){
 if(busy)return;busy=true;$('#retry').hidden=true;$('.connection-state').classList.remove('failed');$('#state-title').textContent='회사 작업 공간에 연결 중';$('#message').textContent='잠시만 기다려주세요.';
 try{
   const result=await window.desktop.retry();
   if(!result.ok){$('.connection-state').classList.add('failed');$('#state-title').textContent=result.configurationRequired?'회사 연결 준비 중':'연결을 확인해주세요';$('#message').textContent=result.error;$('#retry').hidden=false;}
 }catch{$('.connection-state').classList.add('failed');$('#state-title').textContent='다시 연결해주세요';$('#message').textContent='프로그램 연결을 다시 시도해주세요.';$('#retry').hidden=false;}
 finally{busy=false;}
}
$('#retry').onclick=connect;
window.desktop.info().then(info=>{$('#version').textContent='v'+info.version;$('#company-title').textContent=info.companyName+' 작업 공간';connect();}).catch(()=>{$('#message').textContent='프로그램을 다시 실행해주세요.';});
