'use strict';
function companyOrigin(value) {
  if (typeof value !== 'string' || value.length > 2048) throw new Error('회사 연결 주소를 확인해주세요.');
  let url;
  try { url = new URL(value.trim()); } catch { throw new Error('관리자가 안내한 https:// 회사 연결 주소를 입력해주세요.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('https://로 시작하는 회사 주소만 사용할 수 있습니다. 경로·계정정보는 넣지 마세요.');
  }
  return url.origin;
}
function sameOrigin(value, origin) {
  try { return Boolean(origin) && new URL(value).origin === origin; } catch { return false; }
}
module.exports = {companyOrigin, sameOrigin};
