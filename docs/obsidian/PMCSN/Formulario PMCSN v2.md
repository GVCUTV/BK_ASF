# Metodi analitici
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
Infine, un server ha uno scheduling **work-conserving** se esegue costantemente operazioni su dei job finché ce ne sono nel sistema.

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
\begin{align}
E(N_S)=\lambda E(T_S) &\implies E(T_S)={E(N_S) \over \lambda}
\\
E(N_Q)=\lambda E(T_Q) &\implies E(T_Q)={E(N_Q) \over \lambda}
\end{align}
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
<a name="c2"></a>Il coefficiente di variabilità dipende dunque dalla distribuzione in uso:
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
E(T_Q)=\frac{E(N_Q)}{\lambda}=\frac{\rho^2}{2\lambda(1-\rho)}\left[1+C^2\right]=\frac{\rho}{1-\rho}\frac{C^2+1}{2}E(S)=\frac{E(S_{rem})}{1-\rho}=\frac{\frac{\lambda}{2}E(S^2)}{1-\rho}
$$
**Nota**: nel caso dell'esponenziale, $E(S^2)=2E^2(S)$, dunque $E(T_Q)=\frac{\rho E(S)}{1-\rho}$.
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

Per ottenere il tempo che un job qualsiasi passa nel sistema, si può applicare la seguente formula:
$$
E(T_S)=E(T_Q)+E(S)
$$
In particolare, <u>soltanto</u> per scheduling astratto (non size-based), la formula precedente si più riscrivere nei termini dell'equazione KP:
$$
E(T_S)=\frac{\frac{\lambda}{2}E(S^2)}{1-\rho}+E(S)
$$
### Scheduling con priorità
#### Teorema di Conway-Maxwell-Miller
Tutti gli ordini di servizio non-preemptive non fanno uso delle dimensioni del job hanno la stessa distribuzione sul numero di job nel sistema (che tramite Little si estende anche ai tempi).
$$
E(N_S)
\qquad
E(T_S)
\qquad
E(N_Q)
\qquad
E(T_Q)
$$
#### Slowdown
Data $x$ la dimensione di un job, è possibile determinare il tempo di risposta medio per i job di dimensione $x$:
$$
E(T_S(x))=E(x + T_Q(x))=x+E(T_Q)=x+{{\lambda \over 2}E(S^2) \over 1-\rho}
$$
**Nota**: $E(T_Q(x))=E(T_Q)~\forall x$.
Lo **slowdown medio** per un job di dimensione $x$ è il tempo di risposta medio osservato rispetto alla sua dimensione, vale a dire
$$
E(sd(x))=\frac{E(T_S(x))}{x}=1+\frac{\frac{\lambda}{2}E(S^2)}{x(1-\rho)}
$$
Notare che i job di piccole dimensione subiscono uno slowdown maggiore rispetto a quelli grandi.

In un ambiente in cui sono presenti per lo più job di piccole dimensioni:
- il **tempo di risposta** $E(T_S)$ tende ad essere rappresentativo delle prestazioni di solo alcuni job - quelli più grandi - dato che questi influiscono maggiormente sulla media e il loro tempo di risposta è maggiore rispetto agli altri
- lo **slowdown** tende ad essere rappresentativo della gran parte dei job, essendo relazionato alla loro dimensione.
#### Processor sharing
Lo scheduling processor sharing non tiene conto della dimensione dei job, bensì assegna a tutti la stessa porzione del tempo disponibile sul server. I job non attendono in coda, bensì il loro processamento inizia appena essi arrivano. In questo modo, i job più piccoli escono automaticamente più in fretta dal sistema.

Confrontando una disciplina processor sharing su un qualsiasi distribuzione con una disciplina FIFO su una distribuzione esponenziale, si ottengono gli stessi risultati:
$$
\begin{align}
P(N_S=n)^{M/G/1/PS}=&\rho^n(1-\rho)=P(N_S=n)^{M/M/1/FIFO}
\\
E(N_S)^{M/G/1/PS}=&{\rho\over1-\rho}=E(N_S)^{M/M/1/FIFO}
\\
E(T_S)^{M/G/1/PS}=&{E(S)\over1-\rho}=E(T_S)^{M/M/1/FIFO}
\end{align}
$$
Tuttavia, PS è migliore di FIFO quando $C^2>1$ (nel caso dell'esponenziale, $C^2=1$ ([ref](#c2))).

Sia $x$ la dimensione di uno o più job:
$$
E(T_S(x))^{M/G/1/PS}={x \over 1-\rho},
\qquad
E(sd(x))^{M/G/1/PS}={1 \over 1-\rho}
$$
In generale, tutti gli scheduling con prelazione non size-based producono lo stesso slowdown medio per i job di qualsiasi dimensione:
$$
E(sd(x))^{M/G/1/preemp-non-size-based}={1 \over 1-\rho}
$$
### Code a serventi multipli
Si consideri il seguente modello di coda, in cui sono present $m>1$ serventi, ognuno con tasso di servizio $\mu$. Si parla, in questo caso, di **modello multiserver omogeneo**.

In generale, si può definire il numero di job in un sistema con $m$ serventi come
$$
E(N_S)=
\begin{cases}
E(N_Q)+\rho & \text{se }m=1 
\\
E(N_Q)+m\rho & \text{se }m>1
\end{cases}
$$
Infatti, se in un certo istante di tempo tutti gli $m$ serventi sono occupati, ci saranno $N_Q$ job nella coda.

Anche l'utilizzazione può essere espressa in maniera simile:
$$
\rho =
\begin{cases}
{\lambda \over \mu} = \lambda E(S_i) & \text{se } m=1
\\
{\lambda \over m\mu} = {{\lambda E(S_i)}\over m} & \text{se } m>1
\end{cases}
$$
Si può interpretare $\rho$ nel caso globale (all'equilibrio stazionario) come la percentuale di quegli $m$ serventi che sono occupati. Inoltre, si assume che ogni servente $i$ abbia lo stesso tempo di servizio $E(S_i)={1 \over \mu}$. Tuttavia, questo tempo vale se si considera lo stesso job che entra ed esce in un servente. Tuttavia, se si vuole conoscere il tempo medio in cui si libera un servente, ossia il tempo trascorso dall'entrata di un job in un servente all'uscita di un altri job da un altro servente è $E(S)={E(S_i) \over m}={1 \over m\mu}$.

La probabilità di avere $n$ job all'interno del sistema è pari a
$$
p(n) =
\begin{cases}
{1 \over n|} (m\rho)^n p(0) &\text{se } n=1,\dots,m
\\
{m^m\over m!}\rho^n p(0) &\text{se } n>m
\end{cases}
$$
dove
$$
p(0)=\left[ \sum_{i=0}^{m-1} {(m\rho)^i\over i!} + {(m\rho)^m\over m!(1-\rho)} \right]^{-1}
$$
La **formula Erlang-C** consente invece di calcolare probabilità che tutti i serventi siano occupati, ossia la probabilità che si formi coda.
$$
P_Q ={(\rho m)^m \over m!(1-\rho)}p(0)
$$
Segue dunque che
$$
E(N_Q) = P_Q {\rho \over 1-\rho}
\qquad\qquad
E(N_S) = P_Q {\rho \over 1-\rho}+m\rho
$$
e, per la legge di Little
$$
E(T_Q)=
{E(N_Q) \over \lambda}=
P_Q {\rho \over \lambda(1-\rho)}=
{P_Q E(S) \over 1-\rho}
$$
Si può studiare anche il numero di serventi occupati $c$:
$$
E(c) = \sum_{n=0}^{m-1}np(n)+\sum_{n=m}^\infty mp(n)=m\rho
$$
Si può riscrivere $\rho$ nel seguente modo:
$$
\rho = \sum_{n=0}^{m-1}{n\over m}p(n)+\sum_{n=m}^\infty p(n)
= \sum_{n=0}^{m-1}{n\over m}p(n)+P_Q
$$
da cui segue che $\rho \geq P_Q$. Si può dunque osservare la seguente relazione tra il tempi medi di attesa in coda nel caso del multiserver (M/M/m) e nel caso del single server (M/M/1) con abstract scheduling (FIFO, LIFO, ecc.) descritto dall'equazione KP:
$$
E(T_Q)_{Erlang}={P_QE(S) \over 1-\rho} \leq {\rho E(S)\over 1-\rho} = E(T_Q)_{KP}
\implies
E(T_Q)_{Erlang}\leq E(T_Q)_{KP}
$$
#### Organizzazione dei server
In caso di serventi multipli, si possono organizzare i server in maniera diversa.
##### Frequency division multiplexing
I server sono organizzati in $m$ centri indipendenti, ognuno con lo stesso tasso di servizio $\mu$ e tasso di arrivi $\lambda\over m$.
![[Code a serventi multipli.png]]
In questo caso, si ha che
$$
E(T_S)^{FDM}=\frac{1}{\mu-\frac{\lambda}{m}}=\frac{m}{m\mu-\lambda}
$$
##### Statistical multiplexing
Il server è unico, ma il suo tasso di servizio è moltiplicato per $m$. Il flusso entrante è unico:
![[Statistical multiplexing.png]]
Si ha che
$$
E(T_S)^{FM}=\frac{1}{m\mu-\lambda}
$$
##### Confronto
1. Dal punto di vista del QoS, il FDM garantisce il QoS ad ogni stream, garantendo uno specifico tasso di servizio; d'altra parte, lo statistical multiplexing non offre garanzie di QoS.
2. se gli $m$ flussi del FDM fossero molto regolari, ossia molto meno variabili rispetto a un processo di Poisson, la loro unione nello statistical multiplexing comporterebbe l'apporto di molta variabilità nel flusso di arrivo. Questo può portare dei problemi, ad esempio se l'applicazione richiede un ritardo basso, come nel caso di voce o video.
##### Modellazione di un sistema
Si considerino due modellazioni di un sistema, entrambi con un'unica coda di arrivo. un sistema ha $m$ serventi con tasso di servizio unitario, mentre l'altro ha un singolo servente con tasso di servizio $m$. Ad esempio, nel caso in cui $m=4$:
![[Due modelli di servente.png]]
Assumendo i job non prelazionabili e ponendo come obiettivo la minimizzazione del tempo di risposta, si possono distinguere due casi:
- alta variabilità del traffico: è preferibile il modello (B), poiché nel modello (A) i job di grandi dimensioni bloccherebbero quelli più piccoli
- bassa variabilità del traffico: è preferibile il modello (A), dato che tutti i job occuperebbero il servente per circa lo stesso tempo, ma il servente è più veloce.
### Scheduling con priorità
Parlando sempre di scheduling astratto, è possibile dividere il flusso entrante in più code. Ogni classe racchiude una **classe di servizio**, ognuna delle quali ha una **priorità** diversa. Questo tipo di scheduling trova applicazione in diverse situazioni:
- traffico multimediale
- QoS
Uno scheduling prioritario fatto a dovere può migliorare le prestazioni tremendamente. Non ha costo in termini di risorse fisiche, bensì il guadagno di prestazioni è gratis.

Si consideri un sistema con un solo centro a cui sono collegate $r$ code con tasso di arrivo $\lambda_1,\dots,\lambda_r$. In generale, date due classi $k$ e $k'$, con $k<k'$, la classe $k$ è quella con priorità maggiore tra le due.

Si può distinguere tra priorità astratta, se basata su criteri astratti (ad esempio, la sottoscrizione al servizio con una tariffa diversa) o size-based (se basata sulla dimensione dei job).

Per ogni classe $k$, sia $S_k$ il tempo di servizio richiesto da un job di tale classe. Si considerano $E(S_k)=E(S)=\frac{1}{\mu}$, $\sigma^2(S_k)=\sigma^2(S)~\forall k$ e $\rho_k=\lambda_k E(S)$.
#### Priorità astratta senza prelazione
Il tempo di attesa in coda per un job di classe $k$ è
$$
E(T_{Q_k})^{NP\_priority}=\frac{{\lambda\over2} E(S^2)}{\left(1-\sum_{i=1}^k \rho_i\right)\cdot\left(1-\sum_{i=1}^{k-1} \rho_i\right)}
$$
Inoltre, $E(T_{Q_k})\leq E(T_{Q_{k+1}})$.

Sono valide dunque le seguenti misure di prestazioni locali:
$$
\begin{align}
&E(T_{S_k})=E(T_{Q_k})+E(S),\qquad E(T_{S_k})\leq E(T_{S_{k+1}})
\\
&E(N_{Q_k})=\lambda_k E(T_{Q_k})
\\&
E(N_{S_k})=\lambda_k E(T_{S_k}),\qquad E(N_{S_k})=E(N_{Q_k})+\rho_k
\end{align}
$$

Per quanto riguarda le prestazioni globali del sistema:
$$
E(T_Q)^{NP\_priority}=E(E(T_{Q_k}))=\sum_{k=1}^r p_k E(T_{Q_k}),
\qquad
p_k=\frac{\lambda_k}{\lambda}
$$
E in maniera simile per le altre misure
$$
\begin{align}
E(T_S)^{NP\_priority}=E(T_Q)^{NP\_priority}+E(S)
\end{align}
$$
Segue inoltre che
$$
\begin{align}
\lambda_k &= p_k \lambda
\\
\rho_k &= \lambda_k E(S)=p_k \lambda E(S)=p_k \rho
\end{align}
$$
Rispetto alla scheduling astratto senza priorità, valgono le seguenti relazioni:
- per la classe con priorità maggiore:
$$
E(T_{Q_1})^{NP\_priority}=\frac{{\lambda\over 2} E(S^2)}{1-\rho_1}\leq E(T_Q)^{KP}
$$
- per la classe con priorità minore:
$$
E(T_{Q_r})^{NP\_priority}=\frac{{\lambda\over 2} E(S^2)}{(1-\rho)(1-\sum_{i=1}^{r-1}\rho_i)}\geq E(T_Q)^{KP}
$$
- prestazioni globali:
$$
E(T_Q)^{NP\_priority}=E(T_Q)^{KP}
\implies
E(T_S)^{NP\_priority}=E(T_S)^{KP}
$$
#### Priorità astratta con prelazione
Per quanto riguarda le prestazioni locali, il tempo di attesa in coda è$$
E(T_{Q_k})^{P\_priority}=\frac{{1\over2} E(S^2)\sum_{i=1}^k\lambda_i}{\left(1-\sum_{i=1}^k \rho_i\right)\cdot\left(1-\sum_{i=1}^{k-1} \rho_i\right)}
$$Si ha che$$
E(T_{Q_k})^{P\_priority}\leq E(T_{Q_{k+1}})^{P\_priority}
$$e$$E(T_{Q_k})^{P\_priority}\leq E(T_{Q_k})^{NP\_priority}=E(T_{Q_k})^{KP}$$Per quanto riguarda le prestazioni globali,
$$
\begin{align}
E(T_Q)^{P\_priority}&=E(E(T_{Q_k}))=\sum_{k=1}^rp_k E(T_{Q_k})
\\&\leq
E(T_Q)^{NP\_priority} = E(T_Q)^{KP}
\end{align}
$$
##### Tempo di servizio virtuale
Nel caso con prelazione, un job può tornare in coda se si presenta un altro job con priorità maggiore. Il ritorno in coda avviene in una classe minore, corrispondente al tempo di servizio rimanente. Tuttavia, il tempo di attesa viene normalmente calcolato in base a quanto il job prende servizio la prima volta. Il restante tempo che si paga è incluso nel **tempo di servizio virtuale**:
$$
E(S_{virt_k})=\frac{E(S)}{1-\sum_{i=1}^{k-1}\rho_i}
$$
È possibile allora calcolare allora le prestazioni globali come
$$
E(T_S)^{P\_priority}=
E(T_Q)^{P\_priority} + \sum_{k=1}^r p_k E(S_{virt_k})
$$
Solo nel caso di tempi di servizio esponenziali, vale la relazione
$$
E(T_S)^{P\_priority}=E(T_S)^{KP}
$$
#### Priorità size-based
Si supponga di dividere i job in $r$ classi di priorità a seconda della loro dimensione: una classe $k$ racchiude tutti job con dimensione compresa in un intervallo $(x_{k-1}, x_k]$. I job di classe $k$ arrivano al sistema con un tasso $\lambda_k$ e sono processati con tassi $\mu_k$, ossia con un tempo medio $E(S_k)=\frac{1}{\mu_k}$.

Sia $f(t)$ la densità del servizio e $F(x)$ la relativa funzione di sopravvivenza. Ad esempio, se il servizio è esponenziale di tasso $\mu$, $f(t)=\mu e^{-\mu t}$ e $F(x)=\int_0^x f(t)dt=1-e^{-\mu t}$.
Si definiscono le seguenti quantità.
- probabilità che un job sia di classe $k$:
$$
p_k = F(x_k)-F(x_{k-1})
$$
- tasso di arrivo dei job di classe $k$, dato $\lambda$ il tasso di arrivo globale:
$$
\lambda_k = \lambda p_k
$$
- tempo di servizio medio di un job di classe $k$:
$$
E(S_k) = \frac{1}{p_k}\int_{x_{k-1}}^{x_k}tf(t)dt
$$
- utilizzazione da parte dei job di classe $k$:
$$
\rho_k = \lambda \int_{x_{k-1}}^{x_k}tf(t)dt
$$
Il tempo di attesa in coda per un job di classe $k$, dipende da tre fattori:
- il tempo di servizio rimanente del job attualmente in servizio, $E(S_{rem})=\frac{\lambda}{2}E(S^2)$
- carico delle code con priorità maggiore o uguale a $k$, $\left(1-\sum_{i=1}^k \rho_i\right)^{-1}$
- carico delle code con priorità maggiore di $k$, $\left(1-\sum_{i=1}^{k-1} \rho_i\right)^{-1}$
E dunque:
$$
E(T_{Q_k})^{SB\_NP\_priority}=\frac{\frac{\lambda}{2}E(S^2)}{\left(1-\sum_{i=1}^k \rho_i\right)\left(1-\sum_{i=1}^{k-1} \rho_i\right)}
$$
In alternativa, si può scrivere
$$
\sum_{i=1}^k \rho_i = \sum_{i=1}^k \lambda_k \int_{x_{i-1}}^{x_i}tf(t)dt=\lambda\int_0^{x_k} tf(t)dt
$$
e dunque
$$
E(T_{Q_k})^{SB\_NP\_priority}=\frac{\frac{\lambda}{2}E(S^2)}{\left(1-\lambda\int_0^{x_k}tf(t)dt\right)\left(1-\lambda\int_0^{x_{k-1}}tf(t)dt\right)}
$$
Per quanto riguarda le prestazioni globali,
$$
E(T_Q)^{SB\_NP\_priority}=E(E(T_{Q_k}))=\sum_{k=1}^r p_k E(T_{Q_k})
$$
##### Confronto tra priorità astratta e size-based
Per quanto riguarda le prestazioni locali, si ha
$$
E(T_{Q_k})^{SB\_NP}\leq E(T_{Q_k})^{abstract\_NP}
$$
mentre non c'è una relazione certa tra $E(T_{S_k})^{SB\_NP}$ e $E(T_{S_k})^{abstract\_NP}$.
D'altra parte, per le prestazioni globali,
$$
E(T_Q)^{SB\_NP}\leq E(T_Q)^{abstract\_NP}
\implies
E(T_S)^{SB\_NP}\leq E(T_S)^{abstract\_NP}
$$
dato che
$$
E(S)^{SB\_NP}=E(S)^{abstract\_NP}=E(S)
$$
##### Shortest job first
La policy **shortest job first** è un caso particolare della policy size-based, in cui li numero della classi viene fatto tendere all'infinito. Quando il server è libero, sceglie dalla coda il job di dimensione minore. Si ha che
$$
E(T_Q)^{SJF}=\frac{\lambda}{2}E(S^2)\int_0^{\infty}\frac{dF(X)}{\left(1-\lambda\int_0^x tf(t)dt\right)^2}
$$
Per un job di una specifica size $x$, si può scrivere, senza calcolare l'integrale
$$
E(T_Q(x))^{SJF}=\frac{\lambda}{2}E(S^2)\frac{1}{(1-\rho_x)^2}
$$
dove
$$
\rho_x=\lambda\int_o^xtf(t)dt=\lambda F(x)\int_0^xt\frac{f(t)}{F(t)}dt
$$
rappresenta il carico composto dai job di dimensione fino a $x$. La seconda formulazione esprime meglio il concetto, essendo il prodotto di:
- $\lambda F(x)$, il tasso di arrivo dei job di dimensione non maggiore di $x$
- $\int_0^xt\frac{f(t)}{F(t)}dt$, la dimensione media dei job di dimensione non maggiore di $x$.
##### Size-based con prelazione
In una policy size-based, la prelazione viene applicata solo se il tempo rimanente al job in esecuzione (di classe $h$, cioè $E(S_{h_rem})$) è minore del tempo richiesto da un qualsiasi job di classe $k<h$. Se la prelazione avviene, il job viene interrotto e posto in una classe considerando solo il tempo rimanente.

Si ha che
$$
E(T_{Q_k})^{SB\_P}=\frac{\frac{\lambda}{2}\left[\int_0^{x_k}t^2dF(t)+(1-F(X_k))x_k^2\right]}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
$$
da cui $E(T_{Q_k})\leq E(T_{Q_{k+1}})$ e $E(T_{Q_k})^{SB\_P}\leq E(T_{Q_k})^{SB\_NP}$. Si ha inoltre che$$
E(T_{S_k})=E(T_{Q_k})+E(S_{virt\_k}),
\qquad
E(S_{virt\_k})=\frac{E(S_k)}{1-\sum_{i=1}^{k-1}\rho_i}
$$Per quanto riguarda le prestazioni globali,
$$
E(T_Q)^{SB\_P}=E\left(E(T_{Q_k})^{SB\_P}\right)=\sum_{k=1}^r p_kE(T_{Q_k})^{SB\_P}
$$
dove $p_k=\frac{\lambda_k}{\lambda}=F(x_k)-F(x_{k-1})$ è la probabilità che un job sia di classe $k$.
##### Shortest remaining job first
Si può considerare il caso di scheduling size-based con prelazione similmente a come fatto per lo scheduling SJF. Ciò significa considerare un numero infinito di classi, avendo dunque
$$
E(T_Q)^{SRJF}=\frac{\lambda}{2}\int_0^\infty\frac{\left[\int_0^x t^2dF(t)+(1-F(x))x^2\right]}{\left(1-\lambda\int_0^x tf(t)dt\right)^2}dF(x)
$$
Una variante è **shortest remaining processing time**, che è condizionato dalla size:
$$
E(T_Q(x))=\frac{\frac{\lambda}{2}\int_0^tt^2f(t)dt+\frac{\lambda}{2}x^2(1-F(x))}{(1-\rho_x)^2},
\qquad
E(T_S(x))=E(T_Q(x))+\int_0^x\frac{dt}{1-\rho_t}
$$
con $\rho_x=\lambda\int_0^xtf(t)dt$.
## Reti di code
Si consideri la seguente rete composta da due centri concatenati.
![[Pasted image 20250823161548.png]]
Gli arrivi sono definiti da un processo di Poisson e i centri hanno tempi di servizio esponenziali con scheduling FIFO. Si vuole conoscere il numero di job nel sistema:
$$
E=\left\{(n_1,n_2)~|~n_i \geq 0\right\}
$$
Questo valore dipende dal numero di job nei singoli centri, rispettivamente $n_1$ e $n_2$. Si può modellare il numero di job nel sistema come una catena di Markov nel seguente modo:
![[Pasted image 20250823162026.png]]
Ricordando che, per un centro a servente singolo,
$$
\Pr\{N_S=n\}^{M/M/1/FIFO}=\rho^n(1-\rho)
$$
con $\rho$ l'utilizzazione del centro, se $\rho_1={\lambda\over\mu_1}<1$, allora
$$
\Pr\{n_1=k\}=\rho_1^k(1-\rho_1), \qquad k\geq0
$$
Il calcolo dello stesso valore nel secondo centro non è immediato.

Si consideri il **teorema di Burke**:
> Dato un sistema M/M/1 stabile con processo di arrivo di Poisson di parametro $\lambda$, il processo di partenza è anch'esso un processo di Poisson di parametro $\lambda$.

Se vale il teorema di Burke, il calcola diventa identico al precedente: se $\rho_2=\frac{\lambda}{\mu_2} < 1$, allora
$$
\Pr\{n_2=k\}=\rho_2^k(1-\rho_2),\qquad k\geq 0
$$
Per la proprietà di indipendenza, si può calcolare la probabilità di avere $i$ job nel primo sistema e $j$ job nel secondo:
$$
\pi(i,j)=\Pr\{n_1=i\}\Pr\{n_2=j\}\qquad \forall(i,j)\in E
$$

Si consideri ora quest'altro caso, in cui è presente un feedback:
![[Pasted image 20250823165705.png]]
In questo caso, cade l'ipotesi di indipendenza, non valendo più il teorema di Burke. Si ragiona separatamente per i due sistemi. Se $\rho_i<1$, $i=1,2$, si ha sempre che
$$
\begin{align}
&\pi(i,j)=\Pr\{n_1=i\}\Pr\{n_2=j\}, &\forall(i,j)\in E
\\
&\Pr\{n_i=k\}=\rho_i^k(1-\rho_i),  &i=1,2
\end{align}
$$
ma ora $\rho_i$ dipende anche dai job che tornano indietro tramite feedback, ossia
$$
\rho_i=\frac{\lambda}{p\mu_i}
$$
E dunque si ottiene il sistema:
$$
\begin{cases}
\lambda_1=\lambda+(1-p)\lambda_2
\\
\lambda_2=\lambda_1
\end{cases}
,
\qquad
\lambda_1=\frac{\lambda}{p}
$$
Inoltre, il tasso di visita è 
$$
v_1=v_2={1\over p}
$$
Una **rete di Jackson** è una rete in cui vale il teorema di Burke.
## Analisi operazionale
L'analisi operazionale è un'evoluzione dell'applicazione della teoria delle code di Markov. Essa si basa su tre principi:
- tutte le quantità devono poter essere misurabili precisamente e tutte le assunzioni devono poter essere direttamente testabili
- il flusso deve essere bilanciato
- i dispositivi (o centri) devono essere omogenei, ossia il routing deve essere indipendente dal carico delle code, ergo il tempo di servizio medio di un certo dispositivi.

Un'ipotesi di dice **testabile operazionalmente** se la sua veridicità può essere stabilita senza alcun dubbio tramite misurazioni. L'**analisi operazionale** fornisce un approccio matematico rigoroso per studiare le prestazioni dei sistemi di calcolo basandosi soltanto su ipotesi testabili operazionalmente.

Le componenti principali sono:
- un sistema (reale o ipotetico)
- un periodo di tempo finito, detto **periodo di osservazione**

Le quantità di base che vengono considerate sono:
- $T$, la lunghezza del periodo di osservazione
- $A$, il numero di arrivi durante il periodo di osservazione
- $B$, il tempo totale per cui il sistema è occupato durante il periodo di osservazione  ($B\leq T$)
- $C$, il numero di completamenti durante il periodo di osservazione

In una rete di code, aperta o chiusa che sia, le stesse quantità possono essere misurate per ogni dispositivo $i=1,\dots,k$ durante il periodo di osservazione $T$:
- $A_i$, il numero di arrivi al dispositivo $i$
- $B_i$, il tempo totale per cui il dispositivo $i$, ossia in cui $n_i>0$
- $C_{ij}$, il numero di richieste terminate dal dispositivo $i$ che passano direttamente al dispositivo $j$; in caso di feedback, è possibile che $C_{ii}>0$

Tutto ciò che è esterno al sistema è considerato il dispositivo $0$:
- $A_{0j}$, il numero di job che vengono processati per la prima volta dal dispositivo $j$
- $C_{i0}$, numero di job il cui ultimo processamento è stato dal dispositivo $i$
### Equazioni operazionali
**Equazioni del bilanciamento del flusso**, o **job flow balance equations**:
$$
X_j=\sum_{i=0}^k X_i p_{ij}
$$
dove $X_i$ è il throughput del dispositivo $i$ e $p_{ij}$ è la probabilità che un job completato dal dispositivo $i$ passi al dispositivo $j$. $X_0$ è considerato il throughput dell'intero sistema.

**Equazioni del tasso di visite**, o **visit ratio equations**:
$$
\begin{cases}
V_0=1
\\
V_j=p_{0j}+\sum_{i=1}^k V_i p_{ij}
\end{cases}
$$
dove $V_i$ è il tasso di visite al dispositivo $i$, ossia il numero di volte in cui un job - in media - visita il dispositivo.

**Legge dell'utilizzazione**:
$$
U_i = X_i S_i
$$
dove $U_i$ è l'utilizzazione del dispositivo $i$ (analogo di $\rho_i$ nei modelli analitici) e $S_i$ è il tempo di servizio medio del dispositivo.

**Legge di Little**:
$$
\bar{n}_i=X_i R_i
$$
dove $\bar{n}_i$ è il numero medio di visite al centro $i$ e $R_i$ è il tempo di risposta medio del centro.

**Legge del flusso di output**, o **output flow law**:
$$
X_0 = \sum_{i=0}^k X_i p_{i0}
$$
che consente di calcolare il throughput del sistema.

**Legge generale del tempo di risposta**:
$$
R = \sum_{i=1}^k V_i R_i
$$
dove $R$ è il tempo di risposta dell'intero sistema.

**Formula del tempo di risposta interattivo**, assumendo bilanciamento del flusso:
$$
R = \frac{M}{X_0}-Z
$$
Questa formula è applicata nei **sistemi terminal-driven**, ossia sistemi di tipo time-sharing in cui l'utente (job) si alterna tra un periodo di *thinking* e un periodo di *waiting*. $Z$ è la durata media del periodo di thinking e $R$ la durata media del periodo di waiting. $Z$ è indipendente da $M$, mentre $R$ dipende da $M$: infatti, i job si ritardano a vicenda mentre si contendono le risorse.
## Dimostrazioni varie
### Priorità astratta senza prelazione
Si vuole dimostrare che classi con priorità minore attendono meno tempo in coda, ossia
$$
E(T_{Q_k})\leq E(T_{Q_{k+1}})
$$
Si ha che
$$
\begin{align}
\frac{\frac{\lambda}{2}E(S^2)}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
&\leq
\frac{\frac{\lambda}{2}E(S^2)}{\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)}
\\\\
\frac{1}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
&\leq
\frac{1}{\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)}
\\\\
\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)
&\geq
\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)
\\\\
\left(1-\sum_{i=1}^{k-1}\rho_i\right)
&\geq
\left(1-\sum_{i=1}^{k+1}\rho_i\right)
\\\\
\sum_{i=1}^{k-1}\rho_i
&\leq
\sum_{i=1}^{k+1}\rho_i
\\\\
\rho_k+\rho_{k+1}&\geq0
\end{align}
$$
Vero essendo $\rho_k\geq0~\forall k$.
Da questa relazione segue anche che
$$
E(T_{S_k})\leq E(T_{S_{k+1}})
$$
essendo $E(S_k)=E(S_{k+1})=E(S)$.
### Confronto tra priorità e non priorità
Si vuole dimostrare che, in media, il tempo di attesa non cambia con l'introduzione della priorità, ossia che
$$
E(T_Q)^{NP\_priority}=E(T_Q)^{KP}
$$
Per semplicità, si considerino solo due classi di priorità, ossia $r=2$. Si ha che
$$
\begin{align}
E(T_Q)^{NP\_priority}
&=
p_1E(T_{Q_1})+p_2E(T_{Q_2})
\\&=
p_1\frac{\frac{\lambda}{2}E(S^2)}{1-\rho_1}+p_2\frac{\frac{\lambda}{2}E(S^2)}{(1-\rho)(1-\rho_1)}
\\&=
\frac{\lambda}{2}E(S^2)\left[\frac{p_1}{1-\rho_1} + \frac{p_2}{(1-\rho)(1-\rho_1)}\right]
\\&=
\frac{\lambda}{2}E(S^2)\frac{p_1(1-\rho)+p_2}{(1-\rho)(1-\rho_1)}
\\&=
\frac{\frac{\lambda}{2}E(S^2)}{1-\rho}
\\&=
E(T_Q)^{KP}
\end{align}
$$
### Priorità astratta con prelazione
#### Prestazioni locali
Si vuole dimostrare che, anche in presenza di prelazione, il tempo di attesa in coda è ridotto per le classi con priorità maggiore, ossia che
$$
E(T_{Q_k})\leq E(T_{Q_{k+1}})
$$
Si ha che
$$
\begin{align}
\frac{\frac{1}{2}E(S^2)\sum_{i=1}^k\lambda_i}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
&\leq
\frac{\frac{1}{2}E(S^2)\sum_{i=1}^{k+1}\lambda_i}{\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)}
\\\\
\frac{\sum_{i=1}^k\lambda_i}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
&\leq
\frac{\sum_{i=1}^{k+1}\lambda_i}{\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)}
\end{align}
$$
- numeratori:
$$
\begin{align}
\sum_{i=1}^k\lambda_i&\leq\sum_{i=1}^{k+1}\lambda_i
\\\\
\lambda_{k+1}&\geq0
\end{align}
$$
	dato che $\lambda_k\geq0~\forall k$. 
- denominatori (stessa dimostrazione della priorità astratta senza prelazione):
$$
\begin{align}
\frac{1}{\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)}
&\leq
\frac{1}{\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)}
\\\\
\left(1-\sum_{i=1}^k\rho_i\right)\left(1-\sum_{i=1}^{k-1}\rho_i\right)
&\geq
\left(1-\sum_{i=1}^{k+1}\rho_i\right)\left(1-\sum_{i=1}^k\rho_i\right)
\\\\
\left(1-\sum_{i=1}^{k-1}\rho_i\right)
&\geq
\left(1-\sum_{i=1}^{k+1}\rho_i\right)
\\\\
\sum_{i=1}^{k-1}\rho_i
&\leq
\sum_{i=1}^{k+1}\rho_i
\\\\
\rho_k+\rho_{k+1}&\geq0
\end{align}
$$
#### Prestazioni globali
Per definizione,
$$
E(T_{Q_k})^{NP\_priority}\leq E(T_{Q_k})^{P\_priority}\qquad\forall k
$$
Dato che
$$
E(T_Q)^{X\_priority}=\sum_{k=1}^r p_kE(T_{Q_k})
$$
allora
$$
E(T_Q)^{NP\_priority}\leq E(T_Q)^{P\_priority}=E(T_Q)^{NP}
$$
Non si può tuttavia stabilire una relazione tra i tempi di risposta. Infatti,
$$
\begin{align}
E(T_S)^{P\_priority}&=E(T_Q)^{P\_priority}+\sum_{k=1}^r p_kE(S_{virt\_k})
\\\\
E(T_S)^{NP\_priority}&=E(T_Q)^{NP\_priority}+E(S)=E(T_S)^{KP}
\end{align}
$$
Tuttavia,
$$
E(T_Q)^{P\_priority}\leq E(T_Q)^{NP\_priority}
$$
mentre
$$
\sum_{k=1}^r p_kE(S_{virt\_k})\geq E(S)
$$
impedendo di stabilire una relazione generale tra $E(T_S)^{P\_priority}$ e $E(T_S)^{KP}$.
Solo nel caso di distribuzione esponenziale si ottiene l'uguaglianza. Infatti, considerando sempre due classi per semplicità:
$$
\begin{align}
E(T_S)^{P\_priority}
&=
p_1E(T_{S_1})+p_2E(T_{S_2})
\\&=
p_1\left[\frac{\frac{\lambda}{2}E(S^2)}{1-\rho_1}+E(S)\right]+p_2\left[\frac{\frac{\lambda}{2}E(S^2)}{(1-\rho)(1-\rho_1)}+\frac{E(S)}{1-\rho_1}\right]
\\&=
p_1\left[\frac{\rho_1E(S)}{1-\rho_1}+E(S)\right]+p_2\left[\frac{\rho E(S)}{(1-\rho)(1-\rho_1)}+\frac{E(S)}{1-\rho_1}\right]
\\&=
E(S)\left\{p_1\left[\frac{\rho_1+1-\rho_1}{1-\rho_1}\right]+p_2\left[\frac{\rho+1-\rho}{(1-\rho)(1-\rho_1)}\right]\right\}
\\&=
E(S)\left[\frac{p_1}{1-\rho_1}+\frac{p_2}{(1-\rho)(1-\rho_1)}\right]
\\&=
E(S)\frac{p_1(1-\rho)+p_2}{(1-\rho)(1-\rho_1)}
\\&=
E(S)\frac{p_1+p_2-p_1\rho}{(1-\rho)(1-\rho_1)}
\\&=
E(S)\frac{1-\rho_1}{(1-\rho)(1-\rho_1)}
\\&=
\frac{E(S)}{1-\rho}=E(T_S)^{KP}
\end{align}
$$