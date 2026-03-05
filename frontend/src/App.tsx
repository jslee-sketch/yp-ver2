import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { Layout } from './components/layout/Layout';
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
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminSellersPage from './pages/AdminSellersPage';
import AdminBuyersPage from './pages/AdminBuyersPage';
import AdminActuatorsPage from './pages/AdminActuatorsPage';
import AdminDisputePage from './pages/AdminDisputePage';
import AdminSettlementsPage from './pages/AdminSettlementsPage';
import ActuatorSellersPage from './pages/ActuatorSellersPage';
import ActuatorSellerOffersPage from './pages/ActuatorSellerOffersPage';
import ActuatorOffersPage from './pages/ActuatorOffersPage';
import ActuatorStatsPage from './pages/ActuatorStatsPage';
import ActuatorCommissionsPage from './pages/ActuatorCommissionsPage';
import ActuatorInvitePage from './pages/ActuatorInvitePage';

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
          <Route path="/seller/offers" element={<ProtectedRoute><SellerOffersPage /></ProtectedRoute>} />
          <Route path="/seller/reviews" element={<ProtectedRoute><SellerReviewsPage /></ProtectedRoute>} />
          <Route path="/settings"    element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />

          {/* 액추에이터 */}
          <Route path="/actuator/sellers"                    element={<ProtectedRoute><ActuatorSellersPage /></ProtectedRoute>} />
          <Route path="/actuator/sellers/:sellerId/offers"   element={<ProtectedRoute><ActuatorSellerOffersPage /></ProtectedRoute>} />
          <Route path="/actuator/offers"                     element={<ProtectedRoute><ActuatorOffersPage /></ProtectedRoute>} />
          <Route path="/actuator/stats"                      element={<ProtectedRoute><ActuatorStatsPage /></ProtectedRoute>} />
          <Route path="/actuator/commissions"                element={<ProtectedRoute><ActuatorCommissionsPage /></ProtectedRoute>} />
          <Route path="/actuator/invite"                     element={<ProtectedRoute><ActuatorInvitePage /></ProtectedRoute>} />

          {/* 관리자 */}
          <Route path="/admin"           element={<ProtectedRoute><AdminDashboardPage /></ProtectedRoute>} />
          <Route path="/admin/sellers"   element={<ProtectedRoute><AdminSellersPage /></ProtectedRoute>} />
          <Route path="/admin/buyers"    element={<ProtectedRoute><AdminBuyersPage /></ProtectedRoute>} />
          <Route path="/admin/actuators"    element={<ProtectedRoute><AdminActuatorsPage /></ProtectedRoute>} />
          <Route path="/admin/disputes"     element={<ProtectedRoute><AdminDisputePage /></ProtectedRoute>} />
          <Route path="/admin/settlements"  element={<ProtectedRoute><AdminSettlementsPage /></ProtectedRoute>} />

          {/* 404 catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
