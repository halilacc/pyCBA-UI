// /api/* isteklerini Python API'sine yönlendirir: tarayıcı tek kökenle konuşur
// (CORS yok). Üretimde API_URL ortam değişkeni verilir.
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

export default {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};
