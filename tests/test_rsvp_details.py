import pytest

TOKEN = 'event-a-token-123456789012345678901234'


def test_invitation_rsvp_admin_details(client, admin_headers):
    invitation = client.patch(f'/api/admin/events/{TOKEN}/invitation', headers=admin_headers,
                              json={'venue': 'Bahçe', 'guest_note': 'Saat 18:00'})
    assert invitation.status_code == 200
    assert client.get(f'/api/events/{TOKEN}/invitation').json()['venue'] == 'Bahçe'
    payload = {'name': '  Deniz  ', 'email': 'deniz@example.com', 'status': 'attending',
               'people': 7, 'dietary_requirements': 'Glutensiz', 'notes': 'Servis kullanacağım'}
    response = client.post(f'/api/events/{TOKEN}/rsvp', json=payload)
    assert response.status_code == 200
    guest_id = response.json()['id']
    guests = client.get(f'/api/admin/events/{TOKEN}/guests', headers=admin_headers).json()
    guest = next(g for g in guests if g['id'] == guest_id)
    assert (guest['name'], guest['people'], guest['dietary_requirements'], guest['notes']) == ('Deniz', 7, 'Glutensiz', 'Servis kullanacağım')
    assert client.get(f'/api/admin/events/{TOKEN}/guests').status_code == 401
    payload.update(people=3, notes='Servis gerekmiyor')
    updated = client.post(f'/api/events/{TOKEN}/rsvp', json=payload)
    assert updated.json()['id'] == guest_id
    assert updated.json()['people'] == 3
    edited = client.patch(f'/api/admin/events/{TOKEN}/guests/{guest_id}', headers=admin_headers,
                          json={'notes': '', 'dietary_requirements': 'Vegan'})
    assert edited.json()['notes'] == ''
    assert edited.json()['dietary_requirements'] == 'Vegan'
    guests = client.get(f'/api/admin/events/{TOKEN}/guests', headers=admin_headers).json()
    assert len([g for g in guests if g['email'] == payload['email']]) == 1


@pytest.mark.parametrize('changes', [{'name': '   '}, {'email': 'invalid'}, {'people': 0}, {'people': 21}, {'notes': 'x'*2001}, {'dietary_requirements': 'x'*1001}])
def test_invalid_rsvp(client, changes):
    payload = {'name': 'Deniz', 'email': 'deniz@example.com', 'status': 'attending', 'people': 1}
    payload.update(changes)
    assert client.post(f'/api/events/{TOKEN}/rsvp', json=payload).status_code == 422


def test_inactive_invitation_and_rsvp(client, admin_headers):
    from app.db import database
    from app.db.models import Event
    with database.SessionLocal() as db:
        event = db.query(Event).filter(Event.private_token == TOKEN).one()
        event.is_active = False
        db.commit()
    assert client.get(f'/api/events/{TOKEN}/invitation').status_code == 403
    assert client.get(f'/api/admin/events/{TOKEN}/invitation', headers=admin_headers).status_code == 200
    assert client.post(f'/api/events/{TOKEN}/rsvp', json={'name': 'Deniz', 'email': 'deniz@example.com', 'status': 'attending'}).status_code == 403

def test_rsvp_migration_preserves_existing_guests(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/20260912_0005_rsvp_details.py'
    spec = importlib.util.spec_from_file_location('rsvp_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE guests (id TEXT PRIMARY KEY, name TEXT)'))
        connection.execute(sa.text("INSERT INTO guests VALUES ('existing', 'Deniz')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(sa.text('SELECT name, dietary_requirements, notes FROM guests')).one()
        assert tuple(row) == ('Deniz', '', '')
    engine.dispose()
