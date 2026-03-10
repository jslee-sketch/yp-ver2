import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { Layout } from './components/layout/Layout';
import AdminLayout from './components/layout/AdminLayout';
import PingpongFloat from './components/layout/PingpongFloat';
import ProtectedRoute from './components/common/ProtectedRoute';
import HomePage from './pages/HomePage';
import DealsListPage from './pages/DealsListPage';
import DealCreatePage from './pages/DealCreatePage';
import SearchPage from './pages/SearchPage';
import MyDealsPage from './pages/MyDealsPage';
import MyOrdersPage from './pages/MyOrdersPage';
import MyPage from './pages/MyPage';
import SpectatingPage from './pages/SpectatingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import PriceJourneyPage from './pages/PriceJourneyPage';
import OfferCreatePage from './pages/OfferCreatePage';
import CompletedDealsPage from './pages/CompletedDealsPage';
import CompletedDealDetailPage from './pages/CompletedDealDetailPage';
import DealJoinPage from './pages/DealJoinPage';
import NotificationsPage from './pages/NotificationsPage';
import PointsPage from './pages/PointsPage';
import ReviewWritePage from './pages/ReviewWritePage';
import SellerShipPage from './pages/SellerShipPage';
import SettlementsPage from './pages/SettlementsPage';
import SellerOffersPage from './pages/SellerOffersPage';
import SellerReviewsPage from './pages/SellerReviewsPage';
import SettingsPage from './pages/SettingsPage';
import TermsPage from './pages/TermsPage';
import SupportPage from './pages/SupportPage';
import NotFoundPage from './pages/NotFoundPage';
import OAuthCallbackPage from './pages/OAuthCallbackPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import ActuatorSellersPage from './pages/ActuatorSellersPage';
import ActuatorSellerOffersPage from './pages/ActuatorSellerOffersPage';
import ActuatorOffersPage from './pages/ActuatorOffersPage';
import ActuatorStatsPage from './pages/ActuatorStatsPage';
import ActuatorCommissionsPage from './pages/ActuatorCommissionsPage';
import ActuatorInvitePage from './pages/ActuatorInvitePage';
import ActuatorContractPage from './pages/ActuatorContractPage';
import SellerSettlementsPage from './pages/SellerSettlementsPage';
import SellerRefundsPage from './pages/SellerRefundsPage';
import SellerStatsPage from './pages/SellerStatsPage';
import SellerDashboardPage from './pages/SellerDashboardPage';
import SellerReturnsPage from './pages/SellerReturnsPage';
import SellerInquiriesPage from './pages/SellerInquiriesPage';
import SellerShippingPolicyPage from './pages/SellerShippingPolicyPage';
import SellerFeesPage from './pages/SellerFeesPage';
import SellerAnnouncementsPage from './pages/SellerAnnouncementsPage';

// Admin pages
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminSellersPage from './pages/AdminSellersPage';
import AdminBuyersPage from './pages/AdminBuyersPage';
import AdminActuatorsPage from './pages/AdminActuatorsPage';
import AdminDisputePage from './pages/AdminDisputePage';
import AdminSettlementsPage from './pages/AdminSettlementsPage';
import AdminDealsPage from './pages/AdminDealsPage';
import AdminOffersPage from './pages/AdminOffersPage';
import AdminReservationsPage from './pages/AdminReservationsPage';
import AdminDeliveryPage from './pages/AdminDeliveryPage';
import AdminRefundsPage from './pages/AdminRefundsPage';
import AdminPolicyParamsPage from './pages/AdminPolicyParamsPage';
import AdminPolicyDocsPage from './pages/AdminPolicyDocsPage';
import AdminPolicyProposalsPage from './pages/AdminPolicyProposalsPage';
import AdminStatsPage from './pages/AdminStatsPage';
import AdminAnomaliesPage from './pages/AdminAnomaliesPage';
import AdminLogsPage from './pages/AdminLogsPage';
import AdminReportsPage from './pages/AdminReportsPage';
import AdminNotificationsPage from './pages/AdminNotificationsPage';
import AdminAnnouncementsPage from './pages/AdminAnnouncementsPage';
import AdminSettingsPage from './pages/AdminSettingsPage';
import AdminRefundSimulatorPage from './pages/AdminRefundSimulatorPage';
import AdminMinorityReportPage from './pages/AdminMinorityReportPage';
import AdminTaxInvoicesPage from './pages/AdminTaxInvoicesPage';
import SellerTaxInvoicesPage from './pages/SellerTaxInvoicesPage';
import SellerBusinessInfoPage from './pages/SellerBusinessInfoPage';

function App() {
  return (
    <AuthProvider>
    <BrowserRouter>
      <PingpongFloat />
      <Routes>
        {/* 레이아웃 없는 페이지 */}
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/auth/callback/:provider" element={<OAuthCallbackPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* 관리자 전용 레이아웃 (AdminLayout + AdminSidebar) */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index                    element={<AdminDashboardPage />} />
          <Route path="stats"             element={<AdminStatsPage />} />
          <Route path="buyers"            element={<AdminBuyersPage />} />
          <Route path="sellers"           element={<AdminSellersPage />} />
          <Route path="actuators"         element={<AdminActuatorsPage />} />
          <Route path="deals"             element={<AdminDealsPage />} />
          <Route path="offers"            element={<AdminOffersPage />} />
          <Route path="reservations"      element={<AdminReservationsPage />} />
          <Route path="delivery"          element={<AdminDeliveryPage />} />
          <Route path="refunds"           element={<AdminRefundsPage />} />
          <Route path="settlements"       element={<AdminSettlementsPage />} />
          <Route path="tax-invoices"     element={<AdminTaxInvoicesPage />} />
          <Route path="disputes"          element={<AdminDisputePage />} />
          <Route path="policy-params"     element={<AdminPolicyParamsPage />} />
          <Route path="policy-docs"       element={<AdminPolicyDocsPage />} />
          <Route path="policy-proposals"  element={<AdminPolicyProposalsPage />} />
          <Route path="logs"              element={<AdminLogsPage />} />
          <Route path="anomalies"         element={<AdminAnomaliesPage />} />
          <Route path="reports"           element={<AdminReportsPage />} />
          <Route path="refund-simulator" element={<AdminRefundSimulatorPage />} />
          <Route path="minority-report" element={<AdminMinorityReportPage />} />
          <Route path="notifications"     element={<AdminNotificationsPage />} />
          <Route path="announcements"     element={<AdminAnnouncementsPage />} />
          <Route path="settings"          element={<AdminSettingsPage />} />
        </Route>

        {/* 레이아웃 공통 적용 */}
        <Route element={<Layout />}>
          <Route path="/"             element={<HomePage />} />
          <Route path="/deals"        element={<DealsListPage />} />
          <Route path="/deal/:id"     element={<PriceJourneyPage />} />
          <Route path="/search"       element={<SearchPage />} />
          <Route path="/completed-deals"     element={<CompletedDealsPage />} />
          <Route path="/completed-deals/:id" element={<CompletedDealDetailPage />} />
          <Route path="/spectating"   element={<SpectatingPage />} />
          <Route path="/terms"        element={<TermsPage />} />
          <Route path="/support"      element={<SupportPage />} />

          {/* 로그인 필요 */}
          <Route path="/deal/create"  element={<ProtectedRoute><DealCreatePage /></ProtectedRoute>} />
          <Route path="/deal/:id/join"         element={<ProtectedRoute><DealJoinPage /></ProtectedRoute>} />
          <Route path="/deal/:id/offer/create" element={<ProtectedRoute><OfferCreatePage /></ProtectedRoute>} />
          <Route path="/my-deals"    element={<ProtectedRoute><MyDealsPage /></ProtectedRoute>} />
          <Route path="/my-orders"   element={<ProtectedRoute><MyOrdersPage /></ProtectedRoute>} />
          <Route path="/my"          element={<ProtectedRoute><MyPage /></ProtectedRoute>} />
          <Route path="/mypage"      element={<ProtectedRoute><MyPage /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="/points"      element={<ProtectedRoute><PointsPage /></ProtectedRoute>} />
          <Route path="/review/write/:reservationId" element={<ProtectedRoute><ReviewWritePage /></ProtectedRoute>} />
          <Route path="/seller/ship/:reservationId"  element={<ProtectedRoute><SellerShipPage /></ProtectedRoute>} />
          <Route path="/seller/delivery"               element={<ProtectedRoute><SellerShipPage /></ProtectedRoute>} />
          <Route path="/settlements" element={<ProtectedRoute><SettlementsPage /></ProtectedRoute>} />
          <Route path="/seller"                 element={<ProtectedRoute><SellerDashboardPage /></ProtectedRoute>} />
          <Route path="/seller/offers"         element={<ProtectedRoute><SellerOffersPage /></ProtectedRoute>} />
          <Route path="/seller/reviews"        element={<ProtectedRoute><SellerReviewsPage /></ProtectedRoute>} />
          <Route path="/seller/settlements"    element={<ProtectedRoute><SellerSettlementsPage /></ProtectedRoute>} />
          <Route path="/seller/refunds"        element={<ProtectedRoute><SellerRefundsPage /></ProtectedRoute>} />
          <Route path="/seller/returns"        element={<ProtectedRoute><SellerReturnsPage /></ProtectedRoute>} />
          <Route path="/seller/inquiries"      element={<ProtectedRoute><SellerInquiriesPage /></ProtectedRoute>} />
          <Route path="/seller/shipping-policy" element={<ProtectedRoute><SellerShippingPolicyPage /></ProtectedRoute>} />
          <Route path="/seller/stats"          element={<ProtectedRoute><SellerStatsPage /></ProtectedRoute>} />
          <Route path="/seller/fees"           element={<ProtectedRoute><SellerFeesPage /></ProtectedRoute>} />
          <Route path="/seller/tax-invoices"  element={<ProtectedRoute><SellerTaxInvoicesPage /></ProtectedRoute>} />
          <Route path="/seller/business-info" element={<ProtectedRoute><SellerBusinessInfoPage /></ProtectedRoute>} />
          <Route path="/seller/notifications"  element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="/seller/announcements"  element={<ProtectedRoute><SellerAnnouncementsPage /></ProtectedRoute>} />
          <Route path="/settings"    element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />

          {/* 액추에이터 */}
          <Route path="/actuator/sellers"                    element={<ProtectedRoute><ActuatorSellersPage /></ProtectedRoute>} />
          <Route path="/actuator/sellers/:sellerId/offers"   element={<ProtectedRoute><ActuatorSellerOffersPage /></ProtectedRoute>} />
          <Route path="/actuator/offers"                     element={<ProtectedRoute><ActuatorOffersPage /></ProtectedRoute>} />
          <Route path="/actuator/stats"                      element={<ProtectedRoute><ActuatorStatsPage /></ProtectedRoute>} />
          <Route path="/actuator/commissions"                element={<ProtectedRoute><ActuatorCommissionsPage /></ProtectedRoute>} />
          <Route path="/actuator/invite"                     element={<ProtectedRoute><ActuatorInvitePage /></ProtectedRoute>} />
          <Route path="/actuator/contract"                   element={<ProtectedRoute><ActuatorContractPage /></ProtectedRoute>} />

          {/* 404 catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
