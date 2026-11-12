import tempfile
from pathlib import Path
from src.memory.relational_memory import RelationalMemory

with tempfile.TemporaryDirectory() as temp:
    mem = RelationalMemory(Path(temp) / 'test.db')
    assert mem.propose('admin', 'meriva', 'motor', '1.8') == 'new'
    assert mem.save_confirmed('admin', 'meriva', 'motor', '1.8') == 'saved'
    assert mem.propose('admin', 'meriva', 'motor', '2.0') == 'needs_confirmation'
    assert mem.save_confirmed('admin', 'meriva', 'motor', '2.0') == 'needs_confirmation'
    assert mem.active('admin', 'meriva', 'motor')[0]['object'] == '1.8'
    assert mem.save_confirmed('admin', 'meriva', 'motor', '2.0', expected_previous=['1.8']) == 'saved'
    assert mem.active('admin', 'meriva', 'motor')[0]['object'] == '2.0'
    assert len(mem.history('admin', 'meriva', 'motor')) == 2
    assert mem.save_confirmed('admin', 'alberto', 'possui', 'meriva') == 'saved'
    assert mem.save_confirmed('admin', 'alberto', 'possui', 'corsa') == 'saved'
    assert len(mem.active('admin', 'alberto', 'possui')) == 2
    assert not mem.active('outro_usuario', 'alberto', 'possui')
    assert mem.save_confirmed('admin', 'meriva', 'motor', '2.0') == 'already_known'
    mem2 = RelationalMemory(Path(temp) / 'test.db')
    assert mem2.active('admin', 'meriva', 'motor')[0]['object'] == '2.0'
print('8 cenarios validados: confirmacao, historico, multiplos valores, isolamento e persistencia.')

