"""Turn the 2025 working sheet into the two CSVs this folder keeps.

Input: an .xlsx export of the Google Sheet "Tên ĐVHC thay đổi" (tabs Matching and OldCode).
Output: data/old_units.csv (the 10,035 pre-merger communes, GSO codes) and
data/new_units.csv (the 3,321 post-merger communes and the old codes they were built from).

    python3 work/research/admin-2025/extract.py path/to/export.xlsx

Codes typed in by hand in 2025 (the sheet's Added column) were never folded into the code
list; they are kept apart here as hand_codes so a check can tell machine from person.
"""
import csv
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
HERE = Path(__file__).parent


def read_sheet(path, name):
    """Rows of one tab as dicts, stdlib only. Integral numbers come back without '.0'."""
    z = zipfile.ZipFile(path)
    t = lambda el: ''.join(x.text or '' for x in el.iter('{%s}t' % NS['m']))
    shared = [t(si) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheet = next(s for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', NS)
                 if s.get('name') == name)
    target = rels[sheet.get('{%s}id' % NS['r'])].lstrip('/')
    rows = []
    for row in ET.fromstring(z.read(target if target.startswith('xl/') else 'xl/' + target)).iter('{%s}row' % NS['m']):
        cells = {}
        for c in row.findall('m:c', NS):
            v = c.find('m:v', NS)
            x = '' if v is None else shared[int(v.text)] if c.get('t') == 's' else v.text
            if c.get('t') != 's' and re.fullmatch(r'-?\d+\.0', x):
                x = x[:-2]
            cells[re.match(r'[A-Z]+', c.get('r')).group()] = x
        rows.append(cells)
    head = rows[0]
    return [{head[k]: r.get(k, '') for k in head} for r in rows[1:]]


def codes(text):
    return ';'.join(c.strip() for c in str(text).split(',') if c.strip() not in ('', '-'))


def clean(name):
    return name.replace("\\'", "'").strip()


def main(xlsx):
    old = read_sheet(xlsx, 'OldCode')
    with open(HERE / 'data/old_units.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['code', 'name', 'type', 'district_code', 'district', 'province_code', 'province'])
        for r in old:
            w.writerow([r['Ward Code'], clean(r['Ward Name']), r['Ward Type'], r['District Code'],
                        clean(r['District Name']), r['Province Code'], clean(r['Province Name'])])

    new = [r for r in read_sheet(xlsx, 'Matching') if r['New_Ward_Name'].strip()]
    with open(HERE / 'data/new_units.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['province', 'name', 'old_codes', 'hand_codes', 'hand_note', 'sources_text'])
        for r in new:
            hand = codes(r['Added'])
            w.writerow([r['New_Province_Name'].strip(), clean(r['New_Ward_Name']), codes(r['Merged_From_Codes']),
                        hand, r['Match_Notes'].strip() if hand else '', clean(r['Merged_From_Wards'])])
    print(f'{len(old)} old units, {len(new)} new units')


if __name__ == '__main__':
    main(sys.argv[1])
