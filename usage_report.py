from io import BytesIO
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def build_usage_xlsx(report):
    wb = Workbook()
    summary = wb.active
    summary.title = 'Resumen'
    summary.append(['Registros y estadísticas de la calculadora'])
    summary.append(['Desde', report['from'], 'Hasta', report['to']])
    summary.append(['Fuente', 'Registro de uso de la calculadora'])
    summary.append(['Cobertura', 'Solo actividad registrada desde la implementación del seguimiento'])
    summary.append(['Zona horaria', 'Argentina (UTC-3)'])
    summary.append(['Perfil', report.get('type') or 'Todos', 'Búsqueda', report.get('search') or ''])
    summary.append([])
    totals = report['totals']
    for title, key in [('Cuentas registradas', 'users'), ('Usuarios con actividad', 'active_users'), ('Mensuales nuevas', 'monthly_count'), ('Finales nuevas', 'final_count'), ('Correcciones', 'corrections'), ('Recálculos sin cambios', 'repeats'), ('Ejecuciones', 'executions')]:
        summary.append([title, int(totals[key])])
    summary.column_dimensions['A'].width = 38
    summary.column_dimensions['B'].width = 65
    summary.column_dimensions['C'].width = 20
    summary.column_dimensions['D'].width = 35
    sheet = wb.create_sheet('Usuarios')
    sheet.append(['Nombre', 'Email', 'Perfil', 'Organización', 'Estado', 'Registro (Argentina)', 'Mensuales nuevas', 'Finales nuevas', 'Correcciones', 'Recálculos', 'Ejecuciones', 'Último cálculo (Argentina)', 'Novedades'])
    labels = {'empleado': 'Empleado', 'empresa': 'Empresa', 'estudio': 'Estudio contable', 'sindicato': 'Sindicato'}
    def local(value):
        if not value:
            return ''
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M')
    for user in report['users']:
        sheet.append([user['name'], user['email'], labels.get(user['account_type'], user['account_type']), user.get('organization_name', ''), user['status'], local(user['created_at']), *[int(user[k]) for k in ['monthly_count','final_count','corrections','repeats','executions']], local(user.get('last_activity')), 'Aceptadas' if int(user['newsletter_opt_in']) else 'No aceptadas'])
    widths = [30, 40, 22, 35, 14, 23, 20, 20, 18, 18, 18, 25, 20]
    for i, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(i)].width = width
    sheet.freeze_panes = 'C2'
    sheet.auto_filter.ref = sheet.dimensions
    for ws in wb:
        for row in ws:
            for cell in row:
                # Los textos de usuarios nunca se interpretan como fórmulas.
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                cell.alignment = Alignment(vertical='center')
            ws.row_dimensions[row[0].row].height = 24
        for cell in ws[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='15335A')
    result = BytesIO()
    wb.save(result)
    result.seek(0)
    return result
