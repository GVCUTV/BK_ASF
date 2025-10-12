[comment]: # "v1"
## **Project Schedule**

---

### **Meeting 1 [12/7/2025] – Kickoff & System Familiarization**

* **1.1** (All): Lettura rapida e discussione della documentazione ASF (“The Apache Way”), linee guida BookKeeper, overview Jira/GitHub.
* **1.2** (All): Costruzione condivisa del modello concettuale del workflow BookKeeper: stati principali, transizioni, ipotesi chiave.
* **1.3** (Split):

  * A: Inizio stesura dell’introduzione e degli obiettivi della relazione.
  * B: Prima bozza di diagrammi del sistema (whiteboard/Miro/draw.io).
  * C: Elenco dei dati necessari, esplorazione delle issue recenti BookKeeper e struttura dati JIRA/GitHub.
* **End:** 15 min wrap-up, condivisione risultati, eventuale aggiustamento dei compiti e del piano.

---

### **Meeting 2 [29/7/2025] – Conceptual Model & Data Mapping**

* **2.1** (All): Finalizzazione del modello concettuale e dei flussi principali (issue, review, test, feedback loop).
* **2.2** (Split):

  * A: Scrittura della sezione sul modello concettuale e mappatura stati Jira ↔ workflow reale.
  * B: Sviluppo dei primi diagrammi/flow chart per la relazione.
  * C: Raccolta e pulizia dati preliminare, estrazione ticket/PR, condivisione prime statistiche di base.
* **All:** Review incrociato delle bozze, sincronizzazione, discussione dubbi.

---

### **Meeting 3 [1/8/2025] – Analisi Dati & Costruzione Modello Analitico**

* **3.1** (All): Costruzione condivisa del modello a code analitico e delle ipotesi formali.
* **3.2** (Split):

  * A: Scrittura di equazioni analitiche, matrice degli stati/transizioni e parametri di routing.
  * B: Stima preliminare dei parametri da Jira/GitHub (rate arrivo, tempi medi di servizio, tasso reopening).
  * C: Bozza delle metriche chiave (utilizzo, tempo medio in coda, throughput ecc.).
* **All:** Revisione incrociata, verifica coerenza dei dati stimati.

---

### **Meeting 4 [3/8/2025] – Architettura Simulazione & Avvio Coding**

* **4.1** (All): Definizione architettura della simulazione, flusso eventi/stati, strumenti (pseudo-codice o whiteboard).
* **4.2** (Split):

  * A: Setup repo/codice simulazione e base dati di input.
  * B: Implementazione logica di arrivo ticket, gestione transizioni e ciclo feedback.
  * C: Sviluppo logica di servizio, registrazione statistiche e output.
* **All:** Mini code review tra pari, aggiornamento documentazione di progetto.

---

### **Meeting 5 [19/8/2025] – Verifica, Debug e Prime Simulazioni**

* **5.1** (All): Test integrato, esecuzione prima simulazione end-to-end, verifica funzionamento globale.
* **5.2** (Split):

  * A: Documentazione e verifica delle consistenze (Legge di Little, utilizzo, tempi medi).
  * B: Run di sweep parametrici su casi semplici, raccolta output.
  * C: Debug, ottimizzazione codice simulazione e note per sezioni “Validazione”/“Verifica modello”.
* **All:** Discussione anomalie, rifinitura collettiva della logica.

---

### **Meeting 6 [31/8/2025] – Esperimenti & Analisi Risultati**

* **6.1** (All): Definizione scenari sperimentali, variabili da esplorare e output da raccogliere.
* **6.2** (Split):

  * A: Esecuzione simulazioni in transitorio e regime, raccolta dati.
  * B: Produzione e raffinamento di grafici e tabelle.
  * C: Inizio stesura delle sezioni “Esperimenti” e “Analisi dei colli di bottiglia”.
* **All:** Review incrociata dei risultati, scelta delle migliori visualizzazioni.

---

### **Meeting 7 [2/9/2025] – Miglioramento & Modello Ottimizzato**

* **7.1** (All): Brainstorming e scelta di possibili miglioramenti (automatizzazione test, nuovi pattern review, ecc.).
* **7.2** (All):

  * Implementazione del miglioramento scelto nella simulazione.
  * Run comparativa tra scenario base e ottimizzato, raccolta risultati.
  * Bozza del nuovo modello e aggiornamento sezione confronto nel report.
* **All:** Interpretazione collettiva dei risultati, preparazione agli ultimi step.

---

### **Meeting 8 [7/9/2025] – Report Finale & Presentazione**

* **8.1** (All): Assemblaggio finale della relazione, editing collaborativo, referenze.
* **8.2** (Split):

  * A: Slide su introduzione/modello e motivazioni.
  * B: Slide su esperimenti, simulazioni e risultati.
  * C: Slide su miglioramenti, conclusioni e raccomandazioni.
* **All:** Prova presentazione (ognuno simula la propria parte), Q&A tra colleghi, finalizzazione di codice e materiali.
