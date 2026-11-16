"""Arma el archivo Excel del informe a partir de las filas que la persona reviso y edito."""

from io import BytesIO

COLUMNAS = [
    ("Fecha", "fecha", 16),
    ("Código", "codigo", 12),
    ("Máquina", "maquina", 28),
    ("Incidencias", "incidencias", 46),
    ("Mantenimientos", "mantenimientos", 34),
    ("Observaciones", "observaciones", 46),
    ("Estado de la máquina", "estado", 24),
]
COLOR_ESTADO = {
    "operativo": "DCFCE7",
    "en mantenimiento": "FEF3C7",
    "fuera de servicio": "FECACA",
    "con incidencias": "FEF3C7",
}


def _escribir(celda, valor):
    """Escribe texto sin dejar que Excel lo interprete como formula (=, +, -, @)."""
    texto = "" if valor is None else str(valor)
    celda.value = texto
    celda.data_type = "s"


def _color_estado(estado: str):
    e = (estado or "").lower()
    for clave, color in COLOR_ESTADO.items():
        if clave in e:
            return color
    return None


def generar_excel(informe: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Informe"
    ultima_col = len(COLUMNAS)
    borde = Side(style="thin", color="D1D5DB")
    rojo = "B91C1C"

    hoja.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ultima_col)
    titulo = hoja.cell(row=1, column=1)
    _escribir(titulo, f"Informe de funcionamiento de máquinas — {informe.get('etiqueta', '')}")
    titulo.font = Font(name="Calibri", size=16, bold=True, color=rojo)
    titulo.alignment = Alignment(vertical="center")
    hoja.row_dimensions[1].height = 28

    encabezado = [
        ("Gimnasio", informe.get("gimnasio", "")),
        ("Responsable a cargo", informe.get("responsable", "")),
        ("Periodo", f"{informe.get('desde', '')} al {informe.get('hasta', '')}"),
        ("Fecha de emisión", informe.get("generado", "")),
    ]
    for n, (clave, valor) in enumerate(encabezado, start=2):
        c1 = hoja.cell(row=n, column=1)
        _escribir(c1, clave)
        c1.font = Font(bold=True, color="374151")
        hoja.merge_cells(start_row=n, start_column=2, end_row=n, end_column=4)
        _escribir(hoja.cell(row=n, column=2), valor)

    fila_cabecera = len(encabezado) + 3
    for i, (titulo_col, _, ancho) in enumerate(COLUMNAS, start=1):
        c = hoja.cell(row=fila_cabecera, column=i)
        _escribir(c, titulo_col)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=rojo)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(top=borde, bottom=borde, left=borde, right=borde)
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    hoja.row_dimensions[fila_cabecera].height = 24

    filas = informe.get("filas", [])
    for r, fila in enumerate(filas, start=fila_cabecera + 1):
        for i, (_, clave, _) in enumerate(COLUMNAS, start=1):
            c = hoja.cell(row=r, column=i)
            _escribir(c, fila.get(clave, ""))
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = Border(top=borde, bottom=borde, left=borde, right=borde)
        color = _color_estado(fila.get("estado", ""))
        if color:
            hoja.cell(row=r, column=ultima_col).fill = PatternFill("solid", fgColor=color)

    ultima_fila = fila_cabecera + max(len(filas), 1)
    hoja.freeze_panes = hoja.cell(row=fila_cabecera + 1, column=1)
    hoja.auto_filter.ref = f"A{fila_cabecera}:{get_column_letter(ultima_col)}{ultima_fila}"

    firma = ultima_fila + 3
    hoja.merge_cells(start_row=firma, start_column=3, end_row=firma, end_column=4)
    linea = hoja.cell(row=firma, column=3)
    linea.border = Border(top=Side(style="thin", color="111827"))
    pie = hoja.cell(row=firma + 1, column=3)
    _escribir(pie, f"{informe.get('responsable') or 'Responsable'} — Responsable a cargo")
    pie.font = Font(color="374151")

    hoja.page_setup.orientation = "landscape"
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.print_title_rows = f"{fila_cabecera}:{fila_cabecera}"

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
