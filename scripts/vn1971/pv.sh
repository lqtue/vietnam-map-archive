WORK=$(cd "$(dirname "$0")/../.." && pwd)/work/vn1971
magick $WORK/up/$1.jpg -resize 1700x2000 -quality 85 $WORK/allmaps/p$1.jpg; identify -format '%wx%h of ' $WORK/allmaps/p$1.jpg; identify -format '%wx%h\n' $WORK/up/$1.jpg
