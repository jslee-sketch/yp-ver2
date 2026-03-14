import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || ''
const DEALS_PER_PAGE = 6

interface Stats {
    total_stores: number;
    total_heroes: number;
    total_vouchers: number;
    total_amount: number;
    open_deals: number;
}

interface HeroRank {
    rank: number;
    hero_id: number;
    hero_level: string;
    badge: string;
    title: string;
    total_stores: number;
    total_points: number;
}

export default function DonzzulMainPage() {
    const [deals, setDeals] = useState<any[]>([])
    const [stats, setStats] = useState<Stats | null>(null)
    const [ranking, setRanking] = useState<HeroRank[]>([])
    const [currentVote, setCurrentVote] = useState<any>(null)

    // Filter & pagination state
    const [searchText, setSearchText] = useState('')
    const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'CLOSED'>('OPEN')
    const [dateFrom, setDateFrom] = useState('')
    const [dateTo, setDateTo] = useState('')
    const [visibleCount, setVisibleCount] = useState(DEALS_PER_PAGE)

    // Filtered deals
    const filteredDeals = useMemo(() => {
        let result = deals
        if (statusFilter !== 'ALL') {
            result = result.filter(d => d.status === statusFilter)
        }
        if (searchText.trim()) {
            const q = searchText.trim().toLowerCase()
            result = result.filter(d => (d.title || '').toLowerCase().includes(q))
        }
        if (dateFrom) {
            result = result.filter(d => (d.created_at || '') >= dateFrom)
        }
        if (dateTo) {
            const toEnd = dateTo + 'T23:59:59'
            result = result.filter(d => (d.created_at || '') <= toEnd)
        }
        return result
    }, [deals, searchText, statusFilter, dateFrom, dateTo])

    const visibleDeals = filteredDeals.slice(0, visibleCount)
    const hasMore = visibleCount < filteredDeals.length

    // Reset visible count when filters change
    useEffect(() => { setVisibleCount(DEALS_PER_PAGE) }, [searchText, statusFilter, dateFrom, dateTo])

    useEffect(() => {
        fetch(`${API}/donzzul/deals`).then(r => r.json()).then(data => {
            setDeals(Array.isArray(data) ? data : [])
        }).catch(() => {})

        fetch(`${API}/donzzul/stats`).then(r => r.json()).then(setStats).catch(() => {})
        fetch(`${API}/donzzul/actuators/ranking`).then(r => r.json()).then(data => {
            setRanking(Array.isArray(data) ? data.slice(0, 5) : [])
        }).catch(() => {})
        fetch(`${API}/donzzul/votes/current-week`).then(r => r.json()).then(data => {
            if (data && data.id) setCurrentVote(data)
        }).catch(() => {})
    }, [])

    return (
        <div style={{ maxWidth: 600, margin: '0 auto', padding: '20px 16px' }}>
            {/* Hero Banner */}
            <div style={{
                textAlign: 'center', padding: '28px 16px', borderRadius: 16,
                background: 'linear-gradient(135deg, rgba(244,114,182,0.1) 0%, rgba(74,222,128,0.1) 100%)',
                border: '1px solid rgba(244,114,182,0.2)', marginBottom: 20,
            }}>
                <div style={{ fontSize: 48, marginBottom: 8 }}>💚</div>
                <h1 style={{ color: '#f472b6', margin: '0 0 6px', fontSize: 26 }}>돈쭐</h1>
                <p style={{ color: '#999', fontSize: 14, margin: 0, lineHeight: 1.5 }}>
                    착한 가게를 응원하는 상품권 시스템
                </p>
            </div>

            {/* Stats Bar */}
            {stats && (
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
                    marginBottom: 20,
                }}>
                    {[
                        { label: '가게', value: stats.total_stores, color: '#f472b6' },
                        { label: '히어로', value: stats.total_heroes, color: '#4ade80' },
                        { label: '상품권', value: stats.total_vouchers, color: '#60a5fa' },
                        { label: '총 응원금', value: `${Math.floor(stats.total_amount / 10000)}만`, color: '#f59e0b' },
                    ].map(s => (
                        <div key={s.label} style={{
                            background: '#1a1a2e', borderRadius: 10, padding: '12px 8px',
                            textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
                            <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{s.label}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Quick Actions */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 20 }}>
                <Link to="/donzzul/hero/recommend" style={{
                    padding: '14px 8px', borderRadius: 12,
                    background: 'rgba(244,114,182,0.08)', border: '1px solid rgba(244,114,182,0.25)',
                    color: '#f472b6', textAlign: 'center', textDecoration: 'none',
                    fontSize: 13, fontWeight: 600,
                }}>가게 추천</Link>
                <Link to="/donzzul/vouchers" style={{
                    padding: '14px 8px', borderRadius: 12,
                    background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.25)',
                    color: '#4ade80', textAlign: 'center', textDecoration: 'none',
                    fontSize: 13, fontWeight: 600,
                }}>내 상품권함</Link>
                <Link to="/donzzul/vote" style={{
                    padding: '14px 8px', borderRadius: 12,
                    background: 'rgba(96,165,250,0.08)', border: '1px solid rgba(96,165,250,0.25)',
                    color: '#60a5fa', textAlign: 'center', textDecoration: 'none',
                    fontSize: 13, fontWeight: 600,
                }}>이번 주 투표</Link>
            </div>

            {/* Current Vote */}
            {currentVote && (
                <Link to="/donzzul/vote" style={{
                    display: 'block', background: 'rgba(96,165,250,0.06)',
                    border: '1px solid rgba(96,165,250,0.2)', borderRadius: 12,
                    padding: 14, marginBottom: 20, textDecoration: 'none',
                }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#60a5fa', marginBottom: 4 }}>
                        투표 진행 중: {currentVote.week_label}
                    </div>
                    <div style={{ fontSize: 12, color: '#888' }}>
                        {currentVote.candidates?.length || 0}개 후보 | 총 {currentVote.total_votes}표
                    </div>
                </Link>
            )}

            {/* Deals Section */}
            <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
                    가게 목록 ({filteredDeals.length})
                </div>

                {/* Filter Bar */}
                <div style={{
                    background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                    borderRadius: 12, padding: 12, marginBottom: 12,
                    display: 'flex', flexDirection: 'column', gap: 10,
                }}>
                    {/* Search + Status row */}
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <input
                            type="text"
                            placeholder="가게이름 검색"
                            value={searchText}
                            onChange={e => setSearchText(e.target.value)}
                            style={{
                                flex: 1, padding: '8px 12px', borderRadius: 8,
                                border: '1px solid var(--border-subtle)',
                                background: 'var(--bg-elevated)', color: 'var(--text-primary)',
                                fontSize: 13, outline: 'none',
                            }}
                        />
                        <div style={{ display: 'flex', gap: 4 }}>
                            {(['ALL', 'OPEN', 'CLOSED'] as const).map(s => (
                                <button
                                    key={s}
                                    onClick={() => setStatusFilter(s)}
                                    style={{
                                        padding: '6px 10px', borderRadius: 8, fontSize: 12,
                                        fontWeight: 600, cursor: 'pointer',
                                        border: statusFilter === s ? 'none' : '1px solid var(--border-subtle)',
                                        background: statusFilter === s
                                            ? (s === 'OPEN' ? 'var(--accent-green)' : s === 'CLOSED' ? 'var(--accent-orange)' : 'var(--text-muted)')
                                            : 'var(--bg-elevated)',
                                        color: statusFilter === s ? '#000' : 'var(--text-secondary)',
                                    }}
                                >{s === 'ALL' ? '전체' : s === 'OPEN' ? 'OPEN' : 'CLOSED'}</button>
                            ))}
                        </div>
                    </div>
                    {/* Date range row */}
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>기간</span>
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={e => setDateFrom(e.target.value)}
                            style={{
                                flex: 1, padding: '6px 8px', borderRadius: 8,
                                border: '1px solid var(--border-subtle)',
                                background: 'var(--bg-elevated)', color: 'var(--text-primary)',
                                fontSize: 12,
                            }}
                        />
                        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>~</span>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={e => setDateTo(e.target.value)}
                            style={{
                                flex: 1, padding: '6px 8px', borderRadius: 8,
                                border: '1px solid var(--border-subtle)',
                                background: 'var(--bg-elevated)', color: 'var(--text-primary)',
                                fontSize: 12,
                            }}
                        />
                        {(dateFrom || dateTo) && (
                            <button
                                onClick={() => { setDateFrom(''); setDateTo('') }}
                                style={{
                                    padding: '4px 8px', borderRadius: 6, border: 'none',
                                    background: 'var(--bg-elevated)', color: 'var(--text-muted)',
                                    fontSize: 11, cursor: 'pointer',
                                }}
                            >초기화</button>
                        )}
                    </div>
                </div>

                {/* Deal Cards */}
                {filteredDeals.length === 0 && (
                    <div style={{
                        padding: 20, borderRadius: 12, textAlign: 'center',
                        background: 'rgba(244,114,182,0.05)', border: '1px solid rgba(244,114,182,0.15)',
                        color: '#f472b6', fontSize: 13,
                    }}>
                        {deals.length === 0
                            ? '아직 응원 가능한 가게가 없어요. 가게를 추천해주세요!'
                            : '검색 결과가 없습니다.'}
                    </div>
                )}
                {visibleDeals.map(deal => (
                    <Link to={`/donzzul/deals/${deal.id}`} key={deal.id} style={{
                        display: 'block', background: 'var(--bg-secondary)', borderRadius: 12,
                        padding: 14, marginBottom: 8, textDecoration: 'none',
                        border: '1px solid var(--border-subtle)',
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 14 }}>{deal.title}</div>
                            <span style={{
                                fontSize: 11, padding: '2px 8px', borderRadius: 6,
                                background: deal.status === 'OPEN' ? 'rgba(74,222,128,0.15)' : 'rgba(136,136,136,0.15)',
                                color: deal.status === 'OPEN' ? 'var(--accent-green)' : 'var(--text-muted)',
                            }}>{deal.status}</span>
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                            {deal.voucher_count || 0}명 응원 | {(deal.current_amount || 0).toLocaleString()}원
                        </div>
                    </Link>
                ))}

                {/* Load More */}
                {hasMore && (
                    <button
                        onClick={() => setVisibleCount(v => v + DEALS_PER_PAGE)}
                        style={{
                            width: '100%', padding: '12px 0', borderRadius: 10,
                            border: '1px solid var(--border-subtle)',
                            background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                            fontSize: 13, fontWeight: 600, cursor: 'pointer',
                            marginTop: 4,
                        }}
                    >더보기 ({filteredDeals.length - visibleCount}개 남음)</button>
                )}
            </div>

            {/* Hero Ranking */}
            {ranking.length > 0 && (
                <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#e0e0e0', marginBottom: 10 }}>
                        히어로 랭킹 TOP 5
                    </div>
                    {ranking.map(h => (
                        <div key={h.hero_id} style={{
                            display: 'flex', alignItems: 'center', gap: 10,
                            background: '#1a1a2e', borderRadius: 10, padding: '10px 14px',
                            marginBottom: 6,
                        }}>
                            <span style={{
                                fontSize: 16, fontWeight: 700,
                                color: h.rank <= 3 ? '#f59e0b' : '#666', width: 24,
                            }}>{h.rank}</span>
                            <span style={{ fontSize: 18 }}>{h.badge}</span>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 600, color: '#e0e0e0' }}>
                                    {h.title}
                                </div>
                                <div style={{ fontSize: 11, color: '#888' }}>
                                    {h.total_stores}곳 추천 | {h.total_points}pt
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Footer Links */}
            <div style={{
                display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center', flexWrap: 'wrap',
            }}>
                <Link to="/donzzul/hero/my-stores" style={{ color: '#888', fontSize: 12, textDecoration: 'none' }}>
                    내가 추천한 가게
                </Link>
            </div>
        </div>
    )
}
