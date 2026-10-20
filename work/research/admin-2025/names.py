"""Where did each 2025 commune name come from?

Two witnesses read every new name against the old units it was built from:
  A, syllable rules: whole · variant · affix · part · near · kept · compound · reused · new
  B, edit distance:  the nearest source name and how far it is
A syllable match settles itself. A one-letter difference, a compound, and a 'new' name that B
finds close to a source go to out/queue.csv, and a person's answer goes in decisions.csv, which is
applied on the next run. Nothing a person decides is lost, and every count can be rebuilt.

    python3 work/research/admin-2025/names.py           # write out/, print the counts
    python3 work/research/admin-2025/names.py --check   # self-test the folding and rules
"""
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TONES = '̣̀́̃̉'          # huyền sắc ngã hỏi nặng
VOWELS = set('aăâeêioôơuưy')
ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}
PREFIX = re.compile(r'^(phường|xã|thị trấn|thị xã|thành phố|tp\.?|quận|huyện|tỉnh|đặc khu)\s+', re.I)
FAMILY = {'whole': 'whole', 'variant': 'whole',          # a name spelled differently is kept, as the article had it
          'affix': 'partial', 'part': 'partial', 'near': 'partial', 'kept': 'partial', 'compound': 'partial',
          'reused': 'new', 'new': 'new'}
LEVELS = ('province', 'district', 'ward')               # a kept name is credited to the highest unit
                                                        # that bore it, as the article counted
ARTICLE = {'whole': 2596, 'partial': 290, 'new': 435}   # VnExpress, 1 Aug 2025, after hand review
NEAR = 0.34                                               # B: share of characters that must change
CODE_FIXES = {    # the 2025 sheet slipped one row among the Kiên Giang islands (found judging, 2026-10-20)
    ('An Giang', 'Kiên Hải'): '31108;31111;31114;31115',
    ('An Giang', 'Tiên Hải'): '30781',
    ('An Giang', 'Sơn Hải'): '30811',
    # The sheet took a commune one mark away from the one the resolution names (Lộc Thạnh for Lộc
    # Thành). Codes per the 2025 UBTVQH15 resolutions 1654-1687 (checked 2026-10-20).
    ('Nghệ An', 'Châu Bình'): '16804',                       # 1678: not merged; Châu Bính went to Châu Tiến
    ('Đồng Nai', 'Lộc Thành'): '25305;25294',                # 1662 item 43
    ('Đồng Tháp', 'Thanh Hoà'): '28436;28462;28480',         # 1663 item 100
    ('Đồng Tháp', 'Thanh Mỹ'): '30067;30073',                # 1663 item 19
    ('Hà Nội', 'Sơn Đồng'): '9868;9859;9871;9877;9874;9883;9880;9862',  # 1656 item 104; also Song Phương
    ('Lào Cai', 'Nậm Chày'): '3088;3076',                    # 1673 item 59
    ('Sơn La', 'Chiềng Hặc'): '4093;4081;4078',              # 1681 item 39
    ('Thái Nguyên', 'Văn Lăng'): '5671;5665',                # 1683 item 27
    ('Phú Thọ', 'Liên Hoà'): '8789;8833;8812',               # 1676 item 65
    ('Thanh Hoá', 'Đông Tiến'): '16396;15856;16402;15850;15847;15853;16405',  # 1686 item 131; also Thiệu Vân
    ('Thanh Hoá', 'Hoằng Thanh'): '15997;15994;16003;16000', # 1686 item 21; also Hoằng Đông, Hoằng Phụ
    ('Tuyên Quang', 'Tân Thanh'): '2575;2578;2590',          # 1684 item 38
    ('Vĩnh Long', 'Đông Thành'): '29813;29812;29809;29818',  # 1687 item 109: the sheet left out Đông Thành
    ('Tây Ninh', 'Thạnh Phước'): '27880;27877;27874',        # 1682 item 17
    ('Điện Biên', 'Sáng Nhè'): '3247;3259;3244',             # 1661 item 20: the sheet left out Xá Nhè
    ('Hải Phòng', 'Quyết Thắng'): '11758;11761;11764',       # 1669 item 56: Tự Cường (Tiên Lãng), not Tứ Cường
    # resolutions.py found these (2026-10-20): the item text names other communes than the sheet's list.
    # Each was read against its item. The codes follow the item; hand codes stay in hand_codes.
    ('An Giang', 'Chợ Vàm'): '30409;30427;30433',   # 1654 item 12: the sheet left out Phú Thành (Phú Tân)
    ('An Giang', 'Thoại Sơn'): '30682;30721;30724',   # 1654 item 38: Bình Thành (Thoại Sơn), not Bình Thạnh (Châu Thành)
    ('An Giang', 'Long Thạnh'): '30947;30946;30943',   # 1654 item 63: Vĩnh Thạnh (Giồng Riềng), not Vĩnh Thành (Châu Thành)
    ('An Giang', 'Tân Hội'): '30860;30871;30856;30853',   # 1654 item 67: Tân Thành (Tân Hiệp), Tân Hoà (Tân Hiệp), not Tân Thạnh (Tân Châu), Tân Hoà (Phú Tân)
    ('Cà Mau', 'Khánh An'): '32059;32053',   # 1655 item 11: Khánh Lâm (U Minh) is not in the item
    ('Cà Mau', 'Hưng Mỹ'): '32140;32146;32141',   # 1655 item 33: Tân Hưng (Cái Nước) is not in the item
    ('Cà Mau', 'Lý Văn Lâm'): '32014;32032;32122',   # 1655 item 61: Lương Thế Trân (Cái Nước) is not in the item
    ('Cà Mau', 'Tân Thành'): '32008;32025;32026;32020;32017;32035;32029',   # 1655 item 62: Tân Thành (Cà Mau), not Tân Thạnh (Giá Rai)
    ('Hà Nội', 'Giảng Võ'): '31;178;199;25;34;7;28',   # 1656 item 5: Ngọc Hà (Ba Đình) is not in the item
    ('Hà Nội', 'Văn Miếu - Quốc Tử Giám'): '202;205;193;19;196;181;73;256;208;241;226',   # 1656 item 11: Kim Liên (Đống Đa), Bạch Mai (Hai Bà Trưng) is not in the item
    ('Hà Nội', 'Láng'): '187;199;25',   # 1656 item 12: Giảng Võ (Ba Đình) is not in the item
    ('Hà Nội', 'Ô Chợ Dừa'): '178;19;34;190;217;196;181',   # 1656 item 13: Kim Liên (Đống Đa) is not in the item
    ('Hà Nội', 'Định Công'): '307;337;331;643;646;316;325',   # 1656 item 19: Tương Mai (Hoàng Mai) is not in the item
    ('Hà Nội', 'Yên Sở'): '331;340;658;337;334',   # 1656 item 21: Định Công (Hoàng Mai) is not in the item
    ('Hà Nội', 'Phương Liệt'): '352;331;358;307;364;349',   # 1656 item 24: Yên Sở (Hoàng Mai) is not in the item
    ('Hà Nội', 'Xuân Đỉnh'): '610;616;103;611',   # 1656 item 32: Phú Diễn (Bắc Từ Liêm), Phú Thượng (Tây Hồ) is not in the item
    ('Hà Nội', 'Từ Liêm'): '592;631;632;163;625;626',   # 1656 item 35: Phú Diễn (Bắc Từ Liêm) is not in the item
    ('Hà Nội', 'Xuân Phương'): '623;622;634;628;9862;613;620',   # 1656 item 36: Thượng Cát (Bắc Từ Liêm), Đông Ngạc (Bắc Từ Liêm) is not in the item
    ('Hà Nội', 'Đại Mỗ'): '9886;634;9541;631;343;175;632;637',   # 1656 item 38: Yên Hoà (Cầu Giấy) is not in the item
    ('Hà Nội', 'Việt Hưng'): '121;151;127;136;130;124;115',   # 1656 item 41: Bồ Đề (Long Biên) is not in the item
    ('Hà Nội', 'Phúc Lợi'): '148;553;121;127;136;151',   # 1656 item 42: Bồ Đề (Long Biên) is not in the item
    ('Hà Nội', 'Dương Nội'): '9886;9552;9562;9889;634;9551',   # 1656 item 44: Tây Mỗ (Nam Từ Liêm) is not in the item
    ('Hà Nội', 'Thanh Liệt'): '649;316;367;373;9542;646;643',   # 1656 item 48: Hoàng Liệt (Hoàng Mai), Khương Đình (Thanh Xuân) is not in the item
    ('Hà Nội', 'Hồng Vân'): '10225;10207;10213;10210;10192;10186;685',   # 1656 item 59: Ngọc Hồi (Thanh Trì) is not in the item
    ('Hà Nội', 'Chuyên Mỹ'): '10315;10348;10339;10330;10321',   # 1656 item 62: Vân Từ (Phú Xuyên), not Văn Tự (Thường Tín)
    ('Hà Nội', 'Bình Minh'): '10126;10135;10132;10141;10063;10120;9571',   # 1656 item 65: Kiến Hưng (Hà Đông) is not in the item
    ('Hà Nội', 'Hoà Xá'): '10417;10396;10435;10429',   # 1656 item 70: Hoà Phú (Ứng Hoà), not Hoà Phú (Chương Mỹ)
    ('Hà Nội', 'Mỹ Đức'): '10441;10504;10480;10501;10477',   # 1656 item 72: Đại Hưng (Mỹ Đức), not Đại Hùng (Ứng Hoà)
    ('Hà Nội', 'Quảng Oai'): '9688;9679;9682;9685;9619;9667',   # 1656 item 82: Tiên Phong (Ba Vì), not Tiền Phong (Mê Linh)
    ('Hà Nội', 'Cổ Đô'): '9625;9628;9640;9646;9643;9634',   # 1656 item 84: Phú Đông (Ba Vì), not Phù Đổng (Gia Lâm)
    ('Hà Nội', 'Phúc Lộc'): '9724;9733;9721;9739;9727',   # 1656 item 91: Vân Phúc (Phúc Thọ), not Vạn Phúc (Thanh Trì)
    ('Hà Nội', 'Hưng Đạo'): '9931;9919;9934',   # 1656 item 99: Đồng Quang (Quốc Oai), not Đông Quang (Ba Vì)
    ('Hà Nội', 'An Khánh'): '9892;9886;9877;9889;9874;9883;9880',   # 1656 item 105: Song Phương (Hoài Đức), not Đại Mỗ (Nam Từ Liêm), Sơn Đông (Sơn Tây), Song Phượng (Đan Phượng)
    ('Hà Nội', 'Ô Diên'): '9805;9817;9802;9796;9799;9808;9013;607;9820',   # 1656 item 107: Văn Khê (Mê Linh), not Thượng Cát (Bắc Từ Liêm), Đông Ngạc (Bắc Từ Liêm)
    ('Hà Nội', 'Bát Tràng'): '589;154;148;565;577;583',   # 1656 item 111: Phúc Lợi (Long Biên) is not in the item
    ('Hà Nội', 'Yên Lãng'): '9004;9016;8998;8980;9013;9007;9787;9793;9790;9796',   # 1656 item 119: Mê Linh (Mê Linh) is not in the item
    ('Hà Nội', 'Tiến Thắng'): '8995;8983;8986;8974;8977;8992;9013;8980',   # 1656 item 120: Mê Linh (Mê Linh) is not in the item
    ('Hà Nội', 'Quang Minh'): '8973;8989;9010;9019;8974;8977;8992',   # 1656 item 121: Tiến Thắng (Mê Linh) is not in the item
    ('Bắc Ninh', 'Yên Phong'): '9193;9223;9232;9217',   # 1658 item 3: Đông Tiến (Yên Phong), not Đồng Tiến (Yên Thế)
    ('Đà Nẵng', 'Đức Phú'): '20977;20980',   # 1659 item 30: Tam Thạnh (Núi Thành), not Tam Thanh (Tam Kỳ)
    ('Đà Nẵng', 'Tây Hồ'): '20368;20365;20380;20377',   # 1659 item 32: Tam Thành (Phú Ninh), not Tam Thanh (Tam Kỳ)
    ('Đà Nẵng', 'Phú Ninh'): '20392;20387;20395',   # 1659 item 34: Tam Dân (Phú Ninh), not Tam Đàn (Phú Ninh)
    ('Đà Nẵng', 'Nam Trà My'): '20944;20956',   # 1659 item 44: Trà Don (Nam Trà My), not Trà Dơn (Nam Trà My)
    ('Đắk Lắk', 'Ea Drông'): '24334;24328',   # 1660 item 2: Ea Drông (Buôn Hồ), not Ea D'Rơng (Cư M'gar)
    ('Đắk Lắk', 'Ea Knuếc'): '24517;24499;24505',   # 1660 item 26: Hoà Đông (Krông Pắc), not Hoà Đồng (Tây Hoà)
    ('Điện Biên', 'Núa Ngam'): '3359;3365;3358',   # 1661 item 35: Na Tông (Điện Biên), not Nà Tòng (Tuần Giáo)
    ('Đồng Nai', 'Nhơn Trạch'): '26479;26473;26488;26485;26470',   # 1662 item 2: Phước Thiền (Nhơn Trạch), Phú Thạnh (Nhơn Trạch), not Phước Thiện (Bù Đốp), Phú Thanh (Tân Phú)
    ('Đồng Nai', 'Long Thành'): '26368;26392;26395;26404',   # 1662 item 6: Lộc An (Long Thành), not Lộc An (Lộc Ninh)
    ('Đồng Nai', 'Tân Tiến'): '25318;25321;25276',   # 1662 item 49: Tân Thành (Bù Đốp), not Tân Thành (Đồng Xoài)
    ('Đồng Nai', 'Tân Lợi'): '25375;25378;25384',   # 1662 item 60: Tân Hưng (Đồng Phú), not Tân Hưng (Hớn Quản)
    ('Đồng Nai', 'Long Khánh'): '26083;26086;26107',   # 1662 item 78: Xuân Hoà (Long Khánh), Phú Bình (Long Khánh), not Phú Bình (Tân Phú), Xuân Hoà (Xuân Lộc)
    ('Đồng Nai', 'Tân Triều'): '25996;26194;26185;26188',   # 1662 item 80: Thạnh Phú (Vĩnh Cửu), not Thanh Phú (Bình Long)
    ('Đồng Nai', 'Thanh Sơn'): '26209',   # 1662 closing: Thanh Sơn (Định Quán), not Thanh Sơn (Tân Phú)
    ('Đồng Tháp', 'Bình Thành'): '30163;30148',   # 1663 item 16: Bình Tấn (Thanh Bình), not Bình Tân (Gò Công Tây)
    ('Đồng Tháp', 'Tân Long'): '30154;30136;30133;30151;30166;29995',   # 1663 item 17: Tân Bình (Thanh Bình), not Tân Bình (Cai Lậy)
    ('Đồng Tháp', 'Mỹ Hiệp'): '30115;30127;30112',   # 1663 item 28: Mỹ Long (Cao Lãnh), not Mỹ Long (Cai Lậy)
    ('Đồng Tháp', 'Lai Vung'): '30226;30220;30196;30199',   # 1663 item 32: Tân Thành (Lai Vung), not Tân Thanh (Cái Bè)
    ('Đồng Tháp', 'Tân Phú Trung'): '30256;30274;30262;30259',   # 1663 item 38: Tân Bình (Châu Thành), not Tân Bình (Cai Lậy)
    ('Đồng Tháp', 'Tân Thới'): '28693;28699;28690',   # 1663 item 81: Tân Phú (Tân Phú Đông), not Tân Phú (Cai Lậy)
    ('Đồng Tháp', 'Cao Lãnh'): '29869;29875;29872;29878;29892;29893;29899;29890;29896',   # 1663 item 95: Phường 4 (Cao Lãnh), Phường 3 (Cao Lãnh), Phường 6 (Cao Lãnh), not Phường 4 (Mỹ Tho), Phường 6 (Mỹ Tho), Phường 3 (Cai Lậy)
    ('Đồng Tháp', 'Sa Đéc'): '29905;29911;29902;29908;29919;29917;29914;29920',   # 1663 item 98: Phường 3 (Sa Đéc), Phường 1 (Sa Đéc), Phường 2 (Sa Đéc), not Phường 1 (Mỹ Tho), Phường 2 (Mỹ Tho), Phường 3 (Cai Lậy)
    ('Gia Lai', 'Kim Sơn'): '21727;21718',   # 1664 item 27: Ân Nghĩa (Hoài Ân), not An Nghĩa (An Lão)
    ('Gia Lai', 'Ia Tôr'): '23905;23924;23908',   # 1664 item 52: Ia Bang (Chư Prông), not Ia Băng (Đăk Đoa)
    ('Gia Lai', 'Đak Pơ'): '23995;23989;23992;23998',   # 1664 item 61: An Thành (Đăk Pơ), not Ân Thạnh (Hoài Ân)
    ('Gia Lai', 'An Khê'): '23633;23617;23620;23630;23623;23635',   # 1664 item 124: Ngô Mây (An Khê), not Ngô Mây (Quy Nhơn)
    ('Hưng Yên', 'Kiến Xương'): '13138;13165;13162;13144;13075',   # 1666 item 79: Bình Minh (Kiến Xương), not Bình Minh (Khoái Châu)
    ('Hưng Yên', 'Bình Thanh'): '13177;13171;13183',   # 1666 item 83: Minh Tân (Kiến Xương), not Minh Tân (Phù Cừ)
    ('Hưng Yên', 'Vũ Thư'): '13258;13228;13234;13237;13231;13192',   # 1666 item 88: Minh Khai (Vũ Thư), Hoà Bình (Vũ Thư), not Hoà Bình (Hưng Hà), Minh Khai (Hưng Hà)
    ('Hưng Yên', 'Vạn Xuân'): '13198;13195;13219;13201',   # 1666 item 93: Việt Hùng (Vũ Thư), not Việt Hưng (Văn Lâm)
    ('Khánh Hoà', 'Vĩnh Hải'): '22867;22868;22846',   # 1667 item 39: Thanh Hải (Ninh Hải), not Thành Hải (Phan Rang-Tháp Chàm)
    ('Cần Thơ', 'Đại Thành'): '31344;31414;31411',   # 1668 item 21: Tân Thành (Ngã Bảy), not Tân Thạnh (Thới Lai)
    ('Cần Thơ', 'Gia Hoà'): '31714;31726',   # 1668 item 66: Thạnh Quới (Mỹ Xuyên), not Thạnh Quới (Vĩnh Thạnh)
    ('Cần Thơ', 'Nhu Gia'): '31708;31720',   # 1668 item 67: Thạnh Phú (Mỹ Xuyên), not Thạnh Phú (Cờ Đỏ)
    ('Cần Thơ', 'Trường Khánh'): '31648;31657;31654',   # 1668 item 69: Phú Hữu (Long Phú), not Phú Hữu (Châu Thành)
    ('Cần Thơ', 'Tân Thạnh'): '31660;31663;31666',   # 1668 item 71: Tân Thạnh (Long Phú), not Tân Thạnh (Thới Lai)
    ('Cần Thơ', 'Long Phú'): '31639;31669',   # 1668 item 72: Long Phú (Long Phú), not Long Phú (Long Mỹ)
    ('Cần Thơ', 'Thuận Hoà'): '31576;31582',   # 1668 item 80: Phú Tân (Châu Thành), not Phú Tân (Châu Thành)
    ('Cần Thơ', 'Mỹ Hương'): '31606;31612;31591',   # 1668 item 84: Thuận Hưng (Mỹ Tú), not Thuận Hưng (Long Mỹ)
    ('Cần Thơ', 'Tân Long'): '31762;31744;31741',   # 1668 item 85: Tân Long (Ngã Năm), Long Bình (Ngã Năm), not Tân Long (Phụng Hiệp), Long Bình (Long Mỹ)
    ('Hải Phòng', 'Bạch Đằng'): '11473;11500;11539',   # 1669 item 5: Minh Đức (Thuỷ Nguyên), not Minh Đức (Đồ Sơn)
    ('Hải Phòng', 'An Quang'): '11650;11647;11644',   # 1669 item 48: Quốc Tuấn (An Lão), not Quốc Tuấn (Nam Sách)
    ('Hải Phòng', 'Kiến Hải'): '11734;11752;11749;11746',   # 1669 item 53: Tân Phong (Kiến Thuỵ), not Tân Phong (Ninh Giang)
    ('Hải Phòng', 'Nguyễn Bỉnh Khiêm'): '11911;11890;11884',   # 1669 item 63: Hoà Bình (Vĩnh Bảo), not Hoà Bình (Kim Thành)
    ('Hải Phòng', 'Khúc Thừa Dụ'): '11188;11224;11230',   # 1669 item 101: Bình Xuyên (Ninh Giang), not Bình Xuyên (Bình Giang)
    ('Lai Châu', 'Nậm Tăm'): '3509;3526;3517',   # 1670 item 21: Nậm Cha (Sìn Hồ), not Nậm Chà (Nậm Nhùn)
    ('Lâm Đồng', 'Phúc Thọ Lâm Hà'): '24898;24907',   # 1671 item 16: Tân Thanh (Lâm Hà), not Tân Thành (Hàm Thuận Nam)
    ('Lâm Đồng', 'Đam Rông 1'): '24886;24889',   # 1671 item 17: Đạ K' Nàng (Đam Rông), not Đắk Nang (Krông Nô)
    ('Lâm Đồng', 'Bảo Lâm 3'): '25090;25093',   # 1671 item 30: Lộc Thành (Bảo Lâm), not Lộc Thanh (Bảo Lộc)
    ('Lạng Sơn', 'Hoàng Văn Thụ'): '6175;6178;6172;6181;6166',   # 1672 item 29: Hồng Thái (Văn Lãng), not Hồng Thái (Bình Gia)
    ('Lạng Sơn', 'Vân Nham'): '6415;6418;6433',   # 1672 item 47: Nhật Tiến (Hữu Lũng), not Nhất Tiến (Bắc Sơn)
    ('Lạng Sơn', 'Chiến Thắng'): '6481;6469;6502;6472',   # 1672 item 54: Vân Thuỷ (Chi Lăng), not Vạn Thuỷ (Bắc Sơn)
    ('Lạng Sơn', 'Đồng Đăng'): '6184;6208;6214;6205;6190',   # 1672 item 58: Hồng Phong (Cao Lộc), not Hồng Phong (Bình Gia)
    ('Lào Cai', 'Púng Luông'): '4495;4483;4492',   # 1673 item 3: La Pán Tẩn (Mù Căng Chải), not La Pan Tẩn (Mường Khương)
    ('Lào Cai', 'Âu Lâu'): '4546;4543;4567;4540',   # 1673 item 88: Minh Quân (Trấn Yên), not Minh Quán (Trấn Yên)
    ('Lào Cai', 'Sa Pa'): '3016;3003;3002;3028;3006;3001',   # 1673 item 91: the sheet left out Sa Pả (Sa Pa)
    ('Ninh Bình', 'Ninh Cường'): '14077;14074;14083',   # 1674 item 40: Trực Hùng (Trực Ninh), not Trực Hưng (Trực Ninh)
    ('Ninh Bình', 'Yên Từ'): '14719;14737;14728',   # 1674 item 87: Yên Phong (Yên Mô), not Yên Phong (Ý Yên)
    ('Ninh Bình', 'Trung Sơn'): '14368;14365;14380',   # 1674 item 128: Đông Sơn (Tam Điệp), not Đồng Sơn (Nam Trực)
    ('Huế', 'Hương Trà'): '19996;20011;20008',   # 1675 item 6: the sheet left out Hương Văn (Hương Trà)
    ('Phú Thọ', 'Vạn Xuân'): '8470;8461;8467',   # 1676 item 36: Lam Sơn (Tam Nông), not Lâm Sơn (Lương Sơn)
    ('Phú Thọ', 'Văn Miếu'): '8641;8629;8611',   # 1676 item 43: Tân Lập (Thanh Sơn), not Tân Lập (Lạc Sơn)
    ('Phú Thọ', 'Long Cốc'): '8620;8626;8608',   # 1676 item 52: Vinh Tiền (Tân Sơn), not Vĩnh Tiến (Kim Bôi)
    ('Phú Thọ', 'Yên Lập'): '8290;8326;8314;8320',   # 1676 item 53: Hưng Long (Yên Lập), not Hùng Long (Đoan Hùng)
    ('Phú Thọ', 'Yên Lãng'): '8776;8773',   # 1676 item 61: Quang Yên (Sông Lô), not Quảng Yên (Thanh Ba)
    ('Phú Thọ', 'Thái Hoà'): '8785;8791;8788',   # 1676 item 64: Liễn Sơn (Lập Thạch), not Liên Sơn (Lương Sơn)
    ('Phú Thọ', 'Đạo Trù'): '8917;8914',   # 1676 item 70: Yên Dương (Tam Đảo), not Yên Dưỡng (Cẩm Khê)
    ('Phú Thọ', 'Dũng Tiến'): '5077;5083;5086',   # 1676 item 102: Mi Hoà (Kim Bôi), not Mỹ Hoà (Tân Lạc)
    ('Phú Thọ', 'Thượng Cốc'): '5272;5284;5293',   # 1676 item 111: Văn Sơn (Lạc Sơn), not Vân Sơn (Tân Lạc)
    ('Phú Thọ', 'Mai Châu'): '5200;5242;5254;5233;5221',   # 1676 item 119: Thành Sơn (Mai Châu), not Thanh Sơn (Lương Sơn)
    ('Quảng Ngãi', 'Đông Sơn'): '21103;21091;21109;21112;21187',   # 1677 item 9: Bình Thanh (Bình Sơn), not Bình Thạnh (Bình Sơn)
    ('Quảng Ngãi', 'Đăk Pxi'): '23504;23503',   # 1677 item 52: Đăk Long (Đắk Hà), not Đắk Long (Đắk Glei)
    ('Nghệ An', 'Nhân Hoà'): '17350;17347;17344',   # 1678 item 3: Tam Đỉnh (Anh Sơn), not Tam Đình (Tương Dương)
    ('Nghệ An', 'Hùng Châu'): '17395;17392;17398;17401',   # 1678 item 19: Diễn Lâm (Diễn Châu), not Diên Lãm (Quỳ Châu)
    ('Nghệ An', 'Đô Lương'): '17638;17656;17668;17650;17659;17683;17665;17662;17617',   # 1678 item 20: Bắc Sơn (Đô Lương), not Bắc Sơn (Quỳ Hợp)
    ('Nghệ An', 'Văn Hiến'): '17674;17647;17680;17677;17644',   # 1678 item 22: Hoà Sơn (Đô Lương), not Hoa Sơn (Anh Sơn)
    ('Nghệ An', 'Na Ngoi'): '16873;16870',   # 1678 item 35: Nậm Càn (Kỳ Sơn), not Nậm Cắn (Kỳ Sơn)
    ('Nghệ An', 'Nam Đàn'): '17935;17932;17938',   # 1678 item 39: Nam Thanh (Nam Đàn), not Nam Thành (Yên Thành)
    ('Nghệ An', 'Nghi Lộc'): '17827;17899;17893;17911',   # 1678 item 49: Diên Hoa (Nghi Lộc), Nghi Vạn (Nghi Lộc), not Diễn Hoa (Diễn Châu), Nghi Văn (Nghi Lộc)
    ('Nghệ An', 'Sơn Lâm'): '17759;17723',   # 1678 item 92: Thanh Sơn (Thanh Chương), not Thành Sơn (Anh Sơn)
    ('Nghệ An', 'Yên Thành'): '17506;17572;17554;17557',   # 1678 item 102: Đông Thành (Yên Thành), not Đồng Thành (Yên Thành)
    ('Quảng Trị', 'Nam Ba Đồn'): '19084;19075;19069;19090;19096',   # 1680 item 2: Quảng Tiên (Ba Đồn), not Quảng Tiến (Quảng Trạch)
    ('Quảng Trị', 'Phú Trạch'): '19018;19021;19015;19012',   # 1680 item 17: Quảng Phú (Quảng Trạch), not Quang Phú (Đồng Hới)
    ('Quảng Trị', 'Quảng Trị'): '19357;19360;19361;19358;19705',   # 1680 item 76: Phường 1 (Quảng Trị), Phường 2 (Quảng Trị), not Phường 1 (Đông Hà), Phường 2 (Đông Hà)
    ('Quảng Trị', 'Tân Thành'): '18919',   # 1680 closing: Tân Thành (Minh Hoá), not Tân Thành (Hướng Hoá)
    ('Sơn La', 'Yên Sơn'): '4084;4087',   # 1681 item 41: Chiềng On (Yên Châu), not Chiềng Ơn (Quỳnh Nhai)
    ('Sơn La', 'Chiềng Mai'): '4120;4150;4147;4153;4132',   # 1681 item 42: Chiềng Dong (Mai Sơn), not Chiềng Đông (Yên Châu)
    ('Sơn La', 'Chiềng Mung'): '4111;4126;4123',   # 1681 item 45: Mường Bằng (Mai Sơn), not Mường Bang (Phù Yên)
    ('Sơn La', 'Chiềng Khương'): '4213;4222',   # 1681 item 51: Mường Sai (Sông Mã), not Mường Sại (Quỳnh Nhai)
    ('Tây Ninh', 'Mộc Hoá'): '27823;27820;27814',   # 1682 item 11: Tân Thành (Mộc Hoá), not Tân Thành (Tân Châu)
    ('Tây Ninh', 'Tân Thạnh'): '27853;27862;27847;27826',   # 1682 item 15: Tân Bình (Tân Thạnh), not Tân Bình (Tây Ninh)
    ('Tây Ninh', 'Thủ Thừa'): '28036;28063;28042;28057',   # 1682 item 20: Bình Thạnh (Thủ Thừa), not Bình Thạnh (Mộc Hoá)
    ('Tây Ninh', 'Đức Huệ'): '27919;27925;27916',   # 1682 item 26: Bình Thành (Đức Huệ), not Bình Thạnh (Mộc Hoá)
    ('Tây Ninh', 'Bến Lức'): '28012;28021;27991',   # 1682 item 37: Thanh Phú (Bến Lức), not Thạnh Phú (Thạnh Hoá)
    ('Tây Ninh', 'Kiến Tường'): '27787;27788;27806',   # 1682 item 83: Phường 1 (Kiến Tường), Phường 2 (Kiến Tường), not Phường 1 (Tây Ninh), Phường 2 (Tây Ninh)
    ('Tây Ninh', 'Long An'): '27694;27697;27691;27685;27700;27703;28063',   # 1682 item 84: Phường 4 (Tân An), not Phường 4 (Tây Ninh)
    ('Tây Ninh', 'Tân Ninh'): '25456;25468;25459;25462;25465;25597',   # 1682 item 87: the sheet left out Phường 4 (Tây Ninh)
    ('Tuyên Quang', 'Minh Xuân'): '2215;2216;2200;2203;2206;2488;2497',   # 1684 item 106: the sheet left out Trung Môn (Yên Sơn)
    ('TP HCM', 'Bàn Cờ'): '27160;27157;27154;27151;27148',   # 1685 item 5: Phường 5 (3), Phường 3 (3), Phường 2 (3), Phường 1 (3), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu), Phường 3 (Vũng Tàu), Phường 5 (Vũng Tàu)
    ('TP HCM', 'Nhiêu Lộc'): '27142;27133;27130;27127',   # 1685 item 7: Phường 12 (3), Phường 11 (3), Phường 9 (3), not Phường 9 (Vũng Tàu), Phường 11 (Vũng Tàu), Phường 12 (Vũng Tàu)
    ('TP HCM', 'Xóm Chiếu'): '27259;27289;27277;27295',   # 1685 item 8: Phường 13 (4), Phường 16 (4), not Phường 16 (Gò Vấp), Phường 13 (Bình Thạnh)
    ('TP HCM', 'Khánh Hội'): '27271;27265;27292;27283;27295',   # 1685 item 9: Phường 8 (4), Phường 2 (4), not Phường 2 (Vũng Tàu), Phường 8 (Vũng Tàu)
    ('TP HCM', 'Vĩnh Hội'): '27298;27286;27292;27283',   # 1685 item 10: Phường 2 (4), Phường 1 (4), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu)
    ('TP HCM', 'Chợ Quán'): '27325;27307;27301',   # 1685 item 11: Phường 2 (5), Phường 1 (5), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu)
    ('TP HCM', 'An Đông'): '27334;27316;27304',   # 1685 item 12: Phường 7 (5), Phường 5 (5), not Phường 5 (Vũng Tàu), Phường 7 (Vũng Tàu)
    ('TP HCM', 'Chợ Lớn'): '27328;27310;27343;27331',   # 1685 item 13: Phường 12 (5), Phường 11 (5), Phường 13 (5), not Phường 11 (Vũng Tàu), Phường 12 (Vũng Tàu), Phường 13 (Bình Thạnh)
    ('TP HCM', 'Bình Tây'): '27367;27352',   # 1685 item 14: Phường 2 (6), not Phường 2 (Vũng Tàu)
    ('TP HCM', 'Bình Tiên'): '27373;27382;27376',   # 1685 item 15: Phường 1 (6), Phường 7 (6), not Phường 1 (Vũng Tàu), Phường 7 (Vũng Tàu)
    ('TP HCM', 'Bình Phú'): '27385;27364;27430',   # 1685 item 16: Phường 10 (6), not Phường 10 (Vũng Tàu)
    ('TP HCM', 'Phú Lâm'): '27358;27349;27346',   # 1685 item 17: Phường 13 (6), Phường 12 (6), not Phường 12 (Vũng Tàu), Phường 13 (Bình Thạnh)
    ('TP HCM', 'Tân Hưng'): '27490;27481;27472;27475',   # 1685 item 21: Tân Quy (7), not Tân Quý (Tân Phú)
    ('TP HCM', 'Phú Định'): '27421;27427;27415;27430',   # 1685 item 23: Phường 14 (8), not Phường 14 (Gò Vấp)
    ('TP HCM', 'Diên Hồng'): '27202;27187;27169',   # 1685 item 25: Phường 6 (10), not Phường 6 (Gò Vấp)
    ('TP HCM', 'Vườn Lài'): '27184;27190;27193;27181;27178',   # 1685 item 26: Phường 9 (10), Phường 1 (10), Phường 2 (10), Phường 4 (10), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu), Phường 4 (Vũng Tàu), Phường 9 (Vũng Tàu)
    ('TP HCM', 'Hòa Hưng'): '27172;27166;27163;27169',   # 1685 item 27: Phường 13 (10), Phường 12 (10), not Phường 12 (Vũng Tàu), Phường 13 (Bình Thạnh)
    ('TP HCM', 'Minh Phụng'): '27247;27238;27253',   # 1685 item 28: Phường 7 (11), Phường 1 (11), not Phường 1 (Vũng Tàu), Phường 7 (Vũng Tàu)
    ('TP HCM', 'Bình Thới'): '27220;27232;27229',   # 1685 item 29: Phường 3 (11), not Phường 3 (Vũng Tàu)
    ('TP HCM', 'Hoà Bình'): '27211;27214',   # 1685 item 30: Phường 5 (11), not Phường 5 (Vũng Tàu)
    ('TP HCM', 'Phú Thọ'): '27226;27208;27229',   # 1685 item 31: Phường 11 (11), not Phường 11 (Vũng Tàu)
    ('TP HCM', 'Gia Định'): '26944;26941;26926;26950',   # 1685 item 42: Phường 7 (Bình Thạnh), Phường 2 (Bình Thạnh), Phường 1 (Bình Thạnh), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu), Phường 7 (Vũng Tàu)
    ('TP HCM', 'Bình Thạnh'): '26917;26929;26914',   # 1685 item 43: Phường 12 (Bình Thạnh), not Phường 12 (Vũng Tàu)
    ('TP HCM', 'Bình Lợi Trung'): '26923;26908;26905',   # 1685 item 44: Phường 11 (Bình Thạnh), Phường 5 (Bình Thạnh), not Phường 5 (Vũng Tàu), Phường 11 (Vũng Tàu)
    ('TP HCM', 'Hạnh Thông'): '26890;26902',   # 1685 item 47: Phường 1 (Gò Vấp), not Phường 1 (Vũng Tàu)
    ('TP HCM', 'An Nhơn'): '26887;26876',   # 1685 item 48: Phường 5 (Gò Vấp), not Phường 5 (Vũng Tàu)
    ('TP HCM', 'Gò Vấp'): '26884;26875',   # 1685 item 49: Phường 10 (Gò Vấp), not Phường 10 (Vũng Tàu)
    ('TP HCM', 'Thông Tây Hội'): '26898;26899',   # 1685 item 51: Phường 8 (Gò Vấp), not Phường 8 (Vũng Tàu)
    ('TP HCM', 'An Hội Tây'): '26881;26882',   # 1685 item 52: Phường 12 (Gò Vấp), not Phường 12 (Vũng Tàu)
    ('TP HCM', 'Đức Nhuận'): '27043;27046;27049',   # 1685 item 53: Phường 4 (Phú Nhuận), Phường 5 (Phú Nhuận), not Phường 4 (Vũng Tàu), Phường 5 (Vũng Tàu)
    ('TP HCM', 'Cầu Kiệu'): '27058;27061;27052',   # 1685 item 54: Phường 1 (Phú Nhuận), Phường 2 (Phú Nhuận), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu)
    ('TP HCM', 'Phú Nhuận'): '27064;27070;27073;27085',   # 1685 item 55: Phường 8 (Phú Nhuận), Phường 10 (Phú Nhuận), Phường 11 (Phú Nhuận), not Phường 8 (Vũng Tàu), Phường 10 (Vũng Tàu), Phường 11 (Vũng Tàu)
    ('TP HCM', 'Tân Sơn Hoà'): '26977;26965;26980',   # 1685 item 56: Phường 2 (Tân Bình), Phường 1 (Tân Bình), not Phường 1 (Vũng Tàu), Phường 2 (Vũng Tàu)
    ('TP HCM', 'Tân Sơn Nhất'): '26968;26989;26986',   # 1685 item 57: Phường 4 (Tân Bình), Phường 5 (Tân Bình), not Phường 4 (Vũng Tàu), Phường 5 (Vũng Tàu)
    ('TP HCM', 'Tân Hoà'): '26995;26998;27001',   # 1685 item 58: Phường 6 (Tân Bình), Phường 8 (Tân Bình), not Phường 8 (Vũng Tàu), Phường 6 (Gò Vấp)
    ('TP HCM', 'Bảy Hiền'): '26992;26983;26971',   # 1685 item 59: Phường 11 (Tân Bình), Phường 10 (Tân Bình), not Phường 10 (Vũng Tàu), Phường 11 (Vũng Tàu)
    ('TP HCM', 'Tân Bình'): '26974;27004;27007',   # 1685 item 60: Phường 13 (Tân Bình), not Phường 13 (Bình Thạnh)
    ('Thanh Hoá', 'Hoa Lộc'): '16057;16066;16069;16072;16075;16063',   # 1686 item 11: the sheet left out Hoà Lộc (Hậu Lộc)
    ('Thanh Hoá', 'Hồ Vương'): '16138;16141;16135;16159',   # 1686 item 15: Nga Thành (Nga Sơn), not Nga Thanh (Nga Sơn)
    ('Thanh Hoá', 'Hoằng Phú'): '15916;15889;15892;15883',   # 1686 item 25: Hoằng Quý (Hoằng Hoá), not Hoằng Quỳ (Hoằng Hoá)
    ('Thanh Hoá', 'Quảng Bình'): '16543;16546;16558;16468',   # 1686 item 31: Quảng Lộc (Quảng Xương), not Quang Lộc (Hậu Lộc)
    ('Thanh Hoá', 'Quảng Chính'): '16501;16489;16492;16495',   # 1686 item 33: Quảng Trung (Quảng Xương), not Quang Trung (Bỉm Sơn)
    ('Thanh Hoá', 'Trung Chính'): '16282;16285;16291;16288;16294;16297',   # 1686 item 36: Hoàng Sơn (Nông Cống), Hoàng Giang (Nông Cống), not Hoằng Giang (Hoằng Hoá), Hoằng Sơn (Hoằng Hoá)
    ('Thanh Hoá', 'Công Chính'): '16354;16375;16369;16273',   # 1686 item 40: Thanh Tân (Như Thanh), not Thành Tân (Thạch Thành)
    ('Thanh Hoá', 'Biện Thượng'): '15379;15382;15388;15391',   # 1686 item 63: Vĩnh Hùng (Vĩnh Lộc), not Vĩnh Hưng (Vĩnh Lộc)
    ('Thanh Hoá', 'Thanh Phong'): '16213;16219;16216',   # 1686 item 114: Thanh Lâm (Như Xuân), not Thành Lâm (Bá Thước)
    ('Thanh Hoá', 'Thanh Kỳ'): '16276;16273',   # 1686 item 120: Thanh Tân (Như Thanh), not Thành Tân (Thạch Thành)
    ('Thanh Hoá', 'Bỉm Sơn'): '14821;14815;14812;15277',   # 1686 item 136: Lam Sơn (Bỉm Sơn), Đông Sơn (Bỉm Sơn), not Lam Sơn (Thanh Hoá), Đông Sơn (Thanh Hoá)
    ('Thanh Hoá', 'Quang Trung'): '14809;14818;14823;14824',   # 1686 item 137: Ngọc Trạo (Bỉm Sơn), Phú Sơn (Bỉm Sơn), not Phú Sơn (Thanh Hoá), Ngọc Trạo (Thanh Hoá)
    ('Thanh Hoá', 'Trung Sơn'): '14875',   # 1686 closing: Trung Sơn (Quan Hoá), not Trung Sơn (Sầm Sơn)
    ('Vĩnh Long', 'Hoà Hiệp'): '29731;29734;29743',   # 1687 item 20: Hoà Lộc (Tam Bình), not Hoà Lộc (Mỏ Cày Bắc)
    ('Vĩnh Long', 'Tân Lược'): '29776;29782;29785',   # 1687 item 26: Tân Thành (Bình Tân), not Tân Thanh (Giồng Trôm)
    ('Vĩnh Long', 'Châu Thành'): '29374;29380;29383;29377',   # 1687 item 34: Châu Thành (Châu Thành), not Châu Thành (Châu Thành)
    ('Vĩnh Long', 'Hùng Hoà'): '29368;29362;29359',   # 1687 item 43: Tân Hùng (Tiểu Cần), not Tân Hưng (Ba Tri)
    ('Vĩnh Long', 'Thạnh Phú'): '29182;29200;29212;29233',   # 1687 item 77: Bình Thạnh (Thạnh Phú), not Bình Thành (Giồng Trôm)
    ('Vĩnh Long', 'Long Châu'): '29551;29542;29572',   # 1687 item 103: Phường 1 (Vĩnh Long), not Phường 1 (Trà Vinh)
    ('Vĩnh Long', 'Phước Hậu'): '29557;29554;29596',   # 1687 item 104: Phường 3 (Vĩnh Long), not Phường 3 (Trà Vinh)
    ('Vĩnh Long', 'Nguyệt Hoá'): '29254;29257;29395',   # 1687 item 112: Phường 7 (Trà Vinh), not Phường 7 (Bến Tre)
    ('Vĩnh Long', 'Long Hoà'): '29413',   # 1687 closing: Long Hoà (Châu Thành), not Long Hoà (Bình Đại)
}
NAME_FIXES = {'3244': 'Xá Nhè'}   # the old list already carries the new name for Xá Nhè (1661 item 20)


# --- folding: one key per spelling, whatever the tone placement or i/y habit -----------------

def syllable(tok):
    """'hoà' and 'hòa' -> ('hoa', 2); 'quý' and 'quí' -> ('qui', 1). 'thuý' keeps its y."""
    d = unicodedata.normalize('NFD', tok)
    tone = next((TONES.index(ch) + 1 for ch in d if ch in TONES), 0)
    base = unicodedata.normalize('NFC', ''.join(ch for ch in d if ch not in TONES))
    if len(base) > 1 and base.endswith('y') and (base[-2] not in VOWELS or base == 'quy'):
        base = base[:-1] + 'i'
    return base, tone


def key(name):
    s = PREFIX.sub('', unicodedata.normalize('NFC', name.strip().lower()))
    toks = re.sub(r'[-–—.,()]', ' ', re.sub(r"[’‘'`ʼ]", '', s)).split()
    if toks and toks[-1] in ROMAN:
        toks[-1] = ROMAN[toks[-1]]
    return tuple(syllable(t) for t in toks)


def loose(k):
    """Without any marks: Nà Hang and Na Hang meet here."""
    return tuple(unicodedata.normalize('NFD', b.replace('đ', 'd')).encode('ascii', 'ignore').decode() for b, _ in k)


def text(k):
    return ' '.join(f'{b}{t}' for b, t in k)


def squash(k):
    """Spacing in minority-language names drifts (A Vương, Avương; Ea Ly, Ealy): drop it.
    Numbers are dropped too; a number change is an affix, not a spelling."""
    return ''.join(b for b in loose(k) if not b.isdigit())


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


AFFIX = {key(w)[0] for w in ('bắc', 'nam', 'đông', 'tây', 'trung', 'thượng', 'hạ')}


def core(k):
    """Strip one direction word or number from each end, and a trailing A/B: Điện Bàn Bắc -> Điện Bàn,
    1 Bảo Lộc -> Bảo Lộc, Tân Thành A -> Tân Thành. A word is only stripped if two syllables remain,
    so Hà Nam stays Hà Nam."""
    k = list(k)
    for end in (0, -1):
        if len(k) > 1 and (k[end][0].isdigit() or (k[end] in AFFIX and len(k) > 2)
                           or (end == -1 and k[end][0] in ('a', 'b', 'c') and len(k) > 2)):
            k.pop(end)
    return tuple(k)


# --- the two witnesses -------------------------------------------------------------------------

def cover(ws, cands, every=False):
    """Each syllable's sources at the lowest level that bore it: Quế Phước rests on the communes
    Quế Lâm and Phước Ninh, not on the district Quế Sơn. A syllable no source bore is skipped.
    every=True keeps every level that bore it, for the `levels` column."""
    out = []
    for t in ws:
        has = [c for c in cands if t in c[1]]
        low = max((LEVELS.index(c[0]) for c in has), default=None)
        out += [c for c in has if (every or LEVELS.index(c[0]) == low) and c not in out]
    return out


def witness_a(nk, cands, nearby):
    """cands and nearby are (level, key, name). Returns (kind, the candidates it rests on)."""
    hit = [c for c in cands if c[1] == nk]
    if hit:
        return 'whole', hit
    digits = lambda k: [b for b, _ in k if b.isdigit()]
    same = [c for c in cands if digits(c[1]) == digits(nk)]
    hit = [c for c in same if squash(nk) and squash(c[1]) == squash(nk)]
    if hit:
        return 'variant', hit
    words = lambda k: tuple(t for i, t in enumerate(k) if not t[0].isdigit()        # drop numbers, and a
                            and not (i == len(k) - 1 > 1 and t[0] in ('a', 'b', 'c')))  # trailing A/B/C
    hit = [c for c in cands if core(nk) == core(c[1]) and core(nk) != nk or core(c[1]) != c[1] and core(c[1]) == nk
           or words(c[1]) == words(nk)                                              # Đông Hải <- Đông Hải 1, Đông Hưng A
           or len(nk) == 1 and len(c[1]) == 2 and nk[0] in c[1] and (set(c[1]) - set(nk)) <= AFFIX]  # Láng <- Láng Hạ
    if hit:
        return 'affix', hit
    runs = lambda k, n: {k[i:i + n] for i in range(len(k) - n + 1)}
    n = len(nk)       # a run of a longer name: Phan Rang from Phan Rang-Tháp Chàm
    hit = [c for c in cands if n > 1 and len(c[1]) > n and nk in runs(c[1], n)]
    if hit:
        return 'part', hit
    hit = [c for c in same if len(squash(nk)) >= 5 and lev(squash(nk), squash(c[1])) == 1]
    if hit:       # one letter: Châu Bình/Châu Bính is a correction, Tân Ninh/Tây Ninh is another name
        return 'near', hit
    hit = [c for c in cands if 1 < len(c[1]) < n and c[1] in runs(nk, len(c[1]))]
    ws = words(nk)
    if hit:       # a source kept whole in a longer name: Chân Mây - Lăng Cô, but also Chu Văn An
        return 'kept', hit + [c for c in cover([t for t in ws if not any(t in h[1] for h in hit)], cands)
                              if c not in hit]                       # Liên Sơn Lắk: Lắk is the district's
    parts = cover(ws, cands)    # syllables from sources in any order: Thư Vũ <- Vũ Thư, Tuyên Bình
    if len(ws) > 1 and all(any(t in c[1] for c in parts) for t in ws):
        return 'compound', parts
    hit = [c for c in nearby if c[1] == nk]
    if hit:
        return 'reused', hit
    return 'new', []


def witness_b(nk, cands):
    """Nearest source by edit distance on the folded name, and the share of it that must change."""
    t = text(nk)
    scored = [(lev(t, text(c[1])), c) for c in cands]
    if not scored:
        return [], 99, 1.0
    d = min(s for s, _ in scored)
    return [c for s, c in scored if s == d], d, d / max(len(t), 1)


def settle(kind, src, best, ratio):
    """Syllable matches settle themselves. A person sees what the rules cannot prove:
    a one-letter difference, a compound, and a 'new' name that B finds close to a source."""
    names = lambda cs: ' + '.join(sorted({c[2] for c in cs}))
    if kind == 'near':
        return 'check', f'one letter from {names(src)}: correction or another name?'
    if kind == 'compound':
        return 'check', f'built from {len(src)} names: coincidence or intent?'
    if kind == 'kept':
        return 'check', f'keeps {names(src)} and adds to it: intent or another name?'
    if kind == 'new' and ratio <= NEAR:
        return 'check', f'B finds {names(best)} close ({ratio:.2f})'
    return 'auto', ''


# --- data --------------------------------------------------------------------------------------

def split(s):
    return [c for c in s.split(';') if c]


def read(name):
    path = HERE / name
    return list(csv.DictReader(open(path, encoding='utf-8'))) if path.exists() else []


def write(name, rows, cols):
    with open(HERE / name, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def crosswalk(old, new):
    """Checks that could fail: every old commune lands somewhere, and every hand-typed code sits in
    a province the unit's machine-matched codes already come from. Returns flags and bad hand codes."""
    used, flags, bad = Counter(), [], set()
    for u in new:
        machine = split(u['old_codes'])
        provinces = {old[c]['province'] for c in machine if c in old}
        for c in machine + split(u['hand_codes']):
            used[c] += 1
            if c not in old:
                flags.append({'province': u['province'], 'name': u['name'], 'code': c, 'type': 'unknown code',
                              'flag': 'code not in the GSO list'})
        for c in split(u['hand_codes']):
            if c in old and provinces and old[c]['province'] not in provinces:
                bad.add((u['province'], u['name'], c))
                flags.append({'province': u['province'], 'name': u['name'], 'code': c, 'type': 'hand code elsewhere',
                              'flag': f"hand code is {old[c]['name']}, {old[c]['district']}, {old[c]['province']}; "
                                      f"the unit's other codes are in {', '.join(sorted(provinces))}"})
    for c, o in old.items():
        if not used[c]:
            flags.append({'province': o['province'], 'name': '', 'code': c, 'type': 'old unit unassigned',
                          'flag': f"{o['type']} {o['name']}, {o['district']} is in no new unit"})
    return flags, bad, sum(n > 1 for n in used.values())


def main():
    old = {r['code']: r for r in read('data/old_units.csv')}
    for c, nm in NAME_FIXES.items():
        old[c]['name'] = nm
    new = read('data/new_units.csv')
    for u in new:
        u['old_codes'] = CODE_FIXES.get((u['province'], u['name']), u['old_codes'])
    decided = {(d['province'], d['name']): d for d in read('decisions.csv')}
    flags, bad, shared = crosswalk(old, new)

    by_province = defaultdict(dict)
    for o in old.values():
        for lvl, nm in (('ward', o['name']), ('district', o['district'])):
            by_province[o['province']].setdefault((lvl, key(nm)), nm)

    rows = []
    for u in new:
        codes = [c for c in split(u['old_codes']) + split(u['hand_codes'])
                 if c in old and (u['province'], u['name'], c) not in bad]
        cands = {}
        for c in codes:
            o = old[c]
            for lvl, nm in (('ward', o['name']), ('district', o['district']), ('province', o['province'])):
                cands.setdefault((lvl, key(nm)), nm)
        for nm in u['sources_text'].split(','):   # island districts kept whole: "Huyện Côn Đảo"
            if re.match(r'\s*huyện\s', nm, re.I):
                cands[('district', key(nm))] = nm.strip()
        cands = [(lvl, k, nm) for (lvl, k), nm in cands.items()]
        nearby = [(lvl, k, nm) for p in {old[c]['province'] for c in codes}
                  for (lvl, k), nm in by_province[p].items() if (lvl, k, nm) not in cands]

        nk = key(u['name'])
        kind, src = witness_a(nk, cands, nearby)
        best, d, ratio = witness_b(nk, cands)
        status, reason = settle(kind, src, best, ratio)
        levels = {c[0] for c in src}
        origin = next((lvl for lvl in LEVELS if lvl in levels), '')
        if kind == 'compound':      # a higher unit may bear a syllable too: Quế Sơn for Quế Phước
            levels |= {c[0] for c in cover(nk, cands, every=True)}
        row = {'province': u['province'], 'name': u['name'], 'kind': kind, 'origin': origin,
               'sources': ' + '.join(sorted({f'{c[2]} ({c[0]})' for c in src})),
               'levels': '+'.join(lvl for lvl in LEVELS if lvl in levels),
               'b_nearest': ' + '.join(sorted({c[2] for c in best})), 'b_distance': d,
               'status': status, 'reason': reason, 'decided_by': ''}
        if (u['province'], u['name']) in decided:
            dec = decided[(u['province'], u['name'])]
            row.update(kind=dec['kind'], origin=dec['origin'], status='decided', decided_by=f"{dec['by']} {dec['date']}")
        row['family'] = FAMILY[row['kind']]
        rows.append(row)

    cols = ['province', 'name', 'family', 'kind', 'origin', 'levels', 'sources', 'b_nearest', 'b_distance',
            'status', 'reason', 'decided_by']
    write('out/names.csv', rows, cols)
    write('out/queue.csv', [r for r in rows if r['status'] == 'check'], cols)
    write('out/crosswalk_flags.csv', flags, ['type', 'province', 'name', 'code', 'flag'])

    n = len(rows)
    pct = lambda c: f'{c:>5} ({100 * c / n:4.1f} %)'
    print(f'Crosswalk: {n} new units, {len(old)} old units, {shared} old units shared by two or more new ones')
    for t, c in Counter(f['type'] for f in flags).most_common():
        print(f'  flag  {c:>4}  {t}')
    print('\nKind (witness A, after decisions):')
    for k, c in Counter(r['kind'] for r in rows).most_common():
        print(f'  {k:<9}{pct(c)}')
    print('\nFamily    this run          article')
    fam = Counter(r['family'] for r in rows)
    for f in ('whole', 'partial', 'new'):
        print(f'  {f:<8}{pct(fam[f])}   {ARTICLE[f]:>5}')
    print('\nOrigin of kept names:', dict(Counter(r['origin'] for r in rows if r['family'] != 'new')))
    print('Kept names more than one level could explain:',
          sum('+' in r['levels'] for r in rows if r['family'] != 'new'))
    print('Status:', dict(Counter(r['status'] for r in rows)))
    print('Queue by kind:', dict(Counter(r['kind'] for r in rows if r['status'] == 'check')))


def selftest():
    assert key('Hoà Tú') == key('Hòa Tú') and key('Phú Quí') == key('Phú Quý')
    assert key('Thuý') != key('Thúi') and key('Xã Bờ Y') == key('Bờ Y')
    assert key('Hoà Tú II') == key('Hoà Tú 2') and key("Cư M'gar") == key('Cư M’gar')
    assert lev('kitten', 'sitting') == 3
    c = lambda *ns: [('ward', key(n), n) for n in ns]
    a = lambda name, *ns: witness_a(key(name), c(*ns), [])[0]
    assert a('Thành Bình Thọ', 'Thành Sơn', 'Bình Sơn', 'Thọ Sơn') == 'compound'
    assert a('Hội An Tây', 'Hội An', 'Cẩm Phô') == 'affix'
    assert a('Thường Phước', 'Thường Phước 1', 'Thường Phước 2') == 'affix'
    assert a('Nà Hang', 'Na Hang') == 'variant' and a('Avương', 'A Vương') == 'variant'
    assert a('Phan Rang', 'Phan Rang-Tháp Chàm') == 'part' and a('Hiệp Bình', 'Hiệp Bình Chánh') == 'part'
    assert a('Láng', 'Láng Thượng', 'Láng Hạ') == 'affix' and a('Đông Hải', 'Đông Hải 1', 'Nam Hải') == 'affix' == a('Đông Hưng', 'Đông Hưng A')
    assert a('Chân Mây - Lăng Cô', 'Lăng Cô', 'Lộc Tiến') == 'kept'
    k, src = witness_a(key('Quế Phước'), c('Quế Lâm', 'Phước Ninh') + [('district', key('Quế Sơn'), 'Quế Sơn')], [])
    assert k == 'compound' and {s[0] for s in src} == {'ward'}
    assert {s[0] for s in cover(key('Quế Phước'), c('Quế Lâm') + [('district', key('Quế Sơn'), 'Quế Sơn')], every=True)} \
        == {'ward', 'district'}
    assert {s[0] for s in witness_a(key('Liên Sơn Lắk'), c('Liên Sơn') + [('district', key('Lắk'), 'Lắk')], [])[1]} \
        == {'ward', 'district'}
    assert a('Thư Vũ', 'Vũ Thư') == 'compound' and a('Tân Khánh', 'Tân Phước Khánh') == 'compound'
    assert a('Chợ Lớn', '11', '12', '13') == 'new'
    assert a('Hà Nam', 'Hà') == 'new'
    assert witness_a(key('Tân An'), [], [('district', key('Tân An'), 'Tân An')])[0] == 'reused'
    assert a('Tân Thành', 'Tân Thành A') == 'affix' and a('Tân Ninh', 'Tây Ninh') == 'near'
    assert settle('near', c('Tây Ninh'), c('Tây Ninh'), 0.1)[0] == 'check'
    assert settle('new', [], c('Tân Anh'), 0.1)[0] == 'check'
    print('ok')


if __name__ == '__main__':
    selftest() if '--check' in sys.argv else main()
