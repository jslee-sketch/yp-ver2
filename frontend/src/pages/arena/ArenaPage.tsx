// 역핑 배틀 아레나 — 메인 허브
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

const GAMES = [
  { id: 'rps', name: '가위바위보', emoji: '✊', color: '#FFD700', path: '/arena/rps', desc: 'Rock Paper Scissors' },
  { id: 'mjb', name: '묵찌빠', emoji: '👊', color: '#FF4444', path: '/arena/mukjjippa', desc: 'Korean RPS Extended' },
  { id: 'yut', name: '윷놀이', emoji: '🎯', color: '#44BB44', path: '/arena/yut', desc: 'Yut Nori' },
  { id: 'math', name: '수학배틀', emoji: '🧮', color: '#4488FF', path: '/arena/math', desc: 'Math Battle' },
  { id: 'quiz', name: '상식퀴즈', emoji: '🧠', color: '#AA44FF', path: '/arena/quiz', desc: 'Trivia Quiz' },
  { id: 'reaction', name: '반응속도', emoji: '⚡', color: '#FF8800', path: '/arena/reaction', desc: 'Reaction Speed' },
];

const i18n: Record<string, Record<string, string>> = {
  ko: { title: '역핑 배틀 아레나', subtitle: '6가지 미니게임으로 세계와 대결!', rankings: '랭킹', map: '배틀맵', login_prompt: '로그인하면 기록이 저장됩니다!', play: '플레이', level: '레벨', points: '포인트', remaining: '오늘 남은 게임' },
  en: { title: 'YeokPing Battle Arena', subtitle: 'Battle the world with 6 mini-games!', rankings: 'Rankings', map: 'Battle Map', login_prompt: 'Login to save your records!', play: 'Play', level: 'Level', points: 'Points', remaining: 'Games remaining today' },
  ja: { title: 'ヨクピン バトルアリーナ', subtitle: '6つのミニゲームで世界と対戦！', rankings: 'ランキング', map: 'バトルマップ', login_prompt: 'ログインで記録を保存！', play: 'プレイ', level: 'レベル', points: 'ポイント', remaining: '今日の残りゲーム数' },
  zh: { title: '逆评 竞技场', subtitle: '用6款小游戏与全世界对决！', rankings: '排名', map: '战斗地图', login_prompt: '登录后保存记录！', play: '开始', level: '等级', points: '积分', remaining: '今日剩余游戏' },
  es: { title: 'YeokPing Arena de Batalla', subtitle: '¡Compite con el mundo en 6 minijuegos!', rankings: 'Rankings', map: 'Mapa', login_prompt: '¡Inicia sesión para guardar registros!', play: 'Jugar', level: 'Nivel', points: 'Puntos', remaining: 'Juegos restantes hoy' },
};

export default function ArenaPage() {
  const { isLoggedIn } = useAuth();
  const [lang, setLang] = useState('ko');
  const [profile, setProfile] = useState<any>(null);
  const [feed, setFeed] = useState<any[]>([]);
  const [banners, setBanners] = useState<any[]>([]);
  const t = i18n[lang] || i18n.ko;

  useEffect(() => {
    if (isLoggedIn) {
      apiClient.get('/arena/me').then(r => setProfile(r.data)).catch(() => {});
    }
    apiClient.get('/arena/live-feed?limit=10').then(r => setFeed(r.data?.feed || [])).catch(() => {});
    apiClient.get('/arena/deal-banner').then(r => setBanners(r.data?.banners || [])).catch(() => {});
  }, [isLoggedIn]);

  return (
    <div style={{ padding: '20px', maxWidth: 800, margin: '0 auto' }}>
      {/* 언어 선택 */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginBottom: 12 }}>
        {['ko', 'en', 'ja', 'zh', 'es'].map(l => (
          <button key={l} onClick={() => setLang(l)}
            style={{ padding: '4px 10px', borderRadius: 12, border: lang === l ? '2px solid #FFD700' : '1px solid #555', background: lang === l ? '#FFD700' : 'transparent', color: lang === l ? '#000' : '#ccc', cursor: 'pointer', fontWeight: lang === l ? 700 : 400 }}>
            {l.toUpperCase()}
          </button>
        ))}
      </div>

      {/* 타이틀 */}
      <motion.h1 initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.5 }}
        style={{ textAlign: 'center', fontSize: 32, background: 'linear-gradient(135deg, #FFD700, #FF4444)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        🎮 {t.title}
      </motion.h1>
      <p style={{ textAlign: 'center', color: '#aaa', marginBottom: 24 }}>{t.subtitle}</p>

      {/* FOMO: 비로그인 유저 */}
      {!isLoggedIn && (
        <motion.div initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
          style={{ background: 'linear-gradient(135deg, #FF4444, #FFD700)', padding: '12px 20px', borderRadius: 12, textAlign: 'center', marginBottom: 20, color: '#000', fontWeight: 700 }}>
          🔥 {t.login_prompt} <Link to="/login" style={{ color: '#000', textDecoration: 'underline' }}>Login →</Link>
        </motion.div>
      )}

      {/* 내 프로필 */}
      {profile && (
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: 18, fontWeight: 700 }}>{profile.nickname}</span>
            <span style={{ marginLeft: 12, color: '#FFD700' }}>{profile.arena_level?.toUpperCase()}</span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div>{t.points}: <b>{profile.total_points}</b></div>
            <div style={{ fontSize: 12, color: '#888' }}>{t.remaining}: {profile.daily_remaining}</div>
          </div>
        </div>
      )}

      {/* 게임 그리드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16, marginBottom: 30 }}>
        {GAMES.map((g, i) => (
          <motion.div key={g.id} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
            <Link to={g.path} style={{ textDecoration: 'none' }}>
              <div style={{ background: '#16213e', borderRadius: 16, padding: 20, textAlign: 'center', border: `2px solid ${g.color}33`, transition: 'all 0.2s', cursor: 'pointer' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = g.color; (e.currentTarget as HTMLElement).style.transform = 'translateY(-4px)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = g.color + '33'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}>
                <div style={{ fontSize: 48 }}>{g.emoji}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: g.color, marginTop: 8 }}>{g.name}</div>
                <div style={{ fontSize: 11, color: '#888' }}>{g.desc}</div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* 네비 링크 */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 24 }}>
        <Link to="/arena/rankings" style={{ padding: '10px 24px', borderRadius: 20, background: '#FFD700', color: '#000', fontWeight: 700, textDecoration: 'none' }}>🏆 {t.rankings}</Link>
        <Link to="/arena/map" style={{ padding: '10px 24px', borderRadius: 20, background: '#4488FF', color: '#fff', fontWeight: 700, textDecoration: 'none' }}>🗺️ {t.map}</Link>
      </div>

      {/* 실시간 피드 */}
      {feed.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ color: '#FFD700' }}>⚡ Live Feed</h3>
          <div style={{ maxHeight: 200, overflow: 'auto' }}>
            {feed.map((f, i) => (
              <motion.div key={i} initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.05 }}
                style={{ padding: '6px 12px', borderBottom: '1px solid #222', fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
                <span>{GAMES.find(g => g.id === f.game_type)?.emoji} {f.game_type} — <b style={{ color: f.result === 'win' ? '#44BB44' : f.result === 'lose' ? '#FF4444' : '#FFD700' }}>{f.result}</b></span>
                <span style={{ color: '#666' }}>{f.country}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* 역핑 딜 배너 (스며들기) */}
      {banners.length > 0 && (
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16 }}>
          <h4 style={{ color: '#aaa', margin: '0 0 8px' }}>🛍️ 역핑 인기 딜</h4>
          {banners.map(b => (
            <Link key={b.deal_id} to={`/deal/${b.deal_id}`} style={{ display: 'block', padding: '8px 0', borderBottom: '1px solid #222', color: '#ddd', textDecoration: 'none' }}>
              {b.title} <span style={{ color: '#888', fontSize: 12 }}>→ 참여하기</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
