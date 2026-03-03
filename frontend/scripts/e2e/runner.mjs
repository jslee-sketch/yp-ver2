#!/usr/bin/env node
// scripts/e2e/runner.mjs — E2E 500건 테스트 런너
// 사용법:
//   node scripts/e2e/runner.mjs              # 전체 500건
//   node scripts/e2e/runner.mjs 04-deals     # 특정 섹션만
//   node scripts/e2e/runner.mjs 12 13 15     # 여러 섹션 (번호만 가능)

import { printSummary } from './lib/reporter.mjs';

const SECTIONS = [
  { key: '01', name: '01-auth',          file: './sections/01-auth.mjs' },
  { key: '02', name: '02-buyers',        file: './sections/02-buyers.mjs' },
  { key: '03', name: '03-sellers',       file: './sections/03-sellers.mjs' },
  { key: '04', name: '04-deals',         file: './sections/04-deals.mjs' },
  { key: '05', name: '05-participants',  file: './sections/05-participants.mjs' },
  { key: '06', name: '06-offers',        file: './sections/06-offers.mjs' },
  { key: '07', name: '07-reservations',  file: './sections/07-reservations.mjs' },
  { key: '08', name: '08-chat',          file: './sections/08-chat.mjs' },
  { key: '09', name: '09-notifications', file: './sections/09-notifications.mjs' },
  { key: '10', name: '10-points',        file: './sections/10-points.mjs' },
  { key: '11', name: '11-reviews',       file: './sections/11-reviews.mjs' },
  { key: '12', name: '12-ai-pingpong',   file: './sections/12-ai-pingpong.mjs' },
  { key: '13', name: '13-edge-cases',    file: './sections/13-edge-cases.mjs' },
  { key: '14', name: '14-concurrency',   file: './sections/14-concurrency.mjs' },
  { key: '15', name: '15-stress',        file: './sections/15-stress.mjs' },
  { key: '16', name: '16-full-scenario', file: './sections/16-full-scenario.mjs' },
];

// CLI 인자 파싱
const args = process.argv.slice(2);
const filterArgs = args.filter(a => !a.startsWith('--'));
const verbose = args.includes('--verbose');
const failFast = args.includes('--fail-fast');

// 실행할 섹션 필터링
function matchSection(s) {
  if (filterArgs.length === 0) return true;
  return filterArgs.some(arg => {
    const lower = arg.toLowerCase();
    return (
      s.key === arg ||
      s.key === arg.padStart(2, '0') ||
      s.name === lower ||
      s.name.startsWith(lower) ||
      s.name.includes(lower)
    );
  });
}

const selectedSections = SECTIONS.filter(matchSection);

if (selectedSections.length === 0) {
  console.error(`❌ 매칭되는 섹션 없음: ${filterArgs.join(', ')}`);
  console.error(`   사용 가능한 섹션: ${SECTIONS.map(s => s.name).join(', ')}`);
  process.exit(1);
}

// 헤더 출력
const isFullRun = selectedSections.length === SECTIONS.length;
console.log('');
console.log('═'.repeat(70));
if (isFullRun) {
  console.log('  🧪 E2E 500건 전체 테스트 시작');
} else {
  console.log(`  🧪 E2E 테스트 — 섹션 ${selectedSections.length}개`);
  console.log(`     ${selectedSections.map(s => s.name).join(', ')}`);
}
console.log(`  API: ${process.env.API_URL || 'http://127.0.0.1:9000'}`);
console.log(`  시각: ${new Date().toLocaleString('ko-KR')}`);
console.log('═'.repeat(70));
console.log('');

const runnerStart = Date.now();
let sectionErrors = 0;

for (const section of selectedSections) {
  let mod;
  try {
    mod = await import(section.file);
  } catch (e) {
    console.error(`\n❌ [${section.name}] 모듈 로드 실패: ${e.message}`);
    sectionErrors++;
    if (failFast) {
      console.error('--fail-fast 옵션으로 중단합니다.');
      break;
    }
    continue;
  }

  try {
    await mod.run();
  } catch (e) {
    console.error(`\n❌ [${section.name}] 실행 오류: ${e.message}`);
    if (verbose) console.error(e.stack);
    sectionErrors++;
    if (failFast) {
      console.error('--fail-fast 옵션으로 중단합니다.');
      break;
    }
  }
}

const runnerElapsed = Date.now() - runnerStart;

// 최종 요약 출력 + JSON 저장
const summary = printSummary();

console.log('');
console.log('═'.repeat(70));
console.log(`  ⏱  총 소요 시간: ${(runnerElapsed / 1000).toFixed(1)}s`);
if (sectionErrors > 0) {
  console.log(`  ⚠️  섹션 오류: ${sectionErrors}개 (실행 중 예외 발생)`);
}
console.log('═'.repeat(70));
console.log('');

// 종료 코드: 실패 있으면 1
process.exit(summary.failed > 0 || sectionErrors > 0 ? 1 : 0);
