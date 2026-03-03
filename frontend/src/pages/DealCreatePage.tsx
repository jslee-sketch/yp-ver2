import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { aiDealHelper } from '../api/aiApi';
import { FEATURES } from '../config';
import { showToast } from '../components/common/Toast';

// ── 디자인 토큰 ──────────────────────────────────────────
const C = {
  bgDeep:   '#0a0e1a',
  bgCard:   '#111827',
  bgSurface:'#1a2236',
  bgInput:  '#0f1625',
  cyan:     '#00f0ff',
  magenta:  '#ff2d78',
  green:    '#39ff14',
  yellow:   '#ffe156',
  orange:   '#ff8c42',
  purple:   '#a855f7',
  textPri:  '#f0f4ff',
  textSec:  '#8892a8',
  textDim:  '#4a5568',
  border:   'rgba(0,240,255,0.12)',
};

// ── 모델 선택 타입 ────────────────────────────────────────
interface ModelOption {
  name: string;     // "에어팟 프로 2세대"
  subtitle: string; // "ANC, USB-C"
  emoji: string;    // "🎧"
}

// ── AI Mock 동적 생성 ────────────────────────────────────
type AIResult = {
  canonical_name: string;
  model_name: string;
  normalized_free_text: string | null;
  suggested_options: { title: string; selected_value?: string | null; values: string[] }[];
  price: {
    center_price: number | null;
    desired_price_suggestion: number | null;
    max_budget_suggestion: number | null;
    commentary: string | null;
    price_source?: string | null;
  };
  category?: string | null;
  warnings?: string[];
};

function generateMockAIResult(productName: string, freeText: string): AIResult {
  const name = (productName + ' ' + freeText).toLowerCase();

  // ── 에어팟 (구체적 → 일반 순) ──
  if (name.includes('에어팟 맥스') || name.includes('airpods max')) {
    return {
      canonical_name: 'Apple AirPods Max (USB-C)',
      model_name: '에어팟 맥스',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['미드나이트', '스타라이트', '블루', '오렌지', '퍼플'] },
      ],
      price: { center_price: 769000, desired_price_suggestion: 650000, max_budget_suggestion: 720000,
        commentary: 'Apple 공식가 769,000원입니다. 공동구매 시 650,000~720,000원이 현실적이에요.' },
    };
  }
  if (name.includes('에어팟 4') || name.includes('에어팟4') || name.includes('airpods 4')) {
    return {
      canonical_name: 'Apple AirPods 4th Gen',
      model_name: '에어팟 4세대',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '충전 방식', values: ['USB-C'] },
        { title: '각인', values: ['없음', '있음'] },
      ],
      price: { center_price: 199000, desired_price_suggestion: 169000, max_budget_suggestion: 189000,
        commentary: 'Apple 공식가 199,000원입니다. 공동구매 시 169,000~189,000원이 현실적이에요.' },
    };
  }
  if (name.includes('에어팟') || name.includes('airpod')) {
    return {
      canonical_name: 'Apple AirPods Pro 2nd Gen (USB-C)',
      model_name: '에어팟 프로 2세대 (USB-C)',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',     values: ['화이트'] },
        { title: '충전 방식', values: ['USB-C', 'Lightning'] },
        { title: '각인',     values: ['없음', '있음'] },
      ],
      price: { center_price: 339000, desired_price_suggestion: 289000, max_budget_suggestion: 319000,
        commentary: '네이버 최저가 기준 약 339,000원입니다. 공동구매 시 289,000~319,000원이 현실적이에요.' },
    };
  }

  // ── 아이폰 (Pro Max → Pro → 일반 순) ──
  if (name.includes('iphone 16 pro max') || name.includes('16 pro max')
      || name.includes('아이폰 16 프로 맥스') || name.includes('아이폰16 프로맥스')) {
    return {
      canonical_name: 'Apple iPhone 16 Pro Max 256GB',
      model_name: 'iPhone 16 Pro Max',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['블랙 티타늄', '내추럴 티타늄', '화이트 티타늄', '데저트 티타늄'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
        { title: '통신사',  values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1900000, desired_price_suggestion: 1650000, max_budget_suggestion: 1800000,
        commentary: '자급제 기준 1,900,000원입니다. 공동구매 시 1,650,000~1,800,000원이 현실적이에요.' },
    };
  }
  if (name.includes('iphone 16 pro') || name.includes('16 pro')
      || name.includes('아이폰 16 프로') || name.includes('아이폰16 프로')) {
    return {
      canonical_name: 'Apple iPhone 16 Pro 256GB',
      model_name: 'iPhone 16 Pro',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['블랙 티타늄', '내추럴 티타늄', '화이트 티타늄', '데저트 티타늄'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
        { title: '통신사',  values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1550000, desired_price_suggestion: 1350000, max_budget_suggestion: 1480000,
        commentary: '자급제 기준 1,550,000원입니다. 공동구매 시 1,350,000~1,480,000원이 현실적이에요.' },
    };
  }
  if (name.includes('아이폰') || name.includes('iphone')) {
    return {
      canonical_name: 'Apple iPhone 16 128GB',
      model_name: 'iPhone 16',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['울트라마린', '핑크', '화이트', '블랙', '틸'] },
        { title: '저장 용량', values: ['128GB', '256GB', '512GB'] },
        { title: '통신사',  values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1250000, desired_price_suggestion: 1080000, max_budget_suggestion: 1180000,
        commentary: '자급제 기준 1,250,000원입니다. 공동구매 시 1,080,000~1,180,000원이 현실적이에요.' },
    };
  }

  // ── 갤럭시 ──
  if (name.includes('갤럭시') || name.includes('galaxy')) {
    return {
      canonical_name: 'Samsung Galaxy S25 Ultra 256GB',
      model_name: '갤럭시 S25 울트라',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',   values: ['티타늄 블랙', '티타늄 그레이', '티타늄 블루', '티타늄 실버'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
        { title: '통신사', values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1698000, desired_price_suggestion: 1450000, max_budget_suggestion: 1590000,
        commentary: '자급제 기준 약 1,698,000원입니다. 공동구매 시 1,450,000~1,590,000원이 현실적이에요.' },
    };
  }

  // ── 아이패드 ──
  if (name.includes('아이패드') || name.includes('ipad')) {
    return {
      canonical_name: 'Apple iPad mini 7th Gen WiFi 128GB',
      model_name: '아이패드 미니 7세대',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',   values: ['스페이스 그레이', '스타라이트', '퍼플', '블루'] },
        { title: '저장 용량', values: ['128GB', '256GB'] },
        { title: '연결',   values: ['WiFi', 'WiFi + Cellular'] },
      ],
      price: { center_price: 749000, desired_price_suggestion: 650000, max_budget_suggestion: 710000,
        commentary: 'Apple 공식가 기준 749,000원입니다. 공동구매 시 650,000~710,000원이 현실적이에요.' },
    };
  }

  // ── 다이슨 ──
  if (name.includes('다이슨') || name.includes('dyson')) {
    return {
      canonical_name: 'Dyson Airwrap Multi-Styler Complete Long',
      model_name: '다이슨 에어랩 멀티 스타일러 컴플리트 롱',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '모델', values: ['컴플리트 롱', '컴플리트', '오리진'] },
        { title: '색상', values: ['니켈/코퍼', '블루/블러시', '핑크/로즈'] },
      ],
      price: { center_price: 699000, desired_price_suggestion: 580000, max_budget_suggestion: 650000,
        commentary: '다이슨 공식가 699,000원입니다. 공동구매 시 580,000~650,000원이 현실적이에요.' },
    };
  }

  // ── 나이키 ──
  if (name.includes('나이키') || name.includes('nike') || name.includes('에어맥스')) {
    return {
      canonical_name: 'Nike Air Max 97 Silver Bullet',
      model_name: '나이키 에어맥스 97 실버 불렛',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '사이즈', values: ['250', '260', '270', '280', '290'] },
        { title: '색상',   values: ['실버 불렛', '블랙', '화이트'] },
      ],
      price: { center_price: 219000, desired_price_suggestion: 179000, max_budget_suggestion: 199000,
        commentary: '나이키 공식가 219,000원입니다. 공동구매 시 179,000~199,000원이 현실적이에요.' },
    };
  }

  // ── PS5 ──
  if (name.includes('ps5') || name.includes('플스') || name.includes('플레이스테이션')) {
    return {
      canonical_name: 'Sony PlayStation 5 Pro Digital Edition',
      model_name: 'PS5 프로 디지털 에디션',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '에디션',   values: ['디지털 에디션', '디스크 에디션'] },
        { title: '저장 용량', values: ['1TB', '2TB'] },
      ],
      price: { center_price: 798000, desired_price_suggestion: 690000, max_budget_suggestion: 750000,
        commentary: 'Sony 공식가 798,000원입니다. 공동구매 시 690,000~750,000원이 현실적이에요.' },
    };
  }

  // ── 김치 브랜드 (구체적 → 일반 순) ──
  if (name.includes('종가집')) {
    return {
      canonical_name: '종가집 포기김치',
      model_name: '종가집 포기김치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '종류', values: ['포기김치', '맛김치', '총각김치', '깍두기', '열무김치'] },
        { title: '중량', values: ['1kg', '3kg', '5kg', '10kg'] },
        { title: '포장', values: ['일반', '선물세트'] },
      ],
      price: { center_price: 35000, desired_price_suggestion: 28000, max_budget_suggestion: 32000,
        commentary: '3kg 기준 약 35,000원입니다. 공동구매 시 28,000~32,000원이 현실적이에요.' },
    };
  }
  if (name.includes('비비고')) {
    return {
      canonical_name: '비비고 김치',
      model_name: '비비고 김치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '종류', values: ['포기김치', '맛김치', '총각김치', '깍두기'] },
        { title: '중량', values: ['1kg', '1.8kg', '3.3kg'] },
      ],
      price: { center_price: 29000, desired_price_suggestion: 23000, max_budget_suggestion: 27000,
        commentary: '1.8kg 기준 약 29,000원입니다. 공동구매 시 23,000~27,000원이 현실적이에요.' },
    };
  }
  if (name.includes('처갓집')) {
    return {
      canonical_name: '처갓집 양념김치',
      model_name: '처갓집 양념김치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '종류', values: ['포기김치', '맛김치', '열무김치'] },
        { title: '중량', values: ['1kg', '3kg', '5kg'] },
      ],
      price: { center_price: 27000, desired_price_suggestion: 22000, max_budget_suggestion: 25000,
        commentary: '3kg 기준 약 27,000원입니다. 공동구매 시 22,000~25,000원이 현실적이에요.' },
    };
  }
  if (name.includes('피코크')) {
    return {
      canonical_name: '피코크 김치',
      model_name: '피코크 김치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '종류', values: ['포기김치', '맛김치'] },
        { title: '중량', values: ['1kg', '2kg', '5kg'] },
        { title: '포장', values: ['일반', '프리미엄 패키지'] },
      ],
      price: { center_price: 32000, desired_price_suggestion: 25000, max_budget_suggestion: 29000,
        commentary: '2kg 기준 약 32,000원입니다. 공동구매 시 25,000~29,000원이 현실적이에요.' },
    };
  }

  // ── 맥북 (구체적 → 일반 순) ──
  if (name.includes('맥북 에어') || name.includes('macbook air')) {
    return {
      canonical_name: 'Apple MacBook Air M4 13-inch 256GB',
      model_name: '맥북 에어 M4 13인치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['미드나이트', '스타라이트', '실버', '스페이스 그레이'] },
        { title: '메모리',  values: ['16GB', '24GB'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
      ],
      price: { center_price: 1590000, desired_price_suggestion: 1390000, max_budget_suggestion: 1500000,
        commentary: 'Apple 공식가 1,590,000원입니다. 공동구매 시 1,390,000~1,500,000원이 현실적이에요.' },
    };
  }
  if (name.includes('맥북 프로') || name.includes('macbook pro')) {
    return {
      canonical_name: 'Apple MacBook Pro M4 Pro 14-inch 24GB/512GB',
      model_name: '맥북 프로 M4 Pro 14인치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['스페이스 블랙', '실버'] },
        { title: '메모리',  values: ['24GB', '48GB'] },
        { title: '저장 용량', values: ['512GB', '1TB', '2TB'] },
      ],
      price: { center_price: 2990000, desired_price_suggestion: 2650000, max_budget_suggestion: 2850000,
        commentary: 'Apple 공식가 2,990,000원입니다. 공동구매 시 2,650,000~2,850,000원이 현실적이에요.' },
    };
  }
  if (name.includes('맥북') || name.includes('macbook')) {
    return {
      canonical_name: 'Apple MacBook Air M4 13-inch 256GB',
      model_name: '맥북 에어 M4 13인치',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상',    values: ['미드나이트', '스타라이트', '실버', '스페이스 그레이'] },
        { title: '메모리',  values: ['16GB', '24GB'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
      ],
      price: { center_price: 1590000, desired_price_suggestion: 1390000, max_budget_suggestion: 1500000,
        commentary: 'Apple 공식가 1,590,000원입니다. 공동구매 시 1,390,000~1,500,000원이 현실적이에요.' },
    };
  }

  // 기본
  return {
    canonical_name: productName,
    model_name: productName,
    normalized_free_text: freeText || null,
    suggested_options: [{ title: '옵션 1', values: ['기본'] }],
    price: { center_price: 100000, desired_price_suggestion: 85000, max_budget_suggestion: 95000,
      commentary: '정확한 시장가 정보가 부족해요. AI 연동 후 자동으로 업데이트됩니다.' },
  };
}

// ── 색상 키워드 매핑 ──────────────────────────────────────
const COLOR_KEYWORDS: Record<string, string> = {
  '빨간': '레드', '빨강': '레드', '레드': '레드', 'red': '레드',
  '검정': '블랙', '검은': '블랙', '블랙': '블랙', 'black': '블랙',
  '파란': '블루', '파랑': '블루', '블루': '블루', 'blue': '블루',
  '핑크': '핑크', '분홍': '핑크', 'pink': '핑크',
  '실버': '실버', '은색': '실버', 'silver': '실버',
  '골드': '골드', '금색': '골드', 'gold': '골드',
  '그린': '그린', '초록': '그린', 'green': '그린',
  '퍼플': '퍼플', '보라': '퍼플', 'purple': '퍼플',
};

// ── freeText 색상 경고 생성 ───────────────────────────────
function applyWarnings(result: AIResult, freeText: string): AIResult {
  if (!freeText) return result;
  const combined = freeText.toLowerCase();
  const warnings: string[] = [];
  for (const [keyword, colorName] of Object.entries(COLOR_KEYWORDS)) {
    if (combined.includes(keyword)) {
      const colorOpt = result.suggested_options.find(o => o.title === '색상');
      if (colorOpt) {
        const found = colorOpt.values.find(v =>
          v.toLowerCase().includes(colorName.toLowerCase()) ||
          colorName.toLowerCase().includes(v.toLowerCase())
        );
        if (!found) {
          warnings.push(
            `${result.model_name}은(는) 현재 '${colorName}' 색상이 출시되지 않았어요. 가능한 색상: ${colorOpt.values.join(', ')}`
          );
        }
      }
      break;
    }
  }
  if (warnings.length > 0) return { ...result, warnings };
  return result;
}

// ── 모호한 상품 데이터 ────────────────────────────────────
const AMBIGUOUS_PRODUCTS: Record<string, ModelOption[]> = {
  '에어팟': [
    { name: '에어팟 4세대',    subtitle: '오픈형, USB-C',    emoji: '🎧' },
    { name: '에어팟 프로 2세대', subtitle: 'ANC, USB-C',    emoji: '🎧' },
    { name: '에어팟 맥스',     subtitle: '오버이어, 하이파이', emoji: '🎧' },
  ],
  'airpod': [
    { name: '에어팟 4세대',    subtitle: '오픈형, USB-C',    emoji: '🎧' },
    { name: '에어팟 프로 2세대', subtitle: 'ANC, USB-C',    emoji: '🎧' },
    { name: '에어팟 맥스',     subtitle: '오버이어, 하이파이', emoji: '🎧' },
  ],
  '갤럭시': [
    { name: '갤럭시 S25',         subtitle: '6.2인치, 기본',       emoji: '📱' },
    { name: '갤럭시 S25+',        subtitle: '6.7인치, 대화면',     emoji: '📱' },
    { name: '갤럭시 S25 울트라',  subtitle: '6.9인치, S펜, 최상위', emoji: '📱' },
    { name: '갤럭시 Z 폴드6',     subtitle: '폴더블',              emoji: '📱' },
    { name: '갤럭시 Z 플립6',     subtitle: '플립형',              emoji: '📱' },
  ],
  'galaxy': [
    { name: '갤럭시 S25',         subtitle: '6.2인치, 기본',       emoji: '📱' },
    { name: '갤럭시 S25+',        subtitle: '6.7인치, 대화면',     emoji: '📱' },
    { name: '갤럭시 S25 울트라',  subtitle: '6.9인치, S펜, 최상위', emoji: '📱' },
    { name: '갤럭시 Z 폴드6',     subtitle: '폴더블',              emoji: '📱' },
    { name: '갤럭시 Z 플립6',     subtitle: '플립형',              emoji: '📱' },
  ],
  '아이패드': [
    { name: '아이패드 미니 7세대', subtitle: '8.3인치, 휴대성',  emoji: '📋' },
    { name: '아이패드 에어 M3',   subtitle: '11/13인치, 중급',  emoji: '📋' },
    { name: '아이패드 프로 M4',   subtitle: '11/13인치, 최상위', emoji: '📋' },
  ],
  'ipad': [
    { name: '아이패드 미니 7세대', subtitle: '8.3인치, 휴대성',  emoji: '📋' },
    { name: '아이패드 에어 M3',   subtitle: '11/13인치, 중급',  emoji: '📋' },
    { name: '아이패드 프로 M4',   subtitle: '11/13인치, 최상위', emoji: '📋' },
  ],
  '다이슨': [
    { name: '다이슨 에어랩 멀티 스타일러', subtitle: '헤어 스타일링',  emoji: '💨' },
    { name: '다이슨 슈퍼소닉',           subtitle: '헤어 드라이어',  emoji: '💨' },
    { name: '다이슨 V15',               subtitle: '무선 청소기',    emoji: '💨' },
    { name: '다이슨 퓨어쿨',            subtitle: '공기청정기',     emoji: '💨' },
  ],
  'dyson': [
    { name: '다이슨 에어랩 멀티 스타일러', subtitle: '헤어 스타일링',  emoji: '💨' },
    { name: '다이슨 슈퍼소닉',           subtitle: '헤어 드라이어',  emoji: '💨' },
    { name: '다이슨 V15',               subtitle: '무선 청소기',    emoji: '💨' },
    { name: '다이슨 퓨어쿨',            subtitle: '공기청정기',     emoji: '💨' },
  ],
  '나이키': [
    { name: '나이키 에어맥스 97',   subtitle: '클래식 러닝',      emoji: '👟' },
    { name: '나이키 에어포스 1',    subtitle: '캐주얼 스니커즈',  emoji: '👟' },
    { name: '나이키 덩크 로우',     subtitle: '레트로 스니커즈',  emoji: '👟' },
    { name: '나이키 에어 조던 1',   subtitle: '농구/패션',        emoji: '👟' },
  ],
  'nike': [
    { name: '나이키 에어맥스 97',   subtitle: '클래식 러닝',      emoji: '👟' },
    { name: '나이키 에어포스 1',    subtitle: '캐주얼 스니커즈',  emoji: '👟' },
    { name: '나이키 덩크 로우',     subtitle: '레트로 스니커즈',  emoji: '👟' },
    { name: '나이키 에어 조던 1',   subtitle: '농구/패션',        emoji: '👟' },
  ],
  '김치': [
    { name: '종가집 포기김치',   subtitle: '대상, 전통 방식',   emoji: '🥬' },
    { name: '비비고 김치',       subtitle: 'CJ, 깔끔한 맛',    emoji: '🥬' },
    { name: '처갓집 양념김치',   subtitle: '한성식품, 남도식',  emoji: '🥬' },
    { name: '피코크 김치',       subtitle: '이마트, 프리미엄',  emoji: '🥬' },
  ],
  'ps5': [
    { name: 'PS5 슬림', subtitle: '기본형', emoji: '🎮' },
    { name: 'PS5 프로', subtitle: '고성능', emoji: '🎮' },
  ],
  '플스': [
    { name: 'PS5 슬림', subtitle: '기본형', emoji: '🎮' },
    { name: 'PS5 프로', subtitle: '고성능', emoji: '🎮' },
  ],
  '아이폰': [
    { name: 'iPhone 16',        subtitle: '6.1인치, 기본',    emoji: '📱' },
    { name: 'iPhone 16 Plus',   subtitle: '6.7인치, 대화면',  emoji: '📱' },
    { name: 'iPhone 16 Pro',    subtitle: '6.3인치, 프로',    emoji: '📱' },
    { name: 'iPhone 16 Pro Max', subtitle: '6.9인치, 최상위', emoji: '📱' },
  ],
  'iphone': [
    { name: 'iPhone 16',        subtitle: '6.1인치, 기본',    emoji: '📱' },
    { name: 'iPhone 16 Plus',   subtitle: '6.7인치, 대화면',  emoji: '📱' },
    { name: 'iPhone 16 Pro',    subtitle: '6.3인치, 프로',    emoji: '📱' },
    { name: 'iPhone 16 Pro Max', subtitle: '6.9인치, 최상위', emoji: '📱' },
  ],
  '맥북': [
    { name: '맥북 에어 M4 13인치',       subtitle: '휴대성, 가성비',    emoji: '💻' },
    { name: '맥북 에어 M4 15인치',       subtitle: '대화면',            emoji: '💻' },
    { name: '맥북 프로 M4 Pro 14인치',   subtitle: '전문가용',          emoji: '💻' },
    { name: '맥북 프로 M4 Max 16인치',   subtitle: '최상위',            emoji: '💻' },
  ],
  'macbook': [
    { name: '맥북 에어 M4 13인치',       subtitle: '휴대성, 가성비',    emoji: '💻' },
    { name: '맥북 에어 M4 15인치',       subtitle: '대화면',            emoji: '💻' },
    { name: '맥북 프로 M4 Pro 14인치',   subtitle: '전문가용',          emoji: '💻' },
    { name: '맥북 프로 M4 Max 16인치',   subtitle: '최상위',            emoji: '💻' },
  ],
};

function findAmbiguousProduct(productName: string): ModelOption[] | null {
  const name = productName.toLowerCase().trim();
  for (const [keyword, options] of Object.entries(AMBIGUOUS_PRODUCTS)) {
    if (name === keyword || name === keyword + ' ') {
      return options;
    }
  }
  return null;
}

// ── 인기 태그 ─────────────────────────────────────────────
const POPULAR_TAGS = [
  { label: '에어팟 프로', value: '에어팟 프로' },  // 구체적 → 바로 분석
  { label: '갤럭시 S25', value: '갤럭시 S25' },   // 구체적 → 바로 분석
  { label: '아이패드',   value: '아이패드' },      // 모호 → 모델 선택
  { label: '다이슨',     value: '다이슨' },        // 모호 → 모델 선택
  { label: '나이키',     value: '나이키' },        // 모호 → 모델 선택
  { label: 'PS5',       value: 'ps5' },           // 모호 → 모델 선택
];

const CATEGORIES = [
  '전자기기', '가전', '패션/의류', '뷰티/화장품', '식품',
  '스포츠/아웃도어', '가구/인테리어', '유아/키즈', '도서/문구',
  '자동차/바이크', '게임/취미', '기타',
];

const DEADLINE_OPTIONS = [
  { label: '1일 후', days: 1 },
  { label: '2일 후', days: 2 },
  { label: '3일 후', days: 3 },
  { label: '5일 후', days: 5 },
  { label: '7일 후', days: 7 },
];

// ── 헬퍼 ─────────────────────────────────────────────────
const fmtPrice = (n: number) => (n > 0 ? n.toLocaleString('ko-KR') : '');
const parsePrice = (s: string) => parseInt(s.replace(/,/g, ''), 10) || 0;

function getDeadlineDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric', weekday: 'short' });
}

// ── 애니메이션 ────────────────────────────────────────────
const variants = {
  enter:  (dir: number) => ({ x: dir > 0 ? '60%' : '-60%', opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { type: 'spring' as const, damping: 28, stiffness: 300 } },
  exit:   (dir: number) => ({ x: dir > 0 ? '-60%' : '60%', opacity: 0, transition: { duration: 0.18 } }),
};

// ── 섹션 타이틀 ──────────────────────────────────────────
function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, letterSpacing: '0.8px', marginBottom: 10 }}>
      {children}
    </div>
  );
}

// ── 가격 인풋 ─────────────────────────────────────────────
function PriceInput({
  label, value, onChange, hint, required,
}: {
  label: string; value: string; onChange: (s: string) => void; hint?: string; required?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>
        {label}{required && <span style={{ color: C.magenta }}> *</span>}
      </label>
      <div style={{ position: 'relative' }}>
        <span style={{
          position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
          fontSize: 14, color: C.textSec, pointerEvents: 'none',
        }}>₩</span>
        <input
          type="text"
          value={value}
          onChange={e => {
            const raw = e.target.value.replace(/[^\d]/g, '');
            const num = parseInt(raw, 10) || 0;
            onChange(num > 0 ? fmtPrice(num) : '');
          }}
          className="dc-input"
          placeholder="0"
          style={{
            width: '100%', padding: '13px 14px 13px 30px', fontSize: 15,
            fontWeight: 600, fontFamily: "monospace", letterSpacing: '0.5px',
            borderRadius: 12, background: C.bgInput,
            border: `1px solid ${C.border}`, color: C.textPri,
            boxSizing: 'border-box',
          }}
        />
      </div>
      {hint && <div style={{ fontSize: 11, color: C.cyan, paddingLeft: 2 }}>{hint}</div>}
    </div>
  );
}

// ── 기본 인풋 ─────────────────────────────────────────────
function TextInput({
  label, value, onChange, placeholder, required,
}: {
  label: string; value: string; onChange: (s: string) => void; placeholder?: string; required?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>
        {label}{required && <span style={{ color: C.magenta }}> *</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="dc-input"
        style={{
          padding: '13px 14px', fontSize: 14, borderRadius: 12,
          background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
        }}
      />
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────
export default function DealCreatePage() {
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);

  // Step 1
  const [productName,      setProductName]      = useState('');
  const [freeText,         setFreeText]         = useState('');
  const [aiLoading,        setAiLoading]        = useState(false);
  const [showModelSelect,  setShowModelSelect]  = useState(false);
  const [modelOptions,     setModelOptions]     = useState<ModelOption[]>([]);

  // Step 2
  const [aiResult,         setAiResult]         = useState<AIResult | null>(null);
  const [selectedOptions,  setSelectedOptions]  = useState<Record<string, string>>({});
  const [category,         setCategory]         = useState('전자기기');

  // Step 3
  const [targetPriceStr, setTargetPriceStr] = useState('');
  const [maxBudgetStr,   setMaxBudgetStr]   = useState('');
  const [quantity,       setQuantity]       = useState(1);
  const [deadlineDays,   setDeadlineDays]   = useState(3);

  // Step 4
  const [creating, setCreating] = useState(false);

  // 중복 딜 모달
  interface DupDeal { deal_id: number; product_name: string; participants: number; lowest_offer: number; }
  const [dupDeal, setDupDeal] = useState<DupDeal | null>(null);

  // ── 이동 ─────────────────────────────────────────────
  const goTo = (n: number) => { setDir(n > step ? 1 : -1); setStep(n); };

  const goBack = () => {
    if (showModelSelect) {
      setShowModelSelect(false);
      setModelOptions([]);
    } else if (step === 1) {
      navigate(-1);
    } else {
      goTo(step - 1);
    }
  };

  // 스텝 변경 시 브라우저 히스토리 엔트리 추가
  useEffect(() => {
    if (step > 1) {
      window.history.pushState({ step }, '');
    }
  }, [step]);

  // 모델 선택 화면 진입 시 히스토리 엔트리 추가
  useEffect(() => {
    if (showModelSelect) {
      window.history.pushState({ step, showModelSelect: true }, '');
    }
  }, [showModelSelect, step]);

  // 브라우저 뒤로가기 처리
  useEffect(() => {
    const handlePopState = (_e: PopStateEvent) => {
      if (showModelSelect) {
        setShowModelSelect(false);
        setModelOptions([]);
      } else if (step > 1) {
        setStep(prev => prev - 1);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [step, showModelSelect]);

  // ── AI 분석 로직 (공통) ───────────────────────────────
  const runAIAnalysis = async (name: string, text: string) => {
    setAiLoading(true);

    let result: AIResult;

    // API 우선 시도
    if (FEATURES.USE_API_AI) {
      const apiResult = await aiDealHelper(name);
      if (apiResult && typeof apiResult === 'object' && 'canonical_name' in apiResult) {
        // API 응답을 직접 사용
        const api = apiResult as {
          canonical_name: string;
          model_name: string;
          brand?: string;
          normalized_free_text?: string | null;
          category?: string | null;
          suggested_options?: { title: string; selected_value?: string | null; values: string[] }[];
          price?: {
            center_price?: number | null;
            desired_price_suggestion?: number | null;
            max_budget_suggestion?: number | null;
            commentary?: string | null;
            naver_lowest_price?: number | null;
            price_source?: string | null;
          };
        };
        result = {
          canonical_name: api.canonical_name,
          model_name: api.model_name,
          normalized_free_text: api.normalized_free_text ?? null,
          category: api.category ?? null,
          suggested_options: (api.suggested_options ?? []).map(o => ({
            title: o.title,
            selected_value: o.selected_value ?? null,
            values: o.values,
          })),
          price: {
            center_price: api.price?.center_price ?? null,
            desired_price_suggestion: api.price?.desired_price_suggestion ?? null,
            max_budget_suggestion: api.price?.max_budget_suggestion ?? null,
            commentary: api.price?.commentary ?? null,
            price_source: api.price?.price_source ?? null,
          },
        };
        result = applyWarnings(result, text);
        await new Promise(r => setTimeout(r, 500));
        setAiResult(result);
      } else {
        // API 실패 → Mock fallback
        await new Promise(r => setTimeout(r, 2000));
        result = applyWarnings(generateMockAIResult(name, text), text);
        setAiResult(result);
      }
    } else {
      // API 비활성화 → Mock
      await new Promise(r => setTimeout(r, 2000));
      result = applyWarnings(generateMockAIResult(name, text), text);
      setAiResult(result);
    }

    // ── 카테고리 자동 매핑 ──
    if (result.category) {
      const catMap: Record<string, string> = {
        '무선이어폰': '전자기기', '이어폰': '전자기기', '스마트폰': '전자기기', '노트북': '전자기기',
        '태블릿': '전자기기', '모니터': '전자기기', '게임기': '전자기기', '카메라': '전자기기',
        'TV': '전자기기', '스피커': '전자기기', '컴퓨터 주변기기': '전자기기', '스마트워치': '전자기기',
        '헤어스타일러': '가전', '청소기': '가전', '냉장고': '가전', '세탁기': '가전',
        '에어컨': '가전', '공기청정기': '가전', '전자레인지': '가전',
        '운동화': '스포츠/아웃도어', '등산화': '스포츠/아웃도어', '러닝화': '스포츠/아웃도어',
        '쌀': '식품', '식품': '식품', '라면': '식품', '음료': '식품', '과자': '식품',
        '의류': '패션/의류', '신발': '패션/의류', '가방': '패션/의류',
        '화장품': '뷰티/화장품', '스킨케어': '뷰티/화장품',
        '가구': '가구/인테리어', '인테리어': '가구/인테리어',
      };
      const apiCat = result.category;
      const mapped = catMap[apiCat] || CATEGORIES.find(c => apiCat.includes(c) || c.includes(apiCat));
      if (mapped) setCategory(mapped);
      else setCategory('기타');
    }

    // ── 옵션 기본값 선택 (API selected_value 우선) ──
    const combined = text.toLowerCase();
    const defaults: Record<string, string> = {};
    result.suggested_options.forEach(opt => {
      // API가 selected_value를 줬으면 그걸 우선 사용
      if (opt.selected_value && opt.values.includes(opt.selected_value)) {
        defaults[opt.title] = opt.selected_value;
      } else if (opt.title === '색상' && text) {
        let matched = opt.values[0];
        for (const [keyword, colorName] of Object.entries(COLOR_KEYWORDS)) {
          if (combined.includes(keyword)) {
            const found = opt.values.find(v =>
              v.toLowerCase().includes(colorName.toLowerCase()) ||
              colorName.toLowerCase().includes(v.toLowerCase())
            );
            if (found) matched = found;
            break;
          }
        }
        defaults[opt.title] = matched;
      } else {
        defaults[opt.title] = opt.values[0];
      }
    });
    setSelectedOptions(defaults);
    setTargetPriceStr(fmtPrice(result.price.desired_price_suggestion ?? 0));
    setMaxBudgetStr(fmtPrice(result.price.max_budget_suggestion ?? 0));

    setAiLoading(false);
    goTo(2);
  };

  // ── 분석 버튼 클릭 ────────────────────────────────────
  const handleAIAnalysis = async () => {
    const ambiguousOptions = findAmbiguousProduct(productName);
    if (ambiguousOptions && !showModelSelect) {
      setModelOptions(ambiguousOptions);
      setShowModelSelect(true);
      return;
    }
    await runAIAnalysis(productName, freeText);
  };

  // ── 모델 선택 완료 ────────────────────────────────────
  const handleModelSelect = (model: ModelOption) => {
    setProductName(model.name);
    setShowModelSelect(false);
    setModelOptions([]);
    setTimeout(() => {
      runAIAnalysis(model.name, freeText);
    }, 100);
  };

  // ── 딜 생성 (중복 체크 포함) ─────────────────────────
  const handleCreate = async () => {
    setCreating(true);
    await new Promise(r => setTimeout(r, 1000));
    setCreating(false);

    const isDuplicate = productName.includes('에어팟');
    if (isDuplicate) {
      setDupDeal({
        deal_id:       42,
        product_name:  aiResult?.model_name ?? productName,
        participants:  18,
        lowest_offer:  291000,
      });
      return;
    }
    doCreate();
  };

  const doCreate = () => {
    showToast('딜이 생성되었어요! 판매자들이 오퍼를 보내기 시작합니다', 'success');
    setTimeout(() => navigate('/deal/15'), 1800);
  };

  // ── 계산값 ───────────────────────────────────────────
  const targetPrice  = parsePrice(targetPriceStr);
  const anchorPrice  = aiResult?.price.center_price ?? 0;
  const savingPct    = anchorPrice > 0 && targetPrice > 0
    ? ((anchorPrice - targetPrice) / anchorPrice * 100).toFixed(1)
    : null;
  const deadlineDate = getDeadlineDate(deadlineDays);
  const optionSummary = Object.entries(selectedOptions).map(([, v]) => v).join(' · ');

  const step2CanNext = aiResult !== null;
  const step3CanNext = targetPrice > 0 && quantity >= 1;

  // ── TopBar 타이틀 ─────────────────────────────────────
  const getStepTitle = () => {
    if (step === 1 && showModelSelect) return '모델 선택';
    return '딜 만들기';
  };

  // ── 공용 스타일 ──────────────────────────────────────
  const cardStyle: React.CSSProperties = {
    background: C.bgCard, border: `1px solid ${C.border}`,
    borderRadius: 16, padding: '18px 18px',
  };

  const primaryBtn = (label: string, onClick: () => void, disabled?: boolean, loading?: boolean): React.ReactNode => (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        width: '100%', padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
        background: disabled ? `${C.cyan}30` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
        color: disabled ? C.textSec : '#0a0e1a',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        transition: 'opacity 0.15s',
      }}
    >
      {loading && (
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: `2px solid rgba(0,0,0,0.3)`, borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />
      )}
      {label}
    </button>
  );

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, overflow: 'hidden' }}>
      <style>{`
        @keyframes spin     { to { transform: rotate(360deg); } }
        @keyframes ppBlink  { 0%,100%{opacity:1} 50%{opacity:0.45} }
        @keyframes toastIn  { from{opacity:0;transform:translateX(-50%) translateY(12px)} to{opacity:1;transform:translateX(-50%) translateY(0)} }
        .dc-input:focus { border-color: rgba(0,240,255,0.5) !important; outline: none; }
        .dc-input { box-sizing: border-box; width: 100%; }
        select.dc-input { appearance: none; cursor: pointer; }
      `}</style>

      {/* ── TopBar ── */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', zIndex: 10,
        background: 'rgba(10,14,26,0.92)', backdropFilter: 'blur(10px)',
        borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={goBack} style={{ fontSize: 13, color: C.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          ← {getStepTitle()}
        </button>
        <div style={{ fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: C.cyan }}>{step}</span>
          <span style={{ color: C.textSec }}>/4</span>
        </div>
        <div style={{ width: 64 }} />
      </div>

      {/* ── 진행 바 ── */}
      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: `${C.border}` }}>
        <div style={{
          height: '100%', width: `${(step / 4) * 100}%`,
          background: `linear-gradient(90deg, ${C.cyan}, ${C.green})`,
          transition: 'width 0.35s ease',
        }} />
      </div>

      {/* ── AI 로딩 오버레이 ── */}
      <AnimatePresence>
        {aiLoading && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 50,
              background: 'rgba(10,14,26,0.94)', backdropFilter: 'blur(8px)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18,
            }}
          >
            <div style={{ fontSize: 60, animation: 'ppBlink 1.2s ease-in-out infinite' }}>🤖</div>
            <div style={{ fontSize: 17, fontWeight: 800, color: C.textPri }}>AI가 분석 중이에요...</div>
            <div style={{ fontSize: 13, color: C.textSec }}>상품 정보와 시장가를 확인하고 있어요</div>
            <div style={{ width: 34, height: 34, borderRadius: '50%', border: `3px solid ${C.border}`, borderTopColor: C.cyan, animation: 'spin 0.8s linear infinite' }} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 콘텐츠 ── */}
      <div style={{ paddingTop: 60, minHeight: '100dvh' }}>
        <AnimatePresence mode="wait" custom={dir}>
          <motion.div
            key={step}
            custom={dir}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            style={{ width: '100%', maxWidth: 520, margin: '0 auto', padding: '28px 20px 100px' }}
          >

            {/* ══ Step 1: 상품 입력 / 모델 선택 ══ */}
            {step === 1 && (
              showModelSelect ? (
                /* ── 모델 선택 UI ── */
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', damping: 26, stiffness: 300 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: 0 }}
                >
                  {/* 타이틀 */}
                  <div style={{ textAlign: 'center', marginBottom: 28 }}>
                    <div style={{ fontSize: 44, marginBottom: 12 }}>🤖</div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: C.textPri, marginBottom: 8 }}>
                      핑퐁이가 물어봐요
                    </div>
                    <div style={{ fontSize: 14, color: C.textSec, lineHeight: 1.6 }}>
                      <span style={{ color: C.cyan, fontWeight: 700 }}>"{productName}"</span>의 여러 모델이 있어요.
                      <br />어떤 모델을 찾으시나요?
                    </div>
                  </div>

                  {/* 모델 카드 목록 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {modelOptions.map((model, i) => (
                      <motion.button
                        key={model.name}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        whileTap={{ scale: 0.97 }}
                        onClick={() => handleModelSelect(model)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 14,
                          padding: '16px 18px',
                          background: C.bgCard,
                          border: `1px solid ${C.border}`,
                          borderRadius: 14,
                          textAlign: 'left',
                          cursor: 'pointer',
                          width: '100%',
                          transition: 'border-color 0.15s, background 0.15s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.borderColor = `${C.cyan}55`;
                          e.currentTarget.style.background = `${C.cyan}08`;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.borderColor = C.border;
                          e.currentTarget.style.background = C.bgCard;
                        }}
                      >
                        <span style={{ fontSize: 28, flexShrink: 0 }}>{model.emoji}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 600, color: C.textPri }}>
                            {model.name}
                          </div>
                          <div style={{ fontSize: 12, color: C.textDim, marginTop: 2 }}>
                            {model.subtitle}
                          </div>
                        </div>
                        <span style={{ fontSize: 18, color: C.textDim }}>›</span>
                      </motion.button>
                    ))}
                  </div>

                  {/* 다시 입력하기 */}
                  <button
                    onClick={() => { setShowModelSelect(false); setModelOptions([]); }}
                    style={{
                      marginTop: 20, width: '100%', padding: 14,
                      background: 'transparent',
                      border: `1px solid rgba(255,255,255,0.15)`,
                      borderRadius: 12, color: C.textSec, fontSize: 14,
                      cursor: 'pointer', transition: 'border-color 0.15s, color 0.15s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)'; e.currentTarget.style.color = C.textPri; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.color = C.textSec; }}
                  >
                    ← 다시 입력하기
                  </button>
                </motion.div>
              ) : (
                /* ── 일반 Step 1 UI ── */
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 8 }}>
                      어떤 상품을<br />원하시나요?
                    </div>
                    <div style={{ fontSize: 13, color: C.textSec }}>
                      찾고 있는 상품의 이름을 알려주세요.<br />
                      핑퐁이 AI가 옵션과 가격을 분석해드려요 🎯
                    </div>
                  </div>

                  {/* 상품명 */}
                  <TextInput
                    label="상품명" required
                    value={productName} onChange={setProductName}
                    placeholder="예: 에어팟 프로 2세대"
                  />

                  {/* 추가 설명 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>원하는 조건이 있나요? (선택)</label>
                    <textarea
                      value={freeText}
                      onChange={e => setFreeText(e.target.value)}
                      placeholder="색상, 용량, 사이즈 등 원하는 옵션을 적어주세요"
                      rows={3}
                      className="dc-input"
                      style={{
                        padding: '13px 14px', fontSize: 14, borderRadius: 12, resize: 'none',
                        background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
                        lineHeight: 1.55,
                      }}
                    />
                    <div style={{ fontSize: 11, color: C.textDim }}>
                      💡 여기에 적은 내용을 AI가 분석해서 옵션을 자동으로 설정해드려요
                    </div>
                  </div>

                  {/* 인기 태그 */}
                  <div>
                    <div style={{ fontSize: 12, color: C.textSec, marginBottom: 10 }}>💡 이런 딜이 인기 있어요</div>
                    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                      {POPULAR_TAGS.map(tag => (
                        <button
                          key={tag.value}
                          onClick={() => setProductName(tag.value)}
                          style={{
                            flexShrink: 0, padding: '7px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                            background: productName === tag.value ? `${C.cyan}18` : C.bgSurface,
                            border: `1px solid ${productName === tag.value ? C.cyan : C.border}`,
                            color: productName === tag.value ? C.cyan : C.textSec,
                            cursor: 'pointer', transition: 'all 0.15s',
                          }}
                        >
                          {tag.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* CTA */}
                  {primaryBtn('🔍 핑퐁이 AI 분석하기', handleAIAnalysis, !productName.trim())}
                </div>
              )
            )}

            {/* ══ Step 2: AI 결과 + 옵션 ══ */}
            {step === 2 && aiResult && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: C.textPri }}>🎯 AI 분석 결과</div>

                {/* AI 결과 카드 */}
                <div style={{ ...cardStyle, borderColor: `${C.cyan}30`, background: `${C.cyan}08` }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                    <span style={{ fontSize: 28, flexShrink: 0 }}>🏷️</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 15, fontWeight: 800, color: C.textPri, marginBottom: 2 }}>
                        {aiResult.model_name}
                      </div>
                      <div style={{ fontSize: 11, color: C.textSec, marginBottom: 12 }}>
                        {aiResult.canonical_name}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 13, color: C.yellow, fontWeight: 700 }}>
                          💰 시장가 약 ₩{fmtPrice(aiResult.price.center_price ?? 0)}
                        </span>
                      </div>
                      {/* 가격 소스 표시 */}
                      <div style={{
                        fontSize: 11, fontWeight: 600, marginBottom: 8,
                        color: aiResult.price.price_source === 'naver' ? C.green
                             : aiResult.price.price_source === 'llm_estimate' ? C.yellow
                             : '#ff6b6b',
                      }}>
                        {aiResult.price.price_source === 'naver'
                          ? '✅ 네이버쇼핑 실시간 가격 기준'
                          : aiResult.price.price_source === 'llm_estimate'
                          ? '⚠️ AI 추정가입니다. 실제 가격과 다를 수 있어요'
                          : '❌ 시장가 조회 실패. 직접 입력해주세요'}
                      </div>
                      <div style={{
                        fontSize: 11, color: C.textSec, background: C.bgSurface,
                        borderRadius: 8, padding: '8px 10px', lineHeight: 1.5,
                      }}>
                        📝 {aiResult.price.commentary ?? ''}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 경고 메시지 */}
                {aiResult.warnings && aiResult.warnings.length > 0 && (
                  <div style={{
                    padding: '14px 16px',
                    background: 'rgba(255,45,120,0.08)',
                    border: '1px solid rgba(255,45,120,0.25)',
                    borderRadius: 12,
                  }}>
                    {aiResult.warnings.map((w, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'flex-start', gap: 8,
                        fontSize: 13, color: '#ff8eab', lineHeight: 1.5,
                      }}>
                        <span style={{ flexShrink: 0 }}>ℹ️</span>
                        <span>{w}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* 옵션 선택 */}
                <div>
                  <SectionTitle>📦 옵션을 선택하세요</SectionTitle>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {aiResult.suggested_options.map(opt => (
                      <div key={opt.title}>
                        <div style={{ fontSize: 12, color: C.textSec, marginBottom: 8 }}>{opt.title}</div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {opt.values.map(val => {
                            const active = selectedOptions[opt.title] === val;
                            return (
                              <button
                                key={val}
                                onClick={() => setSelectedOptions(prev => ({ ...prev, [opt.title]: val }))}
                                style={{
                                  padding: '7px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600,
                                  background: active ? `${C.cyan}18` : C.bgSurface,
                                  border: `1.5px solid ${active ? C.cyan : C.border}`,
                                  color: active ? C.cyan : C.textSec,
                                  cursor: 'pointer', transition: 'all 0.15s',
                                }}
                              >
                                {val}{active && ' ✓'}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 카테고리 */}
                <div>
                  <SectionTitle>📂 카테고리</SectionTitle>
                  <div style={{ position: 'relative' }}>
                    <select
                      value={category}
                      onChange={e => setCategory(e.target.value)}
                      className="dc-input"
                      style={{
                        padding: '13px 40px 13px 14px', fontSize: 14, borderRadius: 12,
                        background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
                      }}
                    >
                      {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <span style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, pointerEvents: 'none', fontSize: 12 }}>▾</span>
                  </div>
                </div>

                {primaryBtn('다음', () => goTo(3), !step2CanNext)}
              </div>
            )}

            {/* ══ Step 3: 가격 + 조건 ══ */}
            {step === 3 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 8 }}>
                    💰 가격과 조건을<br />설정하세요
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec }}>AI 추천 가격을 참고하세요.</div>
                </div>

                {/* 시장가 참고 */}
                {anchorPrice > 0 && (
                  <div style={{ ...cardStyle, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                    <div>
                      <div style={{ fontSize: 11, color: C.textSec, marginBottom: 2 }}>시장가</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: C.yellow }}>₩{fmtPrice(anchorPrice)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: C.textSec, marginBottom: 2 }}>AI 추천</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: C.cyan }}>
                        ₩{fmtPrice(aiResult!.price.desired_price_suggestion ?? 0)} ~ {fmtPrice(aiResult!.price.max_budget_suggestion ?? 0)}
                      </div>
                    </div>
                  </div>
                )}

                {/* 목표가 */}
                <div>
                  <PriceInput
                    label="목표가 (원하는 가격)" required
                    value={targetPriceStr} onChange={setTargetPriceStr}
                    hint={aiResult?.price.desired_price_suggestion != null ? `AI 추천: ₩${fmtPrice(aiResult.price.desired_price_suggestion)}` : undefined}
                  />
                  {savingPct !== null && parseFloat(savingPct) > 0 && (
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.green, marginTop: 6, paddingLeft: 2 }}>
                      🔥 시장가 대비 {savingPct}% 절약
                    </div>
                  )}
                </div>

                {/* 최대 예산 */}
                <PriceInput
                  label="최대 예산 (이 이상은 비싸요)"
                  value={maxBudgetStr} onChange={setMaxBudgetStr}
                  hint={aiResult?.price.max_budget_suggestion != null ? `AI 추천: ₩${fmtPrice(aiResult.price.max_budget_suggestion)}` : undefined}
                />

                {/* 수량 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>
                    수량 (개)<span style={{ color: C.magenta }}> *</span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <button
                      onClick={() => setQuantity(q => Math.max(1, q - 1))}
                      style={{ width: 38, height: 38, borderRadius: 10, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, fontSize: 18, cursor: 'pointer' }}
                    >−</button>
                    <span style={{ fontSize: 18, fontWeight: 700, color: C.textPri, minWidth: 32, textAlign: 'center' }}>{quantity}</span>
                    <button
                      onClick={() => setQuantity(q => q + 1)}
                      style={{ width: 38, height: 38, borderRadius: 10, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, fontSize: 18, cursor: 'pointer' }}
                    >+</button>
                  </div>
                </div>

                {/* 마감일 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>
                    마감일<span style={{ color: C.magenta }}> *</span>
                  </label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {DEADLINE_OPTIONS.map(opt => {
                      const active = deadlineDays === opt.days;
                      return (
                        <button
                          key={opt.days}
                          onClick={() => setDeadlineDays(opt.days)}
                          style={{
                            padding: '8px 16px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                            background: active ? `${C.cyan}18` : C.bgSurface,
                            border: `1.5px solid ${active ? C.cyan : C.border}`,
                            color: active ? C.cyan : C.textSec,
                            cursor: 'pointer', transition: 'all 0.15s',
                          }}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec, paddingLeft: 2 }}>{deadlineDate}까지</div>
                </div>

                {primaryBtn('다음', () => goTo(4), !step3CanNext)}
              </div>
            )}

            {/* ══ Step 4: 확인 + 생성 ══ */}
            {step === 4 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: C.textPri }}>📋 딜 요약</div>

                {/* 요약 카드 */}
                <div style={{ ...cardStyle }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 14, marginBottom: 14, borderBottom: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: 24 }}>🏷️</span>
                    <div style={{ fontSize: 15, fontWeight: 800, color: C.textPri }}>
                      {aiResult?.model_name ?? productName}
                    </div>
                  </div>

                  {[
                    { label: '카테고리',   value: category },
                    { label: '옵션',       value: optionSummary || '없음' },
                    { label: '목표가',     value: `₩${fmtPrice(targetPrice)}`, color: C.green },
                    { label: '최대 예산',  value: parsePrice(maxBudgetStr) > 0 ? `₩${maxBudgetStr}` : '미설정', color: C.yellow },
                    { label: '시장가',     value: anchorPrice > 0 ? `₩${fmtPrice(anchorPrice)}` : '-', color: C.textSec },
                    { label: '수량',       value: `${quantity}개` },
                    { label: '마감일',     value: deadlineDate },
                    ...(savingPct !== null && parseFloat(savingPct) > 0
                      ? [{ label: '절약률', value: `${savingPct}% 절약 🔥`, color: C.green }]
                      : []),
                  ].map(({ label, value, color }, idx, arr) => (
                    <div
                      key={label}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '10px 0',
                        borderBottom: idx < arr.length - 1 ? `1px solid ${C.border}` : 'none',
                      }}
                    >
                      <span style={{ fontSize: 13, color: C.textSec }}>{label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: color ?? C.textPri }}>{value}</span>
                    </div>
                  ))}
                </div>

                {/* 안내 문구 */}
                <div style={{
                  background: `${C.orange}10`, border: `1px solid ${C.orange}30`,
                  borderRadius: 12, padding: '12px 14px',
                  fontSize: 12, color: C.textSec, lineHeight: 1.6,
                }}>
                  ⚠️ 딜이 생성되면 판매자들이 오퍼를 보내기 시작해요. 목표가는 나중에 수정할 수 있어요.
                </div>

                {primaryBtn('🚀 딜 생성하기', handleCreate, false, creating)}
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── 중복 딜 모달 ── */}
      <AnimatePresence>
        {dupDeal && (
          <>
            <motion.div
              key="dup-overlay"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => { setDupDeal(null); goTo(1); }}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 300, backdropFilter: 'blur(4px)' }}
            />
            <motion.div
              key="dup-modal"
              initial={{ opacity: 0, scale: 0.9, y: 24 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: 16 }}
              transition={{ type: 'spring', damping: 26, stiffness: 320 }}
              style={{
                position: 'fixed', left: '50%', top: '50%',
                transform: 'translate(-50%, -50%)',
                width: 'calc(100vw - 40px)', maxWidth: 380,
                background: C.bgCard, border: `1px solid ${C.border}`,
                borderRadius: 22, padding: '28px 24px',
                zIndex: 301,
              }}
            >
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <div style={{ fontSize: 40, marginBottom: 10 }}>💪</div>
                <div style={{ fontSize: 17, fontWeight: 800, color: C.textPri, marginBottom: 6 }}>
                  이미 진행 중인 딜이 있어요!
                </div>
                <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.6 }}>
                  같은 상품의 딜에 함께 참여하면<br />더 좋은 가격을 받을 수 있어요 💪
                </div>
              </div>

              <div style={{
                background: C.bgSurface, border: `1px solid ${C.border}`,
                borderRadius: 14, padding: '16px', marginBottom: 22,
              }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.textPri, marginBottom: 12 }}>
                  🏷️ {dupDeal.product_name}
                </div>
                <div style={{ display: 'flex', gap: 20 }}>
                  <div>
                    <div style={{ fontSize: 11, color: C.textSec, marginBottom: 3 }}>현재 참여자</div>
                    <div style={{ fontSize: 15, fontWeight: 800, color: C.cyan }}>{dupDeal.participants}명</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: C.textSec, marginBottom: 3 }}>현재 최저 오퍼가</div>
                    <div style={{ fontSize: 15, fontWeight: 800, color: C.green }}>₩{fmtPrice(dupDeal.lowest_offer)}</div>
                  </div>
                </div>
              </div>

              <button
                onClick={() => { setDupDeal(null); navigate(`/deal/${dupDeal.deal_id}`); }}
                style={{
                  width: '100%', padding: '14px', borderRadius: 13,
                  background: `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                  color: '#0a0e1a', fontSize: 14, fontWeight: 800, cursor: 'pointer',
                  marginBottom: 14,
                }}
              >
                기존 딜 참여하기 →
              </button>

              <button
                onClick={() => { setDupDeal(null); goTo(1); }}
                style={{
                  width: '100%', padding: '13px', borderRadius: 13,
                  background: 'transparent', border: `1px solid ${C.border}`,
                  color: C.textSec, fontSize: 14, fontWeight: 600,
                  cursor: 'pointer', transition: 'border-color 0.15s, color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = C.cyan; e.currentTarget.style.color = C.textPri; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.textSec; }}
              >
                ← 옵션 변경하러 가기
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* 토스트: showToast() 사용 — 전역 */}
    </div>
  );
}
