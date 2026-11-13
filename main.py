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

APP_PASSWORD = os.environ.get("APP_PASSWORD", "dumashe123")


def verify_password(x_app_password: Optional[str] = Header(None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta o no proporcionada")


class ProductItem(BaseModel):
    sku: str
    name: str
    qty: Optional[int] = 0
    img: Optional[str] = ""


class StatePayload(BaseModel):
    items: List[ProductItem]
    pendientes: List[ProductItem]


class InventoryPayload(BaseModel):
    items: List[ProductItem]
    notas: Optional[str] = ""


class DeleteItemPayload(BaseModel):
    sku: str
    name: str
    list_type: Optional[str] = "items"  # "items" o "pendientes"


def read_catalog():
    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "pendientes" not in data:
                data["pendientes"] = []
            if "items" not in data:
                data["items"] = []
            return data
    return {"updated_at": None, "items": [], "pendientes": []}


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
    current = read_catalog()

    # Conservar cantidades guardadas previamente en servidor si el producto ya existía
    existing_qty = {(i["sku"], i["name"]): i.get("qty", 0) for i in current.get("items", [])}
    merged_items = []
    for item in payload.items:
        item_dict = item.model_dump()
        key = (item_dict["sku"], item_dict["name"])
        if key in existing_qty and existing_qty[key] != 0:
            item_dict["qty"] = existing_qty[key]
        merged_items.append(item_dict)

    data = {
        "updated_at": now_str,
        "items": merged_items,
        "pendientes": current.get("pendientes", [])
    }
    write_catalog(data)
    return {"status": "ok", "count": len(merged_items), "updated_at": now_str}


@app.post("/api/save-state", dependencies=[Depends(verify_password)])
def save_state(payload: StatePayload):
    tz_col = ZoneInfo("America/Bogota")
    now_str = datetime.now(tz_col).strftime("%d/%m/%Y %I:%M %p")
    data = {
        "updated_at": now_str,
        "items": [item.model_dump() for item in payload.items],
        "pendientes": [item.model_dump() for item in payload.pendientes]
    }
    write_catalog(data)
    return {"status": "ok", "updated_at": now_str}


@app.delete("/api/catalog", dependencies=[Depends(verify_password)])
def clear_catalog():
    current = read_catalog()
    write_catalog({
        "updated_at": None,
        "items": [],
        "pendientes": current.get("pendientes", [])
    })
    return {"status": "ok"}


@app.post("/api/catalog/delete-item", dependencies=[Depends(verify_password)])
def delete_catalog_item(item: DeleteItemPayload):
    data = read_catalog()
    target = "pendientes" if item.list_type == "pendientes" else "items"
    data[target] = [
        i for i in data.get(target, [])
        if not (i["sku"] == item.sku and i["name"] == item.name)
    ]
    write_catalog(data)
    return {"status": "ok", "remaining": len(data[target])}


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
