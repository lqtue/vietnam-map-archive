"""Strip tqdm noise from upstream's raw logs and print the numbers the journal quotes.
usage: python3 -I clean_logs.py RAW_TRAIN_LOG RAW_TEST_LOG OUT_DIR CLASS
Writes OUT_DIR/train_<CLASS>.log and test_<CLASS>.log (lines upstream printed, in order, unchanged).
"""
import re, sys, os

train_raw, test_raw, out, cls = sys.argv[1:5]
os.makedirs(out, exist_ok=True)


def lines(p):
    return open(p, encoding='utf8', errors='replace').read().replace('\r', '\n').split('\n')


keep = re.compile(r'^(INFO:root:(Total loss|Train loss)|time_for_training|train exit|test exit|best checkpoint|'
                  r'Total trainable|Running in test|.*Test Results|ALLDONE|.*UserWarning)')
tr = [l for l in lines(train_raw) if keep.match(l)]
te = [l for l in lines(test_raw) if keep.match(l)]
open(os.path.join(out, f'train_{cls}.log'), 'w').write('\n'.join(tr) + '\n')
open(os.path.join(out, f'test_{cls}.log'), 'w').write('\n'.join(te) + '\n')

val = []
for l in tr:
    m = re.match(r'INFO:root:Total loss: ([\d.]+), IOU: ([\d.]+), DICE: ([\d.]+) \|\| @ epoch (\d+)', l)
    if m:
        val.append((int(m[4]), float(m[1]), float(m[2]), float(m[3])))
secs = [float(l.split()[1]) for l in tr if l.startswith('time_for_training')]
print('epochs validated:', len(val), ' train-only s/epoch mean: %.2f' % (sum(secs) / len(secs)))
best, bd = None, 0.0
for e, loss, iou, dice in val:  # same rule as upstream: save when dice beats the best so far
    if dice > bd:
        best, bd = (e, iou, dice), dice
print('best val dice epoch %d: val IOU %.4f DICE %.4f' % best)
print('last epoch %d: val IOU %.4f DICE %.4f' % (val[-1][0], val[-1][2], val[-1][3]))
for l in te:
    if 'Test Results' in l:
        print(l)
