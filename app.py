import streamlit as st
import pandas as pd
import math
import json
# import os # Ya no es necesario para DATABASE_FILE
# import sqlite3 # Reemplazado por psycopg2
import psycopg2 # Para PostgreSQL
import psycopg2.extras # Para DictCursor
from datetime import datetime
from collections import defaultdict

# --- Configuración de la Página ---
st.set_page_config(page_title="Calculadora de Producción v3 (Supabase)", layout="wide")

# --- Constantes (DEFAULT_CATEGORY se mantiene) ---
DEFAULT_CATEGORY = "General"

# --- Funciones de Conexión a Supabase ---
def get_supabase_connection():
    """Establece y devuelve una conexión a la base de datos Supabase."""
    try:
        conn = psycopg2.connect(
            host=st.secrets.supabase.host,
            port=st.secrets.supabase.port,
            dbname=st.secrets.supabase.dbname,
            user=st.secrets.supabase.user,
            password=st.secrets.supabase.password
        )
        return conn
    except psycopg2.Error as e:
        st.error(f"Error al conectar con Supabase: {e}")
        # Podrías querer terminar la app o reintentar, dependiendo de tu lógica.
        # Por ahora, simplemente mostramos el error y retornamos None.
        # st.stop() # Descomentar si quieres detener la app en caso de no poder conectar.
        return None


# --- Funciones de Base de Datos (Modificadas para Supabase/PostgreSQL) ---

def init_db():
    """Inicializa la BD en Supabase, crea la tabla 'machines' si no existe."""
    conn = get_supabase_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                CREATE TABLE IF NOT EXISTS machines (
                    name TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    description TEXT,
                    setup_params TEXT NOT NULL,      -- Almacenaremos JSON como texto
                    production_params TEXT NOT NULL, -- Almacenaremos JSON como texto
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    category TEXT DEFAULT '{DEFAULT_CATEGORY}'
                )
            ''')
            conn.commit()
        # st.toast("Tabla 'machines' verificada/creada en Supabase.", icon="✅") # Opcional
    except psycopg2.Error as e:
        st.error(f"Error crítico al inicializar la tabla 'machines' en Supabase: {e}")
        # Considera cómo manejar este error. ¿La app puede continuar?
    finally:
        if conn:
            conn.close()

def get_all_machines_db():
    """Obtiene todas las máquinas de Supabase, ordenadas por categoría y nombre."""
    machines = {}
    conn = get_supabase_connection()
    if not conn:
        return machines # Retorna vacío si no hay conexión

    try:
        # Usar DictCursor para acceder a las columnas por nombre
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM machines ORDER BY category, name")
            rows = cur.fetchall()
            for row in rows:
                machine_dict = dict(row) # Convertir DictRow a dict regular
                try:
                    machine_dict['setup_params'] = json.loads(machine_dict['setup_params'])
                    machine_dict['production_params'] = json.loads(machine_dict['production_params'])
                    if machine_dict.get('category') is None:
                        machine_dict['category'] = DEFAULT_CATEGORY
                    machines[machine_dict['name']] = machine_dict
                except json.JSONDecodeError as json_err:
                    st.error(f"Error JSON máquina {machine_dict.get('name', 'DESCONOCIDA')}: {json_err}")
                except Exception as e:
                    st.error(f"Error procesando máquina {machine_dict.get('name', 'DESCONOCIDA')}: {e}")
    except psycopg2.Error as e:
        st.error(f"Error al leer máquinas de la base de datos Supabase: {e}")
    finally:
        if conn:
            conn.close()
    return machines

def add_machine_db(config):
    """Agrega una nueva máquina a la base de datos Supabase."""
    conn = get_supabase_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            category = config.get('category', DEFAULT_CATEGORY) or DEFAULT_CATEGORY
            cur.execute('''
                INSERT INTO machines (name, type, description, setup_params, production_params, created_at, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                config['name'],
                config['type'],
                config.get('description', None),
                json.dumps(config['setup_params']),
                json.dumps(config['production_params']),
                config['created_at'],
                category
            ))
            conn.commit()
        st.success(f"✅ Máquina '{config['name']}' guardada en Supabase (categoría '{category}').")
        return True
    except psycopg2.IntegrityError as e:
        # Esto usualmente ocurre si la 'name' (PRIMARY KEY) ya existe
        st.error(f"⛔ Error: Ya existe una máquina con el nombre '{config['name']}'. Detalles: {e}")
        return False
    except psycopg2.Error as e:
        st.error(f"Error al guardar la máquina en Supabase: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_machine_db(original_name, config):
    """Actualiza una máquina existente en Supabase."""
    conn = get_supabase_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            category = config.get('category', DEFAULT_CATEGORY) or DEFAULT_CATEGORY
            cur.execute('''
                UPDATE machines
                SET name = %s, type = %s, description = %s, setup_params = %s,
                    production_params = %s, updated_at = %s, category = %s
                WHERE name = %s
            ''', (
                config['name'],
                config['type'],
                config.get('description', None),
                json.dumps(config['setup_params']),
                json.dumps(config['production_params']),
                config['updated_at'],
                category,
                original_name # Usar el nombre original en el WHERE
            ))
            conn.commit()
        st.success(f"✅ Máquina '{config['name']}' actualizada en Supabase (Categoría: '{category}').")
        return True
    except psycopg2.Error as e:
        st.error(f"Error al actualizar la máquina en Supabase: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_machine_db(name):
    """Elimina una máquina de la base de datos Supabase."""
    conn = get_supabase_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM machines WHERE name = %s", (name,))
            conn.commit()
        st.success(f"🗑️ Máquina '{name}' eliminada de Supabase.")
        return True
    except psycopg2.Error as e:
        st.error(f"Error al eliminar la máquina de Supabase: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- Inicializar Base de Datos al inicio ---
# Llama a esta función una vez al inicio de tu app si es necesario
# para asegurar que la tabla exista.
init_db() # Asegúrate de que esto se llame correctamente.

# --- CSS (sin cambios, lo omito por brevedad pero debe estar en tu código) ---
st.markdown("""
<style>
/* ... (tu CSS actual) ... */
</style>
""", unsafe_allow_html=True)


# --- Constantes y estado inicial (sin cambios) ---
MACHINE_TYPES = ["Manual", "Semi-Automática", "Automática"]
if 'current_page' not in st.session_state:
    st.session_state.current_page = "calculator"
if 'editing_machine' not in st.session_state:
    st.session_state.editing_machine = None

# --- Funciones de Renderizado (sin cambios, las omito por brevedad) ---
# render_analysis_table, render_interruptions_table

# --- Páginas de la Aplicación (machine_configuration_page, production_calculator_page) ---
# Estas páginas usarán las funciones de DB actualizadas. No necesitan cambios internos
# a menos que quieras modificar la lógica de la UI.
# Las llamadas a add_machine_db, get_all_machines_db, etc., ahora interactuarán con Supabase.

# (Pega aquí tus funciones render_analysis_table, render_interruptions_table,
# machine_configuration_page, y production_calculator_page que ya tienes)

# --- Tu CSS ---
st.markdown("""
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f9; }
div.stApp { background: linear-gradient(to right, #ffffff, #e6e6e6); }
h1, h2, h3 { color: #333333; text-align: center; }
.custom-table { width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; overflow: hidden; }
.custom-table th, .custom-table td { padding: 12px 15px; border: 1px solid #dddddd; text-align: center; font-size: 0.95em; }
.custom-table th { background-color: #4CAF50; color: white; font-weight: bold; }
.custom-table tr:nth-child(even) { background-color: #f8f9fa; }
.custom-table tr:hover { background-color: #e9ecef; }
.progress { background-color: #e9ecef; border-radius: 13px; padding: 3px; margin: 0; height: 26px; }
.progress-bar { background: linear-gradient(to right, #4CAF50, #8BC34A); width: 0%; height: 20px; border-radius: 10px; text-align: center; color: white; line-height: 20px; font-weight: bold; transition: width 0.5s ease-in-out; }
.machine-card { padding: 20px; margin: 15px 0; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); background-color: white; transition: transform 0.3s ease, box-shadow 0.3s ease; border-left: 5px solid #ccc; }
.machine-manual { border-left-color: #3498db; }
.machine-semi { border-left-color: #f39c12; }
.machine-auto { border-left-color: #2ecc71; }
.machine-card h3 { margin-top: 0; margin-bottom: 10px; color: #333; }
.machine-card p { font-size: 0.9em; color: #555; margin-bottom: 5px; }
.machine-card strong { color: #333; }
.category-header {
    padding: 8px 15px;
    background-color: #e9ecef; /* Fondo gris claro para cabecera de categoría */
    border-radius: 5px;
    margin-top: 20px;
    margin-bottom: 10px;
    color: #495057; /* Color de texto gris oscuro */
    font-size: 1.1em;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# --- Constantes y estado inicial ---
MACHINE_TYPES = ["Manual", "Semi-Automática", "Automática"]

if 'current_page' not in st.session_state:
    st.session_state.current_page = "calculator"
if 'editing_machine' not in st.session_state:
    st.session_state.editing_machine = None

# --- Funciones de Renderizado (sin cambios) ---
def render_analysis_table(turno_minutos, tiempo_productivo, tiempo_perdido, eficiencia):
    eficiencia_percent = float(eficiencia) if eficiencia else 0.0
    progress_bar_html = f'''<div class="progress"><div class="progress-bar" style="width: {eficiencia_percent:.2f}%; min-width: 50px;">{eficiencia_percent:.2f}%</div></div>'''
    html = f'''<table class="custom-table"><thead><tr><th>Métrica</th><th>Valor</th></tr></thead><tbody><tr><td>Tiempo Total Turno</td><td>{turno_minutos:.2f} min</td></tr><tr><td>Tiempo Productivo</td><td>{tiempo_productivo:.2f} min</td></tr><tr><td>Tiempo Perdido</td><td>{tiempo_perdido:.2f} min</td></tr><tr><td>Eficiencia</td><td>{progress_bar_html}</td></tr></tbody></table>'''
    return html

def render_interruptions_table(interrupciones_dict, turno_minutos):
    rows = ""
    total_interrupcion_min = 0
    for tipo, tiempo in interrupciones_dict.items():
        tiempo_float = float(tiempo)
        if tiempo_float > 0:
            porcentaje = (tiempo_float / turno_minutos) * 100 if turno_minutos > 0 else 0
            rows += f"<tr><td>{tipo}</td><td>{tiempo_float:.2f} min</td><td>{porcentaje:.2f}%</td></tr>"
            total_interrupcion_min += tiempo_float
    total_porcentaje = (total_interrupcion_min / turno_minutos) * 100 if turno_minutos > 0 else 0
    rows += f"<tr style='font-weight: bold; background-color: #e9ecef;'><td>Total Interrupciones</td><td>{total_interrupcion_min:.2f} min</td><td>{total_porcentaje:.2f}%</td></tr>"
    html = f'''<table class="custom-table"><thead><tr><th>Tipo</th><th>Tiempo (min)</th><th>% Turno</th></tr></thead><tbody>{rows}</tbody></table>'''
    return html

# --- Páginas de la Aplicación ---
def machine_configuration_page():
    st.title("⚙️ Configuración de Máquinas por Categoría (Supabase)")

    with st.expander("➕ Agregar Nueva Máquina", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_machine_name = st.text_input("Nombre de la Máquina", key="new_machine_name")
            new_machine_type = st.selectbox("Tipo de Máquina", options=MACHINE_TYPES, key="new_machine_type")
            new_machine_category = st.text_input(
                "Categoría",
                key="new_machine_category",
                value=DEFAULT_CATEGORY,
                help="Organiza tus máquinas (ej: Línea 1, Prensas, Mantenimiento)."
            )
        with col2:
            new_machine_description = st.text_area("Descripción", key="new_machine_description",
                                                placeholder="Breve descripción de la máquina...")

        st.subheader("Parámetros de Setup")
        setup_col1, setup_col2 = st.columns(2)
        new_setup_params = {}
        with setup_col1:
            new_setup_params["calibracion"] = st.number_input("Tiempo Calibración (min)", 0, value=10, step=1, key="new_calibracion")
            new_setup_params["otros"] = st.number_input("Tiempo Otros (min)", 0, value=30, step=1, key="new_otros")
            new_setup_params["cambio_rollo"] = st.number_input("Tiempo Cambio Rollo (min)", 0, value=4, step=1, key="new_cambio_rollo")
            new_setup_params["cambio_producto"] = st.number_input("Tiempo Cambio Producto (min)", 0, value=15, step=1, key="new_cambio_producto")
        with setup_col2:
            if new_machine_type in ["Manual", "Semi-Automática"]:
                new_setup_params["cambio_cuchillo"] = st.number_input("Tiempo Cambio Cuchillo (min)", 0, value=30, step=1, key="new_cambio_cuchillo")
                new_setup_params["cambio_perforador"] = st.number_input("Tiempo Cambio Perforador (min)", 0, value=10, step=1, key="new_cambio_perforador")
                new_setup_params["cambio_paquete"] = st.number_input("Tiempo Cambio Paquete (min)", 0, value=5, step=1, key="new_cambio_paquete")
            if new_machine_type == "Manual":
                new_setup_params["empaque"] = st.number_input("Tiempo Empaque (segundos)", 0, value=60, step=5, key="new_empaque")

        st.subheader("Parámetros de Producción")
        prod_col1, prod_col2 = st.columns(2)
        new_production_params = {}
        with prod_col1:
            new_production_params["unidades_por_minuto"] = st.number_input("Unidades por Minuto", 1, value=48, step=1, key="new_upm")
            new_production_params["peso_por_unidad"] = st.number_input("Peso por Unidad (gramos)", 0.01, value=45.3, step=0.1, key="new_peso")
        with prod_col2:
            if new_machine_type in ["Manual", "Semi-Automática"]:
                st.write("Tiempo de Ciclo Productivo:")
                cycle_seconds = st.number_input("Duración Ciclo (s)", 1, value=32, step=1, key="new_cycle_time")
                productive_seconds = st.number_input("Tiempo Productivo Ciclo (s)", 1, value=27, step=1, key="new_productive_time")
                if productive_seconds > cycle_seconds: productive_seconds = cycle_seconds
                new_production_params["ciclo_total"] = cycle_seconds
                new_production_params["ciclo_productivo"] = productive_seconds
                new_production_params["ratio_productivo"] = productive_seconds / cycle_seconds if cycle_seconds > 0 else 0
            else:
                new_production_params["ratio_productivo"] = 1.0
                new_production_params["ciclo_total"] = 0
                new_production_params["ciclo_productivo"] = 0

        if st.button("💾 Guardar Nueva Máquina", key="save_new_machine", type="primary"):
            machine_name = new_machine_name.strip()
            category_name = new_machine_category.strip() or DEFAULT_CATEGORY
            if not machine_name:
                st.error("⛔ Error: El nombre de la máquina es obligatorio.")
            else:
                machine_config_to_add = {
                    "name": machine_name,
                    "type": new_machine_type,
                    "description": new_machine_description.strip(),
                    "category": category_name,
                    "setup_params": new_setup_params,
                    "production_params": new_production_params,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                if add_machine_db(machine_config_to_add):
                    st.rerun()

    st.divider()
    st.header("📋 Máquinas Configuradas por Categoría")
    all_machines = get_all_machines_db()

    if not all_machines:
        st.info("ℹ️ No hay máquinas configuradas. Agrega una nueva máquina usando el formulario de arriba.")
    else:
        machines_by_category = defaultdict(list)
        for name, config in all_machines.items():
            category = config.get('category', DEFAULT_CATEGORY)
            machines_by_category[category].append(config)

        sorted_categories = sorted(machines_by_category.keys())

        for category in sorted_categories:
            st.markdown(f"<div class='category-header'>📁 {category}</div>", unsafe_allow_html=True)
            machines_in_category = machines_by_category[category]
            num_columns = 3
            machine_cols = st.columns(num_columns)
            col_idx = 0

            for config in machines_in_category:
                name = config['name']
                machine_class = "machine-card"
                if config["type"] == "Manual": machine_class += " machine-manual"
                elif config["type"] == "Semi-Automática": machine_class += " machine-semi"
                else: machine_class += " machine-auto"

                with machine_cols[col_idx % num_columns]:
                    updated_info = f"<p><small><i>Actualizada: {config['updated_at']}</i></small></p>" if config.get('updated_at') else ""
                    category_info = f"<p><small>Categoría: {config.get('category', DEFAULT_CATEGORY)}</small></p>"
                    st.markdown(f"""
                    <div class="{machine_class}">
                        <h3>{name}</h3>
                        <p><strong>Tipo:</strong> {config["type"]}</p>
                        {category_info}
                        <p><strong>Descripción:</strong> {config.get("description") or "N/A"}</p>
                        <p><small>Creada: {config["created_at"]}</small></p>
                        {updated_info}
                    </div>
                    """, unsafe_allow_html=True)
                    action_cols = st.columns(2)
                    with action_cols[0]:
                        if st.button("🗑️ Eliminar", key=f"delete_{category}_{name}", help=f"Eliminar {name}"):
                            if delete_machine_db(name):
                                st.rerun()
                    with action_cols[1]:
                        if st.button("✏️ Editar", key=f"edit_{category}_{name}", help=f"Editar {name}"):
                            st.session_state.editing_machine = name
                            st.rerun()
                col_idx += 1
            st.markdown("---")

    if st.session_state.editing_machine:
        machine_to_edit_name = st.session_state.editing_machine
        all_machines_for_edit = get_all_machines_db()

        if machine_to_edit_name not in all_machines_for_edit:
            st.error(f"Error: No se encontró '{machine_to_edit_name}' para editar.")
            st.session_state.editing_machine = None
            # st.rerun() # Potentially problematic if this happens during another rerun. Let user see error.
        else:
            machine_config = all_machines_for_edit[machine_to_edit_name]
            st.divider()
            st.header(f"✏️ Editando Máquina: {machine_to_edit_name}")
            col1, col2 = st.columns(2)
            with col1:
                edit_name = st.text_input("Nombre Máquina", value=machine_config["name"], key="edit_machine_name")
                try: type_index = MACHINE_TYPES.index(machine_config["type"])
                except ValueError: type_index = 0
                edit_type = st.selectbox("Tipo Máquina", options=MACHINE_TYPES, index=type_index, key="edit_machine_type")
                edit_category = st.text_input(
                    "Categoría",
                    value=machine_config.get("category", DEFAULT_CATEGORY),
                    key="edit_machine_category",
                    help="Cambia la categoría de la máquina."
                )
            with col2:
                edit_description = st.text_area("Descripción", value=machine_config.get("description", ""), key="edit_machine_description")

            st.subheader("Parámetros de Setup")
            setup_col1, setup_col2 = st.columns(2)
            edit_setup_params = {}
            setup_config = machine_config["setup_params"] # This is already a dict from get_all_machines_db
            with setup_col1:
                edit_setup_params["calibracion"] = st.number_input("Tiempo Calibración (min)", 0, value=setup_config.get("calibracion", 10), step=1, key="edit_calibracion")
                edit_setup_params["otros"] = st.number_input("Tiempo Otros (min)", 0, value=setup_config.get("otros", 30), step=1, key="edit_otros")
                edit_setup_params["cambio_rollo"] = st.number_input("Tiempo Cambio Rollo (min)", 0, value=setup_config.get("cambio_rollo", 4), step=1, key="edit_cambio_rollo")
                edit_setup_params["cambio_producto"] = st.number_input("Tiempo Cambio Producto (min)", 0, value=setup_config.get("cambio_producto", 15), step=1, key="edit_cambio_producto")
            with setup_col2:
                if edit_type in ["Manual", "Semi-Automática"]:
                    edit_setup_params["cambio_cuchillo"] = st.number_input("Tiempo Cambio Cuchillo (min)", 0, value=setup_config.get("cambio_cuchillo", 30), step=1, key="edit_cambio_cuchillo")
                    edit_setup_params["cambio_perforador"] = st.number_input("Tiempo Cambio Perforador (min)", 0, value=setup_config.get("cambio_perforador", 10), step=1, key="edit_cambio_perforador")
                    edit_setup_params["cambio_paquete"] = st.number_input("Tiempo Cambio Paquete (min)", 0, value=setup_config.get("cambio_paquete", 5), step=1, key="edit_cambio_paquete")
                else: # Limpiar si cambia a Automática
                    edit_setup_params.pop("cambio_cuchillo", None)
                    edit_setup_params.pop("cambio_perforador", None)
                    edit_setup_params.pop("cambio_paquete", None)
                    edit_setup_params.pop("empaque", None) # También limpiar empaque
                if edit_type == "Manual":
                    edit_setup_params["empaque"] = st.number_input("Tiempo Empaque (segundos)", 0, value=setup_config.get("empaque", 60), step=5, key="edit_empaque")
                elif "empaque" in edit_setup_params: # Limpiar si no es Manual y existe
                     edit_setup_params.pop("empaque", None)


            st.subheader("Parámetros de Producción")
            prod_col1, prod_col2 = st.columns(2)
            edit_production_params = {}
            prod_config = machine_config["production_params"] # This is already a dict
            with prod_col1:
                edit_production_params["unidades_por_minuto"] = st.number_input("Unidades por Minuto", 1, value=prod_config.get("unidades_por_minuto", 48), step=1, key="edit_upm")
                edit_production_params["peso_por_unidad"] = st.number_input("Peso por Unidad (gramos)", 0.01, value=prod_config.get("peso_por_unidad", 45.3), step=0.1, key="edit_peso")
            with prod_col2:
                if edit_type in ["Manual", "Semi-Automática"]:
                    st.write("Tiempo de Ciclo Productivo:")
                    edit_cycle_seconds = st.number_input("Duración Ciclo (s)", 1, value=prod_config.get("ciclo_total", 32), step=1, key="edit_cycle_time")
                    edit_productive_seconds = st.number_input("Tiempo Productivo Ciclo (s)", 1, value=prod_config.get("ciclo_productivo", 27), step=1, key="edit_productive_time")
                    if edit_productive_seconds > edit_cycle_seconds: edit_productive_seconds = edit_cycle_seconds
                    edit_production_params["ciclo_total"] = edit_cycle_seconds
                    edit_production_params["ciclo_productivo"] = edit_productive_seconds
                    edit_production_params["ratio_productivo"] = edit_productive_seconds / edit_cycle_seconds if edit_cycle_seconds > 0 else 0
                else:
                    edit_production_params["ratio_productivo"] = 1.0
                    edit_production_params["ciclo_total"] = 0
                    edit_production_params["ciclo_productivo"] = 0

            edit_action_cols = st.columns(2)
            with edit_action_cols[0]:
                if st.button("✅ Guardar Cambios", key="save_edit_machine", type="primary"):
                    new_name = edit_name.strip()
                    category_name_edit = edit_category.strip() or DEFAULT_CATEGORY
                    if not new_name:
                        st.error("⛔ Error: El nombre de la máquina es obligatorio.")
                    else:
                        updated_config = {
                            "name": new_name,
                            "type": edit_type,
                            "description": edit_description.strip(),
                            "category": category_name_edit,
                            "setup_params": edit_setup_params,
                            "production_params": edit_production_params,
                            "created_at": machine_config.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if update_machine_db(machine_to_edit_name, updated_config):
                            st.session_state.editing_machine = None
                            st.rerun()
            with edit_action_cols[1]:
                if st.button("❌ Cancelar Edición", key="cancel_edit_machine"):
                    st.session_state.editing_machine = None
                    st.rerun()

def production_calculator_page():
    st.title("🏭 Calculadora de Producción (Supabase)")
    available_machines = get_all_machines_db()

    if not available_machines:
        st.warning("⚠️ No hay máquinas configuradas.")
        if st.button("Ir a Configuración"):
            st.session_state.current_page = "configuration"
            st.rerun()
        return

    machine_names = list(available_machines.keys())
    selected_machine_name = st.selectbox("Seleccione Máquina", options=sorted(machine_names))
    if not selected_machine_name: # Añadido por si acaso la lista está vacía o hay un problema
        st.error("No se pudo seleccionar una máquina.")
        return
    machine_config = available_machines[selected_machine_name]


    st.header(f"📊 Calculando para: {selected_machine_name} ({machine_config['type']})")
    st.caption(f"Categoría: {machine_config.get('category', DEFAULT_CATEGORY)}")
    if machine_config.get("description"):
        st.info(f"Descripción: {machine_config['description']}")

    with st.expander("🔧 Configuración Operativa", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            turno_horas = st.number_input("Duración Turno (h)", 1.0, 24.0, 8.0, 0.5, key="turno_horas")
            desayuno = st.checkbox("Incluir desayuno (15 min)", key="desayuno", value=True)
            almuerzo = st.checkbox("Incluir almuerzo (60 min)", key="almuerzo", value=True)
        with col2:
            st.subheader("Interrupciones Variables (Eventos)")
            interrupciones = {}
            interrupciones["cambios_rollo"] = st.number_input("Nº Cambios rollo", 0, 100, 2, 1, key="n_cambios_rollo")
            interrupciones["cambios_producto"] = st.number_input("Nº Cambios producto", 0, 100, 1, 1, key="n_cambios_producto")
            if machine_config["type"] in ["Manual", "Semi-Automática"]:
                interrupciones["cambios_cuchillo"] = st.number_input("Nº Cambios cuchillo", 0, 100, 0, 1, key="n_cambios_cuchillo")
                interrupciones["cambios_perforador"] = st.number_input("Nº Cambios perforador", 0, 100, 0, 1, key="n_cambios_perforador")
                interrupciones["cambios_paquete"] = st.number_input("Nº Cambios paquete", 0, 100, 0, 1, key="n_cambios_paquete")
            if machine_config["type"] == "Manual":
                interrupciones["cambios_empaque"] = st.number_input("Nº Cambios empaque", 0, 100, 0, 1, key="n_cambios_empaque")
    try:
        setup_params = machine_config["setup_params"] # Ya es un dict
        production_params = machine_config["production_params"] # Ya es un dict
        turno_minutos = turno_horas * 60
        interrupciones_fijas = setup_params.get("calibracion", 0) + setup_params.get("otros", 0)
        tiempo_comidas = (15 if desayuno else 0) + (60 if almuerzo else 0)
        interrupciones_variables = 0
        detalle_interrupciones_variables = {}

        for key, n_eventos in interrupciones.items():
            tiempo_por_evento = 0; nombre_evento = ""
            if n_eventos > 0:
                if key == "cambios_rollo": tiempo_por_evento = setup_params.get("cambio_rollo", 0); nombre_evento = "Cambios Rollo"
                elif key == "cambios_producto": tiempo_por_evento = setup_params.get("cambio_producto", 0); nombre_evento = "Cambios Producto"
                elif key == "cambios_cuchillo": tiempo_por_evento = setup_params.get("cambio_cuchillo", 0); nombre_evento = "Cambios Cuchillo"
                elif key == "cambios_perforador": tiempo_por_evento = setup_params.get("cambio_perforador", 0); nombre_evento = "Cambios Perforador"
                elif key == "cambios_paquete": tiempo_por_evento = setup_params.get("cambio_paquete", 0); nombre_evento = "Cambios Paquete"
                elif key == "cambios_empaque": tiempo_empaque_seg = setup_params.get("empaque", 0); tiempo_por_evento = tiempo_empaque_seg / 60.0; nombre_evento = "Cambios Empaque"

                tiempo_total_evento = n_eventos * tiempo_por_evento
                if tiempo_total_evento > 0 and nombre_evento:
                    interrupciones_variables += tiempo_total_evento
                    detalle_interrupciones_variables[f"{nombre_evento} ({n_eventos}x)"] = tiempo_total_evento

        tiempo_neto_disponible = turno_minutos - (interrupciones_fijas + tiempo_comidas + interrupciones_variables)

        if tiempo_neto_disponible <= 0:
            st.error(f"⛔ Error: Tiempo de interrupciones ({interrupciones_fijas + tiempo_comidas + interrupciones_variables:.1f} min) excede turno ({turno_minutos:.1f} min).")
            tiempo_perdido_total_err = interrupciones_fijas + tiempo_comidas + interrupciones_variables
            eficiencia_err = 0
            analysis_html_err = render_analysis_table(turno_minutos, 0, tiempo_perdido_total_err, eficiencia_err)
            with st.expander("Análisis Tiempos", expanded=True): st.markdown(analysis_html_err, unsafe_allow_html=True)
            interrupciones_dict_error = {"Calibración Fija": setup_params.get("calibracion", 0), "Otros Fijos": setup_params.get("otros", 0), "Comidas": tiempo_comidas, **detalle_interrupciones_variables}
            with st.expander("Detalle Interrupciones", expanded=False): interruptions_html_err = render_interruptions_table(interrupciones_dict_error, turno_minutos); st.markdown(interruptions_html_err, unsafe_allow_html=True)
            return

        ratio_productivo = production_params.get("ratio_productivo", 1.0)
        tiempo_efectivo_produccion = tiempo_neto_disponible * ratio_productivo
        tiempo_detenido_ciclos = tiempo_neto_disponible * (1 - ratio_productivo)
        unidades_por_minuto = production_params.get("unidades_por_minuto", 0)
        peso_por_unidad_g = production_params.get("peso_por_unidad", 0)
        unidades_estimadas = unidades_por_minuto * tiempo_efectivo_produccion
        peso_total_kg = unidades_estimadas * peso_por_unidad_g / 1000 if peso_por_unidad_g > 0 else 0
        eficiencia_oee = (tiempo_efectivo_produccion / turno_minutos) * 100 if turno_minutos > 0 else 0

        st.success("📈 Resultados de Producción Estimados")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            delta_unidades = unidades_estimadas * 0.05
            st.metric("Unidades Estimadas", f"{unidades_estimadas:,.0f}", delta=f"± {delta_unidades:,.0f} uds", delta_color="off")
        with res_col2:
            delta_peso = peso_total_kg * 0.05
            st.metric("Peso Total Estimado", f"{peso_total_kg:,.1f} kg", delta=f"± {delta_peso:,.1f} kg", delta_color="off")

        st.subheader("⏳ Análisis de Tiempos y Eficiencia")
        tiempo_perdido_total = turno_minutos - tiempo_efectivo_produccion
        analysis_html = render_analysis_table(turno_minutos, tiempo_efectivo_produccion, tiempo_perdido_total, eficiencia_oee)
        with st.expander("Ver Análisis de Tiempos", expanded=True):
            st.markdown(analysis_html, unsafe_allow_html=True)

        interrupciones_dict = {"Calibración Fija": setup_params.get("calibracion", 0), "Otros Fijos": setup_params.get("otros", 0), "Comidas": tiempo_comidas, **detalle_interrupciones_variables}
        if machine_config["type"] in ["Manual", "Semi-Automática"] and tiempo_detenido_ciclos > 0:
            interrupciones_dict["Paradas por Ciclo"] = tiempo_detenido_ciclos
        with st.expander("🔍 Detalle de Interrupciones", expanded=False):
            interruptions_html = render_interruptions_table(interrupciones_dict, turno_minutos)
            st.markdown(interruptions_html, unsafe_allow_html=True)

    except KeyError as e:
        st.error(f"⛔ Error Configuración: Falta parámetro '{e}' en '{selected_machine_name}'. Edite la máquina.")
    except Exception as e:
        st.error(f"⛔ Error inesperado en cálculo: {e}")
        st.exception(e) # Muestra el traceback completo para depuración

# --- Función Principal y Navegación ---
def main():
    with st.sidebar:
        st.title("📊 Menú Principal")
        st.markdown("---")
        page_selection = st.radio(
            "Seleccione una página:",
            ("🧮 Calculadora", "⚙️ Configurar Máquinas"),
            key="page_selector",
            index=0 if st.session_state.get('current_page', 'calculator') == 'calculator' else 1
        )
        if page_selection == "🧮 Calculadora": st.session_state.current_page = "calculator"
        else: st.session_state.current_page = "configuration"
        st.markdown("---")
        st.info("💾 Datos en Supabase") # Actualizado
        st.caption(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")

    if st.session_state.current_page == "calculator": production_calculator_page()
    elif st.session_state.current_page == "configuration": machine_configuration_page()
    else: # Default
        st.session_state.current_page = "calculator"
        production_calculator_page()

if __name__ == "__main__":
    main()