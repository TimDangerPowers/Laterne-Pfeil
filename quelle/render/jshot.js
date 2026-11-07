// node jshot.js out.png "query" [w] [h]
const { chromium } = require('playwright');
const [out, qs, w, h] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(w || 1200), height: +(h || 800) }, deviceScaleFactor: 2 });
  p.on('pageerror', (e) => console.log('ERR', e.message));
  await p.goto(`http://127.0.0.1:8781/quelle/render/jaeger.html?${qs}`);
  await p.waitForFunction('window.READY === true', null, { timeout: 180000 });
  await p.screenshot({ path: out, omitBackground: true }); await b.close();
})();
