export const meta = {
  name: 'qs-pruefung',
  description: 'QS-Prüfung mit drei Rollen (Sicherheit, Korrektheit, Wartbarkeit) und anschließender Gegenprüfung aller Befunde',
  whenToUse: 'Codeprüfung eines Diffs, Commit-Bereichs oder Moduls im SHS-Prüfungsprogramm. args = Prüfgegenstand, z. B. "git diff origin/main..HEAD" oder "db_sicherung.py".',
  phases: [
    { title: 'Prüfen', detail: 'qs-sicherheit, qs-korrektheit, qs-wartbarkeit parallel' },
    { title: 'Gegenprüfen', detail: 'ein Skeptiker prüft jeden Befund am Code nach' },
  ],
}

const ziel = typeof args === 'string' && args.trim() ? args.trim() : 'die ungepushten Änderungen (git diff origin/main..HEAD sowie nicht committete Änderungen)'

const BEFUNDE = {
  type: 'object',
  properties: {
    befunde: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          datei: { type: 'string' },
          zeile: { type: 'integer' },
          titel: { type: 'string' },
          beschreibung: { type: 'string', description: 'Ablauf/Angriffsweg, Auswirkung, erwartetes Verhalten' },
          schweregrad: { type: 'string', enum: ['hoch', 'mittel', 'niedrig', 'optional'] },
          vorschlag: { type: 'string' },
        },
        required: ['datei', 'titel', 'beschreibung', 'schweregrad', 'vorschlag'],
      },
    },
  },
  required: ['befunde'],
}

const URTEIL = {
  type: 'object',
  properties: {
    urteile: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          nr: { type: 'integer' },
          bestaetigt: { type: 'boolean' },
          begruendung: { type: 'string' },
        },
        required: ['nr', 'bestaetigt', 'begruendung'],
      },
    },
  },
  required: ['urteile'],
}

const ROLLEN = [
  { typ: 'qs-sicherheit', name: 'Sicherheit' },
  { typ: 'qs-korrektheit', name: 'Korrektheit' },
  { typ: 'qs-wartbarkeit', name: 'Wartbarkeit' },
]

phase('Prüfen')
const ergebnisse = await parallel(ROLLEN.map(r => () =>
  agent(`Prüfe ${ziel} in deiner Rolle (${r.name}). Gib nur belegte Befunde zurück; eine leere Liste ist ein gültiges Ergebnis.`,
    { agentType: r.typ, label: r.typ, phase: 'Prüfen', schema: BEFUNDE })
    .then(e => (e ? e.befunde.map(b => ({ ...b, rolle: r.name })) : null))))

const ausgefallen = ROLLEN.filter((r, i) => ergebnisse[i] === null).map(r => r.typ)
if (ausgefallen.length) log(`Ohne Ergebnis: ${ausgefallen.join(', ')}`)

const alle = ergebnisse.filter(Boolean).flat().map((b, i) => ({ nr: i + 1, ...b }))
if (!alle.length) return { ziel, ausgefallen, bestaetigt: [], verworfen: [] }

phase('Gegenprüfen')
const liste = alle.map(b => `#${b.nr} [${b.rolle}, ${b.schweregrad}] ${b.datei}${b.zeile ? ':' + b.zeile : ''} - ${b.titel}\n${b.beschreibung}`).join('\n\n')
const pruefung = await agent(
  `Drei Reviewer haben ${ziel} geprüft und folgende Befunde gemeldet. Prüfe jeden Befund selbst am Code nach und versuche, ihn zu widerlegen. ` +
  `Bestätige nur, was du am Code nachvollziehen kannst. Verwirf außerdem Doppelungen (verweise auf die Nummer des behaltenen Befunds) ` +
  `und Punkte, die in Fortschritt.md bereits als bewusst abgelehnt oder akzeptiertes Restrisiko stehen. Ändere keine Dateien.\n\n${liste}`,
  { label: 'gegenpruefung', phase: 'Gegenprüfen', schema: URTEIL })

const urteil = new Map((pruefung ? pruefung.urteile : []).map(u => [u.nr, u]))
const mitUrteil = alle.map(b => ({ ...b, urteil: urteil.get(b.nr) || null }))
return {
  ziel,
  ausgefallen,
  bestaetigt: mitUrteil.filter(b => b.urteil && b.urteil.bestaetigt),
  verworfen: mitUrteil.filter(b => b.urteil && !b.urteil.bestaetigt),
  ungeprueft: mitUrteil.filter(b => !b.urteil),
}
