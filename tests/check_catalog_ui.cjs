// Exercise the generated catalog script offline without browser/network access.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

for (const relative of ['output/monsters', 'output/wiz2/monsters', 'output/wiz3/monsters']) {
  const base = path.resolve(__dirname, '..', relative);
  const html = fs.readFileSync(path.join(base, 'index.html'), 'utf8');
  const manifest = JSON.parse(fs.readFileSync(path.join(base, 'monsters.json'), 'utf8'));
  const unescape = s => s.replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  const articles = [...html.matchAll(/<article ([^>]+)>/g)].map(match => ({
    dataset: Object.fromEntries([...match[1].matchAll(/data-([a-z]+)="([^"]*)"/g)].map(m => [m[1], unescape(m[2])])),
    hidden: false,
  }));
  assert.equal(articles.length, manifest.monster_count);
  for (const image of html.matchAll(/<img [^>]*src="([^"]+)"/g)) {
    assert(fs.existsSync(path.join(base, image[1])), image[1]);
  }
  let order = [];
  const control = value => ({ value, events: {}, addEventListener(event, callback) { this.events[event] = callback; } });
  const controls = { '#search': control(''), '#sort': control('id'), '#magic': control('all'), '#count': { textContent: String(articles.length) }, main: { append(article) { order = order.filter(a => a !== article); order.push(article); } } };
  const document = { querySelectorAll: () => articles, querySelector: selector => controls[selector] };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], { document });
  controls['#search'].value = 'ｽﾗｲﾑ';
  controls['#search'].events.input();
  const expectedSlimes = manifest.monsters.filter(m => [m.name_ja, m.unknown_name_ja].some(n => n.includes('スライム'))).length;
  assert.equal(Number(controls['#count'].textContent), expectedSlimes);
  controls['#search'].value = 'THIS_NAME_DOES_NOT_EXIST';
  controls['#search'].events.input();
  assert.equal(Number(controls['#count'].textContent), 0);
  controls['#search'].value = '';
  controls['#magic'].value = '1';
  controls['#sort'].value = 'exp';
  controls['#sort'].events.change();
  const visible = order.filter(a => !a.hidden);
  assert(visible.every(a => a.dataset.magic === '1'));
  assert(visible.every((a, i) => i === 0 || Number(visible[i - 1].dataset.exp) >= Number(a.dataset.exp)));
  controls['#magic'].value = 'all';
  controls['#sort'].value = 'ac';
  controls['#sort'].events.change();
  assert(order.every((a, i) => i === 0 || Number(order[i - 1].dataset.ac) <= Number(a.dataset.ac)));
  assert.equal(Number(controls['#count'].textContent), manifest.monster_count);
  console.log(`${manifest.game}: ${articles.length} HTML records, images, kana search, empty search, magic filter and sorting passed`);
}
