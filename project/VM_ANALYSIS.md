# VM SAP — ANALISIS MENDALAM (Sesi lanjutan)

## ENCODING (TERVERIFIKASI)
```
opcode = ac[pc-1]        (pc = posisi SETELAH baca opcode)
operand = ac[pc], ac[pc+1], ...
len(op) = tabel instruction-length (89 opcode) — dari pc_delta mayoritas
```
**Verifikasi:** disasm cross-check vs trace: HIT=40358, MISS=0 (100% akurat)

## ARSITEKTUR: MODULE-TABLE INTERPRETER (ala webpack, di-VM-kan)

### Jump-table loaders (21 opcode, masing-masing ×938)
```
op23  → 57572      op27  → 2528
op63  → 476        op933 → 2655
op476 → 693        op603 → 2788
op693 → 0          op747 → 459
op199 → 97
op361 → 179
op522 → 282
op421 → 520
op540 → 660
op613 → 814
op75  → 1039
op201 → 1644
op814 → 1676
op506 → 2024
op440 → 2183
op480 → 2292
op719 → 2407
```
Tiap loader dipanggil persis **938×** (jumlah modul). Operand = **entry address**
ke bytecode (semua terverifikasi = instruction boundary).

### Code/Data split
```
ac[0..3266]     = CODE (212 section, jump tables + instructions)
ac[3266] = 99999 = SECTION MARKER
ac[3267..70943] = DATA (consts, encoded strings, packed struct max=791621423)
```

### Reusable helpers (dari interpreter body)
```
tM(x) = read/coerce    (202×)
tB    = operand fetch  (188×)
tG(x,v) = write/store  (102×)
tE(k) = string decode  (47×)   → pakai ak()/ae() table
G(x) = FNV hash        (98×)   basis 0xdeadbeef/0x41c6ce57
H(x) = async device-info (30×)
V()   = pako/zlib      (31×)
```

## SEMANTIK OPCODE (terklasifikasi dari nilai operand runtime)
| Opcode | n | var | Peran |
|---|---|---|---|
| 901 PUSH | 2641 | 353 | push (3 operand) |
| 469 STORE | 1848 | 283 | slot[op0]=op1 |
| 459 CALL | 1844 | 22 | jumlah-arg call |
| 765 DISPATCH | 1539 | 103 | akhir-blok both dispatch |
| 281 INIT | 1498 | 318 | init loop (i, stride) |
| 477 MOV | 844 | 113 | move |
| 732 FRAME | 614 | 348 | frame/loop |
| 878 LOAD | 612 | 33 | slot[op0] |
| 370 CALL | 547 | 7 | call(argc,x,y) |
| 94 BINOP | 513 | 127 | operasi biner |
| 303 FRAME2 | 502 | 313 | frame op |
| 65 OP2 | 419 | 43 | 2-operand |
| 82 OP2b | 351 | 15 | 2-operand |
| ... 86 total |

## PROGRAM SHAPE
```
entry  : pc=39972 (op459)
prologue: 21 jump-loader ops → 21 module-loaders
body   : 938 modul (tiap modul = blok dgn entry di jump table)
tail   : op281 [i, 8*i] init loop → op765 [99999,144] END
pc range: 1..57397; distinct pc: 4625; instr: 25,372
```

## SISA untuk emulator fungsional
1. Definisikan TEPAT 86 opcode (semantik dari operand pattern + helper yg dipanggil)
2. Implementasi stack + slot + call frame
3. Decode data section (pakai `ak_decode.py` yang ada)
4. Validasi: emulator hasilkan x-sap-sec identik utk input sama
