import React, { useState, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const googleApiKey =
  typeof process !== "undefined" && process.env && process.env.REACT_APP_GOOGLE_API_KEY
    ? process.env.REACT_APP_GOOGLE_API_KEY
    : import.meta.env.VITE_GOOGLE_API_KEY;

const Home = () => {
  const [formData, setFormData] = useState({
    startLat: "",
    startLon: "",
    endLat: "",
    endLon: "",
    maxDays: "",
    optimizationType: "time",
    customWeights: {
      time: 0.25,
      cost: 0.25,
      emissions: 0.25,
      logisticsScore: 0.25,
    },
    weight: "",
    volume: "",
  });

  const [initialAddress, setInitialAddress] = useState("");
  const [finalAddress, setFinalAddress] = useState("");
  const [initialCountry, setInitialCountry] = useState("");
  const [finalCountry, setFinalCountry] = useState("");
  const [routes, setRoutes] = useState([]);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [routeStops, setRouteStops] = useState([]);

  // ### Address Geocoding Functions

  const handleInitialSearch = async () => {
    if (!initialAddress || !googleApiKey) {
      console.error("Initial address or Google API key is missing.");
      return;
    }
    try {
      const response = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(
          initialAddress
        )}&key=${googleApiKey}`
      );
      const data = await response.json();
      if (data.status === "OK" && data.results.length > 0) {
        const location = data.results[0].geometry.location;
        setFormData((prev) => ({
          ...prev,
          startLat: location.lat,
          startLon: location.lng,
        }));
        const countryComponent = data.results[0].address_components.find((comp) =>
          comp.types.includes("country")
        );
        setInitialCountry(countryComponent ? countryComponent.long_name : "");
      } else {
        alert("Address not found for Initial Position.");
      }
    } catch (error) {
      console.error("Error fetching geocode data:", error);
    }
  };

  const handleFinalSearch = async () => {
    if (!finalAddress || !googleApiKey) {
      console.error("Final address or Google API key is missing.");
      return;
    }
    try {
      const response = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(
          finalAddress
        )}&key=${googleApiKey}`
      );
      const data = await response.json();
      if (data.status === "OK" && data.results.length > 0) {
        const location = data.results[0].geometry.location;
        setFormData((prev) => ({
          ...prev,
          endLat: location.lat,
          endLon: location.lng,
        }));
        const countryComponent = data.results[0].address_components.find((comp) =>
          comp.types.includes("country")
        );
        setFinalCountry(countryComponent ? countryComponent.long_name : "");
      } else {
        alert("Address not found for Final Position.");
      }
    } catch (error) {
      console.error("Error fetching geocode data:", error);
    }
  };

  // ### Form Submission Logic

  const sumOfWeights = Object.values(formData.customWeights).reduce(
    (acc, val) => acc + val,
    0
  );
  const isSumValid = Math.abs(sumOfWeights - 1) < 0.0001;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setHasSubmitted(true);

    const dataToSend = {
      startLat: formData.startLat,
      startLon: formData.startLon,
      endLat: formData.endLat,
      endLon: formData.endLon,
      maxDays: formData.maxDays || null,
      optimizationType: formData.optimizationType,
      customWeights: formData.customWeights,
      weight: parseFloat(formData.weight),
      volume: parseFloat(formData.volume),
      initialCountry: initialCountry,
      finalCountry: finalCountry,
    };

    try {
      const response = await fetch("http://localhost:5001/api/find-routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dataToSend),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server error: ${response.status} - ${errorText}`);
      }

      const result = await response.json();
      if (result.status === "success") {
        setRoutes(result.routes);
      } else {
        alert(`Backend error: ${result.message}`);
      }
    } catch (error) {
      console.error("Error submitting form:", error);
      alert(`Failed to fetch routes: ${error.message}. Ensure the backend is running on http://localhost:5001.`);
    }
  };

  // ### Route Stops Calculation

  useEffect(() => {
    if (routes.length > 0) {
      const firstRoute = routes[0];
      const intermediateStops = firstRoute.path.slice(1, -1).filter(
        (point) => point !== firstRoute.path[firstRoute.path.length - 1]
      );

      const geocodePromises = intermediateStops.map((stop) =>
        fetch(
          `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(
            stop
          )}&key=${googleApiKey}`
        )
          .then((response) => response.json())
          .then((data) => {
            if (data.status === "OK" && data.results.length > 0) {
              const location = data.results[0].geometry.location;
              return { name: stop, lat: location.lat, lon: location.lng };
            } else {
              console.warn(`Geocode failed for ${stop}`);
              return null;
            }
          })
          .catch((error) => {
            console.error(`Error geocoding ${stop}:`, error);
            return null;
          })
      );

      Promise.all(geocodePromises).then((intermediateCoords) => {
        const filteredCoords = intermediateCoords.filter((coord) => coord !== null);
        const stops = [
          { name: initialAddress, lat: Number(formData.startLat), lon: Number(formData.startLon) },
          ...filteredCoords,
          { name: finalAddress, lat: Number(formData.endLat), lon: Number(formData.endLon) },
        ];
        setRouteStops(stops);
        console.log("Route Stops:", stops); // Verify data in console
      });
    }
  }, [
    routes,
    initialAddress,
    finalAddress,
    formData.startLat,
    formData.startLon,
    formData.endLat,
    formData.endLon,
  ]);

  // ### Map Bounds Adjustment Component

  const MapUpdater = ({ routeStops }) => {
    const map = useMap();
    useEffect(() => {
      if (routeStops.length > 0) {
        const bounds = routeStops.map((stop) => [Number(stop.lat), Number(stop.lon)]);
        console.log("Bounds:", bounds); // Debug coordinates
        map.fitBounds(bounds);
      }
    }, [routeStops, map]);
    return null;
  };

  // ### JSX Rendering

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 neon-card p-6 rounded-lg">
          <h2 className="text-2xl font-bold mb-6">Shipment Details</h2>
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div className="space-y-4">
              <h3 className="text-lg font-medium bg-gradient-to-r from-cyan-400 to-pink-500 bg-clip-text text-transparent">
                Initial Position
              </h3>
              <div className="flex space-x-2">
                <input
                  type="text"
                  className="mt-1 block w-full rounded-md neon-input"
                  value={initialAddress}
                  onChange={(e) => setInitialAddress(e.target.value)}
                  placeholder="Enter initial address"
                />
                <button
                  type="button"
                  onClick={handleInitialSearch}
                  className="neon-button py-2 px-4 rounded-md"
                >
                  Search
                </button>
              </div>
              {formData.startLat && formData.startLon && (
                <div className="mt-2 text-sm text-gray-300">
                  <p>Latitude: {formData.startLat}</p>
                  <p>Longitude: {formData.startLon}</p>
                  <p>Country: {initialCountry}</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <h3 className="text-lg font-medium bg-gradient-to-r from-cyan-400 to-pink-500 bg-clip-text text-transparent">
                Final Position
              </h3>
              <div className="flex space-x-2">
                <input
                  type="text"
                  className="mt-1 block w-full rounded-md neon-input"
                  value={finalAddress}
                  onChange={(e) => setFinalAddress(e.target.value)}
                  placeholder="Enter final address"
                />
                <button
                  type="button"
                  onClick={handleFinalSearch}
                  className="neon-button py-2 px-4 rounded-md"
                >
                  Search
                </button>
              </div>
              {formData.endLat && formData.endLon && (
                <div className="mt-2 text-sm text-gray-300">
                  <p>Latitude: {formData.endLat}</p>
                  <p>Longitude: {formData.endLon}</p>
                  <p>Country: {finalCountry}</p>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300">
                Max Days (Optional)
              </label>
              <input
                type="number"
                min="1"
                className="mt-1 block w-full rounded-md neon-input"
                value={formData.maxDays}
                onChange={(e) =>
                  setFormData({ ...formData, maxDays: e.target.value })
                }
              />
            </div>

            <div>
              <h3 className="text-lg font-medium mb-2">Preferred Optimization</h3>
              <div className="space-y-2">
                {["time", "cost", "emissions", "logisticsScore", "customWeights"].map(
                  (option) => (
                    <label key={option} className="flex items-center">
                      <input
                        type="radio"
                        name="optimizationType"
                        value={option}
                        checked={formData.optimizationType === option}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            optimizationType: e.target.value,
                          })
                        }
                        className="text-cyan-400"
                      />
                      <span className="ml-2 capitalize text-gray-300">
                        {option.replace(/([A-Z])/g, " $1").trim()}
                      </span>
                    </label>
                  )
                )}
              </div>
            </div>

            {formData.optimizationType === "customWeights" && (
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-gray-300">
                  Custom Weights (Sum must equal 1)
                </h4>
                {Object.keys(formData.customWeights).map((weight) => (
                  <div key={weight}>
                    <label className="block text-sm font-medium text-gray-300 capitalize">
                      {weight.replace(/([A-Z])/g, " $1").trim()}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      className="mt-1 block w-full rounded-md neon-input"
                      value={formData.customWeights[weight]}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          customWeights: {
                            ...formData.customWeights,
                            [weight]: parseFloat(e.target.value),
                          },
                        })
                      }
                    />
                  </div>
                ))}
                <div className="mt-2">
                  <p className="text-sm text-gray-300">
                    Current sum: {sumOfWeights.toFixed(2)}
                  </p>
                  {!isSumValid && (
                    <p className="text-red-500 text-sm">
                      Sum of weights must equal 1
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-4">
              <h3 className="text-lg font-medium bg-gradient-to-r from-cyan-400 to-pink-500 bg-clip-text text-transparent">
                Shipment Measurements
              </h3>
              <div>
                <label className="block text-sm font-medium text-gray-300">
                  Weight (kg)
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="mt-1 block w-full rounded-md neon-input"
                  value={formData.weight}
                  onChange={(e) =>
                    setFormData({ ...formData, weight: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300">
                  Volume (m³)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full rounded-md neon-input"
                  value={formData.volume}
                  onChange={(e) =>
                    setFormData({ ...formData, volume: e.target.value })
                  }
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full neon-button py-2 px-4 rounded-md"
              disabled={
                (formData.optimizationType === "customWeights" && !isSumValid) ||
                !formData.startLat ||
                !formData.startLon ||
                !formData.endLat ||
                !formData.endLon ||
                !formData.weight ||
                !formData.volume
              }
            >
              Find Optimal Routes
            </button>
          </form>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <div className="neon-card p-4 rounded-lg h-[400px]">
            <MapContainer
              center={routeStops.length > 0 ? [Number(routeStops[0].lat), Number(routeStops[0].lon)] : [51.505, -0.09]}
              zoom={13}
              className="h-full w-full rounded-lg"
              style={{ filter: "invert(90%) hue-rotate(180deg)" }}
              // Removed filter to ensure yellow line visibility; re-add if needed with adjusted color
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              />
              {routeStops.length > 0 ? (
                <>
                  {routeStops.map((stop, index) => (
                    <Marker key={index} position={[Number(stop.lat), Number(stop.lon)]}>
                      <Popup>{stop.name}</Popup>
                    </Marker>
                  ))}
                  {routeStops.length > 1 && (
                    <Polyline
                      positions={routeStops.map((stop) => [Number(stop.lat), Number(stop.lon)])}
                      color="blue"
                      weight={4} // Thicker line for better visibility
                      opacity={1} // Fully opaque
                      dashArray="5, 10" // Dotted pattern
                    />
                  )}
                  <MapUpdater routeStops={routeStops} />
                </>
              ) : (
                <>
                  {formData.startLat && formData.startLon && (
                    <Marker position={[Number(formData.startLat), Number(formData.startLon)]}>
                      <Popup>Start: {initialAddress}</Popup>
                    </Marker>
                  )}
                  {formData.endLat && formData.endLon && (
                    <Marker position={[Number(formData.endLat), Number(formData.endLon)]}>
                      <Popup>End: {finalAddress}</Popup>
                    </Marker>
                  )}
                </>
              )}
            </MapContainer>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {routes.length > 0 ? (
              routes.map((route) => (
                <div key={route.rank} className="neon-card p-4 rounded-lg">
                  <div className="flex justify-between items-center pb-4 border-b border-gray-700">
                    <div>
                      <h3 className="text-2xl font-bold text-white">Route {route.rank}</h3>
                      <div className="flex space-x-2 mt-2">
                        {route.modes.includes("land") && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-400/20 text-cyan-400">
                            🚛 Land
                          </span>
                        )}
                        {route.modes.includes("air") && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-pink-500/20 text-pink-500">
                            ✈️ Air
                          </span>
                        )}
                        {route.modes.includes("sea") && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-400/20 text-green-400">
                            🚢 Sea
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-medium text-cyan-400">
                        Cost: ${route.cost.toLocaleString()}
                      </p>
                      <p className="text-lg font-medium text-cyan-400">
                        Time: {route.time_days} days
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 p-4 bg-gray-800 rounded-lg">
                    <p className="text-xl font-bold text-white">
                      Route:{" "}
                      {[
                        initialAddress,
                        ...(route.path
                          .slice(1, -1)
                          .filter((point) => point !== route.path[route.path.length - 1])),
                        finalAddress,
                      ].join(" → ")}
                    </p>
                  </div>

                  <div className="mt-4">
                    <p className="text-md text-gray-300">
                      Carbon Footprint: {route.emissions} kg CO₂
                    </p>
                    <div className="w-full bg-gray-800 rounded-full h-2.5 mt-1">
                      <div
                        className="bg-gradient-to-r from-cyan-400 to-pink-500 h-2.5 rounded-full"
                        style={{ width: `${Math.min(route.emissions / 10, 100)}%` }}
                      ></div>
                    </div>
                  </div>

                  <hr className="my-4 border-gray-700" />

                  <div className="mt-4">
                    <p className="text-md font-medium text-gray-300">Cost Breakdown:</p>
                    <div className="mt-2 space-y-1">
                      {Object.entries(route.cost_breakdown).map(([segment, cost]) => (
                        <div
                          key={segment}
                          className="flex justify-between text-sm text-gray-400"
                        >
                          <span>{segment}</span>
                          <span>${cost.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4">
                    <p className="text-md font-medium text-gray-300">Time Breakdown:</p>
                    <div className="mt-2 space-y-1">
                      {Object.entries(route.time_breakdown).map(([segment, time]) => (
                        <div
                          key={segment}
                          className="flex justify-between text-sm text-gray-400"
                        >
                          <span>{segment}</span>
                          <span>{time} days</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))
            ) : hasSubmitted ? (
              <p className="text-gray-400">No routes found.</p>
            ) : (
              <p className="text-gray-400">Submit the form to find optimal routes.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;