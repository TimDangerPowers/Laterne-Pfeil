// node shot.js <port> <ausgabe.png> <query> [breite] [hoehe]
const { chromium } = require('playwright');
const [port, out, qs, w, h] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(w || 900), height: +(h || 1200) }, deviceScaleFactor: 2 });
  p.on('pageerror', (e) => console.log('ERR', e.message));
  await p.goto(`http://127.0.0.1:${port}/quelle/render/view.html?${qs}`);
  await p.waitForFunction('window.READY === true', null, { timeout: 120000 });
  await p.screenshot({ path: out, omitBackground: true });
  await b.close();
})();
