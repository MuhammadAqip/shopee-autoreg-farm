# LAPORAN VM — SESI 2 (2026-10-16, lanjutan)

## Sesi ini: dari "observable" → "disassembled + decompiled"

Lanjutan dari breach pertama. Target: decode encoding penuh + bangun disassembler/decompiler.

---

## ✅ CAPAIAN BARU SESI INI

### 1. BYTECODE PENUH — 70,943 slot (dari 6,000)
`vm_dump_full.py` patch interpreter → snapshot `ac` LENGKAP + operand lookahead.
```
full dump: 70,943 slots  (vs 6,000 sebelumnya = 11.8× lebih banyak)
max value: 791621423 (packed struct)
section marker: 99999 @ index 3266
```

### 2. INSTRUCTION-LENGTH TABLE — 90 opcode
Dari trace: `pc_delta` mayoritas antar eksekusi = panjang instruksi → jumlah operand.
```
op33,63,476,605,824,891: len=1 (0 operand)
op27,62,140,148:         len=2 (1 operand)
op24,65,87,156,469:      len=3 (2 operand)
op23,82,102,112:         len=4 (3 operand)
op20,75,94,522,736:      len=5 (4 operand)
op128:                   len=11 (10 operand!)
```
→ `vm_opcode_lengths.json`

### 3. STRUKTUR BYTECODE
```
ac[0..3266]    = CODE section (instructions + jump targets)
ac[3266]       = 99999 (SECTION MARKER)
ac[3267..]     = DATA section (consts + encoded strings)
```

### 4. DISASSEMBLER — 1045 instruksi
`vm_disasm.py` → `vm_code_disasm.txt`
```
code section: 1045 instr, 142 opcode unik, coverage PENUH (6004/6000)
145 unknown (14.5%) = opcode belum ke-trace
```
Sample:
```
3191: op901 [426,472,9]     ← PUSH
3199: op370 [2,458,442]     ← CALL
3211: op459 [71]            ← CALL_EXT
3215: op765 [0,8]           ← DISPATCH
3218: op469 [16,878]        ← STORE slot16=878
3238: op281 [1,72]          ← INIT (loop 8×, stride 8 byte)
3265: op765 [99999,144]     ← END marker
```

### 5. DECOMPILER — pseudo-code
`vm_decompile.py` → `vm_pseudo.txt` (1044 baris)
```
op469 = STORE    op901 = PUSH    op765 = DISPATCH
op370 = CALL     op878 = LOAD    op94  = BINOP
op281 = INIT     op477 = MOV     op394 = CONST
```

### 6. PROGRAM SHAPE
```
entry: pc=39972 op459
prologue: op23,63,476,693,199,361,522,421,540,613,75... (tiap-tiap 4518×)
body: dispatch per modul (163 modul)
tail: op281 [i, 8*i] init loop (8×) → op765 [99999,144] END
```

---

## 📊 STATUS OPS
| Opcode | Frek | Peran |
|---|---|---|
| 469 STORE | 117 | tulis slot |
| 901 PUSH | 99 | push nilai |
| 878 LOAD | 63 | baca slot |
| 370 CALL | 60 | panggil |
| 765 DISPATCH | 55 | akhir blok/jump |
| 94 BINOP | 40 | operasi biner |
| 128 BIGOP | 26 | 10-operand |

---

## ⏳ SISA (bounded, bukan blind)
1. Map semantik TEPAT 91 opcode (trace) — sebagian udah (STORE/PUSH/LOAD/CALL)
2. Port 163 modul routine ke emulator (`vm_emulator.py`)
3. Decode data section (string ter-encode — pakai `ak_decode.py` yang udah ada)

**Estimasi: 1-3 hari** (turun dari 2-4 hari — disassembler udah jalan).

---

## 📦 ARTEFAK SESI INI
| File | Isi |
|---|---|
| `vm_dump_full.py` | patch → snapshot bytecode penuh + operand |
| `vm_bytecode_FULL.json` | 70,943 slot |
| `vm_opcode_lengths.json` | tabel panjang instruksi (90 opcode) |
| `vm_disasm.py` | disassembler |
| `vm_code_disasm.txt` | 1045 instruksi |
| `vm_decompile.py` | decompiler |
| `vm_pseudo.txt` | pseudo-code (1044 baris) |
| `vm_code_opcode_hist.json` | histogram opcode |
| `vm_full_dump.json` | dump mentah (2.8 MB) |

## 🏁 STATUS LAYER
7. **x-sap-sec** → 🔓 **DISASSEMBLED** (dulu "stop-line", sekarang bytecode kebaca)
8. **af-ac key** → 🔓 X25519 ditangkap, key di VM (data section bisa di-decode)
