// Offline checks of the generated viewer script; no browser/network access.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
for (const relative of ['output/dungeons', 'output/wiz2/dungeons', 'output/wiz3/dungeons']) {
  const base = path.resolve(__dirname, '..', relative);
  const html = fs.readFileSync(path.join(base, 'index.html'), 'utf8');
  const data = JSON.parse(fs.readFileSync(path.join(base, 'maps.json'), 'utf8'));
  const selection = { id: null, setAttribute() {}, remove() {} };
  const svg = { querySelector: () => selection, append() {} };
  const elements = {};
  const element = id => elements[id] ||= { value: '0', checked: id !== 'area', hidden: false, events: {}, innerHTML: '', textContent: '', classList: { values: new Set(['hide-area']), toggle(name, enabled) { enabled ? this.values.add(name) : this.values.delete(name); } }, addEventListener(name, handler) { this.events[name] = handler; }, querySelector: () => svg };
  const document = { getElementById: element, createElementNS: () => selection };
  const context = vm.createContext({ document });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  assert.equal(element('position').textContent, '階層 1 東0・北0');
  for (let i = 0; i < data.floor_count; i++) {
    element('floor').events.change({ target: { value: String(i) } });
    assert.equal((element('map').innerHTML.match(/data-cell=/g) || []).length, 400);
    vm.runInContext('selectCell(19,19)', context);
    assert.equal(element('position').textContent, `階層 ${i + 1} 東19・北19`);
    assert(fs.existsSync(path.join(base, `floor_${String(i + 1).padStart(2, '0')}.svg`)));
  }
  const jump = data.floors.flatMap((f, i) => f.cells.filter(c => c.event?.destination?.floor > 0).map(c => ({ i, c })))[0];
  assert(jump);
  element('floor').events.change({ target: { value: String(jump.i) } });
  vm.runInContext(`selectCell(${jump.c.x},${jump.c.y})`, context);
  assert.equal(element('destination').hidden, false);
  element('destination').onclick();
  const target = jump.c.event.destination;
  assert.equal(element('position').textContent, `階層 ${target.floor} 東${target.x}・北${target.y}`);
  element('dark').checked = false;
  element('dark').events.change();
  assert(element('map').classList.values.has('hide-dark'));
  element('area').checked = true;
  element('area').events.change();
  assert(!element('map').classList.values.has('hide-area'));
  console.log(`${data.game}: ${data.floor_count} floor SVGs, cell selection, event destinations and layer controls passed`);
}
