"""Converte in tinta piena gli sfondi a gradiente che portano del TESTO.

Perche': quando un browser forza il tema scuro (Chrome Auto Dark, MIUI e simili)
un gradiente viene trattato come un'immagine e NON viene invertito, mentre il
testo sopra si'. La coppia si rompe e il contrasto crolla a zero — e' il difetto
segnalato il 26/08/2026 sul riquadro ambra "IMPORTANTE". Con una tinta piena
sfondo e testo si invertono INSIEME e il contrasto regge in entrambi i versi.

I gradienti puramente decorativi (barre di avanzamento, barrette colore delle
categorie, velo lucido di .download-box) non portano testo: restano gradienti.

Come si sceglie la tinta, senza andare a occhio:
  - si calcola il contrasto WCAG di ENTRAMBE le tappe col testo che ci sta sopra;
  - se sono entrambe sopra 4,5:1 si usa il PUNTO MEDIO, che e' la tinta piu'
    fedele all'aspetto originale;
  - se almeno una e' sotto soglia si usa la tappa che contrasta MEGLIO: cosi' il
    riquadro non peggiora mai, e anzi guadagna il contrasto che prima aveva solo
    da un lato.

Idempotente: rilanciarlo su un file gia' convertito non trova piu' nulla da fare.
"""
import io
import re
import sys
from pathlib import Path

# Relativo allo script, non un percorso assoluto: cosi' funziona da qualunque
# cartella lo si lanci e su qualunque macchina.
SRC = Path(__file__).resolve().parent.parent / 'index.html'
SOGLIA_AA = 4.5

# gradiente esatto  ->  colore del testo che ci sta sopra
# (stesso gradiente = stesso trattamento, per questo la chiave basta da sola)
DA_CONVERTIRE = {
    'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)': '#1f2937',  # sfondo pagina
    'linear-gradient(135deg, #d1fae5, #f0fdf4)':         '#065f46',  # documento completato
    'linear-gradient(135deg, #10b981, #059669)':         '#ffffff',  # .download-box
    'linear-gradient(135deg, #059669, #047857)':         '#ffffff',  # .download-box:hover
    'linear-gradient(135deg, #fbbf24, #f59e0b)':         '#451a03',  # .booking-box
    'linear-gradient(135deg, #f59e0b, #d97706)':         '#451a03',  # .booking-box:hover
    'linear-gradient(135deg, #dbeafe, #bfdbfe)':         '#1e40af',  # .info-box
    'linear-gradient(135deg, #ede9fe, #ddd6fe)':         '#5b21b6',  # riquadro Esclusiva
    'linear-gradient(135deg, #8b5cf6, #7c3aed)':         '#ffffff',  # .esclusiva-header/-link
    'linear-gradient(135deg, #7c3aed, #6d28d9)':         '#ffffff',  # .esclusiva-link:hover
    'linear-gradient(135deg, #fee2e2, #fecaca)':         '#1f2937',  # .schedule-box + box info
    'linear-gradient(135deg, #ef4444, #dc2626)':         '#ffffff',  # .cta-section + footer
    'linear-gradient(135deg, #e0f2fe, #bae6fd)':         '#0c4a6e',  # box "seleziona patente"
    'linear-gradient(135deg, #fef3c7, #fde68a)':         '#92400e',  # box "come funziona"
    'linear-gradient(135deg, #ffffff, #f9fafb)':         '#1f2937',  # sezione WhatsApp
    'linear-gradient(135deg, #d1fae5, #a7f3d0)':         '#064e3b',  # schede sedi
}

# Decorativi: nessun testo sopra, il gradiente resta.
DA_LASCIARE = [
    'linear-gradient(90deg, #10b981, #059669)',    # barra avanzamento (verde)
    'linear-gradient(90deg, #fbbf24, #f59e0b)',    # barra avanzamento (ambra)
    'linear-gradient(90deg, #93c5fd, #60a5fa)',    # barra avanzamento (blu)
    'linear-gradient(90deg, #3b82f6, #2563eb)',    # .gradient-a1
    'linear-gradient(90deg, #8b5cf6, #7c3aed)',    # .gradient-a2
    'linear-gradient(90deg, #ef4444, #dc2626)',    # .gradient-a
    'linear-gradient(90deg, #6366f1, #4f46e5)',    # .gradient-b
    'linear-gradient(45deg, transparent,',         # velo lucido .download-box::before
]


def rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminanza(c):
    def canale(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canale(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrasto(a, b):
    la, lb = luminanza(rgb(a)), luminanza(rgb(b))
    chiaro, scuro = max(la, lb), min(la, lb)
    return (chiaro + 0.05) / (scuro + 0.05)


def medio(a, b):
    ra, rb = rgb(a), rgb(b)
    return '#%02x%02x%02x' % tuple((x + y) // 2 for x, y in zip(ra, rb))


def tappe(grad):
    """I due colori esadecimali del gradiente, in ordine."""
    return re.findall(r'#[0-9a-fA-F]{3,8}', grad)


def scegli(grad, testo):
    a, b = tappe(grad)
    ca, cb = contrasto(a, testo), contrasto(b, testo)
    if min(ca, cb) >= SOGLIA_AA:
        scelto, motivo = medio(a, b), 'punto medio (entrambe le tappe gia sopra soglia)'
    else:
        scelto, motivo = (a, 'tappa piu contrastata') if ca >= cb else (b, 'tappa piu contrastata')
    return scelto, ca, cb, contrasto(scelto, testo), motivo


def main():
    s = io.open(SRC, encoding='utf-8').read()
    originale = s
    righe = []
    convertiti = 0

    for grad, testo in DA_CONVERTIRE.items():
        n = s.count(grad)
        if n == 0:
            righe.append(('—', grad, testo, 0, 0, 0, 0, 'gia convertito / non presente'))
            continue
        scelto, ca, cb, cs, motivo = scegli(grad, testo)
        s = s.replace(grad, scelto)
        convertiti += n
        righe.append((n, grad, testo, ca, cb, scelto, cs, motivo))

    print('%-3s %-46s %-8s %-13s %-9s %-6s' % ('n', 'gradiente', 'testo', 'contrasto tappe', 'tinta', 'dopo'))
    print('-' * 104)
    for n, grad, testo, ca, cb, scelto, cs, motivo in righe:
        if n == '—':
            print('  —  %-46s %s' % (grad[:46], motivo))
            continue
        allarme = '  <-- era sotto 4.5' if min(ca, cb) < SOGLIA_AA else ''
        print('%-3d %-46s %-8s %5.2f /%5.2f  %-9s %5.2f%s' %
              (n, grad[:46], testo, ca, cb, scelto, cs, allarme))
        print('      %s' % motivo)

    rimasti = [g for g in re.findall(r'linear-gradient\([^)]*\)', s)
               if not any(g.startswith(d) for d in DA_LASCIARE)]
    print('\nSostituzioni: %d' % convertiti)
    print('Gradienti decorativi lasciati: %d' % sum(s.count(d) for d in DA_LASCIARE))
    if rimasti:
        print('⚠️  GRADIENTI NON CLASSIFICATI, da guardare a mano:')
        for g in sorted(set(rimasti)):
            print('   ' + g)
    else:
        print('✅ Nessun gradiente con testo sopra è rimasto.')

    if '--scrivi' not in sys.argv:
        print('\n(prova a vuoto — rilancia con --scrivi per salvare)')
        return
    if s == originale:
        print('\nNiente da salvare: il file era già a posto.')
        return
    io.open(SRC, 'w', encoding='utf-8').write(s)
    print('\nScritto: %s' % SRC)


if __name__ == '__main__':
    main()
