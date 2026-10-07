WORK=$(cd "$(dirname "$0")/../.." && pwd)/work/vn1971
for n in $(seq -w 1 44); do [ -f $WORK/up/$n.jpg ] || vips autorot "/Users/airm1/Work/Maps/sources/1971 South Vietnam Admin Map/20251002092659863_00$n.jpg" "$WORK/up/$n.jpg[Q=92]" 2>/dev/null; done; echo prepdone
