#!/usr/bin/env python3
"""vm_reflect.py — model reflection + method table VM SAP.

Interpreter pakai REFLECTION via string table:
  tE(k) -> nama method -> dipanggil sbg fungsi.
  tE("0x15")=toString  tE("0x18")=slice  tE("0x1a")="__proto__"
  tE("0x1c")="get"     tE("0x1b")=hardwareConcurrency  tE("0x1e")="P|I" (separator)

Helpers:
  tM(x) = ambil nilai/coerce   (197×)
  tG(a,b) = set/deref          (95×)
  tE(k) = nama method (reflection) (46×)
  H(x) = type-tag reader       (29×)
  V() = pako/zlib              (29×)
  G(x) = FNV hash              (98×, basis 0xdeadbeef/0x41c6ce57)
"""
import re, json, os
ROOT = os.path.dirname(os.path.abspath(__file__))

def load_tE_map():
    body = open(f"{ROOT}/sdk/vm_interp_FULL.js").read()
    idxs = sorted(set(int(x,16) for x in re.findall(r'tE\("0x([0-9a-fA-F]+)"\)', body)))
    tbl = {}
    for l in open(f"{ROOT}/sdk/strings_decoded.txt"):
        m = re.match(r'\[aj:(\d+)\]\s*(.*)', l)
        if m: tbl[int(m.group(1))] = m.group(2)
    return {f"0x{i:x}": tbl.get(i,"?") for i in idxs}

def main():
    m = load_tE_map()
    print("=== VM reflection/method table ===")
    for k,v in m.items(): print(f"  tE({k}) = {v}")
    json.dump(m, open(f"{ROOT}/vm_reflect.json","w"), indent=1)
    print(f"\nsaved vm_reflect.json ({len(m)} entries)")

if __name__ == "__main__":
    main()
