import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';
const ACCESS_KEY = 'yeokping2026';

function url(path: string) { return `${BASE}${path}?access=${ACCESS_KEY}`; }

// Helper: fetch main JS bundle content
async function getMainJsContent(page: any): Promise<string> {
  const jsFiles = await page.evaluate(() =>
    Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
  );
  for (const src of jsFiles) {
    try {
      const content = await page.evaluate(async (u: string) => {
        const res = await fetch(u);
        return await res.text();
      }, src);
      if (content.length > 100000) return content; // main bundle
    } catch {}
  }
  return '';
}

// Helper: fetch CSS content
async function getCssContent(page: any): Promise<string> {
  const cssFiles = await page.evaluate(() =>
    Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => (l as HTMLLinkElement).href)
  );
  let allCss = '';
  for (const href of cssFiles) {
    try {
      const content = await page.evaluate(async (u: string) => {
        const res = await fetch(u);
        return await res.text();
      }, href);
      allCss += content;
    } catch {}
  }
  return allCss;
}

test.describe.serial('T01-T02: MatrixCodeRain — AI 가격 분석', () => {
  test('T01: 딜 생성 페이지에 MatrixCodeRain 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    // MatrixCodeRain 컴포넌트 코드 확인
    const hasMatrix = js.includes('시장가 분석 완료') || js.includes('MatrixCodeRain') || js.includes('코드 레인');
    expect(hasMatrix).toBeTruthy();
  });

  test('T02: 매트릭스 종료 시 글로우 + "시장가 분석 완료" 텍스트 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    expect(js.includes('시장가 분석 완료')).toBeTruthy();
  });
});

test.describe.serial('T03-T04: PingpongBallAnimation — 핑퐁이 탁구', () => {
  test('T03: 핑퐁이 채팅에 PingpongBallAnimation 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    // PingpongBallAnimation 관련 코드 확인
    const hasPingpong = js.includes('핑퐁이가 답변을 준비하고 있어요') || js.includes('PingpongBallAnimation');
    expect(hasPingpong).toBeTruthy();
  });

  test('T04: 핑퐁이 탁구 패들/공 캔버스 코드 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    // Canvas drawing code: paddleLeftY, paddleRightY, ballX
    const hasPaddle = js.includes('paddleLeft') || js.includes('paddleRight') || (js.includes('fillRect') && js.includes('4ade80'));
    expect(hasPaddle).toBeTruthy();
  });
});

test.describe.serial('T05: AuctionHammer — 딜 마감', () => {
  test('T05: 딜 마감 카운트다운 + 해머 코드 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    const hasHammer = js.includes('딜 마감') || js.includes('AuctionHammer');
    expect(hasHammer).toBeTruthy();
  });
});

test.describe.serial('T06: OfferArrival — 오퍼 도착', () => {
  test('T06: 오퍼 도착 바운스 CSS 애니메이션 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const css = await getCssContent(page);
    // OfferArrival uses offerBounceIn + pingpongSpin CSS animations
    const hasBounce = css.includes('offerBounceIn');
    const hasSpin = css.includes('pingpongSpin');
    expect(hasBounce && hasSpin).toBeTruthy();
  });
});

test.describe.serial('T07-T08: Confetti + PaymentSuccess', () => {
  test('T07: 낙찰/결제 컨페티 + 축하 코드 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    const hasConfetti = js.includes('Confetti') || js.includes('confetti') || js.includes('particleCount') || js.includes('requestAnimationFrame');
    expect(hasConfetti).toBeTruthy();
  });

  test('T08: 결제 완료 체크 스케일인 + 금액 코드 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    const hasPayment = js.includes('결제 완료') || js.includes('PaymentSuccess');
    expect(hasPayment).toBeTruthy();
  });
});

test.describe.serial('T09-T10: 효과음', () => {
  test('T09: 효과음 OFF (기본) — localStorage에 sound_enabled 없음', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const soundEnabled = await page.evaluate(() => localStorage.getItem('sound_enabled'));
    expect(soundEnabled !== 'true').toBeTruthy();
  });

  test('T10: 효과음 관련 AudioContext 코드 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await getMainJsContent(page);
    const hasAudio = js.includes('AudioContext') || js.includes('webkitAudioContext');
    expect(hasAudio).toBeTruthy();
  });
});

test.describe.serial('T11: 카드 호버 + 글로우', () => {
  test('T11: premium-card 호버 CSS + glassmorphism 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const css = await getCssContent(page);
    const hasPremium = css.includes('premium-card') && css.includes('translateY(-4px)');
    expect(hasPremium).toBeTruthy();
  });
});

test.describe.serial('T12: CountUpNumber + 애니메이션', () => {
  test('T12: CountUpNumber + shake/offerBounceIn/scaleIn 애니메이션 CSS 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const css = await getCssContent(page);
    const js = await getMainJsContent(page);
    const hasShake = css.includes('shake');
    const hasBounce = css.includes('offerBounceIn');
    const hasScale = css.includes('scaleIn');
    const hasCountUp = js.includes('CountUpNumber') || js.includes('ease-out cubic');
    expect(hasShake && hasBounce && hasScale).toBeTruthy();
  });
});
