// v5
// project_documentation.md
# ASF Project

## 1. Introduzione

Il caso di studio presentato in questo elaborato riguarda l’analisi delle prestazioni del processo di sviluppo software del progetto open source Apache BookKeeper, parte della Apache Software Foundation (ASF). L'obiettivo è applicare le tecniche di modellazione viste nel corso, e in particolare la teoria delle code, per rappresentare e valutare quantitativamente il ciclo di vita di una nuova funzionalità o correzione di bug: dalla creazione del ticket nel sistema di issue tracking Jira, attraverso le fasi di sviluppo e revisione collaborativa su GitHub, fino al rilascio finale.

La specificità di BookKeeper, come di altri progetti ASF, risiede nell’organizzazione basata su contributi volontari, processi decisionali trasparenti e collaborazione asincrona. Queste caratteristiche differenziano fortemente il flusso di lavoro rispetto a quello di una tipica azienda software, introducendo variabilità nei tempi di risposta, iterazioni multiple tra sviluppo, testing e bugfix, e la possibilità di cicli di revisione multipli prima della chiusura definitiva di una issue.

Il lavoro presentato segue una struttura classica di performance engineering: dopo la descrizione concettuale del sistema e la definizione degli obiettivi, viene costruito un modello a code per rappresentare i principali stati e transizioni del workflow di sviluppo. I parametri del modello verranno stimati tramite dati reali estratti dagli archivi pubblici di Jira e GitHub del progetto. Seguiranno la verifica di consistenza, la simulazione per la validazione del modello computazionale tramite confronto dei risultati prodotti con quelli rilevati e la proposta di possibili miglioramenti organizzativi basati sulle evidenze emerse.

## 2. Background e contesto open-source

Apache BookKeeper è un progetto open-source della Apache Software Foundation (ASF), il che significa che il suo sviluppo segue un modello di contributo volontario guidato dalla comunità piuttosto che un processo aziendale tradizionale. Nei progetti ASF non ci sono manager formali che assegnano i compiti; non si utilizza una classica strategia di gestione top-down (tipica delle organizzazioni gerarchiche, ma volunteer-driven, con i collaboratori che scelgono le questioni di loro interesse o più affini alle loro capacità.

Le decisioni vengono prese pubblicamente sulle mailing list o su GitHub attraverso la discussione e la votazione per consenso da parte della comunità. La cosiddetta "Apache Way" porta a un flusso di lavoro con caratteristiche uniche: le funzionalità e le correzioni sono sviluppate in modo collaborativo da volontari distribuiti geograficamente, facendo forte affidamento sulla comunicazione asincrona (e-mail, issue tracker) e sulla peer review. 

Non ci sono programmi fissi o deliverable formali definiti in anticipo, e la progettazione si evolve in modo iterativo. Queste differenze significano che la nostra analisi deve tenere conto di tempi più lenti (i volontari lavorano nelle ore libere), dimensioni variabili del team e progressi non lineari (i problemi possono rallentare o accelerare improvvisamente in base al numero di collaboratori attivi volta per volta). 

Allineeremo il nostro studio a questo contesto, in modo da cogliere le sfumature delle dinamiche di un progetto ASF piuttosto che assumere una rigida pipeline aziendale.

## 3. Analisi preliminare

Prima della definizione degli obiettivi abbiamo ritenuto necessario uno studio preliminare del dominio del problema al fine di ottenere una visione più completa possibile di ciò che riguarda la realtà attorno ASF,  lavorando su questi due punti principali:

- **Mappatura del flusso di lavoro:** Comprendere e modellare il flusso di sviluppo di BookKeeper come risulta da Jira e GitHub. Tracceremo il percorso di una nuova richiesta di funzionalità o di una segnalazione di bug attraverso le varie fasi del processo comunitario di Apache: dalla creazione del ticket iniziale, allo sviluppo e alla revisione del codice, ai test, alle iterazioni di correzione dei bug e infine al rilascio, tenendo conto delle pratiche dell'ASF (volunteer-driven work, consensus approval, and code review norms).
- **Tracciamento della vita delle funzionalità end-to-end:** Concentrarsi sull'intera vita di una funzionalità, dal ticket Jira "New Feature" alla sua messa in produzione (inclusa in una release che gli utenti distribuiscono). Verranno rilevati tutti gli stati intermedi e tutti i cicli (ad esempio, una funzionalità che richiede più cicli di test e correzione di bug prima di essere veramente pronta per la produzione in una release stabile).

## 3. Obiettivi

Il nostro obiettivo è studiare il ciclo di vita completo di una funzionalità o di un problema nel progetto Apache BookKeeper, dall'idea iniziale al rilascio finale. In particolare, ci proponiamo di:

- **Misurare le metriche chiave:** Analizzare quantitativamente il processo con metriche derivate dai dati di Jira e GitHub. Una metrica fondamentale sarà il tempo di risoluzione dei problemi (tempo di risposta), ovvero il tempo medio necessario affinché una funzionalità o una correzione di bug passi dall'inizio (creazione del ticket) alla risoluzione (chiusura in una release) con particolare attenzione al tempo d’attesa, che va dall’apertura del ticket alla presa in carico dello stesso da parte dello sviluppatore. Queste metriche forniranno una visione basata sui dati dell'efficienza del flusso di lavoro.
- **Identificare i colli di bottiglia e proporre miglioramenti:** Utilizzando le metriche di cui sopra e le osservazioni qualitative, individuiamo eventuali colli di bottiglia o inefficienze nel flusso di lavoro attuale. Ad esempio, cercheremo le fasi che dominano la tempistica (magari le revisioni del codice che richiedono molto tempo o i test che rivelano molti bug) e ne individueremo il motivo. Nella fase finale, proporremo miglioramenti concreti al processo di sviluppo e idee per ridurre i tempi di risposta. Queste raccomandazioni terranno conto della natura volontaria di ASF (ad esempio, migliorare l'automazione o la comunicazione, piuttosto che aspettarsi un impegno a tempo pieno da parte degli sviluppatori).
- **Aggiungere obiettivo QoS**

Raggiungendo questi obiettivi, non solo tracceremo il flusso di lavoro in dettaglio, ma forniremo anche indicazioni su come la comunità di BookKeeper possa potenzialmente semplificare il proprio processo di sviluppo, preservando i punti di forza della collaborazione aperta.

## 4. Ambito e fonti dei dati

La nostra analisi si concentra sull'issue tracker Jira e sul repository GitHub di Apache BookKeeper come fonti primarie di dati. L'attenzione a questi due sistemi copre sia il lato di gestione del progetto che quello di sviluppo del codice del flusso di lavoro:

- **Dati Jira**: Estrarremo tutti i problemi rilevanti da Jira di BookKeeper (che tiene traccia dei ticket per nuove funzionalità, miglioramenti, bug, ecc.). I campi chiave da raccogliere includono il tipo di problema, la cronologia dello stato (timestamp delle transizioni come Aperto → In corso → Risolto/Chiuso), la data di risoluzione e qualsiasi collegamento tra i problemi (ad esempio, un bug ticket collegato a una funzionalità). Jira fornisce un registro strutturato degli stati del flusso di lavoro formale che ogni problema attraversa. Mostrerà come i problemi passano attraverso stati come “*Aperto, In corso, Revisione del codice, Risolto, Chiuso”* e se vengono riaperti. Questi cambiamenti di stato e i loro timestamp ci permettono di ricostruire la cronologia della vita di ogni problema. Utilizzeremo Jira anche per identificare i cicli di iterazione - per esempio, se un problema è stato riaperto o se è stato creato un bug "sub-task" dopo che una funzionalità era stata presumibilmente completata, indicando che la funzionalità doveva passare attraverso un altro ciclo di correzione/test.
- **Dati GitHub**: Analizzeremo il repository GitHub di BookKeeper per la visione del codice, concentrandoci sulle pull request (PR), sui commit e sui risultati dei test di continuous integration (CI). Molti problemi di Jira hanno PR corrispondenti (gli sviluppatori spesso menzionano l'ID del problema di Jira nei messaggi di commit o nei titoli delle PR). Collegando i commit e le PR ai Jira Issues, possiamo vedere quando il codice è stato scritto e sottoposto a un merge per un determinato problema. GitHub ci dirà quando è stata aperta una PR, quanto tempo è rimasta in revisione del codice, quanti commit o revisioni ha attraversato e quando è stata finalmente  sottoposta a merge verso la codebase. Verranno anche analizzati i risultati della CI, ad esempio se i test di una PR non sono andati a buon fine, il che potrebbe essere correlato a un ulteriore sforzo di sviluppo o alla correzione di bug prima del merge. Correlando gli eventi di GitHub con i cambiamenti di stato di Jira, possiamo ottenere un quadro completo (ad esempio, un problema di Jira passa a "Risolto" nello stesso momento in cui la sua PR viene unita, e poi magari passa a "Chiuso" quando viene tagliata una release).

L'ambito è limitato alla storia e ai dati del progetto BookKeeper (non faremo confronti con altri progetti, se non come contesto). Probabilmente esamineremo un periodo significativo della storia del progetto (per esempio, gli ultimi anni di attività di sviluppo) per avere dati sufficienti sui cicli di vita delle funzionalità. Se disponibile e necessario, potremo incorporare altre fonti, come le discussioni nelle mailing list o i documenti di progettazione per un contesto qualitativo (ad esempio, per capire perché si sono verificati determinati ritardi), ma l'analisi principale sarà basata sui dati di Jira e GitHub. Questa analisi selettiva mantiene il progetto gestibile e assicura che il nostro studio rimanga fondato su prove derivate dagli artefatti di sviluppo del progetto.

Una descrizione completa degli output di esplorazione dei dati e delle statistiche di coerenza è disponibile nel documento [DATA_LIST_1.3C](DATA_LIST_1.3C.md). La pipeline ETL stabile, i percorsi degli snapshot CSV e le statistiche preliminari che alimentano i modelli sono raccolti in [ETL_OVERVIEW_2.2C](ETL_OVERVIEW_2.2C.md).

## 4. Modello concettuale

Il modello concettuale formalizza il comportamento della community di BookKeeper come una catena di stati sviluppatore e una rete di code coerente con `docs/CONCEPTUAL_WORKFLOW_MODEL.md`. Tale descrizione è la base sia per le derivazioni analitiche sia per la simulazione.

### 4.1 Stati degli sviluppatori (OFF / DEV / REV / TEST)

Gli sviluppatori sono modellati come agenti semi-Markoviani che alternano quattro stati:

- **OFF:** periodi di inattività o indisponibilità del volontario; nessuna risorsa viene erogata ma il ticket rimane nella coda associata.
- **DEV:** il volontario lavora su implementazioni o bugfix, consumando i ticket disponibili nella coda di sviluppo.
- **REV:** il contributore opera come revisore e smaltisce le richieste di pull in attesa.
- **TEST:** il volontario supporta la campagna di validazione manuale/automatica post-merge.

Ogni ingresso in stato attivo prevede l’estrazione di una durata (stint) che determina quanti ticket consecutivi verranno completati prima del prossimo cambio di stato. Al termine dello stint l’agente sorteggia il prossimo stato secondo la matrice di transizione \(P\), mantenendo così la natura volontaria e self-service del progetto.

### 4.2 Code operative (BACKLOG / DEV / REV / TEST / DONE)

Le issue approvate entrano nella **BACKLOG queue**, dove attendono di essere prese da un volontario. Quando un agente passa a **DEV**, estrae il prossimo ticket dalla relativa coda e lo lavora fino alla consegna; il completamento sposta il ticket in **REV** per la peer review. Dopo l’approvazione, il lavoro passa in **TEST** per le verifiche di integrazione. Se i test hanno esito negativo, il ticket ritorna a **DEV** con feedback esplicito; se positivi, l’item esce dal sistema nella coda **DONE**, che rappresenta i rilasci effettivi. La corrispondenza puntuale tra stati Jira, code operative e stati semi-Markov degli sviluppatori è documentata in [`docs/JIRA_WORKFLOW_MAPPING_2.2A.md`](JIRA_WORKFLOW_MAPPING_2.2A.md) e garantisce che tutte le pipeline (ETL, simulazione, note analitiche) adottino la stessa tassonomia.

### 4.3 Diagramma di riferimento

Il diagramma concettuale corrente è archiviato in `docs/diagrams/Diagramma modello concettuale.drawio` con esportazioni `PNG/PDF` (es. `docs/diagrams/Diagramma modello concettuale.png` e `docs/diagrams/Diagramma modello concettuale.pdf`). Qualsiasi descrizione visiva del modello deve puntare a questi file, garantendo che la nomenclatura degli stati e delle code resti sincronizzata con questo documento e con la mappatura descritta in `docs/JIRA_WORKFLOW_MAPPING_2.2A.md`.

### 4.4 Flusso operativo

1. **Arrivo e backlog:** un ticket validato dalle mailing list viene registrato su Jira e collocato nello stato BACKLOG, pronto per essere preso.
2. **Sviluppo volontario (DEV):** un developer in stato DEV preleva il ticket e implementa la funzionalità o la correzione nel proprio fork GitHub.
3. **Revisione cooperativa (REV):** la pull request viene esaminata dalla community; eventuali richieste di modifica riportano il ticket alla coda DEV finché la revisione non è positiva.
4. **Testing e osservazione (TEST):** dopo il merge vengono condotti test CI/manuali. Se emergono regressioni, il ticket torna in DEV con nota di rework.
5. **Chiusura (DONE):** superati i test, l’item viene contrassegnato come risolto e conteggiato nelle metriche di output.

Questo flusso è pienamente allineato con il diagramma concettuale e fornisce la stessa sequenza di stati usata per la modellazione analitica e per il simulatore ad eventi discreti.
