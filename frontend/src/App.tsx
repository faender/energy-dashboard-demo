import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import CustomerDashboard from "./pages/CustomerDashboard";
import ServiceDashboard from "./pages/ServiceDashboard";
import AssetDetailPage from "./pages/AssetDetailPage";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<CustomerDashboard />} />
        <Route path="/service" element={<ServiceDashboard />} />
        <Route path="/service/assets/:assetId" element={<AssetDetailPage />} />
      </Routes>
    </Layout>
  );
}

export default App;
