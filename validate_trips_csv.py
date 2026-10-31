from pathlib import Path
import sys
import pandas as pd

COT_BAT_BUOC = ['trip_id', 'route_id', 'distance_km', 'actual_travel_time',
                'departure_time_full', 'time_slot', 'is_simulated', 'data_source']
DANH_MUC_DATA_SOURCE = {'osrm_api', 'openstreetmap', 'simulated', 'manual'}
FILE_MAC_DINH = Path(__file__).resolve().with_name("trip_data.csv")
COT_TRIP_CSV = [
    'date', 'departure_time', 'route_id', 'route_name', 'distance_km',
    'map_time_min', 'est_time_min', 'avg_speed_kmh', 'status',
    'is_simulated', 'data_source',
]


def _kiem_tra_csv_chuan(df):
    loi = []

    thieu = [c for c in COT_BAT_BUOC if c not in df.columns]
    if thieu:
        loi.append(f"Thieu cot: {thieu}")

    if 'is_simulated' in df.columns:
        gia_tri_la = set(df['is_simulated'].dropna().unique())
        if not gia_tri_la.issubset({0, 1}):
            loi.append(f"is_simulated co gia tri la: {gia_tri_la - {0, 1}}")

    if 'data_source' in df.columns:
        gia_tri_la = set(df['data_source'].dropna().unique())
        if not gia_tri_la.issubset(DANH_MUC_DATA_SOURCE):
            loi.append(f"data_source co gia tri la: {gia_tri_la - DANH_MUC_DATA_SOURCE}")

    for cot in ['distance_km', 'actual_travel_time']:
        if cot in df.columns:
            if not pd.api.types.is_numeric_dtype(df[cot]):
                loi.append(f"{cot} khong phai kieu so")
            elif (df[cot] <= 0).any():
                loi.append(f"{cot} co gia tri <= 0")

    for cot in ['origin_lat', 'origin_lon', 'dest_lat', 'dest_lon']:
        if cot in df.columns and df[cot].notna().any():
            if cot.endswith('lat') and not df[cot].dropna().between(8, 13).all():
                loi.append(f"{cot} nam ngoai mien Viet Nam")
            if cot.endswith('lon') and not df[cot].dropna().between(100, 110).all():
                loi.append(f"{cot} nam ngoai mien Viet Nam")

    if 'trip_id' in df.columns and df['trip_id'].duplicated().any():
        loi.append("trip_id bi trung lap")

    if not loi:
        print(f"[OK] CSV hop le: {len(df)} chuyen, {df['route_id'].nunique()} tuyen, "
              f"is_simulated={sorted(df['is_simulated'].unique())}, "
              f"data_source={sorted(df['data_source'].unique())}")
    return loi


def _kiem_tra_trip_csv(df):
    loi = []
    thieu = [cot for cot in COT_TRIP_CSV if cot not in df.columns]
    if thieu:
        return [f"Thieu cot: {thieu}"]

    ngay = pd.to_datetime(df['date'], format="%Y-%m-%d", errors="coerce")
    if ngay.isna().any():
        loi.append(f"date co {int(ngay.isna().sum())} gia tri trong hoac sai dinh dang")

    gio = pd.to_datetime(df['departure_time'], format="%H:%M", errors="coerce")
    if gio.isna().any():
        loi.append(
            f"departure_time co {int(gio.isna().sum())} gia tri trong hoac sai dinh dang"
        )

    for cot in ['distance_km', 'est_time_min', 'avg_speed_kmh']:
        gia_tri = pd.to_numeric(df[cot], errors="coerce")
        if gia_tri.isna().any():
            loi.append(f"{cot} co {int(gia_tri.isna().sum())} gia tri khong phai so")
        elif (gia_tri <= 0).any():
            loi.append(f"{cot} co gia tri <= 0")

    map_time = df['map_time_min'].astype('string').str.strip()
    map_time_hop_le = map_time.str.fullmatch(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?")
    if not map_time_hop_le.all():
        loi.append(f"map_time_min co {int((~map_time_hop_le).sum())} gia tri sai dinh dang")

    for cot in ['route_id', 'route_name', 'status', 'data_source']:
        gia_tri = df[cot].astype('string').str.strip()
        if gia_tri.isna().any() or gia_tri.eq("").any():
            loi.append(f"{cot} co gia tri trong")

    simulated = df['is_simulated'].astype('string').str.strip().str.lower()
    if not simulated.isin({'true', 'false', '1', '0'}).all():
        loi.append("is_simulated chi duoc nhan true/false hoac 1/0")

    if df.duplicated(subset=['date', 'departure_time', 'route_id']).any():
        loi.append("date, departure_time va route_id bi trung lap")

    if not loi:
        print(
            f"[OK] CSV hop le: {len(df)} chuyen, "
            f"{df['route_id'].nunique()} tuyen, "
            f"is_simulated={sorted(simulated.unique())}, "
            f"data_source={sorted(df['data_source'].astype(str).unique())}"
        )
    return loi


def _doc_csv_bao_cao(file_path):
    raw = pd.read_csv(file_path, header=None, skiprows=1, dtype="string")
    if raw.shape[1] < 22 or raw.empty:
        return None

    headers = raw.iloc[0].fillna("").str.strip()
    if headers.iloc[0] != "Ngày" or headers.iloc[1] != "Giờ đi":
        return None

    return raw.iloc[1:].reset_index(drop=True)


def _kiem_tra_csv_bao_cao(df):
    loi = []
    routes = [
        ("Tuyen 1", 1, 3, 5, 7),
        ("Tuyen 2", 8, 10, 12, 14),
        ("Tuyen 3", 15, 17, 19, 21),
    ]

    ngay = pd.to_datetime(df.iloc[:, 0], format="%d/%m/%Y", errors="coerce")
    if ngay.isna().any():
        loi.append(f"Ngay co {int(ngay.isna().sum())} gia tri trong hoac sai dinh dang")

    for ten_tuyen, cot_gio, cot_quang_duong, cot_du_doan, cot_tinh_trang in routes:
        gio = pd.to_datetime(df.iloc[:, cot_gio], format="%H:%M", errors="coerce")
        if gio.isna().any():
            loi.append(f"{ten_tuyen}: gio di co {int(gio.isna().sum())} gia tri sai")

        for ten_cot, cot in [
            ("quang duong", cot_quang_duong),
            ("thoi gian du doan", cot_du_doan),
        ]:
            gia_tri = pd.to_numeric(df.iloc[:, cot], errors="coerce")
            if gia_tri.isna().any():
                loi.append(f"{ten_tuyen}: {ten_cot} co {int(gia_tri.isna().sum())} gia tri khong phai so")
            elif (gia_tri <= 0).any():
                loi.append(f"{ten_tuyen}: {ten_cot} co gia tri <= 0")

        tinh_trang = df.iloc[:, cot_tinh_trang].fillna("").str.strip()
        if tinh_trang.eq("").any():
            loi.append(f"{ten_tuyen}: co {int(tinh_trang.eq('').sum())} dong thieu tinh trang")

    if not loi:
        print(f"[OK] CSV hop le: {len(df)} dong x 3 tuyen, {len(df) * 3} luot")
    return loi


def kiem_tra(file_path):
    df = pd.read_csv(file_path)
    if set(COT_BAT_BUOC).issubset(df.columns):
        loi = _kiem_tra_csv_chuan(df)
    elif set(COT_TRIP_CSV).issubset(df.columns):
        loi = _kiem_tra_trip_csv(df)
    else:
        report_df = _doc_csv_bao_cao(file_path)
        if report_df is None:
            loi = ["CSV khong dung dinh dang du lieu du chuyen hoac bao cao"]
        else:
            loi = _kiem_tra_csv_bao_cao(report_df)

    if loi:
        print("[LOI] CSV khong hop le:")
        for l in loi:
            print("  -", l)
        sys.exit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    path = sys.argv[1] if len(sys.argv) > 1 else FILE_MAC_DINH
    kiem_tra(path)
