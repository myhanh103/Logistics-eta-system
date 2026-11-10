import pandas as pd
from pathlib import Path

# Xác định thư mục data của project
DATA_DIR = Path(__file__).resolve().parents[1]

# Đường dẫn đến file dữ liệu thô
RAW_FILE = DATA_DIR / "raw" / "sample_trips_raw.csv"

# Đường dẫn lưu dữ liệu sạch mới
OUTPUT_FILE = DATA_DIR / "processed" / "sample_trips_rebuilt.csv"


ROUTES = {"R01": "Cho Ben Thanh -> Landmark 81",
          "R02": "San bay Tan Son Nhat -> DH Bach Khoa"}
SLOT_LABEL = {1: "sang (6h-9h)", 2: "trua (9h-16h)", 3: "gio cao diem (16h-19h)", 4: "toi (19h-23h)"}

def slot_from_hour(h):
    if 6 <= h < 9:
        return 1
    elif 9 <= h < 16:
        return 2
    elif 16 <= h < 19:
        return 3
    elif 19 <= h < 23:
        return 4
    else:
        return None

df = pd.read_csv(RAW_FILE)

# 1. Loai ban ghi trung lap theo trip_id, giu ban dau tien
n_dup = df.trip_id.duplicated().sum()
df = df.drop_duplicates(subset="trip_id", keep="first")

# 2. Chuan hoa kieu du lieu (ngay dang ISO YYYY-MM-DD; dinh dang sai -> NaT -> loai o buoc 4)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["route_name"] = df["route_name"].fillna(df["route_id"].map(ROUTES))

# 3. Tinh lai time_slot TU departure_time de dam bao nhat quan (loai thieu gia tri)
hh = pd.to_numeric(df["departure_time"].str[:2], errors="coerce")
df["time_slot"] = hh.map(slot_from_hour)
df["time_slot_label"] = df["time_slot"].map(SLOT_LABEL)

# 4. Kiem chung nghiep vu — moi dong bi loai phai co LY DO cu the
HCMC_LAT, HCMC_LON = (10.20, 11.20), (106.30, 107.10)
reasons = []
for _, r in df.iterrows():
    why = []
    if not pd.notna(r["date"]): why.append("ngay sai/thieu")
    if not (0.5 <= r["distance_km"] <= 30): why.append(f"khoang cach {r['distance_km']} km")
    if not pd.notna(r["actual_duration_min"]) or not (3 <= r["actual_duration_min"] <= 180):
        why.append("thoi gian <=0 hoac thieu")
    if pd.notna(r["avg_speed_kmh"]) and r["avg_speed_kmh"] > 80: why.append(f"toc do {r['avg_speed_kmh']} km/h")
    if not (HCMC_LAT[0] <= r["dest_lat"] <= HCMC_LAT[1] and HCMC_LON[0] <= r["dest_lon"] <= HCMC_LON[1]):
        why.append("toa do ngoai TP.HCM")
    if not pd.notna(r["time_slot"]): why.append("gio xuat phat sai")
    reasons.append("; ".join(why))
df["_reason"] = reasons
bad = df[df["_reason"] != ""]
clean = df[df["_reason"] == ""].copy()

# 5. Tinh lai toc do sau khi loc, dam bao nhat quan
clean["avg_speed_kmh"] = (clean["distance_km"] / (clean["actual_duration_min"] / 60)).round(1)
clean["date"] = clean["date"].dt.strftime("%Y-%m-%d")
clean = clean.drop(columns=["_reason"]).sort_values(["route_id", "date", "departure_time"])
clean.to_csv(OUTPUT_FILE, index=False)

print(f"Raw: {len(df)+n_dup} | Trung lap loai: {n_dup} | Khong hop le loai: {len(bad)} | Clean: {len(clean)}")
print("Ly do loai tung ban ghi:")
print(bad[["trip_id", "_reason"]].to_string(index=False))
