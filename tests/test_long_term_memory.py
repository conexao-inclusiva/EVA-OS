# -*- coding: utf-8 -*-
"""Test suite verifying long-term memory fact extraction, storage, relational
memory confirmation logic, and family relationship graph capabilities.
"""

import asyncio
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from src.memory.fact_learning import extract as extract_fact, question as question_fact
from src.memory.long_term_memory import LongTermMemory
from src.memory.relational_memory import RelationalMemory
from src.memory.shared_family import SharedFamily
from src.memory.family_relations import FamilyRelations
from src.memory import family_query


class TestLongTermMemoryAndRelations(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        
        # Setup databases
        self.long_term_db = self.tmp_path / "eva_long_term.db"
        self.relational_db = self.tmp_path / "eva_relational.db"
        self.family_db = self.tmp_path / "eva_family_relations.db"
        
        # Initialize an empty SQLite file for family relations so SharedFamily succeeds
        self.family_db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(self.family_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS family_people (
                person_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS family_shared_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                object_id TEXT NOT NULL,
                informed_by TEXT NOT NULL,
                confirmed INTEGER NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_fact_learning_extraction(self):
        # Test explicit fact extraction
        extracted = extract_fact("Meu carro atual é um Chevrolet Meriva 2004")
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["subject"], "veiculo")
        self.assertEqual(extracted["relation"], "carro_atual")
        self.assertEqual(extracted["object"], "Chevrolet Meriva 2004")

        # Test speculative / questioning phrases returning None
        self.assertIsNone(extract_fact("Talvez meu carro seja um Meriva"))
        self.assertIsNone(extract_fact("Qual é o meu carro atual?"))

        # Test question generator helper
        q_result = question_fact("Qual é meu carro atual?")
        self.assertEqual(q_result[0], "veiculo")
        self.assertEqual(q_result[1], "carro_atual")

    def test_long_term_memory_storage(self):
        event_bus = Mock()
        logger = Mock()
        config = Mock()
        config.get.return_value = str(self.long_term_db)

        ltm = LongTermMemory(event_bus, logger, config)
        
        # Store a fact
        ltm.store_fact("admin", "veiculo", "carro_atual", "Chevrolet Meriva 2004", source="ensinado_geral_explicitamente")
        
        # Retrieve facts
        facts = ltm.get_all_facts("admin")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["object"], "Chevrolet Meriva 2004")
        self.assertEqual(facts[0]["relation"], "carro_atual")

    def test_relational_memory_confirmation_logic(self):
        rm = RelationalMemory(self.relational_db)
        
        # Propose and save new single-value relation
        self.assertEqual(rm.propose("admin", "meriva", "motor", "1.8"), "new")
        self.assertEqual(rm.save_confirmed("admin", "meriva", "motor", "1.8"), "saved")
        
        # Propose update (should require confirmation for SINGLE relations)
        self.assertEqual(rm.propose("admin", "meriva", "motor", "2.0"), "needs_confirmation")
        self.assertEqual(rm.save_confirmed("admin", "meriva", "motor", "2.0"), "needs_confirmation")
        
        # Verify old value is still active before confirmation with expected_previous
        active = rm.active("admin", "meriva", "motor")
        self.assertEqual(active[0]["object"], "1.8")
        
        # Save with expected_previous confirmation
        self.assertEqual(rm.save_confirmed("admin", "meriva", "motor", "2.0", expected_previous=["1.8"]), "saved")
        
        # Verify new value is active and history length is 2
        active_new = rm.active("admin", "meriva", "motor")
        self.assertEqual(active_new[0]["object"], "2.0")
        self.assertEqual(len(rm.history("admin", "meriva", "motor")), 2)

    def test_family_relationship_graph_capabilities(self):
        # Populate family db with shared people and relations
        sf = SharedFamily(self.family_db)
        sf.add_person("alberto", "Alberto")
        sf.add_person("juliana", "Juliana")
        sf.add_person("nicolas", "Nicolas")
        sf.add_person("liris", "Liris")

        # Spousal connection (conjuge)
        sf.add_relation("alberto", "conjuge", "juliana", "alberto", confirmed=True)
        
        # Parentage connections (pai, mae)
        sf.add_relation("nicolas", "pai", "alberto", "alberto", confirmed=True)
        sf.add_relation("nicolas", "mae", "juliana", "alberto", confirmed=True)
        sf.add_relation("liris", "pai", "alberto", "alberto", confirmed=True)
        sf.add_relation("liris", "mae", "juliana", "alberto", confirmed=True)

        # Confirm relational queries via family_query
        spouse_answer = family_query.family_answer("Quem é minha esposa?", "alberto", sf)
        self.assertIsNotNone(spouse_answer)
        self.assertIn("Juliana", spouse_answer)

        parents_answer = family_query.family_answer("Quem são os pais do Nicolas?", "alberto", sf)
        self.assertIsNotNone(parents_answer)
        self.assertIn("Alberto", parents_answer)
        self.assertIn("Juliana", parents_answer)

        children_answer = family_query.family_answer("Quem são meus filhos?", "alberto", sf)
        self.assertIsNotNone(children_answer)
        self.assertIn("Nicolas", children_answer)
        self.assertIn("Liris", children_answer)


if __name__ == "__main__":
    unittest.main()
