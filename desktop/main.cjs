'use strict';
const {app, BrowserWindow, ipcMain, session, net, Menu, Tray, nativeImage, dialog} = require('electron');
const path = require('node:path');
const crypto = require('node:crypto');
const {pathToFileURL} = require('node:url');
const {companyOrigin, sameOrigin} = require('./security.cjs');
const config = require('./company-config.json');
let window, tray, currentOrigin='', connecting=false, quitting=false;
let connectionMessage='회사 작업 공간에 연결하고 있습니다.';
const launcher = pathToFileURL(path.join(__dirname,'launcher.html')).href;
// Test overrides are deliberately unavailable in distributed installers.
const testMode=!app.isPackaged && process.env.GIJUNSIL_DESKTOP_TEST==='1';
if (testMode && process.env.GIJUNSIL_TEST_USER_DATA) app.setPath('userData',process.env.GIJUNSIL_TEST_USER_DATA);
if (!app.requestSingleInstanceLock()) app.quit();
app.setAppUserModelId('com.gijunsil.desktop');
function isMain(event) {return window && event.sender===window.webContents && event.senderFrame===window.webContents.mainFrame;}
function targetOrigin() {
  if(testMode && process.env.GIJUNSIL_TEST_SERVER){
    const u=new URL(process.env.GIJUNSIL_TEST_SERVER);
    if(u.protocol==='http:' && u.hostname==='127.0.0.1' && u.pathname==='/' && !u.username && !u.password && !u.search && !u.hash)return u.origin;
    throw new Error('Invalid test server');
  }
  return companyOrigin(config.serverUrl);
}
function guardedSession(partition, origin) {
  const ses=session.fromPartition(partition);
  ses.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
  ses.setPermissionCheckHandler(()=>false);
  ses.webRequest.onBeforeRequest((details,callback)=>{
    const allowed=origin?sameOrigin(details.url,origin):details.url.startsWith(pathToFileURL(__dirname+path.sep).href);
    callback({cancel:!allowed && !details.url.startsWith('devtools://')});
  });
  if(!ses.gijunsilDownloadHandler){
    ses.gijunsilDownloadHandler=true;
    ses.on('will-download',(_event,item)=>{
      item.setSaveDialogOptions({title:'견적 파일 저장',defaultPath:path.join(app.getPath('downloads'),path.basename(item.getFilename())),filters:[{name:'CSV 문서',extensions:['csv']}]});
      item.once('done',(_e,state)=>{if(state==='interrupted' && window)dialog.showMessageBox(window,{type:'error',message:'파일을 저장하지 못했습니다.',detail:'저장 위치와 연결 상태를 확인한 뒤 다시 시도해주세요.'});});
    });
  }
  return ses;
}
async function openWindow(target, partition, origin) {
  const old=window;
  const bounds=old && !old.isDestroyed()?old.getBounds():{width:1380,height:900};
  const maximized=old?.isMaximized();
  const previousOrigin=currentOrigin;
  currentOrigin=origin;
  window=new BrowserWindow({...bounds,minWidth:1000,minHeight:700,show:false,frame:false,backgroundColor:'#f5f6fb',title:'기준실',icon:path.join(__dirname,'assets','icon.png'),webPreferences:{preload:path.join(__dirname,'preload.cjs'),session:guardedSession(partition,origin),sandbox:true,contextIsolation:true,nodeIntegration:false,webSecurity:true,allowRunningInsecureContent:false,spellcheck:false}});
  const created=window;
  created.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  created.webContents.on('will-navigate',(event,url)=>{if(origin?!sameOrigin(url,origin):url!==launcher)event.preventDefault();});
  created.webContents.on('will-attach-webview',event=>event.preventDefault());
  created.on('close',event=>{if(!quitting && created===window){event.preventDefault();app.quit();}});
  try{
    await created.loadURL(target);
    if(maximized)created.maximize();
    created.show();
    if(old && !old.isDestroyed())old.destroy();
  }catch(error){
    if(!created.isDestroyed())created.destroy();
    window=old;currentOrigin=previousOrigin;
    throw error;
  }
}
async function connect(){
  if(connecting)return {ok:false,error:'연결 중입니다.'};
  connecting=true;
  try{
    if(!config.serverUrl && !testMode){
      connectionMessage='회사 연결 설정이 아직 완료되지 않았습니다. 관리자에게 회사용 설치파일을 요청해주세요.';
      return {ok:false,error:connectionMessage,configurationRequired:true};
    }
    const origin=targetOrigin();
    const response=await net.fetch(origin+'/health',{redirect:'error',signal:AbortSignal.timeout(10000),credentials:'omit'});
    if(!response.ok || (await response.json()).status!=='ok')throw new Error('Not ready');
    const partition='persist:company-'+crypto.createHash('sha256').update(origin).digest('hex').slice(0,20);
    await openWindow(origin,partition,origin);
    return {ok:true};
  }catch{
    connectionMessage='회사 작업 공간에 연결하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해주세요.';
    return {ok:false,error:connectionMessage};
  }finally{connecting=false;}
}
ipcMain.handle('desktop:info',event=>{
  if(!isMain(event))throw new Error('허용하지 않는 창입니다.');
  return {version:app.getVersion(),companyName:config.companyName||'우리 회사',configured:Boolean(config.serverUrl)||testMode,message:connectionMessage};
});
ipcMain.handle('desktop:retry',event=>{
  if(!isMain(event)||event.senderFrame.url!==launcher)throw new Error('시작 화면에서만 연결할 수 있습니다.');
  return connect();
});
ipcMain.handle('desktop:reload',async event=>{
  if(!isMain(event))throw new Error('허용하지 않는 창입니다.');
  const answer=await dialog.showMessageBox(window,{type:'question',message:'회사 작업 공간에 다시 연결할까요?',detail:'저장하지 않은 입력 내용은 사라집니다.',buttons:['계속 작업','다시 연결'],defaultId:0,cancelId:0});
  if(answer.response===1){await openWindow(launcher,'launcher','');const result=await connect();if(!result.ok)window.webContents.send('desktop:connection-failed');}
  return {ok:true};
});
for(const action of ['minimize','maximize','close'])ipcMain.on('desktop:'+action,event=>{
  if(!isMain(event))return;
  if(action==='minimize')window.minimize();
  else if(action==='maximize'){if(window.isMaximized())window.unmaximize();else window.maximize();}
  else app.quit();
});
app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.show();window.focus();}});
app.on('before-quit',()=>{quitting=true;});
app.on('window-all-closed',()=>app.quit());
app.whenReady().then(async()=>{
  Menu.setApplicationMenu(null);
  if(!testMode){
  tray=new Tray(nativeImage.createFromPath(path.join(__dirname,'assets','icon.png')));
  tray.setToolTip('기준실 · 견적조건 & 부자재');
  tray.setContextMenu(Menu.buildFromTemplate([{label:'기준실 열기',click:()=>{window?.show();window?.focus();}},{label:'창 숨기기',click:()=>window?.hide()},{type:'separator'},{label:'프로그램 종료',click:()=>app.quit()}]));
  tray.on('double-click',()=>{window?.show();window?.focus();});
  }
  await openWindow(launcher,'launcher','');
  // The trusted local startup page initiates one automatic connection attempt.
}).catch(()=>{dialog.showErrorBox('기준실 실행 오류','프로그램을 시작하지 못했습니다. 다시 설치한 후 실행해주세요.');app.quit();});
