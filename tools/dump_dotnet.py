import sys, os, dnfile

def dump_asm(path, out):
    try:
        pe = dnfile.dnPE(path)
    except Exception as e:
        out.write("### ERROR %s\n" % e); return
    if pe.net is None:
        out.write("### NOT MANAGED: %s\n" % path); return
    md = pe.net.mdtables
    out.write("\n\n########## ASSEMBLY: %s ##########\n" % path)
    td_list = md.TypeDef.rows if md.TypeDef is not None else []
    out.write("\n===== TYPEDEF =====\n")
    for i, td in enumerate(td_list):
        out.write("  [%d] %s.%s\n" % (i+1, td.TypeNamespace, td.TypeName))
    # fields with owner via FieldList
    if md.Field is not None:
        out.write("\n===== FIELDS =====\n")
        for td in td_list:
            for fi in td.FieldList:
                row = md.Field.rows[fi.row_index-1]
                val = ""
                try:
                    if row.Flags.constant and row.Constant is not None:
                        val = " = %r" % (row.Constant.value,)
                except: pass
                out.write("  %s.%s :: %s%s\n" % (td.TypeNamespace, td.TypeName, row.Name, val))
    # methods with owner via MethodList
    mowner = {}
    if md.MethodDef is not None:
        out.write("\n===== METHODDEF =====\n")
        for td in td_list:
            for mi in td.MethodList:
                row = md.MethodDef.rows[mi.row_index-1]
                mowner[mi.row_index] = (td.TypeNamespace, td.TypeName)
                out.write("  [%d] %s.%s :: %s\n" % (mi.row_index, td.TypeNamespace, td.TypeName, row.Name))
    # implmap
    if md.ImplMap is not None:
        out.write("\n===== IMPLMAP =====\n")
        for row in md.ImplMap.rows:
            rid = row.MemberForwarded.row_index
            o = mowner.get(rid, ('?', '?'))
            out.write("  %s!%s  <-  %s.%s::?\n" % (row.ImportScope, row.ImportName, o[0], o[1]))
    # typeref
    if md.TypeRef is not None:
        out.write("\n===== TYPEREF =====\n")
        for row in md.TypeRef.rows:
            out.write("  %s.%s\n" % (row.TypeNamespace, row.TypeName))
    us = getattr(pe.net.metadata, 'user_strings', None)
    if us is not None:
        out.write("\n===== USER STRINGS =====\n")
        for s in us.values():
            try:
                if s and s.strip():
                    out.write("  %s\n" % s)
            except: pass

for p in sys.argv[1:]:
    base = os.path.basename(p)
    try:
        with open(base + ".txt", "w", encoding="utf-8", errors="replace") as o:
            dump_asm(p, o)
    except Exception as e:
        print("FAILED", p, repr(e))
print("done")
