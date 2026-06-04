# 📓 Cloud Projektdagbog: Cloud MM Agent

Velkommen til den officielle projektdagbog for din **Cloud Maskinmester-Agent** (Cloud MM Agent). Dette projekt kører fuldstændig uafhængigt af dine lokale AI-eksperimenter og er optimeret til 100% uafhængig afvikling direkte i skyen (Streamlit Community Cloud), så du frigør alle ressourcer på din Shuttle PC til dine virtuelle maskiner med automationssoftware (Siemens TIA Portal, Rockwell Studio 5000 osv.).

---

## 👤 Profil & Erfaring: Maskinmester Stefan

* **Uddannelse:** Uddannet Maskinmester.
* **Erhvervserfaring:** 5 års tung erhvervserfaring inden for el- og automationsprojekter efter uddannelsen:
  * **Industrielektriker hos Caljan:** Elektrisk idriftsættelse, test af Siemens PLC-styringer og Siemens frekvensomformere på transportbånd.
  * **Testcenter-elektriker hos Johnson Controls:** I/O-test på industrielle køle- og varmepumpeanlæg, mekanisk/elektrisk opstilling på test-rigge, samt idriftsættelse og betjening af **10 kV højspændingskoblingsanlæg** og transformerrum med op til **4 MW el-effekt** (kompressortest op til 25 MW).

---

## 🎯 Visionen for Cloud MM Agenten

Agenten fungerer som din ultimative, faglige sparringspartner på tværs af hele maskinmester-paletten (Elektroteknik, Installation, PLC/Automation, SCADA, Relæteknik, Pumpeteknik, Damp, Ventilation og Termodynamik).

### 💡 Kerne-Arkitektur i Skyen:
1. **Gemini API som Hjerne:** Appen kører på Streamlit Cloud og bruger Gemini 1.5 Pro via din API-nøgle. Dette giver uovertruffen intelligens og et gigantisk 2-million-token kontekstvindue (som kan rumme alle dine manualer og noter på én gang!).
2. **OneDrive som Videnslager:** Dine 178 sektioner (304 sider) og dine PDF-manualer synkroniseres direkte til dit OneDrive, som din agent læser sikkert og hurtigt fra.
3. **Mekanisk Selvlærende Erfaringsdatabase (`erfaringer.json`):**
   * Præcis som i din lokale agent gemmer vi alle dine samtaler og erfaringer i en database.
   * Da Streamlit Cloud er flygtigt (nulstiller filer ved genstart), gemmer og indlæser vi din `erfaringer.json` **direkte i din OneDrive-sky** via Microsoft Graph API! Dette gør databasen fuldstændig permanent, sikker og under din fulde kontrol.
4. **Sikkerhedslås:** Appen i skyen beskyttes af en adgangskodeskrærm, så kun du kan læse dine private noter.

---

## 🗓️ Logbog & Milepæle

### [02. Juni 2026] - Etablering af Cloud-projektet
* **Udført:** Rullet det lokale `MM_dual_agent.py` script tilbage til dets helt oprindelige form for at bevare din optimerede NPU/CPU-pipeline intakt.
* **Udført:** Oprettet den nye projektmappe `cloud_mm_agent/` for at adskille cloud-agenten fuldstændig fra dine lokale filer.
* **Udført:** Oprettet denne dedikerede [projektdagbog.md](file:///C:/Users/Stefan/Desktop/MM%20Agent/cloud_mm_agent/projektdagbog.md).
* **Udført:** Modtaget feedback fra Stefan angående datasikkerhed, ønske om at aktivere Gemini Paid Tier (afregning), samt udfordringen med begrænsningen på 1 privat app i Streamlit Community Cloud (da "Aktienyt" allerede optager denne plads).
* **Beslutning (Løsning A):** Vi kører med Løsning A (offentlig kode på GitHub, men alt data trækkes dynamisk fra OneDrive).
* **Beslutning (Filer frem for Manualer):** Omdøbt alle begreber fra "Manualer" til "Filer" for at afspejle bredden af uploadet materiale (standarder, datablade, noter, el-skemaer).
* **Beslutning (RAM-optimering):** Undgår tung PDF-parsing i skyen ved at lade den lokale synkronisering pakke PDF-data i en letvægts `filer_index.json` på OneDrive.
* **Beslutning (Multi-tabel RAG):** Øget søge-konteksten til top-10 chunks, så Gemini 1.5 Pro kan krydsreferere flere tabeller/dataark på samme tid.


### [04. Juni 2026] - Tråde, Hukommelse & Den Kreative Arkitektur for Erfaringer

* **Problemstilling:** Stefan oplevede, at den oprindelige løsning med automatisk logning af alle beskeder i én lang liste hurtigt blev uoverskuelig og blandede forskellige workflows sammen. Der var brug for en struktureret arkitektur til at gemme specifikke lærdomme og holde emner adskilte.
* **Udført & Push-et:** Opdateret `cloud_mm_agent.py` og udrullet til Streamlit Cloud med følgende ændringer:
* **Beslutning (Aktivt Valg frem for Automatik):** 
  * Tilføjet en dedikeret **"Gem som erfaring 💾"**-knap under hvert svar. Svaret gemmes nu kun, hvis Stefan aktivt beslutter, at denne tekniske guide eller proces skal huskes.
* **Beslutning (Samtale-overskrift = Kategori/Emne):**
  * Den overskrift, der gives til den enkelte chat-tråd, fungerer nu som det permanente tag/emne i `erfaringer.json`.
  * Dette skaber en stærk synergi: Stefans chat-struktur afspejler direkte hans vidensorganisering.
* **Beslutning (Multi-tråd Session Management i Sidebar):**
  * Tilføjet mulighed for at oprette, skifte og slette uafhængige chat-tråde direkte i sidepanelet.
  * For at bevare den arkitektoniske rød tråd, udtrækkes en liste over eksisterende unikke emner fra OneDrive ved opstart, som Stefan kan vælge direkte i en selectbox for at genoptage samtaler under præcis samme overskrifter.
* **Beslutning (Kategori-grupperet Erfaringsdatabase):**
  * I **Tab 2 (Erfaringsdatabase)** vises de gemte Q&A-par nu grupperet i visuelle fold-ud-kasser (`st.expander`) baseret på deres emne.
  * Implementeret **sletning besked-for-besked**, så fejl eller forældede data let kan renses ud af databasen direkte i UI'en og opdateres live på OneDrive.
* **Beslutning (Kontekstuel Hukommelse & Smart RAG):**
  * **Historik-hukommelse:** Agenten husker nu de sidste 6 beskeder (3 turns) i den aktive chat, hvilket muliggør flydende, opfølgende spørgsmål (f.eks. *"Hvad skyldes det normalt?"* efter at have spurgt om en fejlkode).
  * **Kontekstuel RAG-søgning:** For at sikre, at korte opfølgende spørgsmål ikke forvirrer søgemotoren, kombineres det nye spørgsmål med det foregående i RAG-søgningen, så PDF/OneNote-chunks stadig rammer rigtigt.
  * **Erfarings-RAG (Lukket Loop):** Erfaringsdatabasen er nu koblet direkte til søgemotoren. Agenten søger i sine egne tidligere godkendte og gemte svar, hvilket betyder, at den aktivt lærer af tidligere erfaringer.
