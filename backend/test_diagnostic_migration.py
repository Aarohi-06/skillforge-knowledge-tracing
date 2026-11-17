from uuid import uuid4
from alembic import command
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from test_migrations import migration_engine, config
from verify_schema import schema_differences

REVISION = '0005_diagnostic_sessions'
PARENT = '0004_question_bank'


def test_diagnostic_upgrade_downgrade_preserve_existing_rows_and_attempts(migration_engine):
    with migration_engine.begin() as c:
        cfg = config(c)
        command.upgrade(cfg,PARENT)
        c.execute(text("INSERT INTO students(id,username,created_at) VALUES (1,'preserved',CURRENT_TIMESTAMP)"))
        c.execute(text("INSERT INTO concepts(id,name) VALUES (1,'Arrays')"))
        c.execute(text('''INSERT INTO questions(id,concept_id,question_key,title,description,difficulty,options,correct_answer,explanation)
            VALUES (1,1,'arrays-001','Index','Index?','easy','["0","1"]',0,'Authored explanation')'''))
        c.execute(text('''INSERT INTO attempts(id,student_id,question_id,selected_answer,is_correct,attempted_at,mastery_before,mastery_after)
            VALUES (1,1,1,0,TRUE,CURRENT_TIMESTAMP,NULL,NULL)'''))
        c.execute(text('''INSERT INTO mastery(student_id,concept_id,probability,updated_at) VALUES (1,1,0.7,CURRENT_TIMESTAMP)'''))
        before = {table:c.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all()
            for table in ['students','concepts','questions','attempts','mastery','prerequisites']}
        old_sequences = c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).all()
        command.upgrade(cfg,REVISION)
        assert schema_differences(c,revision=REVISION) == []
        assert schema_differences(c,revision=REVISION) == []
        assert MigrationContext.configure(c).get_current_revision() == REVISION
        assert c.scalar(text('SELECT count(*) FROM diagnostic_sessions')) == 0
        assert c.scalar(text('SELECT count(*) FROM diagnostic_assignments')) == 0
        assert set(inspect(c).get_table_names()) == set(before) | {'alembic_version','diagnostic_sessions','diagnostic_assignments'}
        # Partial uniqueness at the database level, not just application logic.
        session_id = uuid4()
        insert = text('''INSERT INTO diagnostic_sessions(id,student_id,status,created_at,updated_at)
            VALUES (:id,1,'in_progress',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)''')
        c.execute(insert,{'id':session_id})
        with pytest.raises(IntegrityError):
            with c.begin_nested(): c.execute(insert,{'id':uuid4()})
        c.execute(text('''INSERT INTO diagnostic_assignments(session_id,position,question_id,attempt_id,submission_id)
            VALUES (:session,0,1,1,:key)'''),{'session':session_id,'key':uuid4()})
        # Duplicate question/order and invalid FK are rejected.
        for params in [{'position':1,'question':1},{'position':0,'question':1},{'position':1,'question':999}]:
            with pytest.raises(IntegrityError):
                with c.begin_nested():
                    c.execute(text('INSERT INTO diagnostic_assignments(session_id,position,question_id) VALUES (:session,:position,:question)'),{'session':session_id,**params})
        for table, rows in before.items():
            assert c.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all() == rows
        after_sequences = dict(c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).all())
        assert all(after_sequences[name] == value for name,value in old_sequences)
        command.downgrade(cfg,PARENT)
        assert schema_differences(c,revision=PARENT) == []
        assert not {'diagnostic_sessions','diagnostic_assignments'} & set(inspect(c).get_table_names())
        for table,rows in before.items():
            assert c.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all() == rows
        assert c.scalar(text('SELECT mastery_after FROM attempts WHERE id=1')) is None
        command.upgrade(cfg,REVISION)
        assert schema_differences(c,revision=REVISION) == []
        assert c.scalar(text('SELECT count(*) FROM diagnostic_sessions')) == 0
