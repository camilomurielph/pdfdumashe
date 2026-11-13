from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

app = FastAPI(title="Dumashe Inventario PDF Generator")

# Permitir peticiones desde Tampermonkey y cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

env = Environment(loader=FileSystemLoader("templates"))

class ProductItem(BaseModel):
    sku: str
    name: str
    qty: int
    img: Optional[str] = None

class InventoryPayload(BaseModel):
    items: List[ProductItem]
    notas: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head><title>Dumashe PDF Service</title></head>
        <body style="font-family: sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; background:#0f172a; color:#fff;">
            <div style="text-align:center;">
                <h1 style="color:#ff2688;">Dumashe PDF Microservice</h1>
                <p>Servicio activo y listo para recibir peticiones desde Tampermonkey en <code>POST /api/export-pdf</code></p>
            </div>
        </body>
    </html>
    """

@app.post("/api/export-pdf")
def generate_pdf(payload: InventoryPayload):
    tz_col = ZoneInfo("America/Bogota")
    now = datetime.now(tz_col)
    fecha_str = now.strftime("%d/%m/%Y %I:%M %p")

    total_unidades = sum(item.qty for item in payload.items)

    template = env.get_template("reporte.html")
    html_content = template.render(
        fecha=fecha_str,
        items=payload.items,
        total_referencias=len(payload.items),
        total_unidades=total_unidades,
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
