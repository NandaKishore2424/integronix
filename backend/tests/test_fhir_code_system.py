"""
The FHIR coding system must describe where a code came from.

An organisation can prefer ICD-11, but without WHO API credentials the
pipeline codes from the local ICD-10-CM tables. Both FHIR builders labelled
those ICD-10-CM codes (E11.22 …) as ICD-11 because they read the
organisation's preference instead of the path that produced the code.
"""
import pytest

from routes.code import _fhir_icd_system_for_state
from services.fhir_claim_builder import _icd_system_for

ICD10CM = "http://hl7.org/fhir/sid/icd-10-cm"


@pytest.mark.parametrize("mapping_path", ["embedding", "direct", "provider_fallback", "no_mapping", None])
def test_local_paths_are_icd10cm_even_when_the_org_prefers_icd11(mapping_path):
    assert _fhir_icd_system_for_state("ICD-11", mapping_path)[0] == ICD10CM
    assert _icd_system_for("ICD-11", mapping_path) == ICD10CM


def test_the_who_icd11_path_is_labelled_icd11():
    system, version = _fhir_icd_system_for_state("ICD-11", "who_api_icd11")
    assert "icd11" in system and version == "ICD-11"
    assert "icd/release/11" in _icd_system_for("ICD-10-CM", "who_api_icd11")
