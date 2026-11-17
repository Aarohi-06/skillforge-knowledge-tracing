import json
import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import inspect, text

from test_migrations import migration_engine, config, IDEMPOTENCY
from verify_schema import schema_differences

REVISION = '0004_question_bank'
MANIFEST = json.loads((Path(__file__).parent / 'migrations/data/0004_legacy_questions.json').read_text(encoding='utf-8'))['questions']


def populate(connection, duplicate=False, altered=False):
    concept_ids = {name: 501 + index * 3 for index, name in enumerate(sorted({item['concept'] for item in MANIFEST}))}
    for name, concept_id in concept_ids.items():
        connection.execute(text('INSERT INTO concepts(id,name) VALUES (:id,:name)'), {'id':concept_id,'name':name})
    for index, item in enumerate(MANIFEST):
        # Deliberately unrelated IDs and insertion order prove mapping is not positional.
        connection.execute(text('''INSERT INTO questions(id,concept_id,title,description,difficulty,options,correct_answer)
            VALUES (:id,:concept_id,:title,:description,:difficulty,:options,:correct_answer)'''), {
            **{key:item[key] for key in ['title','description','difficulty','correct_answer']},
            'id':2000 - index * 11, 'concept_id':concept_ids[item['concept']], 'options':json.dumps(item['options']),
        })
    if altered:
        connection.execute(text("UPDATE questions SET description='Unreviewed changed record' WHERE id=2000"))
    if duplicate:
        connection.execute(text('''INSERT INTO questions (concept_id,title,description,difficulty,options,correct_answer)
            SELECT concept_id,title,description,difficulty,options,correct_answer FROM questions WHERE id=2000'''))
    connection.execute(text("INSERT INTO students(id,username,created_at) VALUES (700,'preserved',CURRENT_TIMESTAMP)"))
    connection.execute(text('''INSERT INTO attempts(student_id,question_id,selected_answer,is_correct,attempted_at,mastery_before,mastery_after,submission_id)
        VALUES (700,2000,2,TRUE,CURRENT_TIMESTAMP,0.2,0.6,'30c6ccea-e419-41d1-b6b1-559f6552ce42'),
               (700,2000,1,FALSE,CURRENT_TIMESTAMP,NULL,NULL,NULL)'''))
    connection.execute(text('''INSERT INTO mastery(student_id,concept_id,probability,updated_at)
        VALUES (700,:concept,0.6,CURRENT_TIMESTAMP)'''), {'concept':concept_ids['Arrays']})


def rows(connection, table):
    return connection.execute(text(f'SELECT * FROM {table} ORDER BY id')).mappings().all()


def test_populated_upgrade_and_downgrade_preserve_identity_foreign_keys_and_sequences(migration_engine):
    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, IDEMPOTENCY)
        populate(connection)
        original = {name:rows(connection,name) for name in ['questions','attempts','mastery','students','concepts','prerequisites']}
        sequences = connection.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).all()
        command.upgrade(cfg, REVISION)
        assert MigrationContext.configure(connection).get_current_revision() == REVISION
        assert schema_differences(connection, revision=REVISION) == []
        assert schema_differences(connection, revision=REVISION) == []
        assert connection.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).all() == sequences
        for table, before in original.items():
            current = rows(connection,table)
            assert [{key:row[key] for key in before[0]} for row in current] == before if before else current == []
        mapped = connection.execute(text('SELECT id,question_key,explanation FROM questions ORDER BY id DESC')).mappings().all()
        assert [(row['id'],row['question_key'],row['explanation']) for row in mapped] == [(2000 - index * 11,item['question_key'],item['explanation']) for index,item in enumerate(MANIFEST)]
        assert connection.scalar(text('SELECT count(*) FROM attempts WHERE feedback_explanation IS NULL AND feedback_correct_answer=2')) == 2
        assert 'uq_question_key' in {item['name'] for item in inspect(connection).get_unique_constraints('questions')}
        assert 'ix_questions_concept_id_id' in {item['name'] for item in inspect(connection).get_indexes('questions')}
        command.downgrade(cfg, IDEMPOTENCY)
        assert MigrationContext.configure(connection).get_current_revision() == IDEMPOTENCY
        assert schema_differences(connection, revision=IDEMPOTENCY) == []
        for table, before in original.items():
            assert rows(connection,table) == before
        command.upgrade(cfg, REVISION)
        assert schema_differences(connection, revision=REVISION) == []


@pytest.mark.parametrize('duplicate,altered', [(True,False),(False,True)])
def test_unrecognized_or_ambiguous_legacy_records_stop_before_schema_adoption(migration_engine, duplicate, altered):
    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, IDEMPOTENCY)
        populate(connection, duplicate=duplicate, altered=altered)
        before = rows(connection,'questions')
        with pytest.raises(RuntimeError, match='Cannot safely adopt legacy question'):
            with connection.begin_nested():
                command.upgrade(cfg, REVISION)
        assert rows(connection,'questions') == before
        assert 'question_key' not in {column['name'] for column in inspect(connection).get_columns('questions')}
        assert MigrationContext.configure(connection).get_current_revision() == IDEMPOTENCY


def test_empty_upgrade_allows_new_keyed_questions_and_downgrade_never_deletes_them(migration_engine):
    with migration_engine.begin() as connection:
        cfg = config(connection)
        command.upgrade(cfg, REVISION)
        assert schema_differences(connection, revision=REVISION) == []
        connection.execute(text("INSERT INTO concepts(id,name) VALUES (1,'Arrays')"))
        connection.execute(text('''INSERT INTO questions(id,question_key,concept_id,title,description,difficulty,options,correct_answer,explanation)
            VALUES (1,'arrays-900',1,'Future authored question','Test','easy','["a","b"]',0,'Authored explanation')'''))
        command.downgrade(cfg, IDEMPOTENCY)
        assert connection.scalar(text('SELECT count(*) FROM questions')) == 1
        assert connection.scalar(text('SELECT title FROM questions WHERE id=1')) == 'Future authored question'


def test_import_cli_dry_run_and_repeated_import_on_disposable_database(migration_engine):
    with migration_engine.begin() as connection:
        command.upgrade(config(connection), REVISION)
        for name in sorted({item['concept'] for item in MANIFEST}):
            connection.execute(text('INSERT INTO concepts(name) VALUES (:name)'), {'name':name})
    environment = os.environ.copy()
    environment['DATABASE_URL'] = migration_engine.url.render_as_string(hide_password=False)
    def run(*arguments):
        result = subprocess.run([sys.executable,'seed_questions.py',*arguments], cwd=Path(__file__).parent,
                                env=environment, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    assert run('--dry-run')['inserts'] == 25
    with migration_engine.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM questions')) == 0
    assert run()['inserts'] == 25
    assert run()['unchanged'] == 25
    with migration_engine.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM questions WHERE explanation IS NOT NULL AND question_key IS NOT NULL')) == 25
