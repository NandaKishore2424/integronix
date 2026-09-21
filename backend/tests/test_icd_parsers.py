"""
Billability must come from the ICD-10-CM release file, not be inferred.

The importer used to discard the order file's header flag and derive
billability from the tabular XML hierarchy. The XML does not list codes built
from 7th characters, so ~51,000 real leaves were never marked billable, and
~12,900 parents such as E11.331 were — which let a parent be proposed for a
claim. These pin the source of truth.
"""
from services.icd_parsers import parse_icd_txt


def _order_line(order: int, code: str, billable: bool, short: str, long: str) -> str:
    # icd10cm_order_*.txt: order(5) sp code(7) sp flag(1) sp short(60) sp long
    return f"{order:05d} {code:<7} {'1' if billable else '0'} {short:<60} {long}"


def test_order_file_header_flag_decides_billability(tmp_path):
    f = tmp_path / "icd10cm_order_2026.txt"
    f.write_text("\n".join([
        _order_line(1, "E11331", False,
                    "Type 2 diab w moderate nonprolif diabetic rtnop w macular edema",
                    "Type 2 diabetes mellitus with moderate nonproliferative diabetic retinopathy with macular edema"),
        _order_line(2, "E113311", True,
                    "Type 2 diab w mod nonp rtnop with macular edema, right eye",
                    "Type 2 diabetes mellitus with moderate nonproliferative diabetic retinopathy with macular edema, right eye"),
        _order_line(3, "S72001A", True,
                    "Fx unsp part of neck of right femur, init",
                    "Fracture of unspecified part of neck of right femur, initial encounter for closed fracture"),
    ]) + "\n")

    rows = {r.code: r for r in parse_icd_txt(str(f))}

    assert rows["E11.331"].is_billable is False, "a header with children is never billable"
    assert rows["E11.3311"].is_billable is True
    assert rows["S72.001A"].is_billable is True, "7th-character codes are billable leaves"
    assert rows["E11.3311"].description.endswith("right eye"), "the long description is used"


def test_codes_file_lists_only_billable_codes(tmp_path):
    f = tmp_path / "icd10cm_codes_2026.txt"
    f.write_text("J189    Pneumonia, unspecified organism\nE1122   Type 2 diabetes mellitus with diabetic chronic kidney disease\n")

    rows = {r.code: r for r in parse_icd_txt(str(f))}

    assert rows["J18.9"].is_billable is True
    assert rows["E11.22"].is_billable is True
