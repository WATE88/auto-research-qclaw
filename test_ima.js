const https = require('https');

const CLIENT_ID = 'cd8f18bf3caa5c8e9be93b73385fe879';
const API_KEY = 'cd8f18bf3caa5c8e9be93b73385fe879';

function apiPost(apiPath, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const options = {
      hostname: 'ima.qq.com',
      port: 443,
      path: '/' + apiPath,
      method: 'POST',
      headers: {
        'ima-openapi-clientid': CLIENT_ID,
        'ima-openapi-apikey': API_KEY,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
      },
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        console.log('STATUS:', res.statusCode);
        console.log('BODY:', body.substring(0, 500));
        resolve({ status: res.statusCode, body });
      });
    });
    req.on('error', (e) => { console.error('ERROR:', e.message); reject(e); });
    req.write(data);
    req.end();
  });
}

async function main() {
  // Test 1: get_knowledge_base list
  console.log('=== Test 1: openapi/wiki/v1/get_knowledge_base ===');
  try { await apiPost('openapi/wiki/v1/get_knowledge_base', {}); } catch(e) {}

  // Test 2: search_knowledge_base
  console.log('\n=== Test 2: openapi/wiki/v1/search_knowledge_base ===');
  try { await apiPost('openapi/wiki/v1/search_knowledge_base', { keyword: 'test' }); } catch(e) {}
}

main();