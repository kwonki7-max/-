'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {companyOrigin,sameOrigin}=require('../security.cjs');
test('company server requires a clean HTTPS origin',()=>{
 assert.equal(companyOrigin(' https://company.example.com/ '),'https://company.example.com');
 assert.equal(companyOrigin('https://company.example.com:8443'),'https://company.example.com:8443');
 for(const url of ['',null,'http://company.example.com','file:///etc/passwd','javascript:alert(1)','https://name:pass@company.example.com','https://company.example.com/path','https://company.example.com/?token=secret','https://company.example.com/#x'])assert.throws(()=>companyOrigin(url));
});
test('navigation scope cannot be escaped using a lookalike domain',()=>{
 assert.equal(sameOrigin('https://company.example.com/api/session','https://company.example.com'),true);
 for(const url of ['https://company.example.com.evil.test','https://company.example.com@evil.test','http://company.example.com','https://evil.test','file:///tmp/test'])assert.equal(sameOrigin(url,'https://company.example.com'),false);
});
