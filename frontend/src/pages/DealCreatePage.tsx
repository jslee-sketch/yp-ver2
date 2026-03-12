import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { aiDealHelper, aiRecalcPrice, aiImageRecognize } from '../api/aiApi';
import { FEATURES } from '../config';
import { showToast } from '../components/common/Toast';
import MatrixCodeRain from '../components/effects/MatrixCodeRain';
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
type PriceAnalysisItem = {
  title: string;
  price: number;
  link?: string | null;
  mall?: string | null;
  reason?: string | null;
};
type PriceAnalysisData = {
  lowest_price: number | null;
  included_items: PriceAnalysisItem[];
  excluded_items: PriceAnalysisItem[];
  total_searched: number;
  total_included: number;
  total_excluded: number;
  notice?: string | null;
  fallback_price?: number | null;
};
// ── 가격 합의 엔진 타입 ─────────────────────────────────
type PriceConsensusSource = {
  source: string;
  source_label: string;
  price: number;
  lowest_price: number;
  items: { title: string; price: number; link?: string }[];
  count: number;
  suspicious: boolean;
  suspicion_reason: string;
};
type PriceConsensus = {
  market_price: number;
  confidence: string;
  confidence_emoji: string;
  confidence_label: string;
  confidence_color: string;
  sources: PriceConsensusSource[];
  source_count: number;
  notice: string | null;
  fallback_price: number | null;
  user_target_price: number;
  luxury_warning?: string;
};

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
  price_analysis?: PriceAnalysisData | null;
  category?: string | null;
  warnings?: string[];
};

// ── 옵션 그룹 타입 ───────────────────────────────────────
interface OptionGroup {
  title: string;
  values: string[];
  selectedIndex: number;  // 선택된 값 인덱스 (-1 = 미선택)
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
  // 사진 인식 (최대 3장)
  type ImageRecResult = {
    product_name: string; brand?: string | null;
    model_name?: string | null; specs?: string | null;
    confidence: string;
  };
  const [imagePreviews,   setImagePreviews]   = useState<string[]>([]);
  const [imageResults,    setImageResults]    = useState<(ImageRecResult | null)[]>([]);
  const [recognizingIdx,  setRecognizingIdx]  = useState(-1);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // 음성 인식
  type VoiceResult = {
    transcript: string; product_query?: string | null; brand?: string | null;
    product_name?: string | null; target_price?: number | null;
    quantity?: number | null; options?: string[] | null; confidence: string;
  };
  const [isRecording,    setIsRecording]    = useState(false);
  const [recordingTime,  setRecordingTime]  = useState(0);
  const [voiceLoading,   setVoiceLoading]   = useState(false);
  const [voiceResult,    setVoiceResult]    = useState<VoiceResult | null>(null);
  const [audioLevel,     setAudioLevel]     = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const timerRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const analyserRef      = useRef<AnalyserNode | null>(null);
  const audioCtxRef      = useRef<AudioContext | null>(null);
  const animFrameRef     = useRef<number>(0);

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
  const [similarDeals,          setSimilarDeals]          = useState<any[]>([]);

  // Step 3: 가격 챌린지 + 목표가격 + 수량
  const [marketPrice,     setMarketPrice]     = useState<number | null>(null);
  const [targetPrice,     setTargetPrice]     = useState('');
  const [quantity,        setQuantity]        = useState(1);
  const [, setPriceCommentary] = useState('');
  // 가격 챌린지 신규 상태
  const [guessPrice,      setGuessPrice]      = useState('');
  const [isAnalyzing,     setIsAnalyzing]     = useState(false);
  const [loadingMsg,      setLoadingMsg]      = useState('');
  const [reaction,        setReaction]        = useState('');
  const [priceAnalysis,   setPriceAnalysis]   = useState<PriceAnalysisData | null>(null);
  const [consensus,       setConsensus]       = useState<PriceConsensus | null>(null);
  const [showConsensus,   setShowConsensus]   = useState(false);
  const [discountPercent, setDiscountPercent] = useState(8);
  const [showExcluded,    setShowExcluded]    = useState(false);
  const [marketChecked,   setMarketChecked]   = useState(false);

  // Step 4: 기타 요청사항
  const [freeTextNote,    setFreeTextNote]    = useState('');

  // Step 5: 생성
  const [creating, setCreating] = useState(false);

  // 옵션 입력값 (parent-level로 관리 → 리렌더링 시 소실 방지)
  const [optionInputs, setOptionInputs] = useState<Record<number, string>>({});
  const isTypingRef = useRef(false);

  // 스크롤 위치 보존용 (타이핑 중에는 복원 안 함)
  const scrollRef = useRef(0);
  useEffect(() => {
    if (!isTypingRef.current) window.scrollTo(0, scrollRef.current);
  }, [optionGroups]);

  // ── Step 3 진입 시 상태 초기화 ─────────────
  const prevStepRef = useRef(step);
  useEffect(() => {
    if (step === 3 && prevStepRef.current === 2) {
      // 2→3 진입: 가격 챌린지 상태 초기화
      setMarketChecked(false);
      setReaction('');
      setPriceAnalysis(null);
      setConsensus(null);
      setShowConsensus(false);
      setShowExcluded(false);
      // 음성 인식 희망가 자동 채우기
      if (voiceResult?.target_price && !guessPrice) {
        setGuessPrice(voiceResult.target_price.toLocaleString('ko-KR'));
      }
    }
    prevStepRef.current = step;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // ── 가격 챌린지: "맞춰보기" 분석 ─────────────
  const loadingMessages = ['시장을 조사하고 있어요...', '네이버쇼핑 검색 중...', '쿠팡 가격 조회 중...', 'AI 시장가 추정 중...', '부품/액세서리 걸러내는 중...', '3중 소스 교차 검증 중...', '신뢰도 등급 판정 중...'];
  const startPriceChallenge = async () => {
    const gp = Number(guessPrice.replace(/,/g, ''));
    if (!gp || gp <= 0) return;
    setIsAnalyzing(true);
    setReaction('');
    setPriceAnalysis(null);
    let msgIdx = 0;
    const iv = setInterval(() => { setLoadingMsg(loadingMessages[msgIdx % loadingMessages.length]); msgIdx++; }, 600);
    try {
      const selectedOptStr = optionGroups
        .filter(g => g.selectedIndex >= 0 && g.selectedIndex < g.values.length)
        .map(g => g.values[g.selectedIndex]).join(' ');
      const searchQuery = [productDetail || productNameConfirmed || productName, selectedOptStr].filter(Boolean).join(' ');
      const result = await aiRecalcPrice(searchQuery, selectedOptStr || undefined, brand || undefined);
      // price_analysis
      const pa = (result as any)?.price_analysis as PriceAnalysisData | null;
      if (pa) setPriceAnalysis(pa);
      // price_consensus (3중 소스 합의)
      const pc = (result as any)?.price_consensus as PriceConsensus | null;
      if (pc) { setConsensus(pc); setShowConsensus(false); }

      // notice가 있으면 (고가 제품 등) fallback 처리
      // consensus notice 우선 적용
      const effectiveNotice = pc?.notice || pa?.notice;
      if (effectiveNotice) {
        const fbp = pc?.fallback_price || pa?.fallback_price || gp;
        setMarketPrice(pc?.market_price || fbp);
        setPriceCommentary(effectiveNotice);
        setReaction(effectiveNotice);
        setTargetPrice(String(gp));
        setDiscountPercent(0);
      } else if (pc && pc.market_price > 0) {
        // consensus 시장가 우선 사용
        const mp = pc.market_price;
        setMarketPrice(mp);
        setPriceCommentary(`${pc.confidence_emoji} ${pc.confidence_label} (${pc.source_count}개 소스 교차 검증)`);
        const diff = Math.abs(gp - mp) / mp * 100;
        if (diff <= 5) setReaction(`${pc.confidence_emoji} 거의 맞추셨어요! (${pc.confidence_label})`);
        else if (diff <= 20) setReaction(`${pc.confidence_emoji} 꽤 괜찮은 감이에요! (${pc.confidence_label})`);
        else setReaction(`${pc.confidence_emoji} 의외의 가격이죠? 아래 시장 분석을 확인해보세요.`);
        setTargetPrice(String(gp));
        const pct = Math.max(0, Math.min(50, Math.round((1 - gp / mp) * 100)));
        setDiscountPercent(pct >= 0 ? pct : 0);
      } else if (result?.price?.center_price) {
        const mp = result.price.center_price;
        setMarketPrice(mp);
        setPriceCommentary(result.price.commentary || '');
        if (pa?.lowest_price) setMarketPrice(pa.lowest_price);
        const finalMp = pa?.lowest_price || mp;
        // 반응 메시지
        const diff = Math.abs(gp - finalMp) / finalMp * 100;
        if (diff <= 5) setReaction('거의 맞추셨어요! 가격 감각이 좋으시네요.');
        else if (diff <= 20) setReaction('꽤 괜찮은 감이에요!');
        else setReaction('의외의 가격이죠? 아래 근거를 확인해보세요.');
        // 초기 목표가 = 예상가
        setTargetPrice(String(gp));
        const pct = Math.max(0, Math.min(50, Math.round((1 - gp / finalMp) * 100)));
        setDiscountPercent(pct >= 0 ? pct : 0);
      } else {
        setReaction('시장가 정보를 찾지 못했어요. 직접 목표가를 입력해주세요.');
      }
      setMarketChecked(true);
    } catch { setReaction('분석 중 오류가 발생했어요.'); setMarketChecked(true); }
    finally { clearInterval(iv); setIsAnalyzing(false); setLoadingMsg(''); }
  };

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

    // 옵션 그룹 (selected_value가 있으면 해당 인덱스 선택)
    const groups: OptionGroup[] = result.suggested_options.map(o => {
      const selIdx = o.selected_value ? o.values.indexOf(o.selected_value) : 0;
      return { title: o.title, values: [...o.values], selectedIndex: selIdx >= 0 ? selIdx : 0 };
    });
    setOptionGroups(groups);
    if (groups.length > 0) filled.add('options');

    setAiFilledFields(filled);
    setFreeTextNote('');

    // Step 3 가격 자동 채움
    setMarketPrice(result.price?.center_price || null);
    setTargetPrice(''); // 빈칸 — 사용자가 직접 입력
    setPriceCommentary(result.price?.commentary || '');
    setQuantity(1);

    // 유사 딜 체크 (비동기 — 블로킹하지 않음)
    setSimilarDeals([]);
    try {
      const pn = result.product_detail || result.canonical_name || result.model_name || name;
      const br = result.brand || '';
      const resp = await apiClient.get(API.DEALS.FIND_SIMILAR, { params: { product_name: pn, brand: br } });
      if (resp.data?.similar_deals?.length > 0) setSimilarDeals(resp.data.similar_deals);
    } catch { /* ignore */ }

    setAiLoading(false);
    goTo(2);
  };

  // ── 사진 인식 (최대 3장) ─────────────────────────────
  const confOrder: Record<string, number> = { high: 3, medium: 2, low: 1 };

  const applyBestRecognition = (results: (ImageRecResult | null)[]) => {
    const valid = results.filter((r): r is ImageRecResult => !!r && !!r.product_name);
    if (valid.length === 0) return;
    const best = valid.reduce((a, b) => (confOrder[a.confidence] || 0) >= (confOrder[b.confidence] || 0) ? a : b);
    if (best.confidence !== 'low') {
      setProductName([best.brand, best.product_name].filter(Boolean).join(' ').trim());
      if (best.specs && !freeText) setFreeText(best.specs);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (imagePreviews.length >= 3) {
      showToast('사진은 최대 3장까지 가능합니다.', 'info');
      return;
    }

    const idx = imagePreviews.length;
    setImagePreviews(prev => [...prev, URL.createObjectURL(file)]);
    setImageResults(prev => [...prev, null]);
    setRecognizingIdx(idx);

    try {
      const result = await aiImageRecognize(file);
      const rec: ImageRecResult = result && result.product_name
        ? result
        : { product_name: '', confidence: 'low' };
      setImageResults(prev => {
        const next = [...prev];
        next[idx] = rec;
        applyBestRecognition(next);
        return next;
      });
    } catch {
      setImageResults(prev => {
        const next = [...prev];
        next[idx] = { product_name: '', confidence: 'low' };
        return next;
      });
    } finally {
      setRecognizingIdx(-1);
      if (imageInputRef.current) imageInputRef.current.value = '';
    }
  };

  const removeImage = (idx: number) => {
    setImagePreviews(prev => prev.filter((_, i) => i !== idx));
    setImageResults(prev => {
      const next = prev.filter((_, i) => i !== idx);
      applyBestRecognition(next);
      return next;
    });
  };

  // ── 음성 녹음 ────────────────────────────────────────
  const startRecording = async () => {
    console.log('[VOICE] startRecording called');
    try {
      console.log('[VOICE] requesting mic permission...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      console.log('[VOICE] mic stream obtained:', stream.getTracks().length, 'tracks');

      // 코덱 우선순위 (브라우저 호환)
      const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', ''];
      let mimeType = '';
      for (const mt of mimeTypes) {
        const supported = !mt || MediaRecorder.isTypeSupported(mt);
        console.log(`[VOICE] codec ${mt || '(default)'}: ${supported}`);
        if (supported && !mimeType) { mimeType = mt; break; }
      }
      console.log('[VOICE] selected mimeType:', mimeType || 'default');

      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      console.log('[VOICE] MediaRecorder created, state:', mr.state);
      chunksRef.current = [];

      mr.ondataavailable = (e) => {
        console.log('[VOICE] data chunk:', e.data.size, 'bytes');
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = () => {
        console.log('[VOICE] recording stopped, chunks:', chunksRef.current.length);
        stream.getTracks().forEach(t => t.stop());
        processVoice(mimeType);
      };

      mr.onerror = (e) => {
        console.error('[VOICE] recorder error:', e);
      };

      mr.start(250);
      console.log('[VOICE] recording started, state:', mr.state);
      mediaRecorderRef.current = mr;
      setIsRecording(true);
      setRecordingTime(0);
      setVoiceResult(null);

      // 실시간 오디오 레벨 시각화
      try {
        const audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        audioCtxRef.current = audioCtx;
        analyserRef.current = analyser;

        const updateLevel = () => {
          if (!analyserRef.current) return;
          const data = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(data);
          const avg = data.reduce((a, b) => a + b, 0) / data.length;
          setAudioLevel(avg);
          animFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (audioErr) {
        console.warn('[VOICE] AudioContext failed (visualization disabled):', audioErr);
      }

      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= 29) { stopRecording(); return 30; }
          return prev + 1;
        });
      }, 1000);
    } catch (err: unknown) {
      const e = err as { name?: string; message?: string };
      console.error('[VOICE] error:', e.name, e.message);
      if (e.name === 'NotAllowedError') {
        showToast('마이크 권한을 허용해주세요. 브라우저 주소창의 🔒 아이콘을 클릭하세요.', 'error');
      } else if (e.name === 'NotFoundError') {
        showToast('마이크를 찾을 수 없습니다. 마이크가 연결되어 있는지 확인해주세요.', 'error');
      } else if (e.name === 'NotReadableError') {
        showToast('마이크가 다른 앱에서 사용 중입니다.', 'error');
      } else {
        showToast(`음성 녹음 오류: ${e.message || '알 수 없는 오류'}`, 'error');
      }
    }
  };

  const stopRecording = () => {
    console.log('[VOICE] stopRecording called');
    console.log('[VOICE] recorder state:', mediaRecorderRef.current?.state);

    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      console.log('[VOICE] recorder.stop() called');
    }

    // 오디오 시각화 정리
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    analyserRef.current = null;
    if (audioCtxRef.current) { audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null; }
    setAudioLevel(0);
    setIsRecording(false);
  };

  const processVoice = async (mimeType?: string) => {
    if (chunksRef.current.length === 0) {
      console.log('[VOICE] no chunks to process');
      return;
    }
    const blob = new Blob(chunksRef.current, { type: mimeType || chunksRef.current[0]?.type || 'audio/webm' });
    console.log('[VOICE] blob size:', blob.size, 'bytes, type:', blob.type);

    if (blob.size < 1000) {
      console.log('[VOICE] blob too small, skipping');
      showToast('음성이 너무 짧아요. 다시 시도해주세요.', 'error');
      return;
    }
    setVoiceLoading(true);
    try {
      const ext = (mimeType || '').includes('mp4') ? 'mp4'
        : (mimeType || '').includes('ogg') ? 'ogg'
        : 'webm';
      const form = new FormData();
      form.append('file', blob, `voice.${ext}`);
      console.log('[VOICE] sending to API, file: voice.' + ext, 'size:', blob.size);

      const resp = await apiClient.post(API.AI.DEAL_HELPER_VOICE, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      const data = resp.data as VoiceResult & { success: boolean };
      console.log('[VOICE] API response:', JSON.stringify(data).substring(0, 300));

      if (data.success && data.product_query) {
        setVoiceResult(data);
        setProductName(data.product_query);
        if (data.quantity && data.quantity > 0) setQuantity(data.quantity);
        showToast('음성 인식 완료!', 'success');
      } else if (data.transcript) {
        setVoiceResult(data);
        showToast('음성은 인식했지만 제품을 찾지 못했어요. 검색창에 직접 입력해주세요.', 'error');
      } else {
        showToast('음성을 인식하지 못했어요. 다시 시도해주세요.', 'error');
      }
    } catch (err: any) {
      console.error('[VOICE] API error:', err);
      // axios 에러에서 서버 응답 추출
      if (err?.response?.data) {
        const d = err.response.data;
        console.error('[VOICE] server response:', d);
        const detail = d.detail || d.error || '서버 오류';
        showToast(`음성 인식 실패: ${detail}`, 'error');
      } else if (err?.message?.includes('timeout')) {
        showToast('음성 인식 시간 초과. 더 짧게 녹음해주세요.', 'error');
      } else {
        showToast('음성 인식 서버 연결에 실패했습니다. 다시 시도해주세요.', 'error');
      }
    }
    setVoiceLoading(false);
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
  const saveScroll = () => { scrollRef.current = window.scrollY; };

  const updateGroupTitle = (idx: number, title: string) => {
    saveScroll();
    setOptionGroups(prev => prev.map((g, i) => i === idx ? { ...g, title } : g));
  };
  const addValueToGroup = (idx: number, val: string) => {
    if (!val.trim()) return;
    saveScroll();
    setOptionGroups(prev => prev.map((g, i) =>
      i === idx ? { ...g, values: [...g.values, val.trim()] } : g
    ));
  };
  const selectValueInGroup = (gIdx: number, vIdx: number) => {
    saveScroll();
    setOptionGroups(prev => prev.map((g, i) =>
      i === gIdx ? { ...g, selectedIndex: vIdx } : g
    ));
  };
  const removeGroup = (idx: number) => {
    saveScroll();
    setOptionGroups(prev => prev.filter((_, i) => i !== idx));
  };
  const addGroup = () => {
    if (optionGroups.length >= 10) return;
    saveScroll();
    setOptionGroups(prev => [...prev, { title: '', values: [], selectedIndex: -1 }]);
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
        options: optionGroups.length > 0 ? JSON.stringify(optionGroups.map(g => ({
          title: g.title,
          values: g.values,
          selected_value: g.selectedIndex >= 0 && g.selectedIndex < g.values.length ? g.values[g.selectedIndex] : null,
        }))) : null,
        free_text: freeTextNote || null,
        desired_qty: quantity,
        target_price: targetPrice ? Number(targetPrice) : null,
        market_price: marketPrice || null,
        anchor_price: aiResult?.price?.center_price || null,
        price_evidence: priceAnalysis ? JSON.stringify(priceAnalysis) : null,
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

  // ── 옵션항목(사양) 에디터 (인라인 — parent state 사용) ──
  const renderOptionGroup = (group: OptionGroup, gIdx: number) => {
    const inputVal = optionInputs[gIdx] || '';
    return (
      <div key={gIdx} style={{
        ...cardStyle,
        borderColor: aiFilledFields.has('options') ? `${C.green}40` : C.border,
        padding: '14px 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <input
            value={group.title}
            onChange={e => updateGroupTitle(gIdx, e.target.value)}
            onFocus={() => { isTypingRef.current = true; }}
            onBlur={() => { isTypingRef.current = false; }}
            placeholder="옵션항목(사양) 이름 (예: 색상)"
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

        {/* 옵션값 라디오 선택 */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {group.values.map((val, vIdx) => {
            const selected = group.selectedIndex === vIdx;
            return (
              <button
                key={vIdx}
                onClick={() => selectValueInGroup(gIdx, vIdx)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '6px 12px', borderRadius: 16, fontSize: 12, fontWeight: 600,
                  background: selected ? `${C.green}20` : C.bgSurface,
                  border: `1.5px solid ${selected ? C.green : C.border}`,
                  color: selected ? C.green : C.textSec,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {selected && '✓ '}{val}
              </button>
            );
          })}
        </div>

        {/* 옵션내용 추가 입력 */}
        <input
          value={inputVal}
          onChange={e => setOptionInputs(prev => ({ ...prev, [gIdx]: e.target.value }))}
          onFocus={() => { isTypingRef.current = true; }}
          onBlur={() => { isTypingRef.current = false; }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              const v = (optionInputs[gIdx] || '').trim();
              if (v) {
                addValueToGroup(gIdx, v);
                setOptionInputs(prev => ({ ...prev, [gIdx]: '' }));
              }
            }
          }}
          placeholder="원하는 내용이 없을 시, 여기 기재 후, Enter"
          className="dc-input"
          style={{
            padding: '7px 10px', fontSize: 12, borderRadius: 8,
            background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
          }}
        />
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
        position: 'fixed', top: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 428, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', zIndex: 10, boxSizing: 'border-box',
        background: 'rgba(10,14,26,0.92)', backdropFilter: 'blur(10px)',
        borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={goBack} style={{ fontSize: 13, color: C.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          ← {getStepTitle()}
        </button>
        <div style={{ fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: C.cyan }}>{step}</span>
          <span style={{ color: C.textSec }}>/5</span>
        </div>
        <div style={{ width: 64 }} />
      </div>

      {/* ── 진행 바 ── */}
      <div style={{ position: 'fixed', top: 56, left: '50%', transform: 'translateX(-50%)', width: '100%', maxWidth: 428, height: 3, zIndex: 10, background: C.border }}>
        <div style={{
          height: '100%', width: `${(step / 5) * 100}%`,
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {/* 타이틀 */}
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, marginBottom: 6 }}>
                      어떤 제품을 찾으세요?
                    </div>
                    <div style={{ fontSize: 13, color: C.textSec }}>
                      핑퐁이 AI가 상품 정보를 분석해드려요
                    </div>
                  </div>

                  {/* 메인 검색창 + AI 분석 버튼 */}
                  <style>{`
                    @keyframes neonPulse {
                      0%, 100% { box-shadow: 0 0 10px rgba(74, 222, 128, 0.4); }
                      50% { box-shadow: 0 0 25px rgba(74, 222, 128, 0.8), 0 0 40px rgba(74, 222, 128, 0.3); }
                    }
                  `}</style>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      type="text"
                      value={productName}
                      onChange={e => setProductName(e.target.value)}
                      placeholder="예: 갤럭시 S25 울트라 256GB"
                      onKeyDown={e => { if (e.key === 'Enter' && productName.trim()) { void handleAIAnalysis(); } }}
                      autoFocus
                      style={{
                        flex: 1, minWidth: 0, padding: '14px 16px', borderRadius: 12,
                        border: productName.trim() ? '2px solid #4ade80' : `2px solid ${C.border}`,
                        background: C.bgInput, color: C.textPri, fontSize: 16,
                        boxShadow: productName.trim() ? '0 0 12px rgba(74, 222, 128, 0.3)' : 'none',
                        transition: 'all 0.3s ease', boxSizing: 'border-box',
                      }}
                    />
                    <button
                      onClick={() => { void handleAIAnalysis(); }}
                      disabled={!productName.trim() || aiLoading}
                      style={{
                        padding: '14px 20px', borderRadius: 12, whiteSpace: 'nowrap',
                        background: productName.trim() && !aiLoading ? '#4ade80' : '#333',
                        color: productName.trim() && !aiLoading ? '#000' : '#666',
                        border: 'none', cursor: productName.trim() && !aiLoading ? 'pointer' : 'default',
                        fontWeight: 800, fontSize: 14,
                        boxShadow: productName.trim() && !aiLoading ? '0 0 15px rgba(74, 222, 128, 0.5)' : 'none',
                        animation: productName.trim() && !aiLoading ? 'neonPulse 1.5s ease-in-out infinite' : 'none',
                        transition: 'all 0.3s ease',
                      }}
                    >
                      {aiLoading ? '분석중...' : 'AI 분석 🔍'}
                    </button>
                  </div>

                  {/* 인기 태그 */}
                  <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 2 }}>
                    {POPULAR_TAGS.map(tag => (
                      <button
                        key={tag.value}
                        onClick={() => setProductName(tag.value)}
                        style={{
                          flexShrink: 0, padding: '6px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                          background: productName === tag.value ? `${C.cyan}18` : C.bgSurface,
                          border: `1px solid ${productName === tag.value ? C.cyan : C.border}`,
                          color: productName === tag.value ? C.cyan : C.textSec,
                          cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >{tag.label}</button>
                    ))}
                  </div>

                  {/* "또는" 구분선 */}
                  <div style={{ position: 'relative', textAlign: 'center', margin: '4px 0' }}>
                    <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: C.border }} />
                    <span style={{
                      position: 'relative', zIndex: 1, padding: '0 14px',
                      background: C.bgDeep, fontSize: 13, color: C.textDim,
                    }}>또는</span>
                  </div>

                  {/* 사진 + 음성 버튼 (나란히) */}
                  <input
                    ref={imageInputRef}
                    type="file" accept="image/*" capture="environment"
                    onChange={handleImageUpload}
                    style={{ display: 'none' }}
                  />
                  <div style={{ display: 'flex', gap: 12 }}>
                    <button
                      onClick={() => imageInputRef.current?.click()}
                      disabled={recognizingIdx >= 0 || imagePreviews.length >= 3}
                      style={{
                        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        gap: 8, padding: 14, background: C.bgSurface, borderRadius: 12,
                        border: `1px solid ${C.border}`, cursor: 'pointer',
                        transition: 'all 0.15s',
                        opacity: recognizingIdx >= 0 ? 0.5 : 1,
                      }}
                    >
                      <span style={{ fontSize: 20 }}>📷</span>
                      <span style={{ color: C.textPri, fontSize: 14 }}>사진으로 찾기</span>
                    </button>
                    <button
                      onClick={isRecording ? stopRecording : startRecording}
                      disabled={voiceLoading}
                      style={{
                        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        gap: 8, padding: 14, borderRadius: 12, cursor: voiceLoading ? 'not-allowed' : 'pointer',
                        background: isRecording ? 'rgba(255,45,120,0.12)' : C.bgSurface,
                        border: `1px solid ${isRecording ? C.magenta + '66' : C.border}`,
                        transition: 'all 0.15s',
                      }}
                    >
                      <span style={{ fontSize: 20 }}>{isRecording ? '⏹' : '🎤'}</span>
                      <span style={{ color: isRecording ? C.magenta : C.textPri, fontSize: 14 }}>
                        {voiceLoading ? '분석중...' : isRecording ? `중지 (${recordingTime}초)` : '음성으로 찾기'}
                      </span>
                    </button>
                  </div>

                  {/* 녹음 중 시각적 피드백 */}
                  {isRecording && (
                    <div style={{ marginBottom: 4 }}>
                      {/* 음성 파형 시각화 — 실시간 audioLevel 반응 */}
                      <div style={{
                        display: 'flex', justifyContent: 'center', alignItems: 'center',
                        gap: 3, height: 40, marginBottom: 8,
                      }}>
                        {Array.from({ length: 20 }, (_, i) => (
                          <div key={i} style={{
                            width: 3,
                            backgroundColor: audioLevel > 30 ? '#4ade80' : audioLevel > 10 ? '#f59e0b' : '#ef4444',
                            borderRadius: 2,
                            height: `${Math.max(4, (audioLevel / 128) * 40 * (0.5 + Math.sin(Date.now() / 200 + i) * 0.5))}px`,
                            transition: 'height 0.1s ease, background-color 0.3s',
                          }} />
                        ))}
                      </div>
                      {/* 진행바 */}
                      <div style={{
                        height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.08)',
                        overflow: 'hidden', marginBottom: 6,
                      }}>
                        <div style={{
                          height: '100%', borderRadius: 2,
                          background: 'linear-gradient(90deg, #ef4444, #f59e0b)',
                          width: `${(recordingTime / 30) * 100}%`,
                          transition: 'width 1s linear',
                        }} />
                      </div>
                      {/* 시간 표시 */}
                      <div style={{ textAlign: 'center', color: '#ef4444', fontSize: 14, fontWeight: 'bold' }}>
                        🔴 녹음 중 {recordingTime}초 / 30초
                      </div>
                    </div>
                  )}

                  {/* 음성 로딩 */}
                  {voiceLoading && !isRecording && (
                    <div style={{
                      textAlign: 'center', padding: 16,
                      background: C.bgSurface, borderRadius: 12, color: C.textSec, fontSize: 13,
                    }}>
                      🎤 음성을 분석하고 있어요...
                    </div>
                  )}

                  {/* 사진 미리보기 (썸네일 가로 배열) */}
                  {imagePreviews.length > 0 && (
                    <div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        {imagePreviews.map((preview, idx) => (
                          <div key={idx} style={{
                            position: 'relative', width: 64, height: 64,
                            borderRadius: 8, overflow: 'hidden',
                            border: `2px solid ${
                              imageResults[idx]?.confidence === 'high' ? C.green :
                              imageResults[idx]?.confidence === 'medium' ? C.yellow :
                              C.border
                            }`,
                          }}>
                            <img src={preview} alt={`사진${idx + 1}`}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            {recognizingIdx === idx && (
                              <div style={{
                                position: 'absolute', inset: 0,
                                background: 'rgba(0,0,0,0.6)', display: 'flex',
                                alignItems: 'center', justifyContent: 'center',
                                color: '#fff', fontSize: 10,
                              }}>분석중</div>
                            )}
                            <button
                              onClick={() => removeImage(idx)}
                              style={{
                                position: 'absolute', top: 1, right: 1,
                                width: 18, height: 18, borderRadius: '50%',
                                background: 'rgba(0,0,0,0.7)', border: 'none',
                                color: '#fff', fontSize: 10, cursor: 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                              }}
                            >✕</button>
                          </div>
                        ))}
                        {imagePreviews.length < 3 && (
                          <button
                            onClick={() => imageInputRef.current?.click()}
                            disabled={recognizingIdx >= 0}
                            style={{
                              width: 64, height: 64, display: 'flex',
                              alignItems: 'center', justifyContent: 'center',
                              background: C.bgSurface, borderRadius: 8,
                              border: `1px dashed ${C.border}`, cursor: 'pointer',
                              fontSize: 20, color: C.textDim,
                            }}
                          >+</button>
                        )}
                      </div>
                      {/* 인식 결과 한 줄 */}
                      {imageResults.some(r => r?.product_name) && (
                        <div style={{ marginTop: 8, fontSize: 13 }}>
                          {imageResults.map((rec, idx) => rec?.product_name && (
                            <div key={idx} style={{ color: rec.confidence === 'high' ? C.green : C.yellow, padding: '2px 0' }}>
                              {rec.confidence === 'high' ? '✅' : '💡'} {rec.brand ? `${rec.brand} ` : ''}{rec.product_name}{rec.specs ? ` (${rec.specs})` : ''}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 음성 인식 결과 (태그 형태) */}
                  {voiceResult && voiceResult.transcript && (
                    <div style={{
                      background: C.bgSurface, borderRadius: 12, padding: 14,
                    }}>
                      <div style={{ color: C.textDim, fontSize: 12, marginBottom: 6 }}>🎤 음성 인식 결과</div>
                      <div style={{ color: C.textPri, fontSize: 14, marginBottom: 10, lineHeight: 1.5 }}>
                        "{voiceResult.transcript}"
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {voiceResult.product_query && (
                          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 10, background: `${C.green}18`, color: C.green }}>
                            제품: {voiceResult.product_query}
                          </span>
                        )}
                        {voiceResult.brand && (
                          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 10, background: `${C.cyan}18`, color: C.cyan }}>
                            브랜드: {voiceResult.brand}
                          </span>
                        )}
                        {voiceResult.target_price != null && voiceResult.target_price > 0 && (
                          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 10, background: `${C.yellow}18`, color: C.yellow }}>
                            희망가: {voiceResult.target_price.toLocaleString()}원
                          </span>
                        )}
                        {voiceResult.quantity != null && voiceResult.quantity > 1 && (
                          <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 10, background: `${C.purple}18`, color: C.purple }}>
                            수량: {voiceResult.quantity}개
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 추가 설명 (선택) */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>추가 설명 (선택)</label>
                    <textarea
                      value={freeText}
                      onChange={e => setFreeText(e.target.value)}
                      placeholder="색상, 용량, 사이즈 등 원하는 옵션을 적어주세요"
                      rows={2}
                      className="dc-input"
                      style={{
                        padding: '12px 14px', fontSize: 14, borderRadius: 12, resize: 'none',
                        background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri,
                        lineHeight: 1.55,
                      }}
                    />
                  </div>

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

                {/* 유사 딜방 안내 */}
                {similarDeals.length > 0 && (
                  <div style={{
                    background: 'rgba(74,222,128,0.06)', border: `1px solid rgba(74,222,128,0.25)`,
                    borderRadius: 14, padding: 16,
                  }}>
                    <div style={{ color: C.green, fontWeight: 800, fontSize: 14, marginBottom: 10 }}>
                      비슷한 딜방이 이미 있어요!
                    </div>
                    {similarDeals.map((deal: any) => (
                      <div key={deal.id} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '10px 12px', background: C.bgCard, borderRadius: 10, marginBottom: 6,
                        border: `1px solid ${C.border}`,
                      }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, color: C.textPri, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {deal.product_detail || deal.product_name}
                          </div>
                          <div style={{ fontSize: 11, color: C.textDim }}>
                            목표가 {deal.target_price?.toLocaleString()}원 · 매칭 {deal.match_score}%
                            {deal.offer_count > 0 && ` · 오퍼 ${deal.offer_count}건`}
                          </div>
                        </div>
                        <button
                          onClick={() => navigate(`/deal/${deal.id}`)}
                          style={{
                            padding: '7px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
                            background: C.green, color: '#000', fontWeight: 700, fontSize: 12,
                            whiteSpace: 'nowrap', marginLeft: 8,
                          }}
                        >참여 →</button>
                      </div>
                    ))}
                    <div style={{ fontSize: 11, color: C.textDim, marginTop: 6 }}>
                      기존 딜방에 참여하거나, 아래에서 새로 만들 수도 있어요.
                    </div>
                  </div>
                )}

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

                {/* 옵션항목(사양) */}
                <div>
                  <SectionTitle>📦 옵션항목(사양)</SectionTitle>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {optionGroups.map((group, gIdx) => renderOptionGroup(group, gIdx))}
                    {optionGroups.length < 10 ? (
                      <button
                        onClick={addGroup}
                        style={{
                          padding: '12px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                          background: 'transparent', border: `1.5px dashed ${C.border}`,
                          color: C.textDim, cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >+ 옵션항목(사양) 추가</button>
                    ) : (
                      <div style={{ fontSize: 11, color: C.orange, textAlign: 'center', padding: '8px 0' }}>
                        최대 10개까지만 추가할 수 있어요
                      </div>
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

            {/* ══ Step 3: 가격 챌린지 + 목표가 + 수량 ══ */}
            {step === 3 && (() => {
              const tp = Number(targetPrice.replace(/,/g, '')) || 0;
              const canNext = marketChecked && tp > 0 && quantity >= 1;
              const tpRatio = marketPrice && tp > 0 ? tp / marketPrice : null;
              const tpWarn = tpRatio != null
                ? tpRatio > 1 ? { msg: '시장가보다 높아요. 판매자 오퍼가 적을 수 있어요.', c: C.yellow }
                : tpRatio < 0.3 ? { msg: '목표가가 매우 낮아요. 오퍼를 받기 어려울 수 있어요.', c: '#ff5252' }
                : tpRatio < 0.7 ? { msg: '도전적인 목표에요!', c: '#60a5fa' }
                : null : null;
              return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                {/* 헤더 */}
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: C.cyan, marginBottom: 6 }}>
                    {productNameConfirmed || productDetail || productName}
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3 }}>
                    지금 시장에서 얼마에 팔리고 있을까요?
                  </div>
                </div>

                {/* 예상 가격 입력 */}
                <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 18 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.textPri, marginBottom: 10 }}>내 예상 가격:</div>
                  <div style={{ position: 'relative' }}>
                    <input
                      type="text" inputMode="numeric"
                      value={guessPrice ? Number(guessPrice.replace(/,/g, '')).toLocaleString() : ''}
                      onChange={e => setGuessPrice(e.target.value.replace(/[^0-9]/g, ''))}
                      onFocus={e => e.target.select()}
                      placeholder="예상 가격 입력"
                      className="dc-input"
                      style={{ padding: '13px 40px 13px 14px', fontSize: 18, fontWeight: 700, borderRadius: 12, background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri, textAlign: 'right' }}
                    />
                    <span style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, fontSize: 14 }}>원</span>
                  </div>
                  <button
                    onClick={startPriceChallenge}
                    disabled={isAnalyzing || !guessPrice || Number(guessPrice) <= 0}
                    style={{
                      width: '100%', marginTop: 12, padding: '14px', borderRadius: 12, border: 'none', fontSize: 16, fontWeight: 800,
                      background: (!guessPrice || Number(guessPrice) <= 0) ? C.bgSurface : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                      color: (!guessPrice || Number(guessPrice) <= 0) ? C.textDim : '#000',
                      cursor: (!guessPrice || Number(guessPrice) <= 0 || isAnalyzing) ? 'not-allowed' : 'pointer',
                      opacity: isAnalyzing ? 0.6 : 1,
                    }}
                  >{isAnalyzing ? loadingMsg || '분석 중...' : '맞춰보기! 🎯'}</button>
                </div>

                {/* 매트릭스 코드 레인 애니메이션 */}
                <MatrixCodeRain
                  active={isAnalyzing}
                  finalPrice={marketPrice || 0}
                />

                {/* 분석 결과 */}
                {marketChecked && marketPrice && (
                  <>
                    {/* 고가 제품 / 온라인 판매 불가 안내 */}
                    {(consensus?.notice || priceAnalysis?.notice) && (
                      <div style={{
                        background: consensus?.confidence === 'not_available' ? '#88888820' : '#f59e0b20',
                        border: `1px solid ${consensus?.confidence === 'not_available' ? '#888' : '#f59e0b'}`,
                        borderRadius: 12, padding: '12px 16px',
                        color: consensus?.confidence === 'not_available' ? '#ccc' : '#f59e0b',
                        fontSize: 13, lineHeight: 1.5,
                      }}>
                        {consensus?.confidence === 'not_available' ? '⚫' : '💡'} {consensus?.notice || priceAnalysis?.notice}
                      </div>
                    )}

                    {consensus?.luxury_warning && (
                      <div style={{
                        background: '#f59e0b15', border: '1px solid #f59e0b40',
                        borderRadius: 12, padding: '10px 14px',
                        color: '#f59e0b', fontSize: 13, lineHeight: 1.5,
                      }}>
                        ⚠️ {consensus.luxury_warning}
                      </div>
                    )}

                    {/* 시장 최저가 + 신뢰도 뱃지 */}
                    <div style={{ textAlign: 'center', padding: 16, background: C.bgCard, border: `1px solid ${consensus ? consensus.confidence_color + '30' : C.border}`, borderRadius: 16 }}>
                      {consensus && (
                        <div style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '4px 12px', borderRadius: 20,
                          background: consensus.confidence_color + '20',
                          border: `1px solid ${consensus.confidence_color}50`,
                          marginBottom: 8,
                        }}>
                          <span style={{ fontSize: 16 }}>{consensus.confidence_emoji}</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: consensus.confidence_color }}>{consensus.confidence_label}</span>
                          <span style={{ fontSize: 11, color: C.textDim }}>({consensus.source_count}개 소스)</span>
                        </div>
                      )}
                      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 4 }}>
                        {(consensus?.notice || priceAnalysis?.notice) ? '참고 가격 (목표가 기준)' : consensus ? '시장 합의가' : '시장 최저가'}
                      </div>
                      <div style={{ fontSize: 32, fontWeight: 900, color: (consensus?.notice || priceAnalysis?.notice) ? '#f59e0b' : consensus ? consensus.confidence_color : C.green }}>{marketPrice.toLocaleString()}원</div>
                      {reaction && !(consensus?.notice || priceAnalysis?.notice) && <div style={{ fontSize: 14, color: C.textSec, marginTop: 8 }}>{reaction}</div>}
                    </div>

                    {/* 채택 상품 근거 */}
                    {priceAnalysis && priceAnalysis.included_items.length > 0 && (
                      <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 18 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: C.textPri, marginBottom: 10 }}>
                          가격 근거 ({priceAnalysis.total_included}건)
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                          {priceAnalysis.included_items.map((item, idx) => (
                            <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: idx < priceAnalysis.included_items.length - 1 ? `1px solid ${C.border}` : 'none' }}>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: 13, color: C.textPri, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</div>
                                <div style={{ fontSize: 11, color: C.textDim }}>{item.mall || '쇼핑몰'}{idx === 0 ? ' · 최저' : ''}</div>
                              </div>
                              <div style={{ fontSize: 14, fontWeight: 700, color: idx === 0 ? C.green : C.textPri, whiteSpace: 'nowrap', marginLeft: 8 }}>
                                {item.price.toLocaleString()}원
                              </div>
                              {item.link && (
                                <a href={item.link} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8, fontSize: 16, textDecoration: 'none', color: C.cyan }}>→</a>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 제외 항목 (접이식) */}
                    {priceAnalysis && priceAnalysis.excluded_items.length > 0 && (
                      <div>
                        <button
                          onClick={() => setShowExcluded(!showExcluded)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: C.textDim, padding: '4px 0' }}
                        >{showExcluded ? '▼' : '▶'} 제외된 항목 {priceAnalysis.total_excluded}건</button>
                        {showExcluded && (
                          <div style={{ marginTop: 6, padding: '8px 12px', background: C.bgCard, borderRadius: 12, border: `1px solid ${C.border}` }}>
                            {priceAnalysis.excluded_items.map((item, idx) => (
                              <div key={idx} style={{ fontSize: 12, color: C.textDim, padding: '4px 0', display: 'flex', gap: 8 }}>
                                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
                                <span style={{ whiteSpace: 'nowrap' }}>{item.price.toLocaleString()}원</span>
                                <span style={{ color: '#ff5252', whiteSpace: 'nowrap' }}>❌ {item.reason}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 3중 소스 비교 (접이식) */}
                    {consensus && consensus.sources.length > 0 && (
                      <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, overflow: 'hidden' }}>
                        <button
                          onClick={() => setShowConsensus(!showConsensus)}
                          style={{
                            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '14px 18px', background: 'none', border: 'none', cursor: 'pointer',
                          }}
                        >
                          <span style={{ fontSize: 14, fontWeight: 700, color: C.textPri }}>
                            {consensus.confidence_emoji} 가격 소스 비교 ({consensus.sources.filter(s => !s.suspicious).length}개 소스)
                          </span>
                          <span style={{ fontSize: 12, color: C.textDim }}>{showConsensus ? '▲ 접기' : '▼ 펼치기'}</span>
                        </button>
                        {showConsensus && (
                          <div style={{ padding: '0 18px 18px' }}>
                            {consensus.sources.map((src, idx) => (
                              <div key={idx} style={{
                                display: 'flex', alignItems: 'center', gap: 12,
                                padding: '12px 0',
                                borderTop: idx > 0 ? `1px solid ${C.border}` : 'none',
                                opacity: src.suspicious ? 0.5 : 1,
                              }}>
                                {/* 소스 라벨 */}
                                <div style={{
                                  width: 60, flexShrink: 0, textAlign: 'center',
                                  padding: '4px 0', borderRadius: 8, fontSize: 11, fontWeight: 700,
                                  background: src.source === 'naver' ? '#2db40020' : src.source === 'coupang' ? '#e4433520' : '#a855f720',
                                  color: src.source === 'naver' ? '#2db400' : src.source === 'coupang' ? '#e44335' : '#a855f7',
                                  border: `1px solid ${src.source === 'naver' ? '#2db40040' : src.source === 'coupang' ? '#e4433540' : '#a855f740'}`,
                                }}>{src.source_label}</div>
                                {/* 가격 */}
                                <div style={{ flex: 1 }}>
                                  <div style={{
                                    fontSize: 16, fontWeight: 700,
                                    color: src.suspicious ? '#ff5252' : C.textPri,
                                    textDecoration: src.suspicious ? 'line-through' : 'none',
                                  }}>
                                    {src.price > 0 ? `${src.price.toLocaleString()}원` : '-'}
                                  </div>
                                  {src.count > 0 && (
                                    <div style={{ fontSize: 11, color: C.textDim }}>{src.count}건 검색</div>
                                  )}
                                </div>
                                {/* 의심 표시 */}
                                {src.suspicious && (
                                  <div style={{ fontSize: 11, color: '#ff5252', maxWidth: 120 }}>
                                    {src.suspicion_reason || '의심'}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* AI 분석 면책 */}
                    <div style={{
                      padding: '10px 14px', background: 'rgba(255,165,0,0.08)',
                      border: '1px solid rgba(255,165,0,0.2)', borderRadius: 10,
                      fontSize: 11, color: '#b0b0b0', lineHeight: 1.5,
                    }}>
                      AI 시장가 분석은 참고용이며, 실제 가격과 다를 수 있습니다. 거래 결정은 이용자 본인의 책임입니다.
                    </div>

                    {/* 목표가 설정 */}
                    <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 18 }}>
                      <div style={{ fontSize: 16, fontWeight: 800, color: C.textPri, marginBottom: 14 }}>
                        자, 이제 목표가를 정해볼까요?
                      </div>

                      {/* 할인율 슬라이더 */}
                      <input
                        type="range" min={0} max={50} step={1}
                        value={discountPercent}
                        onChange={e => {
                          const pct = Number(e.target.value);
                          setDiscountPercent(pct);
                          if (marketPrice) setTargetPrice(String(Math.round(marketPrice * (1 - pct / 100))));
                        }}
                        style={{ width: '100%', accentColor: C.green, marginBottom: 4 }}
                      />
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: C.textDim }}>
                        <span>0%</span>
                        <span style={{ color: C.green, fontWeight: 700, fontSize: 16 }}>{discountPercent}% 절감</span>
                        <span>50%</span>
                      </div>

                      {/* 절감액 */}
                      {tp > 0 && marketPrice && tp < marketPrice && (
                        <div style={{ textAlign: 'center', padding: 12, background: 'rgba(74,222,128,0.1)', borderRadius: 8, marginTop: 8 }}>
                          <span style={{ color: C.green, fontSize: 18, fontWeight: 700 }}>
                            {(marketPrice - tp).toLocaleString()}원 절감!
                          </span>
                        </div>
                      )}

                      {/* 직접 입력 */}
                      <div style={{ marginTop: 14 }}>
                        <div style={{ fontSize: 13, color: C.textSec, marginBottom: 6 }}>또는 직접 입력:</div>
                        <div style={{ position: 'relative' }}>
                          <input
                            type="text" inputMode="numeric"
                            value={targetPrice ? Number(targetPrice.replace(/,/g, '')).toLocaleString() : ''}
                            onChange={e => {
                              const num = e.target.value.replace(/[^0-9]/g, '');
                              setTargetPrice(num);
                              if (marketPrice && Number(num) > 0) {
                                const pct = Math.max(0, Math.min(50, Math.round((1 - Number(num) / marketPrice) * 100)));
                                setDiscountPercent(pct >= 0 ? pct : 0);
                              }
                            }}
                            placeholder="목표가 입력"
                            className="dc-input"
                            style={{ padding: '13px 40px 13px 14px', fontSize: 16, fontWeight: 700, borderRadius: 12, background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri, textAlign: 'right' }}
                          />
                          <span style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, fontSize: 14 }}>원</span>
                        </div>
                      </div>

                      {/* 목표가 검증 */}
                      {tpWarn && (
                        <div style={{ fontSize: 12, color: tpWarn.c, marginTop: 8 }}>{tpWarn.msg}</div>
                      )}
                    </div>

                    {/* 수량 */}
                    <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 18 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: C.textPri, marginBottom: 10 }}>수량</div>
                      <div style={{ position: 'relative' }}>
                        <input
                          type="text" inputMode="numeric"
                          value={quantity > 0 ? quantity.toLocaleString() : ''}
                          onChange={e => {
                            const n = Number(e.target.value.replace(/[^0-9]/g, ''));
                            setQuantity(Math.max(1, Math.min(9999, n || 1)));
                          }}
                          className="dc-input"
                          style={{ padding: '13px 40px 13px 14px', fontSize: 16, fontWeight: 700, borderRadius: 12, background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPri, textAlign: 'right' }}
                        />
                        <span style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, fontSize: 14 }}>개</span>
                      </div>
                      {tp > 0 && quantity > 1 && (
                        <div style={{ fontSize: 13, color: C.textSec, marginTop: 8 }}>
                          예상 총액: <span style={{ color: C.cyan, fontWeight: 700 }}>{(tp * quantity).toLocaleString()}원</span>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* 다음 버튼 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
                  {canNext
                    ? primaryBtn('다음 →', () => goTo(4))
                    : <div style={{ width: '100%', padding: '14px', borderRadius: 14, textAlign: 'center', background: C.bgSurface, color: C.textDim, fontSize: 15, fontWeight: 700 }}>다음 →</div>
                  }
                  {!marketChecked && <div style={{ fontSize: 12, color: C.textDim, textAlign: 'center' }}>예상 가격을 입력하고 시장가를 확인해주세요.</div>}
                </div>
              </div>
              );
            })()}

            {/* ══ Step 4: 기타 요청사항 ══ */}
            {step === 4 && (
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
                    placeholder="배송 조건, 특별 요청 등 자유롭게 입력해주세요"
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
                  {primaryBtn('다음', () => goTo(5))}
                  {skipBtn(() => goTo(5))}
                </div>
              </div>
            )}

            {/* ══ Step 5: 최종 확인 + 딜 만들기 ══ */}
            {step === 5 && (
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
                    { label: '옵션항목(사양)', value: optionGroups.length > 0
                      ? optionGroups.map(g => {
                          const sel = g.selectedIndex >= 0 && g.selectedIndex < g.values.length
                            ? g.values[g.selectedIndex] : g.values[0] || '-';
                          return `${g.title}: ${sel}`;
                        }).join(' / ')
                      : '없음' },
                    { label: '시장가격',   value: marketPrice ? `${marketPrice.toLocaleString()}원` : '-' },
                    { label: '목표가격',   value: targetPrice ? `${Number(targetPrice).toLocaleString()}원` : '-' },
                    { label: '수량',       value: `${quantity}개` },
                    ...(targetPrice && Number(targetPrice) > 0 && quantity > 0
                      ? [{ label: '예상 총액', value: `${(Number(targetPrice) * quantity).toLocaleString()}원` }]
                      : []),
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
