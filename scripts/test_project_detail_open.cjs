const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("../frontend/node_modules/typescript");

const source = fs.readFileSync(
  path.join(__dirname, "../frontend/lib/projectDetailNavigation.ts"),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const moduleUnderTest = { exports: {} };
new Function("exports", "module", compiled)(moduleUnderTest.exports, moduleUnderTest);
const { revealProjectDetail } = moduleUnderTest.exports;

test("reveals the selected project detail in the stacked mobile layout", () => {
  const calls = [];
  revealProjectDetail({ scrollIntoView: (options) => calls.push(options) }, true);
  assert.deepEqual(calls, [{ block: "start", behavior: "smooth" }]);
});

test("keeps the desktop side-by-side layout in place", () => {
  let scrolled = false;
  revealProjectDetail({ scrollIntoView: () => { scrolled = true; } }, false);
  assert.equal(scrolled, false);
});

test("handles a missing detail element while projects load", () => {
  assert.doesNotThrow(() => revealProjectDetail(null, true));
});

test("the project selection effect reveals the actual detail panel", () => {
  const manager = fs.readFileSync(
    path.join(__dirname, "../frontend/components/projects/ProjectsManager.tsx"),
    "utf8",
  );
  assert.match(manager, /ref=\{detailRef\}/);
  assert.match(manager, /revealProjectDetail\(detailRef\.current, window\.matchMedia/);
});
