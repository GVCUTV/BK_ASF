## Metodi analitici
### Terminologia
Si utilizza la seguente terminologia:
- $S$ tempo di servizio (o $\mu$ tasso medio di servizio, con $S={1 \over \mu}$)
- $\lambda$ tasso medio di arrivo
- $T_Q$ tempo nella coda o tempo di attesa
- $T_S$ tempo nel sistema o tempo di residenza/risposta (dall'arrivo nella coda alla terminazione del job)
  **Nota**: nei sistemi a coda singola, i termini "tempo di residenza" e "tempo di risposta" sono sinonimi. Differiscono tuttavia nelle reti.
- $N_S$ numero di job nel sistema
- $N_Q$ numero di job nella coda
- $U$ o $\rho$ numero di job nel servizio, anche detto **utilizzazione**.

Sulle metriche prima definite, si considerano le seguenti metriche, classificate per tempo e popolazione:
- $E(T_Q)$ -> tempo medio di attesa nella coda
- $E(T_S)$ -> tempo medio nel sistema
- $E(N_S)$ -> numero medio di job nel sistema
- $E(N_Q)$ -> numero medio di job nella coda
- $Prob \{T_S > t\}$ -> probabilità  che il tempo di servizio sia superiore a una data soglia, molto usato nei SLA dei provider
- $E(n)_t$ -> numero di job serviti in $t$ unità di tempo
All'aumentare di $\lambda$, queste metriche aumentano, mentre all'aumentare di $\mu$ esse decrescono.

Quando si analizza a posteriori una coda di servizio, si possono considerare le **tracce**, ossia le coppie <tempo di arrivo, tempo richiesto di servizio> di ogni job arrivato alla coda. Si parla in questo caso di simulazione guidata da tracce.

Altre metriche note e utilizzate sono:
- il **throughtput**, definito come $E(n)_1$ (limitato superiormente da $\mu$)
- l'**utilizzazione** $\rho = {\lambda \over \mu} \in [0,1]$

L'utilizzazione è interpretabile come la probabilità di trovare il servente occupato.

Si hanno inoltre le seguenti relazioni:
- $E(T_S)=E(T_Q)+E(S)$, con $E(S)$ tempo medio di servizio
- $E(N_S)=E(N_Q)+E(number ~ in ~ service) = E(N_Q)+\rho$, dato che l'utilizzazione indica, in media, il numero di job nel servente.
### Definizioni
La **capacità** di una coda è il numero di richieste che può contenere, incluso quello in attuale processamento. La coda si può assumere avere capacità infinita, ma nella realtà le risorse sono sempre limitate. Per questo motivo, si possono considerare anche le code a capacità limitata. In questo caso la coda, se piena, non è in grado di accettare ulteriori richieste fino al completamento di quelle già accodate, dunque è costretta a scartare le richieste in arrivo. In alcuni contesti, la **probabilità di perdita** - definita come la probabilità che una richiesta in arrivo venga scartata dalla coda - può essere un indicatore di qualità del servizio. È sempre bene calcolarla.

Si definisce **scheduling** (o **disciplina di coda** o **ordine di servizio**) l'algoritmo usato per selezionare un job dalla coda perché entri in servizio. Esistono diversi tipi noti di scheduling, che possono essere divisi in categorie, a seconda del punto di vista. Se si guarda alla regola attuata per portare i job dalla coda al processamento, si può distinguere tra:
- **scheduling astratto**: dipende da discipline di alto livello e non tiene conto di caratteristiche concrete dei job, ad esempio della dimensione (size). Tra questi rientrano
	- **FIFO** (First In, First Out) -> le richieste sono servite nell'ordine di arrivo
	- **LIFO** (Last In, First Out) -> le richieste sono servite nell'ordine opposto a quello di arrivo; rischia di lasciare delle richieste nella coda per un tempo indeterminato
	- **Random** -> le richieste sono servite in ordine casuale
	- **Priorità** -> le richieste sono servite il base alla loro priorità, definita secondo un certo criterio, di solito size-based (in particolare, Shortest Job First, SJF)
- **scheduling size-based**: è una forma di scheduling con priorità che tiene però conto della dimensione dei job (in termini di tempo di servizio) per passare al processamento.
Alcune misure su questi criteri sono indipendenti dalla dimensione.
Se, invece, si guarda alla disciplina di interruzione dei job in fase di processamento, si distingue tra:
- **scheduling preemptive**: il processamento di un job può essere interrotto per riportare il job in coda e iniziare/riprendere il processamento di un altro job
- **scheduling non-preemptive**: una volta iniziato il processamento di un job, questo deve terminare senza interruzioni.

Un generico centro di servizio può avere una o più code (ad esempio nel caso di scheduling con priorità) e uno o più serventi. Per distinguere i vari casi, includendo anche le caratteristiche descritte sopra, si ricorre alla **notazione di Kendall**, che consente di rappresentare in maniera coincisa le caratteristiche di una coda di servizio:
$$
A/S/m/B/N/D
$$
dove:
- $A$ è la distribuzione degli arrivi
- $S$ è la distribuzione del servizio
- $m$ è il numero di serventi
- $B$ è la capacità della coda (include i job nei serventi)
- $N$ è la dimensione della popolazione
- $D$ è la disciplina della coda

Alcune tra le distribuzioni di servizio più utilizzate sono:
- D -> deterministica
- M -> markoviana (esponenziale)
- E<sub>k</sub> -> Erlang con k stati
- H<sub>2</sub> -> iperesponenziale
- G -> qualsiasi
Alcune distribuzioni implicano un processamento suddiviso in più fasi. Si parla, in questo caso, di distribuzioni a fasi. Il numero di fasi dipende solo dalla distribuzione ed è indipendente dal numero di serventi.

Si consideri il caso di un centro a servente singolo. Fissando il tempo di servizio medio per l'intero centro a $\frac{1}{\mu}$, si può modellare il servente con diverse distribuzioni.
- **esponenziale**: una sola fase con distribuzione esponenziale di parametro $\frac{1}{\mu}$
- **k-Erlang**: consiste di k fasi consecutive, ognuna distribuita esponenzialmente con parametro $\frac{1}{k\mu}$
- **iperesponenziale**: il processo è composto da due fasi esclusive, ossia un job può essere processato secondo una o l'altra. Una fase ha probabilità $p$ di essere scelta per il processamento e tempo di servizio medio pari a $\frac{1}{2p\mu}$, mentre l'altra ha probabilità $1-p$ e tempo di servizio medio pari a $\frac{1}{2(1-p)\mu}$
- **coxiana**: la distribuzione di Cox consente di modellare una qualsiasi distribuzione a fasi in cui il job può uscire dal processamento in qualsiasi fase. Date $k$ fasi, per ogni $i<k$ si definiscono $a_i$ (probabilità di passare dalla fase $i$ alla fase $i+1$) e $b_i$ (probabilità di uscire dal processamento alla fase $i$), mentre $a_k=0$ e $b_k=1$.

Di seguito sono riportati i modelli delle distribuzioni a fasi con i relativi tassi di servizio (gli inversi dei tempi) su ogni fase:
![[Distribuzioni a fasi.png]]
### Leggi note
#### Legge di Little (1961)
Si consideri una coda con disciplina FIFO, capacità infinita e bilanciamento dei flussi. Sia $\lambda$ il tasso di arrivo nel sistema (sconosciuto) e $T$ una finestra temporale di osservazione. Il numero di elementi nel sistema nell'arco temporale $T$ è $N=\lambda T$.
- se si considera l'intero centro, il teorema si applica la popolazione media nel centro -> $E(N_S)=\lambda E(T_S)$.
- se si considera solo la coda, il teorema è applicato alla popolazione media nella coda -> $E(N_Q)=\lambda E(T_Q)$
- se si considera il solo server, si ottiene l'utilizzazione -> $\rho = \lambda E(S)$
- se si considera un'intera rete di nodi connessi in qualsiasi modo, si ha il numero di job nella rete: $N=\lambda T$.

Si può applicare la legge di Little considerando che $E(T_S)=E(T_Q)+E(S)$ e $E(N_S)=E(N_Q)+\rho$. Si ha che 
$$
E(N_S)=\lambda E(T_S) \implies E(T_S)={E(N_S) \over \lambda}
$$$$
E(N_Q)=\lambda E(T_Q) \implies E(T_Q)={E(N_Q) \over \lambda}
$$
#### Equazione di Khinchin-Pollaczek (KP)
Si consideri una coda M/G/1:
- M -> arrivi di Poisson
- G -> qualsiasi tipo di distribuzione di servizio
- 1 -> un solo servente

L'**equazione di KP** asserisce che
$$
E(N_Q)={{\rho^2} \over {2(1-\rho)}} \left[ 1 - {\sigma^2(S)\over E(S)^2}\right]
$$
dove:
- ${\rho^2 \over 2(1-\rho)}$ deriva dal fatto che il tempo di servizio è proporzionale al \[TODO chiedere/risentire la lezione]

Si può estrarre dall'equazione il **coefficiente di variabilità**
$$
C^2 = {\sigma^2(S)\over E(S)^2}
$$
Il coefficiente di variabilità dipende dunque dalla distribuzione in uso:
- D -> $C^2 = 0$
- E<sub>k</sub> -> $C^2 = {1 \over k}, k \geq 1$
- M -> $C^2=1$
- H<sub>2</sub> -> $C^2=g(p)={1 \over {2p(1-p)}}-1$, in particolare:
	- $p=0.6 \implies C^2=1.08\bar{3}$
	- $p=0.7 \implies C^2=1.38095$
	- $p=0.8 \implies C^2=2.125$
	- $p=0.9 \implies C^2=4.\bar{5}$
Applicando la legge di Little, si ottiene anche il tempo medio:
$$
E(T_Q)=\frac{E(N_Q)}{\lambda}=\frac{\rho^2}{2\lambda(1-\rho)}\left[1+C^2\right]=\frac{\rho}{1-\rho}\frac{C^2+1}{2}E(S)
$$
Per riassumere, ponendo
$$
\begin{equation}
g(p)={1 \over {2p(1-p)}}-1
\qquad
E(N_Q)={{\rho^2} \over {2(1-\rho)}} \left[ 1 - C^2\right]
\qquad
E(T_Q)={\rho \over {1-\rho}} {{C^2+1}\over 2}E(S)
\end{equation}
$$
si hanno i seguenti risultati.

| Tempo di servizio |       Coda        |                          $E(N_Q)$                           |                             $E(T_Q)$                             |
| :---------------- | :---------------: | :---------------------------------------------------------: | :--------------------------------------------------------------: |
| Deterministico    |       M/D/1       |                 $\rho^2 \over {2(1-\rho)}$                  |                 ${\rho E(S)} \over {2(1-\rho)}$                  |
| Esponenziale      |       M/M/1       |                   $\rho^2 \over {1-\rho}$                   |                   ${\rho E(S)} \over {1-\rho}$                   |
| k-Erlang          | M/E<sub>k</sub>/1 | ${\rho^2 \over {2(1-\rho)}} \left( 1 + {1 \over k} \right)$ | ${{\rho E(S)} \over {2(1-\rho)}} \left( 1 + {1 \over k} \right)$ |
| Iperesponenziale  | M/H<sub>2</sub>/1 |    ${\rho^2 \over {2(1-\rho)}} \left( 1 + g(p) \right)$     |    ${{\rho E(S)} \over {2(1-\rho)}} \left( 1 + g(p) \right)$     |
L'equazione di KP vale per qualsiasi tipo di scheduling astratto. Al contrario, $\sigma^2(T_Q)$ dipende dalla disciplina in uso.
## Analisi operazionale