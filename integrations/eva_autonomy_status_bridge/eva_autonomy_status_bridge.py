"""EVA OS - read-only supervision status interface (stage 30).

Never imports, evaluates or runs generated candidate code. This is a standalone
integration seam, deliberately NOT registered in boot.py or plugin_manager.py.
"""
import argparse
import hashlib
import json
from pathlib import Path

MISSION = '6e7ad60703972c4f462b0e4e9ae3c0df'
FUNCTION = 'detect_learning_gaps'
EXPECTED_TESTS = 24
RECEIPT_NAME = 'stage30_receipt.json'
INDEX_REL = Path('sandbox_runs/latest_autonomy_29.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def within(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    return path == root or root in path.parents


def safe_read(path, root, limit=128000):
    path, root = Path(path), Path(root)
    if not within(path, root) or path.is_symlink() or not path.is_file():
        raise ValueError('unsafe_path:' + path.name)
    if path.stat().st_size > limit:
        raise ValueError('oversized_file:' + path.name)
    return path.read_bytes()


def safe_json(path, root, limit=128000):
    return json.loads(safe_read(path, root, limit).decode('utf-8-sig'))


def validate_receipt(receipt, lab):
    """Read the exact evidence from the lab without importing candidate code."""
    lab = Path(lab)
    if lab.is_symlink() or not lab.is_dir():
        raise ValueError('invalid_lab_root')
    if type(receipt) is not dict or receipt.get('schema') != 1:
        raise ValueError('invalid_receipt_schema')
    if (receipt.get('mission_id') != MISSION
            or receipt.get('function') != FUNCTION
            or receipt.get('sandbox_status') != 'APPROVED_IN_SANDBOX'
            or receipt.get('tests_expected') != EXPECTED_TESTS
            or receipt.get('production_registration_allowed') is not False
            or receipt.get('host_execution_allowed') is not False
            or receipt.get('human_approval_required') is not True):
        raise ValueError('invalid_receipt_policy')
    if type(receipt.get('tests_expected')) is not int:
        raise ValueError('invalid_test_count')
    for key in ('candidate_sha256', 'report_sha256', 'index_sha256'):
        val = receipt.get(key)
        if type(val) is not str or len(val) != 64 or any(c not in '0123456789abcdef' for c in val):
            raise ValueError('invalid_digest:' + key)
    idx_raw = safe_read(lab / INDEX_REL, lab)
    if digest(idx_raw) != receipt['index_sha256']:
        raise ValueError('index_changed')
    idx = json.loads(idx_raw.decode('utf-8-sig'))
    if (idx.get('mission_id') != MISSION or idx.get('function_name') != FUNCTION
            or idx.get('tests_expected') != EXPECTED_TESTS
            or idx.get('production_registration_allowed') is not False
            or idx.get('source_sha256') != receipt['candidate_sha256']):
        raise ValueError('invalid_index')
    run_root = Path(idx.get('root', ''))
    candidate_root = Path(idx.get('candidate_dir', ''))
    if (run_root.is_symlink() or candidate_root.is_symlink()
            or not within(run_root, lab / 'sandbox_runs')
            or not within(candidate_root, lab / 'generated_candidates')):
        raise ValueError('escaped_run_path')
    if (Path(idx.get('sandbox_file', '')).resolve() !=
            (run_root / 'EVA_autonomy_29.wsb').resolve()):
        raise ValueError('wrong_sandbox_file')
    code = safe_read(candidate_root / 'skill_candidate.py', lab)
    if digest(code) != receipt['candidate_sha256']:
        raise ValueError('candidate_changed')
    if safe_read(run_root / 'input' / 'skill_candidate.py', lab) != code:
        raise ValueError('sandbox_input_changed')
    manifest = safe_json(candidate_root / 'manifest.json', lab)
    if (manifest.get('mission_id') != MISSION
            or manifest.get('required_function') != FUNCTION
            or manifest.get('source_sha256') != receipt['candidate_sha256']
            or manifest.get('host_execution') is not False
            or manifest.get('production_registration_allowed') is not False):
        raise ValueError('manifest_invalid')
    raw_report = safe_read(run_root / 'output' / 'sandbox_report.json', lab)
    if digest(raw_report) != receipt['report_sha256']:
        raise ValueError('sandbox_report_changed')
    report = json.loads(raw_report.decode('utf-8-sig'))
    tests = report.get('tests')
    if (report.get('mission_id') != MISSION
            or report.get('source_sha256') != receipt['candidate_sha256']
            or report.get('environment') != 'Windows Sandbox'
            or report.get('status') != 'APPROVED_IN_SANDBOX'
            or report.get('production_registration_allowed') is not False
            or type(report.get('tests_total')) is not int
            or report['tests_total'] != EXPECTED_TESTS
            or type(report.get('tests_passed')) is not int
            or report['tests_passed'] != EXPECTED_TESTS
            or type(tests) is not list or len(tests) != EXPECTED_TESTS
            or any(type(x) is not dict or type(x.get('name')) is not str or
                   x.get('passed') is not True for x in tests)
            or len(set(x['name'] for x in tests)) != EXPECTED_TESTS
            or report.get('errors') != []):
        raise ValueError('sandbox_not_validated')
    return {'status': 'SANDBOX_APPROVED_REVIEW_REQUIRED',
            'mission_id': MISSION, 'function': FUNCTION,
            'sandbox_tests_passed': EXPECTED_TESTS,
            'candidate_sha256': receipt['candidate_sha256'],
            'execution_allowed': False, 'production_registration_allowed': False,
            'human_approval_required': True, 'source': 'verified_lab_evidence'}


def read_status(installation_directory=None):
    folder = Path(installation_directory or Path(__file__).resolve().parent)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('invalid_bridge_directory')
    receipt = safe_json(folder / RECEIPT_NAME, folder)
    lab = receipt.get('lab')
    if type(lab) is not str or not lab:
        raise ValueError('invalid_lab_reference')
    return validate_receipt(receipt, Path(lab))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = read_status()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        result = {'status': 'EVIDENCE_INVALID', 'error': str(exc)[:180],
                  'execution_allowed': False, 'production_registration_allowed': False}
        print(json.dumps(result, sort_keys=True, ensure_ascii=True))
        return 3
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
