/** 주문번호 표시 컴포넌트 — order_number 우선, 없으면 R-{id} 폴백 */
export default function OrderNumber({ orderNumber, reservationId, style }: {
    orderNumber?: string | null;
    reservationId?: number | null;
    style?: React.CSSProperties;
}) {
    const display = orderNumber || (reservationId ? `R-${reservationId}` : '—');
    return (
        <span style={{
            fontFamily: 'monospace',
            fontWeight: 600,
            letterSpacing: '0.5px',
            ...style,
        }}>
            {display}
        </span>
    );
}
