import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from fastapi import FastAPI, Response, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

app = FastAPI(title="Dumashe Inventario PDF Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

env = Environment(loader=FileSystemLoader("templates"))
DATA_DIR = "data"
CATALOG_FILE = os.path.join(DATA_DIR, "catalogo.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Leer contraseña desde Variable de Entorno en Coolify
APP_PASSWORD = os.environ.get("APP_PASSWORD", "dumashe123")

def verify_password(x_app_password: Optional[str] = Header(None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta o no proporcionada")

class ProductItem(BaseModel):
    sku: str
    name: str
    qty: Optional[int] = 0
    img: Optional[str] = ""

class InventoryPayload(BaseModel):
    items: List[ProductItem]
    notas: Optional[str] = ""

class DeleteItemPayload(BaseModel):
    sku: str
    name: str

def read_catalog():
    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "items": []}

def write_catalog(data):
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/", response_class=HTMLResponse)
def home():
    template = env.get_template("index.html")
    return template.render()

@app.post("/api/login")
def login(x_app_password: Optional[str] = Header(None)):
    if x_app_password == APP_PASSWORD:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/api/catalog", dependencies=[Depends(verify_password)])
def get_catalog():
    return read_catalog()

@app.post("/api/sync-catalog", dependencies=[Depends(verify_password)])
def sync_catalog(payload: InventoryPayload):
    tz_col = ZoneInfo("America/Bogota")
    now_str = datetime.now(tz_col).strftime("%d/%m/%Y %I:%M %p")
    data = {
        "updated_at": now_str,
        "items": [item.model_dump() for item in payload.items]
    }
    write_catalog(data)
    return {"status": "ok", "count": len(payload.items), "updated_at": now_str}

@app.delete("/api/catalog", dependencies=[Depends(verify_password)])
def clear_catalog():
    write_catalog({"updated_at": None, "items": []})
    return {"status": "ok"}

@app.post("/api/catalog/delete-item", dependencies=[Depends(verify_password)])
def delete_catalog_item(item: DeleteItemPayload):
    data = read_catalog()
    data["items"] = [
        i for i in data["items"]
        if not (i["sku"] == item.sku and i["name"] == item.name)
    ]
    write_catalog(data)
    return {"status": "ok", "remaining": len(data["items"])}

@app.post("/api/export-pdf", dependencies=[Depends(verify_password)])
def generate_pdf(payload: InventoryPayload):
    tz_col = ZoneInfo("America/Bogota")
    now = datetime.now(tz_col)
    fecha_str = now.strftime("%d/%m/%Y %I:%M %p")

    template = env.get_template("reporte.html")
    html_content = template.render(
        fecha=fecha_str,
        items=payload.items,
        notas=payload.notas
    )

    pdf_bytes = HTML(string=html_content).write_pdf()
    filename = f"Inventario_Dumashe_{now.strftime('%Y-%m-%d_%H%M')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
