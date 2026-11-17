"""Strict snapshot comparison with one reviewed PostgreSQL representation exception.

Only public diagnostic_sessions.ck_diagnostic_status may use either exact SQL
string below. These expressions have identical text[] values, types and NULL
semantics, verified against the retained Stage 13 restore. This is not a SQL
normalizer: unknown spellings, casts, values, names, tables and other fields fail
the ordinary strict comparison. Inputs and original evidence are never mutated.
"""
from copy import deepcopy

ARRAY_CAST = "status::text = ANY (ARRAY['in_progress'::character varying, 'completed'::character varying, 'abandoned'::character varying]::text[])"
ELEMENT_CASTS = "status::text = ANY (ARRAY['in_progress'::character varying::text, 'completed'::character varying::text, 'abandoned'::character varying::text])"


def _comparison_copy(snapshot):
    result = deepcopy(snapshot)
    if not isinstance(result, dict):
        return result
    schema = result.get('schema')
    table = schema.get('diagnostic_sessions') if isinstance(schema, dict) else None
    constraints = table.get('check_constraints') if isinstance(table, dict) else None
    if isinstance(constraints, list):
        for constraint in constraints:
            if (isinstance(constraint, dict)
                    and constraint.get('name') == 'ck_diagnostic_status'
                    and constraint.get('sqltext') in (ARRAY_CAST, ELEMENT_CASTS)):
                constraint['sqltext'] = ARRAY_CAST
    return result


def snapshot_differences(before, restored):
    """Return every unequal JSON path, accepting only the reviewed exception."""
    left, right = _comparison_copy(before), _comparison_copy(restored)
    differences = []

    def compare(a, b, path):
        if type(a) is not type(b):
            differences.append({'path': path, 'before': a, 'restored': b})
        elif isinstance(a, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    differences.append({'path': path + '.' + key,
                                        'before': a.get(key), 'restored': b.get(key),
                                        'before_present': key in a, 'restored_present': key in b})
                else:
                    compare(a[key], b[key], path + '.' + key)
        elif isinstance(a, list):
            if len(a) != len(b):
                differences.append({'path': path + '.length', 'before': len(a), 'restored': len(b)})
            for index in range(min(len(a), len(b))):
                compare(a[index], b[index], f'{path}[{index}]')
        elif a != b:
            differences.append({'path': path, 'before': a, 'restored': b})

    compare(left, right, '$')
    return differences


def snapshots_equal(before, restored):
    return not snapshot_differences(before, restored)
