# reg.sh NN: build work/vn1971/annotations/<map-uuid>.json for sheet NN (dry; store with georef_write.mjs)
D=$(cd "$(dirname "$0")" && pwd); WORK=$D/../../work/vn1971
ID=$(python3 -c "
import json,sys;print([r['id'] for r in json.load(open('$WORK/maps.json')) if r['sheet_number'].lstrip('0')==sys.argv[1].lstrip('0')][0])" $1)
python3 $D/build.py $1 $ID "${@:2}"
