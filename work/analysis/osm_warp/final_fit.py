"""Final fit (similarity candidates only: the 6-param affine is not identifiable, see report) on all cells (blind windows already excluded) -> field.pkl (affine v, accepted cell shifts)."""
from pipeline import *
from cv import d, P1, P0
g, cells = load_surfaces()
sc, kind, v, aff, res, models = fit_all(d, P1, P0, g, cells, sorted(cells), kinds=('sim',))
print('chosen', kind, v, 'train meanQ', sc, 'res cells', len(res))
pickle.dump(dict(v=v, res=res, kind=kind, score=sc), open(SP / 'field.pkl', 'wb'))
