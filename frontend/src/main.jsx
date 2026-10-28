
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { compareRoutes } from "./services/routesApi";
import "./style.css";
import RouteMap from "./components/RouteMap";

// Địa điểm đã biết tọa độ để thử API.
// Bước sau sẽ bổ sung tìm kiếm địa điểm / geocoding.
const LOCATIONS = {
  "Chợ Bến Thành, Quận 1, TP.HCM": {
    lat: 10.773233,
    lng: 106.697935
  },
  "Landmark 81, Bình Thạnh, TP.HCM": {
    lat: 10.794820,
    lng: 106.721950
  }
};

function Steps({ screen }) {
  const names = [
    "Nhập chuyến đi",
    "So sánh tuyến",
    "Đề xuất"
  ];

  return (
    <div className="steps">
      {names.map((name, index) => (
        <div
          key={name}
          className={
            "step " +
            (screen === index + 1 ? "active" : "")
          }
        >
          {String(index + 1).padStart(2, "0")}
          &nbsp; {name}
        </div>
      ))}
    </div>
  );
}


function MapPreview({
    compare = false,
    routes = [],
    recommendedRouteId = null,
    onlyRecommended = false,
    selectedRouteId = null,
    onSelectRoute
}) {
  // Màn hình 3 chỉ hiển thị tuyến được đề xuất.
  const visibleRoutes = onlyRecommended
    ? routes.filter(
        (route) =>
          route.route_id === recommendedRouteId
      )
    : routes;

  return (
    <div
      className={
        "map-panel real-map-panel " +
        (compare ? "compare-map" : "")
      }
    >
      <div className="real-map-title">
        Khu vực tìm đường tại TP.HCM
      </div>

      <RouteMap
        routes={visibleRoutes}
        recommendedRouteId={recommendedRouteId}
        selectedRouteId={selectedRouteId}
        onSelectRoute={onSelectRoute}
      />

      <div className="real-map-note">
        {visibleRoutes.length > 0
          ? "TUYẾN ĐƯỜNG TỪ OSRM • CHƯA CÓ GPS REALTIME"
          : "BẢN ĐỒ OPENSTREETMAP • CHƯA TÌM TUYẾN"}
      </div>
    </div>
  );
}

function App() {
  const [screen, setScreen] = useState(1);

  const [origin, setOrigin] = useState(
    "Chợ Bến Thành, Quận 1, TP.HCM"
  );

  const [destination, setDestination] = useState(
    "Landmark 81, Bình Thạnh, TP.HCM"
  );

  const [departure, setDeparture] = useState(
    "2026-10-30T08:00"
  );

  // Dữ liệu thực tế nhận từ FastAPI
  const [routes, setRoutes] = useState([]);
  const [recommendedRouteId, setRecommendedRouteId] =
    useState(null);

  const [selectedRouteId, setSelectedRouteId] =
    useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const recommendedRoute = routes.find(
    (route) => route.route_id === recommendedRouteId
  );

  // Gửi dữ liệu React → FastAPI → OSRM
  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");

    const originPoint = LOCATIONS[origin.trim()];
    const destinationPoint = LOCATIONS[destination.trim()];

    if (!originPoint || !destinationPoint) {
      setMessage(
        "Bản thử nghiệm hiện chỉ hỗ trợ Chợ Bến Thành và Landmark 81. " +
        "Hãy dùng đúng tên hai địa điểm mẫu."
      );
      return;
    }

    if (origin.trim() === destination.trim()) {
      setMessage(
        "Điểm xuất phát và điểm đến phải khác nhau."
      );
      return;
    }

    if (!departure) {
      setMessage("Vui lòng chọn thời gian khởi hành.");
      return;
    }

    setLoading(true);
    setRoutes([]);
    setRecommendedRouteId(null);

    try {
      const data = await compareRoutes({
        origin: originPoint,
        destination: destinationPoint,
        departure_time: new Date(departure).toISOString()
      });

      if (
        !Array.isArray(data.candidate_routes) ||
        data.candidate_routes.length === 0
      ) {
        throw new Error("API không trả về tuyến đường.");
      }

      if (
        !data.candidate_routes.some(
          (route) =>
            route.route_id === data.recommended_route_id
        )
      ) {
        throw new Error(
          "API không trả về tuyến đề xuất hợp lệ."
        );
      }

      setRoutes(data.candidate_routes);
      setRecommendedRouteId(data.recommended_route_id);
      setSelectedRouteId(data.recommended_route_id);
      setScreen(2);

    } catch (error) {
      setMessage(
        "Không lấy được dữ liệu tuyến đường: " +
        error.message
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">

      {/* HEADER */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon">↗</div>
          <span>LOGISTICS ETA</span>
        </div>

        <span className="header-subtitle">
          Dự báo thời gian và chọn tuyến giao hàng
        </span>
      </header>

      <main className="main">
        <Steps screen={screen} />

        {/* MÀN HÌNH 1 */}
        {screen === 1 && (
          <>
            <div className="page-heading">
              <h1>Lập kế hoạch chuyến đi</h1>
              <p>
                Nhập thông tin chuyến hàng để tìm
                tuyến đường phù hợp.
              </p>
            </div>

            <div className="content-grid">
              <form
                className="input-panel"
                onSubmit={handleSubmit}
              >
                <div className="field">
                  <label htmlFor="origin">
                    Điểm xuất phát
                  </label>

                  <input
                    id="origin"
                    value={origin}
                    onChange={(e) =>
                      setOrigin(e.target.value)
                    }
                  />
                </div>

                <div className="field">
                  <label htmlFor="destination">
                    Điểm đến
                  </label>

                  <input
                    id="destination"
                    value={destination}
                    onChange={(e) =>
                      setDestination(e.target.value)
                    }
                  />
                </div>

                <div className="field">
                  <label htmlFor="departure">
                    Thời gian khởi hành
                  </label>

                  <input
                    id="departure"
                    type="datetime-local"
                    value={departure}
                    onChange={(e) =>
                      setDeparture(e.target.value)
                    }
                  />
                </div>

                <p className="helper-text">
                  Hiện hỗ trợ thử nghiệm với
                  Chợ Bến Thành và Landmark 81.
                </p>

                <button
                  type="submit"
                  className="primary-btn"
                  disabled={loading}
                >
                  {loading
                    ? "Đang lấy tuyến từ OSRM..."
                    : "Tìm và so sánh tuyến đường →"}
                </button>

                {message && (
                  <p
                    className="form-message"
                    role="alert"
                  >
                    {message}
                  </p>
                )}
              </form>

              <MapPreview />
            </div>
          </>
        )}

        {/* MÀN HÌNH 2 */}

        {screen === 2 && (
          <>
            <div className="page-heading">
              <h1>So sánh tuyến đường</h1>
              <p>
                {origin} → {destination}
                {" · "}
                Khởi hành: {departure.replace("T", " ")}
              </p>
            </div>

            <div className="comparison-grid">

              <MapPreview
                compare
                routes={routes}
                recommendedRouteId={recommendedRouteId}
                selectedRouteId={selectedRouteId}
                onSelectRoute={setSelectedRouteId}
              />

              <section className="route-sidebar">
                <h2>Các tuyến ứng viên</h2>

                <p className="selected-route-info">
                Đang xem: Tuyến {selectedRouteId || "—"}
                {selectedRouteId === recommendedRouteId
                    ? " (tuyến đề xuất)"
                    : " (tuyến thay thế)"}
                </p>


                {routes.map((route) => {
                  const isBest =
                    route.route_id === recommendedRouteId;

                  return (
                    <div
                      key={route.route_id}
                      className={
                        "route-card " +
                        (isBest ? "recommended" : "") +
                        (
                            selectedRouteId === route.route_id
                            ? " selected"
                            : ""
                        )
                      }
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedRouteId(route.route_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          setSelectedRouteId(route.route_id);
                        }
                      }}
                    >
                      <div className="route-title-row">
                        <h3>
                          Tuyến {route.route_id}
                        </h3>

                        {isBest && (
                          <span className="recommended-tag">
                            ĐỀ XUẤT
                          </span>
                        )}
                      </div>

                      <div className="route-details">
                        <span>
                          {route.distance_km.toLocaleString(
                            "vi-VN"
                          )} km
                        </span>

                        <strong>
                          {route.predicted_duration_min.toLocaleString(
                            "vi-VN"
                          )} phút
                        </strong>
                      </div>
                    </div>
                  );
                })}

                <p className="demo-notice">
                  Dữ liệu tuyến thực tế từ OSRM.
                  Thời gian là ước tính OSRM,
                  chưa phải dự đoán ML.
                </p>

                <button
                  className="primary-btn"
                  type="button"
                  onClick={() => setScreen(3)}
                  disabled={!recommendedRoute}
                >
                  Xem tuyến được đề xuất →
                </button>
              </section>
            </div>

            <button
              className="back-btn"
              type="button"
              onClick={() => setScreen(1)}
            >
              ← Quay lại nhập liệu
            </button>
          </>
        )}

        {/* MÀN HÌNH 3 */}
        {screen === 3 && recommendedRoute && (
          <>
            <div className="page-heading">
              <h1>Tuyến đường được đề xuất</h1>
              <p>
                Dựa trên thời gian OSRM ước tính
                thấp nhất trong các tuyến khả dụng.
              </p>
            </div>

            <div className="recommendation-grid">

              <section className="recommendation-panel">
                <div className="best-label">
                  ✓ TUYẾN NHANH NHẤT THEO OSRM
                </div>

                <h2>
                  Tuyến {recommendedRoute.route_id}
                </h2>

                <div className="best-eta">
                  {recommendedRoute.predicted_duration_min.toLocaleString(
                    "vi-VN"
                  )} phút
                </div>

                <p className="eta-caption">
                  Thời gian ước tính từ OSRM
                </p>

                <div className="recommendation-info">
                  <div>
                    <span>Quãng đường</span>
                    <strong>
                      {recommendedRoute.distance_km.toLocaleString(
                        "vi-VN"
                      )} km
                    </strong>
                  </div>

                  <div>
                    <span>Điểm đến</span>
                    <strong>{destination}</strong>
                  </div>
                </div>
              </section>

              <MapPreview
                compare
                routes={routes}
                recommendedRouteId={recommendedRouteId}
              />
            </div>

            <section className="quick-comparison">
              <h2>So sánh nhanh</h2>

              <div className="quick-route-list">
                {routes.map((route) => (
                  <div
                    key={route.route_id}
                    className={
                      "quick-route " +
                      (
                        route.route_id === recommendedRouteId
                          ? "best"
                          : ""
                      )
                    }
                  >
                    Tuyến {route.route_id}
                    {" · "}
                    {route.predicted_duration_min.toLocaleString(
                      "vi-VN"
                    )} phút
                    {" · "}
                    {route.distance_km.toLocaleString(
                      "vi-VN"
                    )} km
                  </div>
                ))}
              </div>
            </section>

            <div className="recommendation-actions">
              <button
                className="back-btn"
                type="button"
                onClick={() => setScreen(2)}
              >
                ← Quay lại so sánh
              </button>

              <button
                className="new-trip-btn"
                type="button"
                onClick={() => {
                  setMessage("");
                  setRoutes([]);
                  setRecommendedRouteId(null);
                  setScreen(1);
                }}
              >
                Tạo chuyến đi mới ↻
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
