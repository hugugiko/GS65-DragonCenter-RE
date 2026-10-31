import sys, os, dnfile
from dncil.cil.body import reader as cil_reader
from dncil.cil.body.reader import Token

def resolve(pe, ins, md):
    op = ins.operand
    if op is None:
        return ""
    if isinstance(op, Token):
        t, rid = op.table, op.rid
        if t == 0x70:
            s = pe.net.user_strings.get(rid)
            if s is not None:
                return '"%s"' % str(s.value)
            return "<str@%d>" % rid
        def nm(table, rid):
            try: return table.rows[rid-1].Name
            except: return "?"
        if t == 0x06 and md.MethodDef is not None: return "MethodDef::" + nm(md.MethodDef, rid)
        if t == 0x0A and md.MemberRef is not None: return "MemberRef::" + nm(md.MemberRef, rid)
        if t == 0x04 and md.Field is not None: return "Field::" + nm(md.Field, rid)
        if t == 0x01 and md.TypeRef is not None:
            try: return "TypeRef::" + md.TypeRef.rows[rid-1].TypeName
            except: return "TypeRef"
        if t == 0x02 and md.TypeDef is not None:
            try: return "TypeDef::" + md.TypeDef.rows[rid-1].TypeName
            except: return "TypeDef"
        if t == 0x2B: return "MethodSpec"
        return "tok(0x%08X)" % op.value
    if isinstance(op, int):
        return "0x%X (%d)" % (op & 0xFFFFFFFF, op if op < 0x80000000 else op - 0x100000000)
    if isinstance(op, list):
        return "[" + ", ".join("0x%X" % (x & 0xFFFFFFFF) for x in op) + "]"
    return repr(op)

def dump_method(pe, row, out):
    rva = row.Rva
    if not rva:
        out.write("    (no body / abstract)\n"); return
    md = pe.net.mdtables
    try:
        off = pe.get_offset_from_rva(rva)
        data = pe.get_data(off, 0x20000)
        body = cil_reader.read_method_body_from_bytes(data)
        for ins in body.instructions:
            out.write("    %-12s %s\n" % (ins.opcode, resolve(pe, ins, md)))
    except Exception as e:
        out.write("    <FAILED %s>\n" % e)

def main(path, filter_str, out):
    pe = dnfile.dnPE(path)
    md = pe.net.mdtables
    out.write("### IL for methods matching '%s' in %s ###\n" % (filter_str, os.path.basename(path)))
    for td in md.TypeDef.rows:
        tname = "%s.%s" % (td.TypeNamespace, td.TypeName)
        for mi in td.MethodList:
            row = md.MethodDef.rows[mi.row_index-1]
            full = "%s::%s" % (tname, row.Name)
            if filter_str.lower() in full.lower():
                out.write("\n===== %s =====\n" % full)
                dump_method(pe, row, out)

if __name__ == "__main__":
    with open(sys.argv[3], "w", encoding="utf-8", errors="replace") as o:
        main(sys.argv[1], sys.argv[2], o)
    print("done")
