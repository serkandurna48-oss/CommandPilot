// Focused offline regression checks; run: node scripts/test_frontend_load_errors.cjs
// Uses installed frontend dependencies. Hooks and API calls are simulated;
// this checks component output/handlers, not browser rendering or React scheduling.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const { test } = require('node:test');
const frontend = path.resolve(__dirname, '../frontend');
const requireFrontend = createRequire(path.join(frontend, 'package.json'));
const ts = requireFrontend('typescript');
const React = requireFrontend('react');
const { renderToStaticMarkup } = requireFrontend('react-dom/server');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

function mount(file, name, api, props = {}, overrides = {}) {
  let cursor = 0;
  const slots = [];
  const effects = [];
  const hooks = {
    ...React,
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = initial;
      return [slots[index], value => {
        slots[index] = typeof value === 'function' ? value(slots[index]) : value;
      }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useCallback: fn => fn,
    useMemo: fn => fn(),
    useEffect: fn => { effects.push(fn); },
  };
  const stub = ({ children }) => React.createElement('div', null, children);
  const imports = new Proxy({}, { get: () => stub });
  const module = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(path.join(frontend, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(source, {
    module, exports: module.exports, Error,
    localStorage: { getItem: () => null },
    require(id) {
      if (id in overrides) return overrides[id];
      if (id === 'react') return hooks;
      if (id === 'react/jsx-runtime') return requireFrontend(id);
      if (id === '@/lib/api') return { api };
      if (id === '@/lib/i18n') return { useT: () => key => key };
      if (id === '@/lib/utils') return { cn: () => '', formatDateShort: String, formatDate: String };
      if (id === '@/lib/workOrderMapper') return { mapWorkOrderFromApi: value => value };
      return imports;
    },
  }, { filename: file });
  function render() {
    cursor = 0;
    effects.length = 0;
    return module.exports[name](props);
  }
  render();
  const effect = effects[0];
  let cleanup = effect?.();
  return {
    render,
    html: () => renderToStaticMarkup(render()),
    replayEffect() { cleanup?.(); cleanup = effect(); },
    unmount() { cleanup?.(); },
  };
}

test('HomeBriefing: even blank plan/order errors override cached data and provide retry', () => {
  const component = mount('components/dashboard/HomeBriefing.tsx', 'HomeBriefing', {}, {
    plan: { main_win: 'Outdated plan' }, planError: '', ordersError: '',
    needsDecision: [], inProgress: [], activity: [], projects: [], projectsError: null,
    onRetryPlan() {}, onRetryOrders() {}, onRetryProjects() {}, onRequeue() {},
  });
  const html = component.html();
  assert.equal((html.match(/error.load_failed/g) || []).length, 4);
  assert.equal((html.match(/button.retry/g) || []).length, 4);
  assert.doesNotMatch(html, /Outdated plan/);
});

function dashboard(api, observeContext = () => {}) {
  return mount('app/(app)/dashboard/page.tsx', 'default', api, {}, {
    '@/lib/jarvisContext': { useSetJarvisContext: observeContext },
    '@/components/dashboard/HomeBriefing': { HomeBriefing: () => null, buildActivity: () => [] },
  });
}

test('Dashboard: failed reads must not tell Jarvis there are zero records or no plan', async () => {
  let context;
  const fail = () => Promise.reject(new Error(''));
  const component = dashboard({
    plans: { listMine: fail }, workOrders: { listMine: fail }, projects: { listMine: fail },
  }, value => { context = value; });
  assert.ok(context.snapshot.every(field => field.value === 'common.loading'));
  await settle();
  component.render();
  assert.ok(context.snapshot.every(field => field.value === 'error.load_failed'));
  for (const action of context.quickActions.slice(0, 3)) {
    assert.match(action.prompt, /could not verify/);
    assert.doesNotMatch(action.prompt, /No plan has been generated|currently have 0|0 work order/);
  }
  component.unmount();
});

test('Dashboard: successful empty reload clears previously loaded plan', async () => {
  let calls = 0;
  const component = dashboard({
    plans: { listMine: async () => ++calls === 1 ? [{ main_win: 'Old plan' }] : [] },
    workOrders: { listMine: async () => [] }, projects: { listMine: async () => [] },
  });
  await settle();
  assert.equal(component.render().props.plan.main_win, 'Old plan');
  await component.render().props.onRetryPlan();
  assert.equal(component.render().props.plan, null);
  assert.equal(component.render().props.planError, null);
  component.unmount();
});

test('Dashboard: cleaned-up request cannot overwrite the latest successful snapshot', async () => {
  const first = deferred();
  let calls = 0;
  const component = dashboard({
    plans: { listMine: () => ++calls === 1 ? first.promise : Promise.resolve([{ main_win: 'Current plan' }]) },
    workOrders: { listMine: async () => [] }, projects: { listMine: async () => [] },
  });
  component.replayEffect();
  await settle();
  first.resolve([{ main_win: 'Old plan' }]);
  await settle();
  assert.equal(component.render().props.plan.main_win, 'Current plan');
  component.unmount();
});

test('ProjectCards: empty error text still shows failure and retry', () => {
  const component = mount('components/dashboard/ProjectCards.tsx', 'ProjectCards', {}, {
    projects: [], loadError: '', onRetry() {},
  });
  assert.match(component.html(), /dashboard.project_cards.load_error/);
  assert.ok(retryButton(component.render()));
});

function buttonWithLabel(tree, label) {
  if (!tree || typeof tree !== 'object') return null;
  if (tree.props?.onClick && React.Children.toArray(tree.props.children).includes(label)) return tree;
  for (const child of React.Children.toArray(tree.props?.children)) {
    const found = buttonWithLabel(child, label);
    if (found) return found;
  }
  return null;
}
const retryButton = tree => buttonWithLabel(tree, 'button.retry');

test('LifecycleControls: review-ready Accept invokes the accepted transition', async () => {
  const transitions = [];
  const component = mount('components/operator/LifecycleControls.tsx', 'LifecycleControls', {}, {
    status: 'review_ready', isLive: true, onStatusChange: async status => { transitions.push(status); },
  });
  const accept = buttonWithLabel(component.render(), 'operator.lifecycle.accept');
  assert.ok(accept);
  assert.equal(accept.props.disabled, false);
  await accept.props.onClick();
  assert.deepEqual(transitions, ['accepted']);
});

test('LifecycleControls: failed Accept stays visible and is retryable', async () => {
  let calls = 0;
  const component = mount('components/operator/LifecycleControls.tsx', 'LifecycleControls', {}, {
    status: 'review_ready', isLive: true,
    onStatusChange: async () => { if (++calls === 1) throw new Error('Accept unavailable'); },
  });
  await buttonWithLabel(component.render(), 'operator.lifecycle.accept').props.onClick();
  assert.match(component.html(), /Accept unavailable/);
  const accept = buttonWithLabel(component.render(), 'operator.lifecycle.accept');
  assert.equal(accept.props.disabled, false);
  await accept.props.onClick();
  assert.equal(calls, 2);
  assert.doesNotMatch(component.html(), /Accept unavailable/);
});

test('LifecycleControls: running exposes Stop but no manual result or Accept transition', () => {
  const component = mount('components/operator/LifecycleControls.tsx', 'LifecycleControls', {}, {
    status: 'running', isLive: true, onStatusChange() {},
  });
  assert.ok(buttonWithLabel(component.render(), 'operator.lifecycle.stop'));
  assert.equal(buttonWithLabel(component.render(), 'operator.lifecycle.accept'), null);
  assert.doesNotMatch(component.html(), /operator.lifecycle.accept|review_ready/);
});

const cases = [
  ['morning/CheckinHistory', 'checkins', 'listMine'],
  ['morning/PlanHistory', 'plans', 'listMine'],
  ['review/ReviewHistory', 'reviews', 'listMine'],
  ['jarvis/JarvisDecisionHistory', 'jarvis', 'listDecisions'],
  ['rules/RulesManager', 'rules', 'listMine'],
  ['operator/OperatorManager', 'workOrders', 'listMine'],
];

for (const [file, group, method] of cases) {
  const name = file.split('/').at(-1);
  const empty = group === 'jarvis' ? { decisions: [] } : [];
  test(`${name}: retry restores returned records, not only an empty success`, async () => {
    const row = {
      id: 'offline-record', title: 'Restored record', main_win: 'Restored record',
      mood: 'Restored record', biggest_win: 'Restored record', rule_text: 'Real rule',
      is_active: true, status: 'draft', decision: 'confirmed', work_order_id: 'offline-order',
      created_at: '2026-09-24', plan_date: '2026-09-24', repo: 'offline-repo',
      goal: 'Real goal', timeLimitMinutes: 15,
    };
    const data = group === 'jarvis' ? { decisions: [row] } : [row];
    let calls = 0;
    const component = mount(`components/${file}.tsx`, name, {
      [group]: { [method]: () => ++calls === 1 ? Promise.reject(new Error('Offline')) : Promise.resolve(data) },
    });
    await settle();
    await retryButton(component.render()).props.onClick();
    await settle();
    assert.match(component.html(), /Restored record/);
    assert.doesNotMatch(component.html(), /error.load_failed/);
    component.unmount();
  });
  for (const message of ['Network unavailable', '']) {
    test(`${name}: rejected fetch (${JSON.stringify(message)}) stays visible and retry recovers`, async () => {
      let calls = 0;
      const component = mount(`components/${file}.tsx`, name, {
        [group]: { [method]: () => ++calls === 1 ? Promise.reject(new Error(message)) : Promise.resolve(empty) },
      });
      await settle();
      assert.match(component.html(), /error.load_failed/);
      const retry = retryButton(component.render());
      assert.ok(retry, 'error must offer a retry');
      await retry.props.onClick();
      await settle();
      assert.equal(calls, 2);
      assert.doesNotMatch(component.html(), /error.load_failed|button.retry/);
      component.unmount();
    });
  }
  test(`${name}: late response from cleaned-up effect cannot overwrite the next request`, async () => {
    const first = deferred();
    const second = deferred();
    let calls = 0;
    const component = mount(`components/${file}.tsx`, name, {
      [group]: { [method]: () => ++calls === 1 ? first.promise : second.promise },
    });
    component.replayEffect();
    second.resolve(empty);
    await settle();
    first.reject(new Error('Obsolete request'));
    await settle();
    assert.doesNotMatch(component.html(), /error.load_failed|Obsolete request/);
    component.unmount();
  });
}
