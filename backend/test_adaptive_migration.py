from uuid import uuid4
from alembic import command
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from test_migrations import migration_engine, config
from verify_schema import schema_differences

PARENT='0005_diagnostic_sessions'
REVISION='0006_adaptive_sessions'


def snapshot(c,tables):
    return {table:c.execute(text(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text')).scalars().all() for table in tables}


def test_populated_adaptive_upgrade_and_downgrade_preserve_all_existing_data(migration_engine):
    with migration_engine.begin() as c:
        cfg=config(c);command.upgrade(cfg,PARENT)
        c.execute(text("INSERT INTO students(id,username,created_at) VALUES (1,'preserved',CURRENT_TIMESTAMP)"))
        c.execute(text("INSERT INTO concepts(id,name) VALUES (1,'Arrays')"))
        c.execute(text('''INSERT INTO questions(id,concept_id,question_key,title,description,difficulty,options,correct_answer,explanation)
            VALUES (1,1,'arrays-001','Index','Index?','easy','["a","b"]',0,'Authored explanation')'''))
        c.execute(text('''INSERT INTO attempts(id,student_id,question_id,selected_answer,is_correct,attempted_at,mastery_before,mastery_after,feedback_explanation)
            VALUES (1,1,1,0,TRUE,CURRENT_TIMESTAMP,NULL,NULL,NULL)'''))
        c.execute(text('''INSERT INTO mastery(student_id,concept_id,probability,updated_at) VALUES (1,1,0.7,CURRENT_TIMESTAMP)'''))
        diagnostic_id=uuid4()
        c.execute(text('''INSERT INTO diagnostic_sessions(id,student_id,status,created_at,updated_at)
            VALUES (:id,1,'in_progress',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)'''),{'id':diagnostic_id})
        c.execute(text('''INSERT INTO diagnostic_assignments(session_id,position,question_id,attempt_id,submission_id)
            VALUES (:id,0,1,1,:key)'''),{'id':diagnostic_id,'key':uuid4()})
        tables=set(inspect(c).get_table_names())-{'alembic_version'}
        before=snapshot(c,tables)
        sequences=dict(c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public'")).all())
        command.upgrade(cfg,REVISION);command.check(cfg)
        assert schema_differences(c)==[]
        assert MigrationContext.configure(c).get_current_revision()==REVISION
        assert snapshot(c,tables)==before
        assert c.scalar(text('SELECT count(*) FROM adaptive_sessions'))==0
        assert c.scalar(text('SELECT count(*) FROM adaptive_assignments'))==0
        current=dict(c.execute(text("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public'")).all())
        assert all(current[name]==value for name,value in sequences.items())
        session=uuid4()
        insert=text('''INSERT INTO adaptive_sessions(id,student_id,status,created_at,updated_at)
            VALUES (:id,1,'in_progress',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)''')
        c.execute(insert,{'id':session})
        with pytest.raises(IntegrityError):
            with c.begin_nested():c.execute(insert,{'id':uuid4()})
        c.execute(text('''INSERT INTO adaptive_assignments(session_id,position,question_id,selection_reason,attempt_id,submission_id)
            VALUES (:id,0,1,'Recorded selection reason',1,:key)'''),{'id':session,'key':uuid4()})
        for values in [{'position':1,'question':1},{'position':0,'question':1},{'position':1,'question':999},{'position':5,'question':1}]:
            with pytest.raises(IntegrityError):
                with c.begin_nested():
                    c.execute(text('''INSERT INTO adaptive_assignments(session_id,position,question_id,selection_reason)
                        VALUES (:id,:position,:question,'Reason')'''),{'id':session,**values})
        # Existing diagnostic metadata/legacy NULL snapshots survive downgrade.
        command.downgrade(cfg,PARENT)
        assert schema_differences(c,revision=PARENT)==[]
        assert snapshot(c,tables)==before
        assert not {'adaptive_sessions','adaptive_assignments'} & set(inspect(c).get_table_names())
        command.upgrade(cfg,REVISION);command.check(cfg)
        assert c.scalar(text('SELECT count(*) FROM adaptive_sessions'))==0


def test_empty_database_upgrades_to_adaptive_head(migration_engine):
    with migration_engine.begin() as c:
        command.upgrade(config(c),REVISION)
        command.check(config(c))
        assert schema_differences(c)==[]
        assert c.scalar(text('SELECT count(*) FROM adaptive_assignments'))==0
