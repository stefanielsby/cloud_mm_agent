import os
import sys
import json
import time
import base64
import requests
import io
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import msal

# Indlæs miljøvariabler (.env findes typisk i rodmappen under lokal test)
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_mm_agent", ".env"))

# Hent API-nøgler og konfiguration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY and "GEMINI_API_KEY" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

CLIENT_ID = os.getenv("CLIENT_ID", "d5ac000c-55af-4993-a895-f0a460c749da")

# Konfigurer Gemini API, hvis nøglen findes
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- DESIGN & AESTHETICS (PREMIUM DARK MODE) ---
st.set_page_config(
    page_title="MM Agent - Overmaskinmesteren",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for at skabe et premium mørkeblå maskinrums-udtryk med lækker typografi og animationer
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
            background-color: #0b132b;
            color: #e0e1dd;
        }
        
        .stApp {
            background-color: #0b132b;
        }
        
        h1, h2, h3, h4, h5, h6 {
            color: #e0e1dd;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
        }
        
        /* Premium kasser og containere */
        .premium-container {
            background: linear-gradient(135deg, #1c2541 0%, #1c2541 100%);
            border: 1px solid #3a506b;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            margin-bottom: 20px;
        }
        
        /* Chat-bobler med glat skygge */
        .chat-bubble-user {
            background-color: #3a506b;
            padding: 16px;
            border-radius: 18px 18px 0px 18px;
            margin-bottom: 12px;
            color: #e0e1dd;
            border: 1px solid #5bc0be;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        
        .chat-bubble-agent {
            background-color: #1c2541;
            padding: 16px;
            border-radius: 18px 18px 18px 0px;
            margin-bottom: 12px;
            color: #e0e1dd;
            border-left: 5px solid #5bc0be;
            border-right: 1px solid #3a506b;
            border-top: 1px solid #3a506b;
            border-bottom: 1px solid #3a506b;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        
        /* Input styling */
        .stTextInput>div>div>input {
            background-color: #1c2541;
            color: #e0e1dd;
            border-color: #3a506b;
            border-radius: 8px;
        }
        
        /* Smukke knap hover-effekter */
        .stButton>button {
            background: linear-gradient(135deg, #3a506b 0%, #1c2541 100%);
            color: #e0e1dd;
            border-radius: 8px;
            border: 1px solid #3a506b;
            transition: all 0.3s cubic-bezier(.25,.8,.25,1);
            font-weight: 600;
            padding: 10px 20px;
        }
        
        .stButton>button:hover {
            border-color: #5bc0be;
            color: #5bc0be;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(91,192,190,0.2);
        }
    </style>
""", unsafe_allow_html=True)

# --- PASSWORD SECURITY GATE ---
def check_password():
    """Returnerer True hvis brugeren har indtastet den rigtige adgangskode."""
    correct_password = os.getenv("AGENT_PASSWORD", "mm2020")
    if "AGENT_PASSWORD" in st.secrets:
        correct_password = st.secrets["AGENT_PASSWORD"]
        
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        
    if st.session_state["password_correct"]:
        return True
        
    st.write("<h2 style='text-align: center; margin-top: 50px;'>⚓ Adgangskontrol: MM Agent</h2>", unsafe_allow_html=True)
    st.write("<p style='text-align: center; color: #888;'>Indtast din adgangskode for at starte Overmaskinmesteren</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password_input = st.text_input("Adgangskode", type="password", key="app_password")
        if st.button("Lås op 🔓", use_container_width=True):
            if password_input == correct_password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Forkert adgangskode! Prøv igen.")
                
    return False

if not check_password():
    st.stop()

# --- MICROSOFT AUTHENTICATION (MSAL) LOGIC ---
SCOPES = ["Notes.Read", "Notes.Read.All", "Files.ReadWrite"]

def load_token_cache():
    """Henter token-cache fra enten Streamlit Secrets (Base64) eller den lokale disk."""
    token_cache_b64 = None
    if "MS_TOKEN_CACHE" in st.secrets:
        token_cache_b64 = st.secrets["MS_TOKEN_CACHE"]
    elif os.getenv("MS_TOKEN_CACHE"):
        token_cache_b64 = os.getenv("MS_TOKEN_CACHE")
        
    cache = msal.SerializableTokenCache()
    if token_cache_b64:
        try:
            cache_data = base64.b64decode(token_cache_b64.encode('utf-8')).decode('utf-8')
            cache.deserialize(cache_data)
        except Exception as e:
            st.sidebar.warning(f"⚠️ Kunne ikke afkode token-cache fra Secrets: {e}")
    else:
        # Lokal fallback (til testbrug på din mini-PC)
        local_cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_mm_agent", "token_cache.bin")
        if os.path.exists(local_cache_path):
            try:
                with open(local_cache_path, "r") as f:
                    cache.deserialize(f.read())
            except Exception:
                pass
    return cache

# Initialiser MSAL session status
if "msal_token" not in st.session_state:
    st.session_state["msal_token"] = None
if "new_cache_b64" not in st.session_state:
    st.session_state["new_cache_b64"] = None

def get_silent_token(cache):
    """Forsøger at hente en gyldig adgangstoken lydløst via cache."""
    app = msal.PublicClientApplication(
        CLIENT_ID, 
        authority="https://login.microsoftonline.com/common", 
        token_cache=cache
    )
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            if cache.has_state_changed:
                serialized = cache.serialize()
                b64 = base64.b64encode(serialized.encode('utf-8')).decode('utf-8')
                st.session_state["new_cache_b64"] = b64
            return result["access_token"]
    return None

# --- ONEDRIVE DOWNLOAD & UPLOAD ---
def download_from_onedrive(dest_filename, token):
    """Henter en fil direkte fra OneDrive under mappen /MM_Agent."""
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/MM_Agent/{dest_filename}:/content"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.content
        elif response.status_code == 404:
            return None
        response.raise_for_status()
    except Exception as e:
        st.error(f"⚠️ Netværksfejl under hentning af {dest_filename} fra OneDrive: {e}")
        return None

def upload_to_onedrive(dest_filename, data_bytes, token):
    """Uploader en fil direkte til OneDrive under mappen /MM_Agent."""
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/MM_Agent/{dest_filename}:/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json" if dest_filename.endswith(".json") else "application/octet-stream"
    }
    try:
        response = requests.put(url, headers=headers, data=data_bytes)
        response.raise_for_status()
        return True
    except Exception as e:
        st.sidebar.error(f"⚠️ Kunne ikke gemme {dest_filename} på OneDrive: {e}")
        return False

# --- LOG IND SKÆRM (DEVICE CODE FLOW) ---
if not st.session_state["msal_token"]:
    cache = load_token_cache()
    token = get_silent_token(cache)
    
    if token:
        st.session_state["msal_token"] = token
        st.rerun()
    else:
        st.write("<h2 style='text-align: center; margin-top: 50px;'>🔑 Forbind til din OneDrive</h2>", unsafe_allow_html=True)
        st.info("Da denne agent kører uafhængigt i skyen, skal du godkende forbindelsen til din Microsoft OneDrive én gang.")
        
        app = msal.PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common", token_cache=cache)
        
        if "device_flow" not in st.session_state:
            if st.button("Start Microsoft Login 🚀", use_container_width=True):
                flow = app.initiate_device_flow(scopes=SCOPES)
                if "user_code" in flow:
                    st.session_state["device_flow"] = flow
                    st.session_state["msal_app"] = app
                    st.session_state["msal_cache"] = cache
                    st.rerun()
                else:
                    st.error(f"❌ Kunne ikke oprette forbindelse til Microsoft login-serveren. Detaljer: {flow}")
        else:
            flow = st.session_state["device_flow"]
            st.markdown(f"""
            <div class="premium-container">
                <h4 style='margin-top: 0;'>Følg disse nemme trin:</h4>
                <ol>
                    <li>Gå til websiden: <a href="https://microsoft.com/devicelogin" target="_blank" style="color: #5bc0be; font-weight: 600; text-decoration: underline;">microsoft.com/devicelogin</a></li>
                    <li>Indtast denne kode: <span style="font-size: 22px; color: #5bc0be; font-weight: 800; font-family: 'Space Grotesk';">{flow['user_code']}</span></li>
                    <li>Log ind med din Microsoft-konto (den du bruger til OneNote).</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Godkendt? Forbind nu 🔌", use_container_width=True):
                app = st.session_state["msal_app"]
                cache = st.session_state["msal_cache"]
                result = app.acquire_token_by_device_flow(flow)
                if "access_token" in result:
                    st.session_state["msal_token"] = result["access_token"]
                    # Gem token cache som base64, så Stefan kan tilføje den til secrets
                    serialized = cache.serialize()
                    b64 = base64.b64encode(serialized.encode('utf-8')).decode('utf-8')
                    st.session_state["new_cache_b64"] = b64
                    st.success("🎉 Forbindelse oprettet fejlfrit!")
                    del st.session_state["device_flow"]
                    st.rerun()
                else:
                    st.error("❌ Kunne ikke registrere dit login. Sørg for at du har gennemført alle trin i browseren først.")
        st.stop()

# --- DATALOAD (INDLÆS INDEKSER FRA ONEDRIVE MED CACHE) ---
@st.cache_data(show_spinner=False)
def hent_indekser_fra_skyen(token):
    """Downloader de konsoliderede OneNote og Filer chunks direkte fra OneDrive."""
    with st.spinner("⚡ Indlæser dine OneNote-noter og Filer..."):
        onenote_bytes = download_from_onedrive("onenote_index.json", token)
        filer_bytes = download_from_onedrive("filer_index.json", token)
        
        onenote_index = json.loads(onenote_bytes.decode('utf-8')) if onenote_bytes else []
        filer_index = json.loads(filer_bytes.decode('utf-8')) if filer_bytes else []
        
        return onenote_index, filer_index

onenote_index, filer_index = hent_indekser_fra_skyen(st.session_state["msal_token"])

# --- LÆS ERFARINGS-DATABASE ---
@st.cache_data(show_spinner=False)
def load_erfaringer_onedrive(token):
    erfaringer_bytes = download_from_onedrive("erfaringer.json", token)
    if erfaringer_bytes:
        try:
            return json.loads(erfaringer_bytes.decode('utf-8'))
        except Exception:
            return []
    return []

erfaringer = load_erfaringer_onedrive(st.session_state["msal_token"])

def gem_erfaring_onedrive(sporgsmal, svar, emne, token):
    """Tilføjer en erfaring med emne/kategori og uploader den opdaterede JSON til OneDrive."""
    global erfaringer
    erfaringer.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "emne": emne,
        "sporgsmal": sporgsmal,
        "svar": svar
    })
    # Tving nulstilling af cache, så Streamlit indlæser det rigtige næste gang
    st.cache_data.clear()
    
    data_bytes = json.dumps(erfaringer, ensure_ascii=False, indent=2).encode('utf-8')
    upload_to_onedrive("erfaringer.json", data_bytes, token)

# --- EXCEL EXPORT GENERERING ---
def generate_excel(erfaringer_list):
    df = pd.DataFrame(erfaringer_list)
    if not df.empty:
        cols = []
        for col in ["timestamp", "emne", "sporgsmal", "svar"]:
            if col in df.columns:
                cols.append(col)
        df = df[cols]
        
        rename_dict = {
            "timestamp": "Tidspunkt",
            "emne": "Emne / Kategori",
            "sporgsmal": "Spørgsmål",
            "svar": "Svar"
        }
        df = df.rename(columns=rename_dict)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Erfaringer")
    return buffer.getvalue()

# --- SØGE-MOTOR (RAG OVER 10 CHUNKS TIL MULTI-TABEL SØGNING) ---
def scan_knowledge_in_memory(query, onenote_idx, filer_idx, top_k=10):
    query_lower = query.lower()
    search_terms = query_lower.split()
    scored_chunks = []
    
    # 1. Scan OneNote data
    for item in onenote_idx:
        text = item["text"]
        text_lower = text.lower()
        score = 0
        for term in search_terms:
            if len(term) >= 2 and term in text_lower:
                score += 1.8  # OneNote-noter vægtes tungest
                if term.startswith('e') and len(term) == 3: score += 2.0  # Fejlkode boost
        if score > 0:
            scored_chunks.append({"text": text, "source": item["source"], "score": score})
            
    # 2. Scan Filer (standarder/manualer/skemaer)
    for item in filer_idx:
        text = item["text"]
        text_lower = text.lower()
        score = 0
        for term in search_terms:
            if len(term) >= 2 and term in text_lower:
                score += 1.0
                if term.startswith('e') and len(term) == 3: score += 1.5
        if "fejl" in query_lower or "error" in query_lower:
            if "trip" in text_lower or "alarm" in text_lower:
                score += 0.5
        if score > 0:
            scored_chunks.append({"text": text, "source": item["source"], "score": score})
            
    # 3. Scan Erfaringer (gemte erfaringer fra OneDrive)
    global erfaringer
    for item in erfaringer:
        sporgsmal = item.get("sporgsmal", "")
        svar = item.get("svar", "")
        emne = item.get("emne", "Generelt")
        text = f"Emne: {emne}\nSpørgsmål: {sporgsmal}\nSvar: {svar}"
        text_lower = text.lower()
        score = 0
        for term in search_terms:
            if len(term) >= 2 and term in text_lower:
                score += 1.5  # Gemte erfaringer vægtes også højt
        if score > 0:
            scored_chunks.append({"text": text, "source": f"Erfaringer (Emne: {emne})", "score": score})
            
    # Sorter efter score
    best_chunks = sorted(scored_chunks, key=lambda x: x["score"], reverse=True)[:top_k]
    
    context = ""
    sources = []
    for item in best_chunks:
        context += f"\n[Kilde: {item['source']}]\n{item['text']}\n"
        sources.append(item['source'])
        
    return context, list(set(sources))

# --- SYSTEM-INSTRUCTION ---
SYSTEM_INSTRUCTION = """Du er Overmaskinmesteren – en yderst erfaren, tålmodig og faglært mentor for Stefan.
Du taler og svarer på et flydende, teknisk præcist og professionelt dansk.

Stefan er uddannet Maskinmester. Efter sin uddannelse har han arbejdet 5 år med komplekse el- og automationsprojekter:
- Industrielektriker hos Caljan: Elektrisk idriftsættelse, test af Siemens PLC-styringer og frekvensomformere.
- Testcenter-elektriker hos Johnson Controls: I/O-test på industrielle varmepumper, betjening af 10 kV højspændingsanlæg og transformerrum med op til 4 MW el-effekt.

Derfor skal du:
1. Tale til ham som en ligeværdig, erfaren kollega. Undgå overforklaringer og banale teorier.
2. Gå direkte til de tekniske fakta, matematiske formler, standarder (især maskinsikkerhedsstandarden DS/EN 60204-1) og praktiske metoder.
3. Ræsonnere dybt på tværs af data. Hvis du får givet flere kilder med tabeller (f.eks. komponent-indstillinger ét sted og driftsdata et andet sted), så krydsreferér dem aktivt for at give et præcist svar.
4. Spænde bredt over el, automation, hydraulik, termodynamik og fejlfinding helt ned på printkort- og komponentniveau.
"""

# --- INITIALISER CHAT-TRÅDE (SESSION STATE) ---
if "threads" not in st.session_state:
    st.session_state["threads"] = {"Generelt": []}
if "active_thread" not in st.session_state:
    st.session_state["active_thread"] = "Generelt"

# --- SIDEBAR (KONTROL-PANEL) ---
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/ship.png", width=75)
    st.write("## 🚢 Maskinrummet")
    st.write("---")
    
    # Status
    if GEMINI_API_KEY:
        st.success("🔌 Gemini API: Online 🟢")
    else:
        st.error("🔌 Gemini API: Offline 🔴")
        
    st.write("---")
    
    # Modelvælger
    st.write("### 🧠 Vælg Model")
    st.selectbox(
        "Hjerne",
        options=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-3.5-flash"],
        format_func=lambda x: {
            "gemini-2.5-flash": "Gemini 2.5 Flash ⚡ (Gratis & Hurtig)",
            "gemini-2.5-pro": "Gemini 2.5 Pro 🧠 (Kræver Billing)",
            "gemini-2.0-flash": "Gemini 2.0 Flash 🚄 (Hurtig)",
            "gemini-3.5-flash": "Gemini 3.5 Flash 🚀 (Nyeste Preview)"
        }.get(x, x),
        key="selected_model"
    )
    
    st.write("---")
    
    # Metadata info
    st.write(f"📂 **OneNote chunks:** {len(onenote_index)} stk")
    st.write(f"📁 **Fil chunks:** {len(filer_index)} stk")
    st.write(f"💾 **Gemte erfaringer:** {len(erfaringer)} stk")
    
    st.write("---")
    
    # Samtaler (Tråde) sektion i sidebar
    st.write("### 💬 Samtaler (Tråde)")
    
    active_threads = list(st.session_state["threads"].keys())
    if st.session_state["active_thread"] not in active_threads:
        st.session_state["active_thread"] = active_threads[0]
        
    selected_thread = st.selectbox(
        "Aktiv chat:",
        options=active_threads,
        index=active_threads.index(st.session_state["active_thread"]),
        key="thread_selector"
    )
    st.session_state["active_thread"] = selected_thread
    
    # Opret ny tråd
    with st.expander("➕ Opret/Resume tråd", expanded=False):
        # Ekstraher unikke emner fra erfaringer på OneDrive
        unique_topics = sorted(list(set(erf.get("emne", "Generelt") for erf in erfaringer)))
        if "Generelt" not in unique_topics:
            unique_topics.insert(0, "Generelt")
            
        creation_mode = st.radio("Vælg:", ["Brug eksisterende emne", "Nyt emne"], key="creation_mode")
        
        if creation_mode == "Brug eksisterende emne":
            new_thread_name = st.selectbox("Eksisterende:", options=unique_topics, key="existing_topic_select")
        else:
            new_thread_name = st.text_input("Nyt navn:", placeholder="F.eks. Fejlfinding Siemens", key="new_topic_input")
            
        if st.button("Opret & Skift 🚀", use_container_width=True):
            if new_thread_name and new_thread_name.strip():
                clean_name = new_thread_name.strip()
                if clean_name not in st.session_state["threads"]:
                    st.session_state["threads"][clean_name] = []
                st.session_state["active_thread"] = clean_name
                st.success(f"Tråd '{clean_name}' oprettet!")
                time.sleep(0.5)
                st.rerun()
                
    # Slet aktiv tråd (så længe der er mere end en)
    if len(active_threads) > 1:
        if st.button("Slet aktiv tråd 🗑️", use_container_width=True):
            active = st.session_state["active_thread"]
            del st.session_state["threads"][active]
            st.session_state["active_thread"] = list(st.session_state["threads"].keys())[0]
            st.success("Tråd slettet!")
            time.sleep(0.5)
            st.rerun()
            
    st.write("---")
    
    # Synkroniser knap
    if st.button("Synkroniser skyen 🔄", use_container_width=True):
        st.cache_data.clear()
        st.success("Henter nye data fra OneDrive...")
        time.sleep(1)
        st.rerun()
        
    # Excel download
    if erfaringer:
        excel_data = generate_excel(erfaringer)
        st.download_button(
            label="Exporter erfaringer til Excel 📊",
            data=excel_data,
            file_name="mm_agent_erfaringer.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    st.write("---")
    
    # Ryd chat-historik for aktiv tråd
    if st.button("Ryd samtale 🧹", use_container_width=True):
        active = st.session_state["active_thread"]
        st.session_state["threads"][active] = []
        st.success(f"Tråden '{active}' er ryddet!")
        time.sleep(0.5)
        st.rerun()
        
    # Hjælp til automatisk login (Streamlit Secrets)
    if st.session_state["new_cache_b64"]:
        st.write("---")
        with st.expander("🔑 Automatisk Login Secret"):
            st.caption("For at slippe for at logge ind med Microsoft i fremtiden, kan du kopiere denne kode og tilføje den til dine Streamlit Secrets under navnet 'MS_TOKEN_CACHE':")
            st.text_area("Token Cache Kode", value=st.session_state["new_cache_b64"], height=100)

# --- HOVED BRUGERFLADE MED TABS ---
st.write(f"<h1>🚢 Overmaskinmesteren <span style='font-size: 16px; color: #5bc0be;'>Cloud Edition</span></h1>", unsafe_allow_html=True)
st.write("<p style='color: #888; font-style: italic;'>Ligeværdig, tung faglig sparring til maskinmesteren</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["💬 Sparring (Chat)", f"🗄️ Erfaringsdatabase ({len(erfaringer)} stk)"])

with tab1:
    active_thread = st.session_state["active_thread"]
    
    st.markdown(f"""
        <div style="background-color: #1c2541; padding: 10px; border-radius: 8px; border-left: 5px solid #5bc0be; margin-bottom: 15px;">
            <span style="color: #888; font-size: 12px; text-transform: uppercase; font-weight: bold;">Aktiv samtale:</span><br>
            <span style="color: #e0e1dd; font-size: 18px; font-weight: 600; font-family: 'Space Grotesk';">💬 {active_thread}</span>
        </div>
    """, unsafe_allow_html=True)
    
    thread_messages = st.session_state["threads"].get(active_thread, [])

    # Vis tidligere beskeder
    for idx, msg in enumerate(thread_messages):
        role_class = "chat-bubble-user" if msg["role"] == "user" else "chat-bubble-agent"
        role_name = "Dig" if msg["role"] == "user" else "Overmaskinmesteren"
        st.markdown(f"""
            <div class="{role_class}">
                <strong>👤 {role_name}:</strong><br>
                {msg["content"]}
            </div>
        """, unsafe_allow_html=True)
        
        if msg["role"] == "assistant":
            if "sources" in msg and msg["sources"]:
                st.write(f"<span style='font-size: 12px; color: #888;'>📚 Kilder: {', '.join(msg['sources'])}</span>", unsafe_allow_html=True)
            
            # Knap til aktivt at gemme som erfaring
            if idx > 0 and thread_messages[idx-1]["role"] == "user":
                sporgsmal = thread_messages[idx-1]["content"]
                svar = msg["content"]
                
                is_saved = any(erf.get("sporgsmal") == sporgsmal and erf.get("emne", "Generelt") == active_thread for erf in erfaringer)
                
                if is_saved:
                    st.markdown("<span style='font-size: 12px; color: #5bc0be; font-weight: bold; display: inline-block; margin-bottom: 10px;'>💾 Gemt som erfaring ✓</span>", unsafe_allow_html=True)
                else:
                    if st.button("Gem som erfaring 💾", key=f"save_erf_{active_thread}_{idx}"):
                        gem_erfaring_onedrive(sporgsmal, svar, active_thread, st.session_state["msal_token"])
                        st.success(f"✅ Erfaring gemt under emnet '{active_thread}' på OneDrive!")
                        time.sleep(0.5)
                        st.rerun()

    # Inputfelt
    if prompt := st.chat_input("Hvad oplever du af udfordringer i maskinrummet i dag?"):
        # Tilføj brugerens besked til session state
        if active_thread not in st.session_state["threads"]:
            st.session_state["threads"][active_thread] = []
            
        st.session_state["threads"][active_thread].append({"role": "user", "content": prompt})
        
        # Vis med det samme
        st.markdown(f"""
            <div class="chat-bubble-user">
                <strong>👤 Dig:</strong><br>
                {prompt}
            </div>
        """, unsafe_allow_html=True)
        
        # 1. RAG-SØGNING I HUKOMMELSEN (Kombinerer med forrige besked for bedre opfølgende spørgsmål)
        history_messages = st.session_state["threads"][active_thread][:-1]
        rag_query = prompt
        if len(history_messages) >= 2:
            last_user_msg = next((m for m in reversed(history_messages) if m["role"] == "user"), None)
            if last_user_msg:
                rag_query = f"{last_user_msg['content']} {prompt}"
                
        with st.spinner("🔍 Gennemsøger OneNote, Filer og Erfaringer..."):
            context, sources = scan_knowledge_in_memory(rag_query, onenote_index, filer_index)
            
        # 2. GEMINI SVAR GENERERING
        if not GEMINI_API_KEY:
            st.error("❌ Gemini API-nøglen mangler. Kan ikke generere svar.")
        else:
            with st.spinner("🧠 Overmaskinmesteren analyserer kilder og ræsonnerer..."):
                try:
                    # Format samtalehistorik til prompt (sidste 6 beskeder / 3 turns)
                    history_text = ""
                    recent_history = history_messages[-6:]
                    if recent_history:
                        history_text = "\nNylig samtalehistorik for at bevare kontekst:\n"
                        for msg in recent_history:
                            role_name = "Stefan" if msg["role"] == "user" else "Overmaskinmesteren"
                            history_text += f"{role_name}: {msg['content']}\n"
                            
                    full_prompt = f"""{SYSTEM_INSTRUCTION}

RÅ TEKNISK DATA FRA DINE FILER OG NOTER:
{context}
{history_text}
SPØRGSMÅL FRA MASKINMESTER STEFAN:
{prompt}

SVAR:"""
                    
                    selected_model = st.session_state.get("selected_model", "gemini-2.5-flash")
                    model = genai.GenerativeModel(selected_model)
                    response = model.generate_content(full_prompt)
                    svar_tekst = response.text
                    
                    # Tilføj til tråd-historik
                    st.session_state["threads"][active_thread].append({
                        "role": "assistant",
                        "content": svar_tekst,
                        "sources": sources
                      })
                      
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Fejl under generering af svar: {e}")

with tab2:
    st.write("### 🗄️ Administrer Gemte Erfaringer")
    st.write("Her kan du se din database af erfaringer (gemt på din OneDrive), grupperet efter emner/chats. Du kan folde hvert emne ud og slette enkelte erfaringer, hvis du vil rette fejl eller fjerne forældede svar.")
    
    if not erfaringer:
        st.info("Der er endnu ikke gemt nogen erfaringer i databasen.")
    else:
        # Grupper erfaringer efter emne (kategori)
        grouped_erfaringer = {}
        for idx, erf in enumerate(erfaringer):
            emne = erf.get("emne", "Generelt")
            if emne not in grouped_erfaringer:
                grouped_erfaringer[emne] = []
            grouped_erfaringer[emne].append((idx, erf))
            
        # Vis grupper i Streamlit expandere
        for emne, items in sorted(grouped_erfaringer.items()):
            with st.expander(f"📁 {emne} ({len(items)} stk)", expanded=False):
                for orig_idx, item in reversed(items):
                    st.markdown(f"""
                    <div style="background-color: #1c2541; padding: 15px; border-radius: 8px; border: 1px solid #3a506b; margin-bottom: 10px; color: #e0e1dd;">
                        <span style="color: #5bc0be; font-size: 12px; font-weight: bold;">📅 {item.get('timestamp', 'Ukendt tidspunkt')}</span><br><br>
                        <strong>👤 Spørgsmål:</strong><br>
                        <p style="color: #e0e1dd; margin-left: 10px; font-style: italic;">"{item['sporgsmal']}"</p>
                        <strong>🚢 Svar:</strong><br>
                        <p style="color: #e0e1dd; margin-left: 10px; white-space: pre-wrap;">{item['svar']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Slet-knap til denne specifikke erfaring
                    if st.button(f"Slet denne erfaring 🗑️", key=f"del_erf_{orig_idx}"):
                        erfaringer.pop(orig_idx)
                        # Tving nulstilling af cache og upload til OneDrive
                        st.cache_data.clear()
                        data_bytes = json.dumps(erfaringer, ensure_ascii=False, indent=2).encode('utf-8')
                        if upload_to_onedrive("erfaringer.json", data_bytes, st.session_state["msal_token"]):
                            st.success("✅ Erfaring slettet fra OneDrive!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("❌ Kunne ikke slette erfaring fra OneDrive. Tjek forbindelsen.")

