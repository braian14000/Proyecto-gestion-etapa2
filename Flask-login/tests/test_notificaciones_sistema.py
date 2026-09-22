from datetime import datetime

from app import build_system_event_reminder_message, build_event_change_message


def test_build_system_event_reminder_message():
    fecha = datetime(2026, 9, 4)
    mensaje = build_system_event_reminder_message(fecha, 'Taller de Arduino')

    assert mensaje == 'En 04/09/2026 tenés el evento Taller de Arduino.'


def test_build_event_change_message():
    mensaje = build_event_change_message(
        'Taller de Arduino',
        '04/09/2026',
        '10:00',
        '05/09/2026',
        '11:30'
    )

    assert 'Taller de Arduino' in mensaje
    assert '04/09/2026' in mensaje
    assert '05/09/2026' in mensaje
    assert '10:00' in mensaje
    assert '11:30' in mensaje
