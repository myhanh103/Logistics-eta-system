
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# API gốc của Người 5
from app.api.v1.endpoints import router as api_v1_router

# API tích hợp OSRM và thuật toán chọn tuyến Người 4
from app.api.v1.real_routes import router as real_routes_router


# ==========================================
# 1. KHỞI TẠO FASTAPI
# ==========================================

app = FastAPI(
    title="Smart Logs ETA API Service",
    description=(
        "Hệ thống dự đoán thời gian di chuyển "
        "và lựa chọn tuyến giao hàng tối ưu"
    ),
    version="1.0.0"
)


# ==========================================
# 2. CẤU HÌNH CORS
# Cho phép Frontend React kết nối Backend
# ==========================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ],

    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ==========================================
# 3. API KIỂM TRA BACKEND
# ==========================================

@app.get("/health", tags=["Health Check"])
def health_check():
    return {
        "status": "ok",
        "message": (
            "Smart Logs Backend đang "
            "hoạt động bình thường"
        )
    }


# ==========================================
# 4. ĐĂNG KÝ API GỐC - NGƯỜI 5
# ==========================================

app.include_router(
    api_v1_router,
    prefix="/api/v1",
    tags=["Routes & ETA"]
)


# ==========================================
# 5. ĐĂNG KÝ API OSRM + THUẬT TOÁN
# ==========================================

app.include_router(
    real_routes_router,
    prefix="/api/v1",
    tags=["OSRM - Real Routes"]
)
