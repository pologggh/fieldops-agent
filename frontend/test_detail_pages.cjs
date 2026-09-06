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
    '--user-data-dir=C:\\Users\\user\\AppData\\Local\\Temp\\chrome-debug-detail'
  ]);

  await new Promise(r => setTimeout(r, 1500));

  try {
    const list = await putJson('http://127.0.0.1:9222/json/new?http://127.0.0.1:5173/login');
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
        const text = msg.params.args.map(a => a.value || a.description).join(' ');
        if (!text.includes('[vite]')) {
          console.log('[Browser Console]', msg.params.type, text);
        }
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

    // Login as operator
    await evaluate(`(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Operator');
      if (btn) btn.click();
    })()`);
    await new Promise(r => setTimeout(r, 2000));
    console.log('Logged in as Operator, URL:', await evaluate('window.location.href'));

    // Go to /service-requests
    await evaluate(`(() => {
      const a = document.querySelector('a[href="/service-requests"]');
      if (a) a.click();
    })()`);
    await new Promise(r => setTimeout(r, 1500));
    console.log('Navigated to:', await evaluate('window.location.href'));

    // Click external link to /service-requests/2
    console.log('Clicking into service request detail...');
    let clickDetail = await evaluate(`(() => {
      const a = document.querySelector('a[href^="/service-requests/"]');
      if (a) {
        a.click();
        return 'Clicked ' + a.href;
      }
      return 'Link to detail not found';
    })()`);
    console.log('Click detail result:', clickDetail);

    await new Promise(r => setTimeout(r, 2000));
    console.log('URL after clicking detail:', await evaluate('window.location.href'));
    let bodyText = await evaluate('document.body.innerText');
    console.log('Body length:', (bodyText || '').length);
    console.log('Body text snippet:', (bodyText || '').substring(0, 300));

    // Now test Appointments list and detail
    console.log('\nTesting Appointments...');
    await evaluate(`(() => {
      const a = document.querySelector('a[href="/appointments"]');
      if (a) a.click();
    })()`);
    await new Promise(r => setTimeout(r, 1500));
    console.log('Appointments URL:', await evaluate('window.location.href'));

    // Click appointment row or link
    let clickAppt = await evaluate(`(() => {
      const row = document.querySelector('table tbody tr');
      if (row) {
        row.click();
        return 'Clicked appointment row';
      }
      return 'No appointment row found';
    })()`);
    console.log('Click appt result:', clickAppt);
    await new Promise(r => setTimeout(r, 2000));
    console.log('URL after appt click:', await evaluate('window.location.href'));
    bodyText = await evaluate('document.body.innerText');
    console.log('Appt body length:', (bodyText || '').length);

    ws.close();
  } catch (err) {
    console.error(err);
  } finally {
    chrome.kill();
  }
}

run();
