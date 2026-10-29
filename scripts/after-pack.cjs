'use strict';
const fs=require('node:fs');
const path=require('node:path');
module.exports=async context=>{
 if(context.electronPlatformName!=='win32')return;
 const files=[],dirs=[];
 function walk(dir,relative=''){
   for(const item of fs.readdirSync(dir,{withFileTypes:true})){
     const next=relative?relative+'/'+item.name:item.name;
     if(/[\r\n"$]/.test(next))throw new Error('Unsupported filename in installer manifest');
     if(item.isDirectory()){walk(path.join(dir,item.name),next);dirs.push(next);}
     else files.push(next);
   }
 }
 walk(context.appOutDir);
 const output=path.join(context.packager.projectDir,'.desktop-build');
 fs.mkdirSync(output,{recursive:true});
 const lines=[...files.map(file=>'Delete "$INSTDIR\\'+file.replaceAll('/','\\')+'"'),...dirs.map(dir=>'RMDir "$INSTDIR\\'+dir.replaceAll('/','\\')+'"')];
 fs.writeFileSync(path.join(output,'uninstall-files.nsh'),'; Generated from packaged files. Unknown user files are retained.\n'+lines.join('\n')+'\n');
};
