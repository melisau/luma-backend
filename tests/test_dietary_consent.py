"""Dietary info is special-category data (KVKK m.6): stored only with the guest's explicit consent."""
from datetime import datetime

TOKEN = 'event-a-token-123456789012345678901234'
BASE = {'name': 'Deniz', 'email': 'deniz@example.com', 'status': 'attending', 'people': 2}


def _guest(client, admin_headers, guest_id):
    guests = client.get(f'/api/admin/events/{TOKEN}/guests', headers=admin_headers).json()
    return next(g for g in guests if g['id'] == guest_id)


def _rsvp(client, **changes):
    return client.post(f'/api/events/{TOKEN}/rsvp', json={**BASE, **changes})


def test_consent_defaults_to_false():
    from app.schemas.guest import RsvpSubmit
    assert RsvpSubmit(**BASE).dietary_consent is False


def test_without_consent_dietary_is_dropped_but_rsvp_saved(client, admin_headers):
    response = _rsvp(client, dietary_requirements='Fıstık alerjisi')
    assert response.status_code == 200
    body = response.json()
    assert body['dietary_dropped'] is True
    assert body['dietary_requirements'] == ''
    assert body['dietary_consent_at'] is None
    guest = _guest(client, admin_headers, body['id'])
    assert (guest['status'], guest['people'], guest['dietary_requirements']) == ('attending', 2, '')


def test_consent_stores_dietary_with_timestamp(client, admin_headers):
    body = _rsvp(client, dietary_requirements='Helal', dietary_consent=True).json()
    assert body['dietary_dropped'] is False
    guest = _guest(client, admin_headers, body['id'])
    assert guest['dietary_requirements'] == 'Helal'
    assert datetime.fromisoformat(guest['dietary_consent_at'].replace('Z', '+00:00'))


def test_clearing_field_withdraws_consent(client, admin_headers):
    first = _rsvp(client, dietary_requirements='Glutensiz', dietary_consent=True).json()
    second = _rsvp(client, edit_token=first['edit_token'], dietary_requirements='', dietary_consent=True)
    assert second.status_code == 200
    assert second.json()['dietary_dropped'] is False
    guest = _guest(client, admin_headers, first['id'])
    assert guest['dietary_requirements'] == '' and guest['dietary_consent_at'] is None


def test_unticking_on_edit_removes_stored_dietary(client, admin_headers):
    first = _rsvp(client, dietary_requirements='Vegan', dietary_consent=True).json()
    _rsvp(client, edit_token=first['edit_token'], dietary_requirements='Vegan')
    guest = _guest(client, admin_headers, first['id'])
    assert guest['dietary_requirements'] == '' and guest['dietary_consent_at'] is None


def test_planner_entry_has_no_guest_consent(client, admin_headers):
    first = _rsvp(client, dietary_requirements='Vegan', dietary_consent=True).json()
    url = f'/api/admin/events/{TOKEN}/guests/{first["id"]}'
    edited = client.patch(url, headers=admin_headers, json={'dietary_requirements': 'Vejetaryen'}).json()
    assert edited['dietary_requirements'] == 'Vejetaryen'
    assert edited['dietary_consent_at'] is None
    # Saving the same dietary text with other fields keeps the guest's consent record.
    again = _rsvp(client, edit_token=first['edit_token'], dietary_requirements='Vegan', dietary_consent=True).json()
    kept = client.patch(url, headers=admin_headers, json={'notes': 'Masa 4', 'dietary_requirements': 'Vegan'}).json()
    assert kept['dietary_consent_at'] == again['dietary_consent_at']


def test_csv_includes_consent_time(client, admin_headers):
    import csv
    import io
    _rsvp(client, dietary_requirements='Koşer', dietary_consent=True)
    response = client.get(f'/api/admin/events/{TOKEN}/guests.csv', headers=admin_headers)
    rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert rows[0][4:6] == ['Beslenme', 'Beslenme Rızası']
    assert rows[1][4] == 'Koşer' and rows[1][5]


def test_consent_migration_is_idempotent(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/20261116_0023_dietary_consent.py'
    spec = importlib.util.spec_from_file_location('consent_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE guests (id TEXT PRIMARY KEY, dietary_requirements TEXT)"))
        connection.execute(sa.text("INSERT INTO guests VALUES ('g1', 'Vegan')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(sa.text('SELECT dietary_requirements, dietary_consent_at FROM guests')).one()
        assert tuple(row) == ('Vegan', None)
    engine.dispose()
