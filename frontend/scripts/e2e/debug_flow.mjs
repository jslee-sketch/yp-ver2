// STEP 0: 전체 플로우 디버그
import { req, login, sellerLogin } from './lib/client.mjs';

const ts = Date.now().toString(36);
console.log('=== Buyer 생성 ===');
const buyerRes = await req('POST', '/buyers/', {
  email: `debug_${ts}@test.com`,
  password: 'Test1234!',
  name: `Dbg${ts}`.slice(0,15),
  nickname: `Dbg${ts}`.slice(0,15),
});
console.log('buyer:', buyerRes.status, JSON.stringify(buyerRes.data).slice(0,150));
const buyerId = buyerRes.data?.id;

console.log('\n=== Buyer 로그인 ===');
const loginRes = await login(`debug_${ts}@test.com`, 'Test1234!');
console.log('login:', loginRes.status, !!loginRes.data?.access_token);
const token = loginRes.data?.access_token;

console.log('\n=== 딜 생성 (creator_id) ===');
const dealRes = await req('POST', '/deals/', {
  creator_id: buyerId,
  product_name: '디버그딜',
  desired_qty: 50,
  target_price: 100000,
}, token);
console.log('deal:', dealRes.status, JSON.stringify(dealRes.data).slice(0,200));

console.log('\n=== DealCreate 필수 필드 확인 ===');
const spec = await req('GET', '/openapi.json');
for (const [k, v] of Object.entries(spec.data.components?.schemas || {})) {
  if (k.toLowerCase().includes('deal') && k.toLowerCase().includes('create')) {
    console.log(k, 'required:', JSON.stringify(v.required));
    console.log('properties:', Object.keys(v.properties || {}).join(', '));
    break;
  }
}

console.log('\n=== Seller 생성 ===');
const biz = `DS${ts}`.slice(0,15);
const sRes = await req('POST', '/sellers/', {
  email: `debug_s_${ts}@test.com`, password: 'Test1234!',
  business_name: biz, nickname: biz,
  business_number: '321-45-11111',
  phone: '010-0000-0001', address: '서울시', zip_code: '12345',
  established_date: '2020-01-01T00:00:00',
});
console.log('seller:', sRes.status, sRes.data?.id ? 'id='+sRes.data.id : JSON.stringify(sRes.data).slice(0,150));
const sellerId = sRes.data?.id;

if (sellerId) {
  await req('POST', `/sellers/${sellerId}/approve`);
  const sl = await sellerLogin(`debug_s_${ts}@test.com`, 'Test1234!');
  console.log('seller login:', sl.status, !!sl.data?.access_token);
  const sellerToken = sl.data?.access_token;
  const dealId = dealRes.data?.id;

  if (dealId && sellerId) {
    console.log('\n=== 오퍼 생성 ===');
    const offerRes = await req('POST', '/offers', {
      deal_id: dealId, seller_id: sellerId,
      price: 90000, total_available_qty: 10,
      shipping_mode: 'INCLUDED',
    }, sellerToken);
    console.log('offer:', offerRes.status, JSON.stringify(offerRes.data).slice(0,200));
  }
}

console.log('\n=== 최종 결과 ===');
console.log('buyer:', buyerRes.ok ? 'OK' : `FAIL(${buyerRes.status}) ${buyerRes.data?.detail||''}`);
console.log('login:', loginRes.ok ? 'OK' : `FAIL(${loginRes.status})`);
console.log('deal:', dealRes.ok ? 'OK(id='+dealRes.data?.id+')' : `FAIL(${dealRes.status}) ${dealRes.data?.detail||JSON.stringify(dealRes.data).slice(0,100)}`);
console.log('seller:', sRes.ok ? 'OK(id='+sRes.data?.id+')' : `FAIL(${sRes.status}) ${sRes.data?.detail||''}`);
