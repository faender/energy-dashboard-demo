import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { SiteSummary } from "../api/client";
import { ASSET_TYPE_LABEL, SERIES_COLOR } from "../theme";

function radiusForSite(site: SiteSummary) {
  // grobe Flächenskalierung nach Anlagenanzahl je Standort, rein optisch
  return Math.max(8, Math.min(26, 6 + site.asset_count * 0.8));
}

export default function PortfolioMap({ sites }: { sites: SiteSummary[] }) {
  return (
    <MapContainer center={[47.65, 14.9]} zoom={7} scrollWheelZoom={false} className="h-full w-full rounded-xl">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {sites.map((site) => {
        const color = SERIES_COLOR[site.asset_type];
        const allOnline = site.online_count === site.asset_count;
        return (
          <CircleMarker
            key={site.site_id}
            center={[site.lat, site.lon]}
            radius={radiusForSite(site)}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: allOnline ? 0.55 : 0.3,
              weight: 2,
            }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">{site.site_name}</div>
                <div className="text-gray-500">{ASSET_TYPE_LABEL[site.asset_type]}</div>
                <div className="mt-1">
                  {site.online_count} / {site.asset_count} Anlagen online
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
