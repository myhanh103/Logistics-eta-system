
import React, { useEffect, useMemo } from "react";

import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER = [10.78, 106.71];

// OSRM: [lng, lat] -> Leaflet: [lat, lng]
function convertCoordinates(coordinates = []) {
  return coordinates
    .filter(
      (point) =>
        Array.isArray(point) &&
        point.length >= 2 &&
        Number.isFinite(point[0]) &&
        Number.isFinite(point[1])
    )
    .map(([lng, lat]) => [lat, lng]);
}

// Tự phóng bản đồ để thấy tất cả tuyến đường
function MapBounds({ routes }) {
  const map = useMap();

  useEffect(() => {
    map.invalidateSize();

    const allPoints = routes.flatMap(
      (route) => route.positions
    );

    if (allPoints.length > 0) {
      map.fitBounds(allPoints, {
        padding: [35, 35],
        maxZoom: 15
      });
    }
  }, [map, routes]);

  return null;
}

export default function RouteMap({
  routes = [],
  recommendedRouteId = null,
  selectedRouteId = null,
  onSelectRoute
}) {
  const preparedRoutes = useMemo(() => {
    return routes
      .map((route) => ({
        ...route,
        positions: convertCoordinates(
          route.geometry?.coordinates || []
        )
      }))
      .filter((route) => route.positions.length >= 2)

      // Vẽ tuyến đề xuất trước.
      // Tuyến thay thế được vẽ sau để không bị che.
      .sort((a, b) => {
        const aBest =
          a.route_id === recommendedRouteId ? 1 : 0;

        const bBest =
          b.route_id === recommendedRouteId ? 1 : 0;

        return bBest - aBest;
      });
  }, [routes, recommendedRouteId]);

  const firstRoute = preparedRoutes[0];

  const startPoint = firstRoute?.positions[0];

  const endPoint =
    firstRoute?.positions[
      firstRoute.positions.length - 1
    ];

  return (
    <div className="route-map-container">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={13}
        scrollWheelZoom={true}
        style={{
          height: "100%",
          width: "100%"
        }}
      >
        <TileLayer
          attribution={
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          }
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapBounds routes={preparedRoutes} />

        {preparedRoutes.map((route) => {
          const isRecommended =
            route.route_id === recommendedRouteId;

          const isSelected =
            route.route_id === selectedRouteId;

          return (
            <Polyline
              key={route.route_id}
              positions={route.positions}
              pathOptions={{
                // Tuyến đề xuất: xanh đậm
                // Tuyến thay thế: cam
                color: isRecommended
                  ? "#1d4ed8"
                  : "#f97316",

                weight: isSelected
                  ? 8
                  : isRecommended
                    ? 6
                    : 5,

                opacity: isSelected ? 1 : 0.85,

                // Nét đứt để nhận diện tuyến khác
                dashArray: isRecommended
                  ? undefined
                  : "9 8"
              }}
              eventHandlers={{
                click: () => {
                  onSelectRoute?.(route.route_id);
                }
              }}
            >
              <Tooltip sticky>
                Tuyến {route.route_id}
                {" — "}
                {route.distance_km} km
                {" — "}
                {route.osrm_duration_min} phút
                {isRecommended ? " — Đề xuất" : ""}
              </Tooltip>
            </Polyline>
          );
        })}

        {startPoint && (
          <CircleMarker
            center={startPoint}
            radius={9}
            pathOptions={{
              color: "#ffffff",
              weight: 3,
              fillColor: "#1d4ed8",
              fillOpacity: 1
            }}
          >
            <Tooltip>Điểm xuất phát</Tooltip>
          </CircleMarker>
        )}

        {endPoint && (
          <CircleMarker
            center={endPoint}
            radius={9}
            pathOptions={{
              color: "#ffffff",
              weight: 3,
              fillColor: "#15803d",
              fillOpacity: 1
            }}
          >
            <Tooltip>Điểm đến</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}
