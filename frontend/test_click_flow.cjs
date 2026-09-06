const { spawn } = require('child_process');
const http = require('http');

async function putJson(url) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method: 'PUT' }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    });
    req.on('error', reject);
    req.end();
  });
}

async function run() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const chrome = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--user-data-dir=C:\\Users\\user\\AppData\\Local\\Temp\\chrome-debug-profile-click'
  ]);

  await new Promise(r => setTimeout(r, 1500));

  try {
    const list = await putJson('http://127.0.0.1:9222/json/new?http://127.0.0.1:5173/customer/login');
    const wsUrl = list.webSocketDebuggerUrl;
    const ws = new WebSocket(wsUrl);
    let msgId = 1;
    const pending = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg.result);
        pending.delete(msg.id);
      }
      if (msg.method === 'Runtime.consoleAPICalled') {
        console.log('[Browser Console]', msg.params.type, msg.params.args.map(a => a.value || a.description).join(' '));
      }
      if (msg.method === 'Runtime.exceptionThrown') {
        console.error('[Browser Exception!]', JSON.stringify(msg.params.exceptionDetails));
      }
    };

    await new Promise(r => ws.onopen = r);

    function send(method, params = {}) {
      return new Promise(resolve => {
        const id = msgId++;
        pending.set(id, resolve);
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    await send('Runtime.enable');
    await send('Log.enable');
    await send('Page.enable');

    async function evaluate(code) {
      const res = await send('Runtime.evaluate', { expression: code });
      return res.result ? res.result.value : null;
    }

    await new Promise(r => setTimeout(r, 2000));
    console.log('1. Loaded:', await evaluate('window.location.href'));

    // Click the "调度控制台入口" link (client-side React router Link to /login)
    console.log('2. Clicking "调度控制台入口"...');
    let clickOpLink = await evaluate(`(() => {
      const links = Array.from(document.querySelectorAll('a'));
      const link = links.find(a => a.href.includes('/login'));
      if (link) {
        link.click();
        return 'Clicked ' + link.textContent;
      }
      return 'Link not found';
    })()`);
    console.log(clickOpLink);

    await new Promise(r => setTimeout(r, 1500));
    console.log('3. URL after clicking link:', await evaluate('window.location.href'));

    // Now on /login, click "Operator" button
    console.log('4. Clicking "Operator" quick login...');
    let clickOp = await evaluate(`(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const btn = btns.find(b => b.textContent.trim() === 'Operator');
      if (btn) {
        btn.click();
        return 'Clicked Operator';
      }
      return 'Operator button not found';
    })()`);
    console.log(clickOp);

    await new Promise(r => setTimeout(r, 2000));
    console.log('5. URL after clicking Operator:', await evaluate('window.location.href'));
    let bodyText = await evaluate('document.body.innerText');
    console.log('Body text length:', (bodyText || '').length);
    console.log('Body text:', (bodyText || '').substring(0, 300));

    ws.close();
  } catch (err) {
    console.error(err);
  } finally {
    chrome.kill();
  }
}

run();
