// Independent, bounded audit of the supplied pure JavaScript domain core.
// Runs read-only source in a VM without DOM, file-system, network or process APIs.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.join(__dirname, 'ROVER_Real_Hardware_Studio');
const context = vm.createContext({});
vm.runInContext(
  fs.readFileSync(path.join(root, 'src/core.js'), 'utf8') + '\n' +
  fs.readFileSync(path.join(root, 'src/hardware_core.js'), 'utf8'),
  context, { timeout: 2000 }
);
const out = vm.runInContext(`(() => {
  const rows = [];
  for (const profile of ['nx16', 'pi5_8', 'pi5_16']) {
    HW = hardwareDefaults(profile);
    for (const candidate of ['A', 'B0', 'B1', 'B2']) {
      const config = RoverCore.config(candidate);
      const result = RoverCore.checks(config);
      const graph = RoverCore.model(config);
      rows.push({ profile, candidate, power_W: config.power_W,
        runtime_h: result.runtime_h, pass: RoverCore.numericPass(result),
        fails: result.checks.filter(x => x.status === 'FAIL').map(x => x.id),
        graphRequirementIds: graph.nodes.filter(x => x.kind === 'requirement').map(x => x.data.id) });
    }
  }
  HW = hardwareDefaults();
  const original = RoverCore.model(RoverCore.config('A'));
  const changed = RoverCore.clone(original);
  // Deliberate audit input mutation: delete EVERY model relationship.
  changed.edges = [];
  return {
    rows,
    removedEdgesDiff: RoverCore.diff(original, changed),
    deletedAllGraphEdgesStillChecksPass: RoverCore.numericPass(RoverCore.checks(changed.config)),
    noRequirementMatch: RoverCore.retrieve(original, 'R-02').status,
    defaultSysmlHasSubject: /\\bsubject\\b/.test(RoverCore.sysml(RoverCore.config('A'))),
    defaultSysmlHasSatisfy: /\\bsatisfy\\b/.test(RoverCore.sysml(RoverCore.config('A')))
  };
})()`, context, { timeout: 2000 });
const json = JSON.stringify(out, null, 2) + '\n';
fs.writeFileSync(path.join(__dirname, 'independent-core-checks.json'), json);
console.log(json);
