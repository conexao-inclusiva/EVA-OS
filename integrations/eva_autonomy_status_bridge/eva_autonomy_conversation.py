"""EVA-OS: conversational, read-only status route.

Only the already-installed, trusted status bridge is imported. Never imports
or runs generated skill_candidate.py. No changes to lab or approvals.
"""
import asyncio
import unicodedata

from .eva_autonomy_status_bridge import read_status


def _normalize(text):
    if not isinstance(text, str):
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text.casefold())
        if not unicodedata.combining(c)
    )


def is_autonomy_status_question(text):
    """Deliberately narrow, deterministic intent detector."""
    t = ' '.join(_normalize(text).split())
    if not t or len(t) > 500:
        return False
    return any(phrase in t for phrase in (
        'autoevoluc', 'auto evoluc', 'autoprogram', 'auto program',
        'sua evolucao', 'seu desenvolvimento',
        'status da eva', 'status de desenvolvimento da eva',
        'habilidade que voce desenvolveu', 'habilidades que voce desenvolveu',
        'seus modulos novos', 'sua capacidade de evoluir',
        'como esta evoluindo, eva', 'como voce esta evoluindo',
    ))


async def answer_if_status_question(text):
    """Return None for unrelated queries; otherwise a grounded PT-BR answer."""
    if not is_autonomy_status_question(text):
        return None
    try:
        status = await asyncio.wait_for(asyncio.to_thread(read_status), timeout=6)
        if (type(status) is not dict
                or status.get('status') != 'SANDBOX_APPROVED_REVIEW_REQUIRED'
                or status.get('execution_allowed') is not False
                or status.get('production_registration_allowed') is not False
                or status.get('human_approval_required') is not True
                or status.get('function') != 'detect_learning_gaps'
                or type(status.get('sandbox_tests_passed')) is not int
                or status.get('sandbox_tests_passed') != 24):
            raise ValueError('unexpected_evidence_status')
    except Exception:
        return ('Nao consegui verificar agora o estado da minha autoevolucao. '
                'Por seguranca, nao vou afirmar que uma habilidade foi aprovada '
                'sem conferir as evidencias do laboratorio.')
    return (
        'Minha autoevolucao esta em fase supervisionada. '
        'Desenvolvi a habilidade detect_learning_gaps, que passou em '
        f"{status['sandbox_tests_passed']} de 24 testes no Windows Sandbox. "
        'O codigo ainda aguarda revisao e aprovacao humana: nao esta '
        'autorizado para execucao nem registrado como modulo ativo da EVA. '
        f"Identificador da missao: {status['mission_id']}."
    )
