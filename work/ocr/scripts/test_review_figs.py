"""The whole-sheet box must be the sheet, and 1882 place names must stay on 1882."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_figs import MAP, WINDOWS, windows_for  # noqa: E402


def test() -> None:
    # 1898: 16267 x 14859. The old bug cropped it to the 1882 sheet's 12102 x 8982.
    other = windows_for("20ec4f9a-16bd-4895-a593-40c6ed9c9555", 16267, 14859)
    name, box, _, _ = other[0]
    assert (name, box) == ("whole_sheet", (0, 0, 16267, 14859)), box
    names = [w[0] for w in other]
    assert not ({w[0] for w in WINDOWS} & set(names)), names
    assert len(other) == 10, names
    # the grid tiles the sheet edge to edge, no remainder strip
    assert other[1][1][:2] == (0, 0) and other[-1][1][2:] == (16267, 14859)

    own = windows_for(MAP, 12102, 8982)
    assert own[0][1] == (0, 0, 12102, 8982)
    assert [w[0] for w in own[1:]] == [w[0] for w in WINDOWS]
    print("ok")


if __name__ == "__main__":
    test()
