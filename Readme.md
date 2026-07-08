# Spiegazione scelta struttura DB

| Aspetto                                      | Tabella unica `ForecastDay` con JSON                    | Due tabelle `DailyWeather` + `DailyEventState`                            | Tabella snapshot `ForecastSnapshot`                                       |
| -------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Struttura                                    | Una riga rappresenta un giorno completo                 | Una riga meteo più molte righe evento                                     | Una riga rappresenta una richiesta/previsione completa                    |
| Cosa salva                                   | Dati meteo del giorno + `events` finali del giorno      | Dati meteo separati dagli eventi giornalieri                              | Risultato completo della chiamata, per esempio tutti gli 8 giorni         |
| Eventi del giorno                            | Salvati direttamente nel campo `events` del giorno      | Distribuiti su più righe nella tabella `DailyEventState`                  | Salvati dentro un unico JSON complessivo                                  |
| Recupero giorno precedente                   | Semplice: si legge `previous_day.events`                | Serve recuperare il giorno precedente e poi filtrare gli eventi collegati | Meno naturale, perché i dati sono dentro uno snapshot complessivo         |
| Compatibilità con Problema 1                 | Alta, perché `events` è già una lista JSON              | Media, perché bisogna convertire righe DB in lista JSON                   | Alta come output finale, ma meno comoda per elaborare giorno per giorno   |
| Numero righe con 100 eventi × 8 giorni       | 8 righe totali                                          | 8 righe meteo + circa 800 righe evento                                    | 1 riga per ogni previsione completa                                       |
| Query                                        | Semplici e dirette                                      | Più query o join                                                          | Molto semplici se devi solo restituire il risultato già calcolato         |
| Storico eventi                               | Presente giorno per giorno nel campo JSON               | Presente giorno per giorno in forma normalizzata                          | Presente solo come blocco complessivo della previsione                    |
| Analisi su singolo evento                    | Meno comoda                                             | Molto comoda                                                              | Poco comoda, perché tutto è annidato nel JSON dello snapshot              |
| Cercare `event_index = 37` su tutti i giorni | Più scomodo perché il dato è dentro JSON                | Molto semplice con query relazionale                                      | Ancora più scomodo, perché il dato è dentro un JSON più grande            |
| Prendere tutti gli eventi del giorno prima   | Molto semplice                                          | Più verboso                                                               | Scomodo, perché devi estrarre il giorno precedente dal JSON complessivo   |
| Ricalcolo della stessa richiesta             | Evitabile tramite `processed=True` sul singolo giorno   | Evitabile controllando se gli eventi del giorno esistono già              | Molto facile: se lo snapshot esiste, restituisci quello                   |
| Granularità                                  | Giornaliera                                             | Giornaliera + evento per evento                                           | Intera previsione                                                         |
| Complessità del codice                       | Minore                                                  | Maggiore                                                                  | Bassa per salvare/restituire, più alta se devi riusare i dati interni     |
| Aderenza al progetto attuale                 | Migliore                                                | Più orientata a un modello relazionale classico                           | Buona solo se il Problema 2 deve restituire sempre la previsione completa |
| Quando conviene                              | Quando devi elaborare sequenzialmente giorno per giorno | Quando devi fare analisi dettagliate sugli eventi                         | Quando vuoi cacheare l’intera risposta finale senza manipolarla troppo    |
| Svantaggio principale                        | Query statistiche sugli eventi meno comode              | Troppe righe e più join                                                   | Poco flessibile per recuperare facilmente lo stato del giorno precedente  |

# Notazione O-grande per il Problema 2

## Cosa significa notazione O-grande

La **notazione O-grande**, o **Big-O notation**, è un modo per descrivere quanto cresce il costo di un algoritmo quando cresce la dimensione dell'input.

Nel contesto del **Problema 2**, la richiesta progettuale chiede di stimare:

- la **complessità temporale**, cioè quanto tempo computazionale serve;
- la **complessità spaziale**, cioè quanta memoria o spazio dati viene usato;
- come questi costi crescono quando aumentano i giorni elaborati e il numero di eventi.

Non si tratta quindi di misurare il tempo reale in millisecondi, ma di descrivere il comportamento teorico dell'algoritmo.

---

## Esempio semplice

Immaginiamo di avere una lista di eventi:

```python
events = [
    {"index": 0, "X": 0.2},
    {"index": 1, "X": 0.4},
    {"index": 2, "X": 0.8},
]
```

Se bisogna aggiornare tutti gli eventi, l'algoritmo deve scorrerli uno per uno.

Quindi:

- con 3 eventi servono circa 3 operazioni;
- con 100 eventi servono circa 100 operazioni;
- con 1000 eventi servono circa 1000 operazioni.

Questa operazione ha complessità:

```text
O(E)
```

dove `E` rappresenta il numero di eventi.

Significa che il costo cresce in modo **lineare** rispetto al numero di eventi.

---

## Variabili principali del Problema 2

Per descrivere la complessità del Problema 2 si possono usare queste variabili:

```text
D = numero di giorni ricevuti nella chiamata
E = numero medio o massimo di eventi presenti in un giorno
```

Nel progetto, `D` è limitato superiormente, perché le previsioni possono arrivare al massimo a 7 giorni.

Quindi:

```text
D <= 7
```

Formalmente si può comunque scrivere la complessità in funzione di `D`, ma nella pratica `D` è una costante piccola.

---

## Complessità delle operazioni principali

| Operazione                                                      |        Complessità temporale |                              Complessità spaziale | Motivazione                                                                                                                                           |
| --------------------------------------------------------------- | ---------------------------: | ------------------------------------------------: | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Validare i dati meteo multi-giornalieri                         |                       `O(D)` |                                            `O(D)` | Occorre leggere e validare tutti i giorni ricevuti nella richiesta.                                                                                   |
| Recuperare dal DB lo stato precedente                           |          `O(1)` o `O(log N)` |                                            `O(E)` | Con un indice su `doy`, il recupero è efficiente. Poi bisogna caricare la lista degli eventi del giorno precedente.                                   |
| Elaborare un singolo giorno tramite la black-box del Problema 1 |                       `O(E)` |                                            `O(E)` | Il Problema 1 aggiorna tutti gli eventi esistenti e può eventualmente aggiungerne uno nuovo.                                                          |
| Elaborare tutti i giorni della richiesta                        |                   `O(D × E)` |                          `O(E)` oppure `O(D × E)` | Per ogni giorno vengono elaborati tutti gli eventi. La memoria dipende dal fatto che si mantenga solo lo stato corrente o tutta la risposta completa. |
| Salvare ogni risposta nel DB                                    |                   `O(D × E)` |                            `O(D × E)` persistente | Per ogni giorno viene salvata la lista degli eventi risultanti.                                                                                       |
| Ricostruire la serie temporale di un evento specifico           | `O(D × E)` con JSON semplice | `O(D)` se si usa un indice o struttura ausiliaria | Con un campo JSON bisogna leggere i giorni e cercare l'evento richiesto dentro ogni lista di eventi.                                                  |
| Ricostruire tutte le serie temporali                            |                   `O(D × E)` |                                        `O(D × E)` | Bisogna attraversare tutti i giorni e tutti gli eventi salvati.                                                                                       |

---

## Caso pratico

Se una chiamata contiene:

```text
D = 7 giorni
E = 100 eventi
```

il numero di aggiornamenti evento è circa:

```text
7 × 100 = 700 aggiornamenti evento
```

La complessità generale dell'elaborazione multi-giornaliera è quindi:

```text
O(D × E)
```

Poiché però `D` è al massimo 7, nella pratica si può anche osservare che:

```text
O(7 × E) = O(E)
```

Quindi, nel caso specifico del progetto, il costo cresce principalmente in modo lineare rispetto al numero di eventi.

---

## Motivazione della struttura dati scelta

La soluzione scelta utilizza una tabella `ForecastDay` con un campo JSON `events`.

Ogni record rappresenta un giorno elaborato:

```text
ForecastDay
- doy
- temperature
- bagnatura
- humidity
- rain
- events JSON
- processed
```

Il campo `events` contiene lo stato finale degli eventi alla fine di quel giorno.

Questa scelta è coerente con il Problema 1, perché l'API riceve e restituisce già gli eventi come array JSON:

```json
[
  { "index": 0, "X": 0.2 },
  { "index": 1, "X": 0.4 }
]
```

Salvare gli eventi nello stesso formato evita conversioni inutili tra righe relazionali e payload JSON.

---

## Vantaggi della soluzione con JSON

La scelta di usare un campo JSON per gli eventi ha questi vantaggi:

- struttura più semplice;
- meno tabelle;
- nessuna necessità di join per recuperare gli eventi del giorno precedente;
- formato dati coerente con l'input/output del Problema 1;
- recupero immediato dello stato del giorno precedente tramite `previous_day.events`.

---

## Limite principale della soluzione

Il limite principale è che le query analitiche sui singoli eventi sono meno immediate.

Per esempio, cercare l'andamento di un singolo evento:

```text
event_index = 37
```

richiede di leggere i record giornalieri e cercare quell'evento dentro il JSON di ciascun giorno.

Questa operazione è più semplice da implementare a livello applicativo, ma meno efficiente rispetto a una tabella normalizzata `DailyEventState`.

---

## Conclusione

La complessità principale del Problema 2 è:

```text
O(D × E)
```

dove:

- `D` è il numero di giorni elaborati;
- `E` è il numero di eventi presenti.

Dato che `D` è limitato a massimo 7 giorni, il costo pratico cresce soprattutto rispetto al numero di eventi:

```text
O(E)
```

La struttura dati scelta, cioè `ForecastDay` con campo JSON `events`, è quindi adeguata per il progetto perché privilegia semplicità, coerenza con l'API del Problema 1 e recupero rapido dello stato del giorno precedente.
