// scripts/e2e/lib/reporter.mjs
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const allResults = [];
let currentSection = '';

export function setSection(name) { currentSection = name; }

export function record(id, name, pass, detail = '', elapsed = 0) {
  const r = { id, section: currentSection, name, pass, detail, elapsed };
  allResults.push(r);
  const icon = pass ? '  ✅' : '  ❌';
  const ms = elapsed ? ` (${elapsed}ms)` : '';
  console.log(`${icon} [${id}] ${name}${ms}${detail ? ' — ' + detail : ''}`);
}

export function expect(testId, testName, condition, detail = '', elapsed = 0) {
  record(testId, testName, !!condition, detail, elapsed);
  return !!condition;
}

export function printSummary() {
  const sections = [...new Set(allResults.map(r => r.section))];
  console.log('\n' + '═'.repeat(70));
  console.log('  E2E 테스트 결과 요약');
  console.log('═'.repeat(70));

  let totalPass = 0, totalFail = 0;
  for (const sec of sections) {
    const items = allResults.filter(r => r.section === sec);
    const pass = items.filter(r => r.pass).length;
    const fail = items.filter(r => !r.pass).length;
    totalPass += pass;
    totalFail += fail;
    const icon = fail === 0 ? '✅' : '⚠️';
    console.log(`\n${icon} ${sec}: ${pass}/${items.length} 성공 (${fail}건 실패)`);
    if (fail > 0) {
      items.filter(r => !r.pass).forEach(r => {
        console.log(`     ❌ [${r.id}] ${r.name}: ${r.detail}`);
      });
    }
  }

  console.log('\n' + '─'.repeat(70));
  console.log(`  ✅ 성공: ${totalPass}건`);
  console.log(`  ❌ 실패: ${totalFail}건`);
  console.log(`  📊 총계: ${allResults.length}건`);
  const rate = allResults.length > 0 ? (totalPass / allResults.length * 100).toFixed(1) : '0.0';
  console.log(`  📈 성공률: ${rate}%`);

  const withElapsed = allResults.filter(r => r.elapsed > 0);
  if (withElapsed.length > 0) {
    const avgElapsed = withElapsed.reduce((s, r) => s + r.elapsed, 0) / withElapsed.length;
    console.log(`  ⏱️  평균 응답: ${avgElapsed.toFixed(0)}ms`);
    const slowest = [...withElapsed].sort((a, b) => b.elapsed - a.elapsed).slice(0, 5);
    console.log(`\n  🐢 가장 느린 API TOP 5:`);
    slowest.forEach(r => console.log(`     ${r.elapsed}ms — [${r.id}] ${r.name}`));
  }
  console.log('═'.repeat(70));

  try {
    const resultsDir = join(__dirname, '..', 'results');
    mkdirSync(resultsDir, { recursive: true });
    const filename = `e2e_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    writeFileSync(join(resultsDir, filename), JSON.stringify({
      timestamp: new Date().toISOString(),
      total: allResults.length,
      passed: totalPass,
      failed: totalFail,
      rate: rate + '%',
      results: allResults,
    }, null, 2));
    console.log(`\n📁 결과 저장: scripts/e2e/results/${filename}`);
  } catch {}

  return { total: allResults.length, passed: totalPass, failed: totalFail };
}

export function getResults() { return allResults; }
