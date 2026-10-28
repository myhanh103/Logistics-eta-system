
const API_URL = "http://127.0.0.1:8000/api/v1/routes/compare";

export async function compareRoutes(payload) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const result = await response.json();

  if (!response.ok) {
    const detail = result.detail;

    throw new Error(
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail || "API gặp lỗi")
    );
  }

  return result;
}
