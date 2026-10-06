#!/bin/bash
set -e
export WINEDEBUG=-all WINEPREFIX=~/.wine32 WINEARCH=win32
cd "$1/commondb/res"
wine ../../db_utils/db_make.exe load . 2>&1 | tail -2
python3 - <<'PY'
b=bytearray(open('res0005.bin','rb').read()); assert len(b)%196==0
for i in range(len(b)//196): b[i*196+118]=115
open('res0005.bin','wb').write(b)
PY
wine ../../db_utils/res_add_headers.exe res db >/dev/null 2>&1
rm -f commondb.res
wine ../../db_utils/res_implode.exe res db commondb.res >/dev/null 2>&1
ls -la commondb.res
