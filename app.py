import streamlit as st
from google import genai
from google.genai import types
import os
import time

# --- 1. CONFIGURACIÓN ---
try:
    # Intenta leer la llave desde los secretos (Nube o Local seguro)
    api_key = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # Por si acaso no encuentra el archivo
    st.error(
        "❌ No se encontró la API Key. Asegurate de configurar .streamlit/secrets.toml"
    )
    st.stop()

client = genai.Client(api_key=api_key)

# Modelo estable
MODELO_ELEGIDO = "gemini-flash-latest"


# --- 2. GESTIÓN DE ARCHIVOS ---
def cargar_documentos():
    docs_path = "documentos"
    if not os.path.exists(docs_path):
        st.error(f"⚠️ Creá la carpeta '{docs_path}' y poné los PDFs ahí.")
        return []

    archivos_locales = [f for f in os.listdir(docs_path) if f.lower().endswith(".pdf")]

    if not archivos_locales:
        st.warning("La carpeta 'documentos' está vacía.")
        return []

    st.info(f"📂 Archivos base detectados: {len(archivos_locales)}")
    # Lista compacta para no ocupar mucho espacio
    st.caption(", ".join(archivos_locales))

    refs = []
    my_bar = st.progress(0, text="Analizando documentos...")

    for i, archivo in enumerate(archivos_locales):
        path = os.path.join(docs_path, archivo)
        try:
            file_ref = client.files.upload(file=path)
            while file_ref.state.name == "PROCESSING":
                time.sleep(1)
                file_ref = client.files.get(name=file_ref.name)

            if file_ref.state.name == "FAILED":
                st.error(f"❌ Falló: {archivo}")
            else:
                refs.append(file_ref)
        except Exception as e:
            st.error(f"❌ Error: {e}")

        my_bar.progress(int(((i + 1) / len(archivos_locales)) * 100))

    my_bar.empty()
    return refs


# --- 3. INTERFAZ GRÁFICA ---
st.set_page_config(page_title="Consultor Electoral", page_icon="🌹")

st.title("🌹 CONSULTOR ELECTORAL")
st.caption(f"🟢 Asesoría en Línea | Modelo: {MODELO_ELEGIDO}")

# Inicialización de Estado
if "files_ready" not in st.session_state:
    st.session_state.files_ready = False
    st.session_state.chat_history = []
    st.session_state.files_refs = []
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# --- PASO 1: CARGA DE DOCUMENTOS ---
if not st.session_state.files_ready:
    st.markdown("### 1. Iniciar Sistema")
    st.info("ℹ️ Cargá los documentos legales para activar al consultor.")
    if st.button("📂 Cargar Base Legal"):
        with st.spinner("Leyendo carpeta local..."):
            refs = cargar_documentos()
            if refs:
                st.session_state.files_refs = refs
                st.session_state.files_ready = True
                st.rerun()

# --- PASO 2: IDENTIFICACIÓN (BIENVENIDA) ---
elif st.session_state.files_ready and st.session_state.user_name is None:
    st.markdown("### 2. Identificación")
    st.success("✅ Documentos cargados correctamente.")
    st.markdown("---")
    st.markdown("👋 **¡Bienvenido, compañero!**")
    st.markdown(
        "Soy tu Asesor Electoral Técnico. Para dirigirnos con la confianza y el respeto adecuado:"
    )

    nombre_input = st.text_input(
        "¿Cómo querés que te llame?",
        placeholder="Ej: David, Chepe, o solo Compañero(a)...",
    )

    if st.button("Guardar y Entrar"):
        if nombre_input.strip():
            st.session_state.user_name = nombre_input
            # Mensaje inicial de cortesía en el chat
            st.session_state.chat_history.append(
                (
                    "assistant",
                    f"¡Entendido, **{nombre_input}**! Estoy listo. Consultame sobre cualquier duda legal o estratégica.",
                )
            )
            st.rerun()
        else:
            st.warning("Por favor, escribí un nombre para continuar.")

# --- PASO 3: CHAT DE CONSULTORÍA ---
elif st.session_state.files_ready and st.session_state.user_name:

    # Configuración DINÁMICA (Incluye el nombre del usuario)
    generate_config = types.GenerateContentConfig(
        temperature=0.1,
        top_p=0.95,
        max_output_tokens=8192,
        system_instruction=f"""
        ROL: Asesor Legal y Político Veterano del FMLN.
        USUARIO ACTUAL: Te estás dirigiendo a "{st.session_state.user_name}". Usá su nombre ocasionalmente para dar un trato personalizado.
        
        TU IDENTIDAD:
        Eres un estratega comprometido, profesional pero cercano (usá "vos").
        
        INSTRUCCIONES DE DESAMBIGUACIÓN (CRÍTICO):
        1. ESTATUTOS vs. ÉTICA: Distinguí claramente entre estructura orgánica (Estatutos) y régimen disciplinario (Ética).
        2. UNIDAD LEGAL: La Ley de Voto en el Exterior es UN solo documento.
        
        REGLAS DE CONVERSACIÓN:
        1. HABLÁ CLARO: Explicaciones sencillas para {st.session_state.user_name}.
        2. SOLUCIONES: Si hay trabas legales, proponé la alternativa viable.
        3. CULTURA DE PARTIDO: Usá términos como "compañero", "militancia".
        4. CITAS PRECISAS: Citá siempre el DOCUMENTO y ARTÍCULO exacto.
        """,
    )

    # Mostrar historial
    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)

    # Input del usuario
    if prompt := st.chat_input(f"Adelante, {st.session_state.user_name}..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.chat_history.append(("user", prompt))

        with st.chat_message("assistant"):
            with st.spinner("Analizando estrategia..."):
                try:
                    response = client.models.generate_content(
                        model=MODELO_ELEGIDO,
                        contents=[prompt] + st.session_state.files_refs,
                        config=generate_config,
                    )
                    st.markdown(response.text)
                    st.session_state.chat_history.append(("assistant", response.text))
                except Exception as e:
                    if "429" in str(e):
                        st.error("⏳ El sistema está cargado. Esperá 1 minuto.")
                    elif "404" in str(e):
                        st.error("❌ Error de conexión con el modelo.")
                    else:
                        st.error(f"Error técnico: {e}")
