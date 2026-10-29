'use strict';
// Run by the maintainer before packaging; no address input is exposed to employees.
const fs=require('node:fs');
const path=require('node:path');
const {companyOrigin}=require('../desktop/security.cjs');
try{
 const serverUrl=companyOrigin(process.argv[2]);
 const companyName=(process.argv[3]||'우리 회사').trim();
 if(!companyName || companyName.length>80)throw new Error('회사명은 1~80자로 입력해주세요.');
 fs.writeFileSync(path.join(__dirname,'../desktop/company-config.json'),JSON.stringify({serverUrl,companyName},null,2)+'\n');
 console.log('Company connection configured. Rebuild the installer to apply it.');
}catch(error){console.error(error.message);process.exitCode=1;}
