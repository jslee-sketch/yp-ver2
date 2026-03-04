import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { aiDealHelper } from '../api/aiApi';
import { FEATURES } from '../config';
import { showToast } from '../components/common/Toast';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

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
  name: string;
  subtitle: string;
  emoji: string;
}

// ── AI 결과 타입 ──────────────────────────────────────────
type AIResult = {
  canonical_name: string;
  model_name: string;
  brand?: string | null;
  brands?: string[];
  product_code?: string | null;
  product_detail?: string | null;
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

// ── 옵션 그룹 타입 ───────────────────────────────────────
interface OptionGroup {
  title: string;
  values: string[];
}

// ── Mock 데이터 ──────────────────────────────────────────
function generateMockAIResult(productName: string, freeText: string): AIResult {
  const name = (productName + ' ' + freeText).toLowerCase();

  if (name.includes('에어팟') || name.includes('airpod')) {
    return {
      canonical_name: 'Apple AirPods Pro 2nd Gen (USB-C)',
      model_name: '에어팟 프로 2세대 (USB-C)',
      brand: 'Apple', brands: ['Apple'],
      product_code: 'MTJV3KH/A',
      product_detail: '애플 에어팟 프로 2세대 USB-C MagSafe',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['화이트'] },
        { title: '충전 방식', values: ['USB-C', 'Lightning'] },
        { title: '각인', values: ['없음', '있음'] },
      ],
      price: { center_price: 339000, desired_price_suggestion: 289000, max_budget_suggestion: 319000,
        commentary: '네이버 최저가 기준 약 339,000원입니다.', price_source: 'naver' },
      category: '무선이어폰',
    };
  }
  if (name.includes('갤럭시') || name.includes('galaxy')) {
    return {
      canonical_name: 'Samsung Galaxy S25 Ultra 256GB',
      model_name: '갤럭시 S25 울트라',
      brand: 'Samsung', brands: ['Samsung', '삼성'],
      product_code: 'SM-S938N',
      product_detail: '삼성 갤럭시 S25 울트라 256GB 자급제',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['티타늄 블랙', '티타늄 그레이', '티타늄 블루', '티타늄 실버'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
        { title: '통신사', values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1698000, desired_price_suggestion: 1450000, max_budget_suggestion: 1590000,
        commentary: '자급제 기준 약 1,698,000원입니다.', price_source: 'naver' },
      category: '스마트폰',
    };
  }
  if (name.includes('아이폰') || name.includes('iphone')) {
    return {
      canonical_name: 'Apple iPhone 16 Pro 256GB',
      model_name: 'iPhone 16 Pro',
      brand: 'Apple', brands: ['Apple'],
      product_code: 'MYW53KH/A',
      product_detail: '애플 아이폰 16 프로 256GB 자급제',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['블랙 티타늄', '내추럴 티타늄', '화이트 티타늄', '데저트 티타늄'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
        { title: '통신사', values: ['자급제', 'SKT', 'KT', 'LG U+'] },
      ],
      price: { center_price: 1550000, desired_price_suggestion: 1350000, max_budget_suggestion: 1480000,
        commentary: '자급제 기준 1,550,000원입니다.', price_source: 'naver' },
      category: '스마트폰',
    };
  }
  if (name.includes('김치')) {
    return {
      canonical_name: '종가집 포기김치',
      model_name: '종가집 포기김치',
      brand: '종가집', brands: ['종가집', '비비고', '풀무원', '처갓집', '피코크'],
      product_code: null,
      product_detail: '종가집 포기김치 3kg',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '종류', values: ['포기김치', '맛김치', '총각김치', '깍두기'] },
        { title: '중량', values: ['1kg', '3kg', '5kg', '10kg'] },
      ],
      price: { center_price: 35000, desired_price_suggestion: 28000, max_budget_suggestion: 32000,
        commentary: '3kg 기준 약 35,000원입니다.', price_source: 'naver' },
      category: '식품',
    };
  }
  if (name.includes('다이슨') || name.includes('dyson')) {
    return {
      canonical_name: 'Dyson Airwrap Multi-Styler Complete Long',
      model_name: '다이슨 에어랩 멀티 스타일러 컴플리트 롱',
      brand: 'Dyson', brands: ['Dyson', '다이슨'],
      product_code: null,
      product_detail: '다이슨 에어랩 멀티 스타일러 컴플리트 롱',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '모델', values: ['컴플리트 롱', '컴플리트', '오리진'] },
        { title: '색상', values: ['니켈/코퍼', '블루/블러시', '핑크/로즈'] },
      ],
      price: { center_price: 699000, desired_price_suggestion: 580000, max_budget_suggestion: 650000,
        commentary: '다이슨 공식가 699,000원입니다.', price_source: 'naver' },
      category: '헤어스타일러',
    };
  }
  if (name.includes('맥북') || name.includes('macbook')) {
    return {
      canonical_name: 'Apple MacBook Air M4 13-inch 256GB',
      model_name: '맥북 에어 M4 13인치',
      brand: 'Apple', brands: ['Apple'],
      product_code: null,
      product_detail: '애플 맥북 에어 M4 13인치 256GB',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['미드나이트', '스타라이트', '실버', '스페이스 그레이'] },
        { title: '메모리', values: ['16GB', '24GB'] },
        { title: '저장 용량', values: ['256GB', '512GB', '1TB'] },
      ],
      price: { center_price: 1590000, desired_price_suggestion: 1390000, max_budget_suggestion: 1500000,
        commentary: 'Apple 공식가 1,590,000원입니다.', price_source: 'naver' },
      category: '노트북',
    };
  }
  if (name.includes('나이키') || name.includes('nike')) {
    return {
      canonical_name: 'Nike Air Max 97 Silver Bullet',
      model_name: '나이키 에어맥스 97 실버 불렛',
      brand: 'Nike', brands: ['Nike', '나이키'],
      product_code: null,
      product_detail: '나이키 에어맥스 97 실버 불렛',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '사이즈', values: ['250', '260', '270', '280', '290'] },
        { title: '색상', values: ['실버 불렛', '블랙', '화이트'] },
      ],
      price: { center_price: 219000, desired_price_suggestion: 179000, max_budget_suggestion: 199000,
        commentary: '나이키 공식가 219,000원입니다.', price_source: 'naver' },
      category: '운동화',
    };
  }
  if (name.includes('아이패드') || name.includes('ipad')) {
    return {
      canonical_name: 'Apple iPad mini 7th Gen WiFi 128GB',
      model_name: '아이패드 미니 7세대',
      brand: 'Apple', brands: ['Apple'],
      product_code: null,
      product_detail: '애플 아이패드 미니 7세대 WiFi 128GB',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '색상', values: ['스페이스 그레이', '스타라이트', '퍼플', '블루'] },
        { title: '저장 용량', values: ['128GB', '256GB'] },
        { title: '연결', values: ['WiFi', 'WiFi + Cellular'] },
      ],
      price: { center_price: 749000, desired_price_suggestion: 650000, max_budget_suggestion: 710000,
        commentary: 'Apple 공식가 기준 749,000원입니다.', price_source: 'naver' },
      category: '태블릿',
    };
  }
  if (name.includes('ps5') || name.includes('플스') || name.includes('플레이스테이션')) {
    return {
      canonical_name: 'Sony PlayStation 5 Pro Digital Edition',
      model_name: 'PS5 프로 디지털 에디션',
      brand: 'Sony', brands: ['Sony'],
      product_code: null,
      product_detail: '소니 플레이스테이션 5 프로 디지털 에디션',
      normalized_free_text: freeText || null,
      suggested_options: [
        { title: '에디션', values: ['디지털 에디션', '디스크 에디션'] },
        { title: '저장 용량', values: ['1TB', '2TB'] },
      ],
      price: { center_price: 798000, desired_price_suggestion: 690000, max_budget_suggestion: 750000,
        commentary: 'Sony 공식가 798,000원입니다.', price_source: 'naver' },
      category: '게임기',
    };
  }

  return {
    canonical_name: productName,
    model_name: productName,
    brand: null, brands: [],
    product_code: null,
    product_detail: null,
    normalized_free_text: freeText || null,
    suggested_options: [{ title: '옵션 1', values: ['기본'] }],
    price: { center_price: 100000, desired_price_suggestion: 85000, max_budget_suggestion: 95000,
      commentary: '정확한 시장가 정보가 부족해요. AI 연동 후 자동으로 업데이트됩니다.', price_source: null },
  };
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
  ],
  'galaxy': [
    { name: '갤럭시 S25',         subtitle: '6.2인치, 기본',       emoji: '📱' },
    { name: '갤럭시 S25+',        subtitle: '6.7인치, 대화면',     emoji: '📱' },
    { name: '갤럭시 S25 울트라',  subtitle: '6.9인치, S펜, 최상위', emoji: '📱' },
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
  ],
  'dyson': [
    { name: '다이슨 에어랩 멀티 스타일러', subtitle: '헤어 스타일링',  emoji: '💨' },
    { name: '다이슨 슈퍼소닉',           subtitle: '헤어 드라이어',  emoji: '💨' },
    { name: '다이슨 V15',               subtitle: '무선 청소기',    emoji: '💨' },
  ],
  '나이키': [
    { name: '나이키 에어맥스 97',   subtitle: '클래식 러닝',      emoji: '👟' },
    { name: '나이키 에어포스 1',    subtitle: '캐주얼 스니커즈',  emoji: '👟' },
    { name: '나이키 덩크 로우',     subtitle: '레트로 스니커즈',  emoji: '👟' },
  ],
  'nike': [
    { name: '나이키 에어맥스 97',   subtitle: '클래식 러닝',      emoji: '👟' },
    { name: '나이키 에어포스 1',    subtitle: '캐주얼 스니커즈',  emoji: '👟' },
    { name: '나이키 덩크 로우',     subtitle: '레트로 스니커즈',  emoji: '👟' },
  ],
  '김치': [
    { name: '종가집 포기김치',   subtitle: '대상, 전통 방식',   emoji: '🥬' },
    { name: '비비고 김치',       subtitle: 'CJ, 깔끔한 맛',    emoji: '🥬' },
    { name: '처갓집 양념김치',   subtitle: '한성식품, 남도식',  emoji: '🥬' },
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
    if (name === keyword || name === keyword + ' ') return options;
  }
  return null;
}

// ── 인기 태그 ─────────────────────────────────────────────
const POPULAR_TAGS = [
  { label: '에어팟 프로', value: '에어팟 프로' },
  { label: '갤럭시 S25', value: '갤럭시 S25' },
  { label: '아이패드',   value: '아이패드' },
  { label: '다이슨',     value: '다이슨' },
  { label: '나이키',     value: '나이키' },
  { label: 'PS5',       value: 'ps5' },
];

const CATEGORIES = [
  '전자기기', '가전', '패션/의류', '뷰티/화장품', '식품',
  '스포츠/아웃도어', '가구/인테리어', '유아/키즈', '도서/문구',
  '자동차/바이크', '게임/취미', '기타',
];

const CAT_MAP: Record<string, string> = {
  '무선이어폰': '전자기기', '이어폰': '전자기기', '스마트폰': '전자기기', '노트북': '전자기기',
  '태블릿': '전자기기', '모니터': '전자기기', '게임기': '전자기기', '카메라': '전자기기',
  'TV': '전자기기', '스피커': '전자기기', '스마트워치': '전자기기',
  '헤어스타일러': '가전', '청소기': '가전', '냉장고': '가전', '세탁기': '가전',
  '에어컨': '가전', '공기청정기': '가전',
  '운동화': '스포츠/아웃도어', '등산화': '스포츠/아웃도어', '러닝화': '스포츠/아웃도어',
  '쌀': '식품', '식품': '식품', '라면': '식품', '음료': '식품',
  '의류': '패션/의류', '신발': '패션/의류', '가방': '패션/의류',
  '화장품': '뷰티/화장품', '스킨케어': '뷰티/화장품',
  '가구': '가구/인테리어',
};

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

// ── 기본 인풋 ─────────────────────────────────────────────
function TextInput({
  label, value, onChange, placeholder, required, aiFilled,
}: {
  label: string; value: string; onChange: (s: string) => void; placeholder?: string; required?: boolean; aiFilled?: boolean;
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
          background: C.bgInput,
          border: `1px solid ${aiFilled ? `${C.green}50` : C.border}`,
          color: C.textPri,
        }}
      />
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────
export default function DealCreatePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);

  // Step 1: 상품 입력
  const [productName,      setProductName]      = useState('');
  const [freeText,         setFreeText]         = useState('');
  const [aiLoading,        setAiLoading]        = useState(false);
  const [showModelSelect,  setShowModelSelect]  = useState(false);
  const [modelOptions,     setModelOptions]     = useState<ModelOption[]>([]);

  // AI 결과
  const [aiResult,         setAiResult]         = useState<AIResult | null>(null);

  // Step 2: 상품 정보 확인
  const [category,              setCategory]              = useState('');
  const [brand,                 setBrand]                 = useState('');
  const [brandCandidates,       setBrandCandidates]       = useState<string[]>([]);
  const [brandCustomMode,       setBrandCustomMode]       = useState(false);
  const [productNameConfirmed,  setProductNameConfirmed]  = useState('');
  const [productDetail,         setProductDetail]         = useState('');
  const [productCode,           setProductCode]           = useState('');
  const [conditionNew,          setConditionNew]          = useState(true);
  const [optionGroups,          setOptionGroups]          = useState<OptionGroup[]>([]);
  const [aiFilledFields,        setAiFilledFields]        = useState<Set<string>>(new Set());

  // Step 3: 기타 요청사항
  const [freeTextNote,    setFreeTextNote]    = useState('');

  // Step 4: 생성
  const [creating, setCreating] = useState(false);

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

  useEffect(() => {
    if (step > 1) window.history.pushState({ step }, '');
  }, [step]);

  useEffect(() => {
    if (showModelSelect) window.history.pushState({ step, showModelSelect: true }, '');
  }, [showModelSelect, step]);

  useEffect(() => {
    const handlePopState = () => {
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

  // ── AI 분석 로직 ───────────────────────────────────────
  const runAIAnalysis = async (name: string, text: string) => {
    setAiLoading(true);
    let result: AIResult;

    if (FEATURES.USE_API_AI) {
      const apiResult = await aiDealHelper(name, text);
      if (apiResult && typeof apiResult === 'object' && 'canonical_name' in apiResult) {
        const api = apiResult as Record<string, unknown>;
        const priceObj = (api.price ?? {}) as Record<string, unknown>;
        result = {
          canonical_name: api.canonical_name as string,
          model_name: api.model_name as string,
          brand: (api.brand as string) ?? null,
          brands: (api.brands as string[]) ?? [],
          product_code: (api.product_code as string) ?? null,
          product_detail: (api.product_detail as string) ?? null,
          normalized_free_text: (api.normalized_free_text as string) ?? null,
          category: (api.category as string) ?? null,
          suggested_options: ((api.suggested_options ?? []) as AIResult['suggested_options']).map(o => ({
            title: o.title,
            selected_value: o.selected_value ?? null,
            values: o.values,
          })),
          price: {
            center_price: (priceObj.center_price as number) ?? null,
            desired_price_suggestion: (priceObj.desired_price_suggestion as number) ?? null,
            max_budget_suggestion: (priceObj.max_budget_suggestion as number) ?? null,
            commentary: (priceObj.commentary as string) ?? null,
            price_source: (priceObj.price_source as string) ?? null,
          },
        };
        await new Promise(r => setTimeout(r, 500));
      } else {
        await new Promise(r => setTimeout(r, 2000));
        result = generateMockAIResult(name, text);
      }
    } else {
      await new Promise(r => setTimeout(r, 2000));
      result = generateMockAIResult(name, text);
    }

    setAiResult(result);

    // ── Step 2 필드 자동 채움 ──
    const filled = new Set<string>();

    // 카테고리
    if (result.category) {
      const apiCat = result.category;
      const mapped = CAT_MAP[apiCat] || CATEGORIES.find(c => apiCat.includes(c) || c.includes(apiCat));
      setCategory(mapped || '기타');
      filled.add('category');
    } else {
      setCategory('');
    }

    // 브랜드
    const brands = result.brands ?? [];
    if (result.brand && !brands.includes(result.brand)) brands.unshift(result.brand);
    setBrandCandidates(brands);
    if (brands.length > 0) {
      setBrand(brands[0]);
      setBrandCustomMode(false);
      filled.add('brand');
    } else {
      setBrand('');
      setBrandCustomMode(true);
    }

    // 상품명
    setProductNameConfirmed(result.model_name || name);
    if (result.model_name) filled.add('productName');

    // 제품명
    setProductDetail(result.product_detail || result.canonical_name || '');
    if (result.product_detail || result.canonical_name) filled.add('productDetail');

    // 제품코드
    setProductCode(result.product_code || '');
    if (result.product_code) filled.add('productCode');

    // 신품 기본
    setConditionNew(true);

    // 옵션 그룹
    const groups: OptionGroup[] = result.suggested_options.map(o => ({
      title: o.title,
      values: [...o.values],
    }));
    setOptionGroups(groups);
    if (groups.length > 0) filled.add('options');

    setAiFilledFields(filled);
    setFreeTextNote('');
    setAiLoading(false);
    goTo(2);
  };

  // ── 분석 버튼 ────────────────────────────────────────
  const handleAIAnalysis = async () => {
    const ambiguousOptions = findAmbiguousProduct(productName);
    if (ambiguousOptions && !showModelSelect) {
      setModelOptions(ambiguousOptions);
      setShowModelSelect(true);
      return;
    }
    await runAIAnalysis(productName, freeText);
  };

  const handleModelSelect = (model: ModelOption) => {
    setProductName(model.name);
    setShowModelSelect(false);
    setModelOptions([]);
    setTimeout(() => runAIAnalysis(model.name, freeText), 100);
  };

  // ── 옵션 그룹 핸들러 ──────────────────────────────────
  const updateGroupTitle = (idx: number, title: string) => {
    setOptionGroups(prev => prev.map((g, i) => i === idx ? { ...g, title } : g));
  };
  const addValueToGroup = (idx: number, val: string) => {
    if (!val.trim()) return;
    setOptionGroups(prev => prev.map((g, i) =>
      i === idx ? { ...g, values: [...g.values, val.trim()] } : g
    ));
  };
  const removeValueFromGroup = (gIdx: number, vIdx: number) => {
    setOptionGroups(prev => prev.map((g, i) =>
      i === gIdx ? { ...g, values: g.values.filter((_, j) => j !== vIdx) } : g
    ));
  };
  const removeGroup = (idx: number) => {
    setOptionGroups(prev => prev.filter((_, i) => i !== idx));
  };
  const addGroup = () => {
    if (optionGroups.length >= 5) return;
    setOptionGroups(prev => [...prev, { title: '', values: [] }]);
  };

  // ── 딜 생성 API ─────────────────────────────────────
  const handleCreate = async () => {
    setCreating(true);
    try {
      const dealData = {
        product_name: productNameConfirmed || productName,
        creator_id: user?.id ?? 1,
        category: category || null,
        brand: brand || null,
        product_detail: productDetail || null,
        product_code: productCode || null,
        condition: conditionNew ? 'new' : 'refurbished',
        options: optionGroups.length > 0 ? JSON.stringify(optionGroups) : null,
        free_text: freeTextNote || null,
        desired_qty: 1,
        anchor_price: aiResult?.price?.center_price || null,
      };
      const res = await apiClient.post(API.DEALS.CREATE, dealData);
      const newDealId = res.data?.id;
      showToast('딜이 생성되었어요!', 'success');
      setTimeout(() => navigate(newDealId ? `/deal/${newDealId}` : '/deals'), 1200);
    } catch (err: unknown) {
      console.error('딜 생성 실패:', err);
      showToast('딜 생성에 실패했어요. 다시 시도해주세요.', 'error');
    } finally {
      setCreating(false);
    }
  };

  // ── TopBar ─────────────────────────────────────────
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
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.3)', borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />
      )}
      {label}
    </button>
  );

  const skipBtn = (onClick: () => void) => (
    <button
      onClick={onClick}
      style={{
        background: 'none', border: 'none', color: C.textDim, fontSize: 13,
        cursor: 'pointer', padding: '8px 0', textDecoration: 'underline',
      }}
    >
      건너뛰기
    </button>
  );

  // ── 옵션 태그 입력 컴포넌트 ────────────────────────────
  const OptionGroupEditor = ({ group, gIdx }: { group: OptionGroup; gIdx: number }) => {
    const [newVal, setNewVal] = useState('');
    return (
      <div style={{
        ...cardStyle,
        borderColor: aiFilledFields.has('options') ? `${C.green}40` : C.border,
        padding: '14px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <input
            value={group.title}
            onChange={e => updateGroupTitle(gIdx, e.target.value)}
            placeholder="옵션명 (예: 색상)"
            className="dc-input"
            style={{
              flex: 1, padding: '8px 10px', fontSize: 13, borderRadius: 8,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
            }}
          />
          <button
            onClick={() => removeGroup(gIdx)}
            style={{
              width: 28, height: 28, borderRadius: 8, background: 'rgba(255,45,120,0.15)',
              border: 'none', color: C.magenta, fontSize: 14, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >✕</button>
        </div>

        {/* 태그들 */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {group.values.map((val, vIdx) => (
            <span key={vIdx} style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '5px 10px', borderRadius: 16, fontSize: 12, fontWeight: 600,
              background: `${C.cyan}15`, border: `1px solid ${C.cyan}30`, color: C.cyan,
            }}>
              {val}
              <button
                onClick={() => removeValueFromGroup(gIdx, vIdx)}
                style={{
                  background: 'none', border: 'none', color: C.cyan, fontSize: 12,
                  cursor: 'pointer', padding: 0, lineHeight: 1,
                }}
              >✕</button>
            </span>
          ))}
        </div>

        {/* 값 추가 */}
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={newVal}
            onChange={e => setNewVal(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') { e.preventDefault(); addValueToGroup(gIdx, newVal); setNewVal(''); }
            }}
            placeholder="값 입력 후 Enter"
            className="dc-input"
            style={{
              flex: 1, padding: '7px 10px', fontSize: 12, borderRadius: 8,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
            }}
          />
          <button
            onClick={() => { addValueToGroup(gIdx, newVal); setNewVal(''); }}
            style={{
              padding: '7px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
              background: `${C.cyan}20`, border: `1px solid ${C.cyan}40`, color: C.cyan,
              cursor: 'pointer',
            }}
          >+ 추가</button>
        </div>
      </div>
    );
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, overflow: 'hidden' }}>
      <style>{`
        @keyframes spin     { to { transform: rotate(360deg); } }
        @keyframes ppBlink  { 0%,100%{opacity:1} 50%{opacity:0.45} }
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
      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
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
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', damping: 26, stiffness: 300 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: 0 }}
                >
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
                          padding: '16px 18px', background: C.bgCard,
                          border: `1px solid ${C.border}`, borderRadius: 14,
                          textAlign: 'left', cursor: 'pointer', width: '100%',
                          transition: 'border-color 0.15s, background 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = `${C.cyan}55`; e.currentTarget.style.background = `${C.cyan}08`; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.background = C.bgCard; }}
                      >
                        <span style={{ fontSize: 28, flexShrink: 0 }}>{model.emoji}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 600, color: C.textPri }}>{model.name}</div>
                          <div style={{ fontSize: 12, color: C.textDim, marginTop: 2 }}>{model.subtitle}</div>
                        </div>
                        <span style={{ fontSize: 18, color: C.textDim }}>›</span>
                      </motion.button>
                    ))}
                  </div>
                  <button
                    onClick={() => { setShowModelSelect(false); setModelOptions([]); }}
                    style={{
                      marginTop: 20, width: '100%', padding: 14,
                      background: 'transparent', border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: 12, color: C.textSec, fontSize: 14, cursor: 'pointer',
                    }}
                  >← 다시 입력하기</button>
                </motion.div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 8 }}>
                      어떤 상품을<br />원하시나요?
                    </div>
                    <div style={{ fontSize: 13, color: C.textSec }}>
                      찾고 있는 상품의 이름을 알려주세요.<br />
                      핑퐁이 AI가 상품 정보를 분석해드려요 🎯
                    </div>
                  </div>

                  <TextInput
                    label="상품명" required
                    value={productName} onChange={setProductName}
                    placeholder="예: 에어팟 프로 2세대"
                  />

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>추가 설명 (선택)</label>
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
                      여기에 적은 내용을 AI가 분석해서 옵션을 자동으로 설정해드려요
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 12, color: C.textSec, marginBottom: 10 }}>이런 딜이 인기 있어요</div>
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
                        >{tag.label}</button>
                      ))}
                    </div>
                  </div>

                  {primaryBtn('🔍 핑퐁이 AI 분석하기', handleAIAnalysis, !productName.trim())}
                </div>
              )
            )}

            {/* ══ Step 2: 상품 정보 확인 ══ */}
            {step === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 6 }}>
                    🎯 상품 정보 확인
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec }}>AI가 분석한 정보를 확인하고 수정해주세요</div>
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
                        background: C.bgInput,
                        border: `1px solid ${aiFilledFields.has('category') ? `${C.green}50` : C.border}`,
                        color: C.textPri,
                      }}
                    >
                      <option value="">선택해주세요</option>
                      {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <span style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, pointerEvents: 'none', fontSize: 12 }}>▾</span>
                  </div>
                </div>

                {/* 브랜드 */}
                <div>
                  <SectionTitle>🏢 브랜드</SectionTitle>
                  {!brandCustomMode && brandCandidates.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {brandCandidates.map(b => (
                          <button
                            key={b}
                            onClick={() => setBrand(b)}
                            style={{
                              padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600,
                              background: brand === b ? `${C.cyan}18` : C.bgSurface,
                              border: `1.5px solid ${brand === b ? C.cyan : C.border}`,
                              color: brand === b ? C.cyan : C.textSec,
                              cursor: 'pointer', transition: 'all 0.15s',
                            }}
                          >{b}{brand === b && ' ✓'}</button>
                        ))}
                        <button
                          onClick={() => { setBrandCustomMode(true); setBrand(''); }}
                          style={{
                            padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600,
                            background: C.bgSurface, border: `1.5px solid ${C.border}`,
                            color: C.textDim, cursor: 'pointer',
                          }}
                        >직접 입력</button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <input
                        value={brand}
                        onChange={e => setBrand(e.target.value)}
                        placeholder="브랜드명 입력"
                        className="dc-input"
                        style={{
                          padding: '13px 14px', fontSize: 14, borderRadius: 12,
                          background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
                        }}
                      />
                      {brandCandidates.length > 0 && (
                        <button
                          onClick={() => { setBrandCustomMode(false); setBrand(brandCandidates[0]); }}
                          style={{ background: 'none', border: 'none', color: C.cyan, fontSize: 12, cursor: 'pointer', textAlign: 'left', padding: '2px 0' }}
                        >← AI 추천 브랜드 보기</button>
                      )}
                    </div>
                  )}
                </div>

                {/* 상품명 */}
                <TextInput
                  label="🏷️ 상품명" required
                  value={productNameConfirmed} onChange={setProductNameConfirmed}
                  placeholder="예: 에어팟 프로 2세대"
                  aiFilled={aiFilledFields.has('productName')}
                />

                {/* 제품명 (상세) */}
                <TextInput
                  label="📝 제품명 (상세)"
                  value={productDetail} onChange={setProductDetail}
                  placeholder="예: 종가집 포기김치 2.5kg"
                  aiFilled={aiFilledFields.has('productDetail')}
                />

                {/* 제품코드 */}
                <TextInput
                  label="🔢 제품코드 / 모델번호"
                  value={productCode} onChange={setProductCode}
                  placeholder="예: SM-S936N, MTJV3KH/A"
                  aiFilled={aiFilledFields.has('productCode')}
                />

                {/* 신품 여부 */}
                <div>
                  <SectionTitle>✨ 신품 여부</SectionTitle>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button
                      onClick={() => setConditionNew(true)}
                      style={{
                        flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                        background: conditionNew ? `${C.green}15` : C.bgSurface,
                        border: `1.5px solid ${conditionNew ? C.green : C.border}`,
                        color: conditionNew ? C.green : C.textSec,
                        cursor: 'pointer', transition: 'all 0.15s',
                      }}
                    >신품{conditionNew && ' ✓'}</button>
                    <button
                      onClick={() => {
                        showToast('추후 선택 가능하도록 개발 예정이에요!', 'info');
                        setConditionNew(true);
                      }}
                      style={{
                        flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                        background: C.bgSurface, border: `1.5px solid ${C.border}`,
                        color: C.textDim, cursor: 'pointer', transition: 'all 0.15s',
                      }}
                    >리퍼/중고</button>
                  </div>
                </div>

                {/* 옵션 그룹 */}
                <div>
                  <SectionTitle>📦 옵션</SectionTitle>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {optionGroups.map((group, gIdx) => (
                      <OptionGroupEditor key={gIdx} group={group} gIdx={gIdx} />
                    ))}
                    {optionGroups.length < 5 && (
                      <button
                        onClick={addGroup}
                        style={{
                          padding: '12px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                          background: 'transparent', border: `1.5px dashed ${C.border}`,
                          color: C.textDim, cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >+ 옵션그룹 추가</button>
                    )}
                  </div>
                </div>

                {/* 버튼 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
                  {primaryBtn('다음', () => goTo(3))}
                  {skipBtn(() => goTo(3))}
                </div>
              </div>
            )}

            {/* ══ Step 3: 기타 요청사항 ══ */}
            {step === 3 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 8 }}>
                    📝 기타 요청사항
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec }}>
                    추가로 원하는 조건이 있으면 자유롭게 작성해주세요
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <textarea
                    value={freeTextNote}
                    onChange={e => {
                      if (e.target.value.length <= 500) setFreeTextNote(e.target.value);
                    }}
                    placeholder="희망 수량, 가격, 배송 조건 등 자유롭게 입력해주세요"
                    rows={6}
                    className="dc-input"
                    style={{
                      padding: '14px 16px', fontSize: 14, borderRadius: 12, resize: 'none',
                      background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
                      lineHeight: 1.6,
                    }}
                  />
                  <div style={{ fontSize: 11, color: freeTextNote.length >= 450 ? C.orange : C.textDim, textAlign: 'right' }}>
                    {freeTextNote.length}/500
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
                  {primaryBtn('다음', () => goTo(4))}
                  {skipBtn(() => goTo(4))}
                </div>
              </div>
            )}

            {/* ══ Step 4: 최종 확인 + 딜 만들기 ══ */}
            {step === 4 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: C.textPri }}>📋 딜 요약</div>

                <div style={{ ...cardStyle }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 14, marginBottom: 14, borderBottom: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: 24 }}>🏷️</span>
                    <div style={{ fontSize: 15, fontWeight: 800, color: C.textPri }}>
                      {productNameConfirmed || productName}
                    </div>
                  </div>

                  {[
                    { label: '카테고리',   value: category || '-' },
                    { label: '브랜드',     value: brand || '-' },
                    { label: '제품명',     value: productDetail || '-' },
                    { label: '제품코드',   value: productCode || '-' },
                    { label: '신품 여부',  value: conditionNew ? '신품' : '리퍼/중고' },
                    { label: '옵션',       value: optionGroups.length > 0
                      ? optionGroups.map(g => `${g.title}: ${g.values.join(', ')}`).join(' / ')
                      : '없음' },
                    ...(freeTextNote ? [{ label: '기타 요청', value: freeTextNote }] : []),
                  ].map(({ label, value }, idx, arr) => (
                    <div
                      key={label}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                        padding: '10px 0', gap: 16,
                        borderBottom: idx < arr.length - 1 ? `1px solid ${C.border}` : 'none',
                      }}
                    >
                      <span style={{ fontSize: 13, color: C.textSec, flexShrink: 0, minWidth: 70 }}>{label}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri, textAlign: 'right', wordBreak: 'break-word' }}>{value}</span>
                    </div>
                  ))}
                </div>

                <div style={{
                  background: `${C.orange}10`, border: `1px solid ${C.orange}30`,
                  borderRadius: 12, padding: '12px 14px',
                  fontSize: 12, color: C.textSec, lineHeight: 1.6,
                }}>
                  딜이 생성되면 판매자들이 오퍼를 보내기 시작해요. 가격/수량 등 구매 조건은 오퍼 단계에서 설정됩니다.
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    onClick={() => goTo(2)}
                    style={{
                      flex: 1, padding: '14px', borderRadius: 14, fontSize: 14, fontWeight: 700,
                      background: 'transparent', border: `1px solid ${C.border}`,
                      color: C.textSec, cursor: 'pointer',
                    }}
                  >수정하기</button>
                  <button
                    onClick={handleCreate}
                    disabled={creating}
                    style={{
                      flex: 2, padding: '14px', borderRadius: 14, fontSize: 15, fontWeight: 800,
                      background: creating ? `${C.cyan}30` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                      color: creating ? C.textSec : '#0a0e1a',
                      cursor: creating ? 'not-allowed' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    }}
                  >
                    {creating && (
                      <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.3)', borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />
                    )}
                    🚀 딜 만들기
                  </button>
                </div>
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
