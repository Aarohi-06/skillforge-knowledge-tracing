"""Pure unittest suite: no conftest, database fixtures or database connections."""
from copy import deepcopy
import unittest
from backup_comparison import ARRAY_CAST, ELEMENT_CASTS, snapshot_differences, snapshots_equal


def sample(sql=ARRAY_CAST):
    return {'schema': {'diagnostic_sessions': {'check_constraints': [
        {'name': 'ck_diagnostic_status', 'sqltext': sql, 'validated': True}],
        'columns': [{'name': 'status', 'nullable': False}],
        'primary_key': {'constrained_columns': ['id']},
        'foreign_keys': [{'referred_table': 'students'}],
        'indexes': [{'name': 'uq_diagnostic_active_student', 'unique': True}]}},
        'tables': {'attempts': {'count': 11, 'hash': 'original-hash', 'rows': ['original-row']}},
        'revision': '0005_diagnostic_sessions',
        'sequences': {'attempts_id_seq': {'last_value': 11, 'is_called': True}}}


class BackupComparisonTests(unittest.TestCase):
    def test_only_known_representations_equal_in_both_directions(self):
        for a in (ARRAY_CAST, ELEMENT_CASTS):
            for b in (ARRAY_CAST, ELEMENT_CASTS):
                self.assertTrue(snapshots_equal(sample(a), sample(b)))

    def test_inputs_are_not_modified(self):
        a, b = sample(), sample(ELEMENT_CASTS)
        originals = deepcopy((a, b))
        snapshots_equal(a, b)
        self.assertEqual((a, b), originals)

    def test_allowed_status_changes_are_rejected(self):
        for sql in (ELEMENT_CASTS.replace('abandoned', 'expired'),
                    ELEMENT_CASTS.replace('completed', 'COMPLETED'),
                    ELEMENT_CASTS.replace("'abandoned'::character varying::text", "NULL::text")):
            self.assertFalse(snapshots_equal(sample(), sample(sql)))

    def test_other_sql_changes_are_rejected(self):
        for sql in (ELEMENT_CASTS + ' OR TRUE', ELEMENT_CASTS.replace(' = ANY', ' <> ALL'),
                    ELEMENT_CASTS.replace('status::text', 'other_column::text'),
                    ELEMENT_CASTS.replace('character varying::text', 'character varying::citext')):
            self.assertFalse(snapshots_equal(sample(), sample(sql)))

    def test_constraint_rename_and_renamed_pair_are_rejected(self):
        a, b = sample(), sample(ELEMENT_CASTS)
        b['schema']['diagnostic_sessions']['check_constraints'][0]['name'] = 'other_status'
        self.assertFalse(snapshots_equal(a, b))
        a['schema']['diagnostic_sessions']['check_constraints'][0]['name'] = 'other_status'
        self.assertFalse(snapshots_equal(a, b))

    def test_no_normalization_in_other_tables(self):
        a, b = sample(), sample(ELEMENT_CASTS)
        for value in (a, b):
            value['schema']['other_table'] = value['schema'].pop('diagnostic_sessions')
        self.assertFalse(snapshots_equal(a, b))

    def test_all_other_evidence_is_strict(self):
        paths = [
            ('schema', 'diagnostic_sessions', 'columns', 0, 'nullable'),
            ('schema', 'diagnostic_sessions', 'primary_key', 'constrained_columns'),
            ('schema', 'diagnostic_sessions', 'foreign_keys', 0, 'referred_table'),
            ('schema', 'diagnostic_sessions', 'indexes', 0, 'unique'),
            ('schema', 'diagnostic_sessions', 'check_constraints', 0, 'validated'),
            ('tables', 'attempts', 'count'), ('tables', 'attempts', 'hash'),
            ('tables', 'attempts', 'rows'), ('revision',),
            ('sequences', 'attempts_id_seq', 'last_value'),
            ('sequences', 'attempts_id_seq', 'is_called'),
        ]
        for path in paths:
            with self.subTest(path=path):
                a, b = sample(), sample(ELEMENT_CASTS)
                parent = b
                for key in path[:-1]: parent = parent[key]
                parent[path[-1]] = 'unrelated change'
                self.assertFalse(snapshots_equal(a, b))

    def test_order_missing_fields_and_json_types_remain_strict(self):
        a, b = sample(), sample(ELEMENT_CASTS)
        b['tables']['attempts']['count'] = True
        a['tables']['attempts']['count'] = 1
        self.assertFalse(snapshots_equal(a, b))
        a, b = sample(), sample(ELEMENT_CASTS)
        b['schema']['diagnostic_sessions']['columns'].append({'name': 'unexpected'})
        self.assertFalse(snapshots_equal(a, b))
        a, b = sample(), sample(ELEMENT_CASTS)
        del b['revision']
        self.assertFalse(snapshots_equal(a, b))
        a, b = sample(), sample(ELEMENT_CASTS)
        a['tables']['attempts']['rows'] = ['a', 'b']
        b['tables']['attempts']['rows'] = ['b', 'a']
        self.assertFalse(snapshots_equal(a, b))

    def test_actionable_difference_paths(self):
        a, b = sample(), sample(ELEMENT_CASTS)
        b['tables']['attempts']['hash'] = 'changed'
        self.assertEqual(snapshot_differences(a, b), [
            {'path': '$.tables.attempts.hash', 'before': 'original-hash', 'restored': 'changed'}])


if __name__ == '__main__':
    unittest.main()
