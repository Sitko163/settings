"""Оперативные вылеты (Старт/Стоп из Telegram)."""
import logging
from datetime import timedelta

from django.utils import timezone

from flights.models import Flight, FlightResultTypes, LiveFlight, LiveFlightCloseReason, Pilot

logger = logging.getLogger(__name__)

LIVE_FLIGHT_TIMEOUT = timedelta(minutes=40)
LIVE_FLIGHT_HISTORY = timedelta(hours=24)
LIVE_FLIGHT_ACTION_START = 'start'
LIVE_FLIGHT_ACTION_STOP = 'stop'


def close_expired_live_flights():
    """Авто-закрытие: ended_at = started_at + 40 мин."""
    now = timezone.now()
    updated = 0
    active = LiveFlight.objects.filter(ended_at__isnull=True)
    for flight in active.iterator():
        deadline = flight.started_at + LIVE_FLIGHT_TIMEOUT
        if deadline > now:
            continue
        flight.ended_at = deadline
        flight.close_reason = LiveFlightCloseReason.TIMEOUT
        flight.save(update_fields=['ended_at', 'close_reason', 'modified'])
        updated += 1
    return updated


def _get_pilot_by_telegram_id(telegram_user_id):
    return Pilot.objects.filter(tg_id=telegram_user_id).first()


def _get_active_flight(telegram_user_id):
    return (
        LiveFlight.objects.filter(
            telegram_user_id=telegram_user_id,
            ended_at__isnull=True,
        )
        .order_by('-started_at')
        .first()
    )


def record_live_flight_start(*, telegram_user_id, chat_id, message_id=None):
    """Старт вылета: закрыть предыдущий active у этого tg_id, открыть новый."""
    pilot = _get_pilot_by_telegram_id(telegram_user_id)
    if not pilot:
        logger.warning('Старт без привязанного пилота, tg_id=%s', telegram_user_id)
        return {'ok': False, 'error': 'pilot_not_linked'}

    now = timezone.now()
    previous = _get_active_flight(telegram_user_id)
    if previous:
        previous.ended_at = now
        previous.close_reason = LiveFlightCloseReason.NEW_START
        previous.save(update_fields=['ended_at', 'close_reason', 'modified'])

    flight = LiveFlight.objects.create(
        pilot=pilot,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        started_at=now,
        message_id_start=message_id,
    )
    logger.info('Старт: %s (tg_id=%s)', pilot.callname, telegram_user_id)
    return {'ok': True, 'flight_id': str(flight.id), 'callname': pilot.callname}


def record_live_flight_stop(*, telegram_user_id, chat_id=None, message_id=None):
    """Стоп вылета."""
    pilot = _get_pilot_by_telegram_id(telegram_user_id)
    if not pilot:
        logger.warning('Стоп без привязанного пилота, tg_id=%s', telegram_user_id)
        return {'ok': False, 'error': 'pilot_not_linked'}

    active = _get_active_flight(telegram_user_id)
    if not active:
        logger.info('Стоп без active-вылета: %s', pilot.callname)
        return {'ok': False, 'error': 'no_active_flight'}

    now = timezone.now()
    active.ended_at = now
    active.close_reason = LiveFlightCloseReason.STOP
    if message_id is not None:
        active.message_id_stop = message_id
    active.save(update_fields=['ended_at', 'close_reason', 'message_id_stop', 'modified'])
    logger.info('Стоп: %s (tg_id=%s)', pilot.callname, telegram_user_id)
    return {'ok': True, 'flight_id': str(active.id), 'callname': pilot.callname}


def record_live_flight_event(*, action, telegram_user_id, chat_id, message_id=None):
    close_expired_live_flights()
    if action == LIVE_FLIGHT_ACTION_START:
        return record_live_flight_start(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    if action == LIVE_FLIGHT_ACTION_STOP:
        return record_live_flight_stop(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    return {'ok': False, 'error': 'invalid_action'}


def _format_time_msk(dt):
    if dt is None:
        return ''
    local = timezone.localtime(dt)
    return local.strftime('%H:%M')


def serialize_live_flight(flight, *, active=False):
    pilot_name = flight.pilot.callname
    started = _format_time_msk(flight.started_at)
    payload = {
        'id': str(flight.id),
        'callname': pilot_name,
        'started_at': started,
        'started_at_iso': flight.started_at.isoformat(),
    }
    if active:
        return payload
    ended = _format_time_msk(flight.ended_at)
    payload['time_range'] = f'{started}–{ended}'
    payload['ended_at_iso'] = flight.ended_at.isoformat() if flight.ended_at else None
    payload['is_auto'] = flight.close_reason == LiveFlightCloseReason.TIMEOUT
    payload['close_reason'] = flight.close_reason or ''
    return payload


def _active_pilot_callnames():
    close_expired_live_flights()
    now = timezone.now()
    timeout_threshold = now - LIVE_FLIGHT_TIMEOUT
    return set(
        LiveFlight.objects.filter(
            ended_at__isnull=True,
            started_at__gt=timeout_threshold,
        )
        .values_list('pilot__callname', flat=True)
    )


def get_dashboard_map_points():
    """Координаты вылетов за 24 ч (из Flight) для карты на дашборде."""
    now = timezone.now()
    since = now - LIVE_FLIGHT_HISTORY
    since_date = timezone.localtime(since).date()
    active_callnames = _active_pilot_callnames()

    flights = (
        Flight.objects.filter(flight_date__gte=since_date)
        .exclude(lat_wgs84__isnull=True)
        .exclude(lon_wgs84__isnull=True)
        .select_related('pilot')
        .only(
            'id', 'number', 'pilot_id', 'drone', 'flight_date', 'flight_time',
            'target', 'result', 'coordinates', 'lat_wgs84', 'lon_wgs84',
            'comment', 'pilot__callname',
        )
    )

    points_by_key = {}
    for flight in flights.iterator(chunk_size=500):
        lat = flight.lat_wgs84
        lon = flight.lon_wgs84
        if lat is None or lon is None or (lat == 90.0 and lon == 0.0):
            continue

        pilot_name = flight.pilot.callname if flight.pilot_id else ''
        point = {
            'id': str(flight.id),
            'lat': lat,
            'lng': lon,
            'number': flight.number,
            'pilot_name': pilot_name,
            'is_active_pilot': pilot_name in active_callnames,
            'drone': flight.drone or '',
            'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
            'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
            'target': flight.target or '',
            'result': flight.result,
            'coordinates': flight.coordinates or '',
        }
        dedupe_key = FlightResultTypes.map_dedupe_key(flight)
        existing = points_by_key.get(dedupe_key)
        if existing is None:
            points_by_key[dedupe_key] = point
        elif FlightResultTypes.result_priority(flight.result) > FlightResultTypes.result_priority(
            existing['result']
        ):
            points_by_key[dedupe_key] = point

    return list(points_by_key.values())


def get_dashboard_daily_stats():
    from flights.utils.telegram_report_stats import get_dashboard_daily_stats as tg_stats

    return tg_stats()


def get_dashboard_live_flights(*, weather_region_id=None):
    close_expired_live_flights()
    now = timezone.now()
    timeout_threshold = now - LIVE_FLIGHT_TIMEOUT

    active_qs = (
        LiveFlight.objects.filter(
            ended_at__isnull=True,
            started_at__gt=timeout_threshold,
        )
        .select_related('pilot')
        .order_by('started_at')
    )

    since = now - LIVE_FLIGHT_HISTORY
    completed_qs = (
        LiveFlight.objects.filter(
            ended_at__isnull=False,
            started_at__gte=since,
        )
        .select_related('pilot')
        .order_by('-ended_at')
    )

    from flights.utils.dashboard_alerts import get_dashboard_alerts
    from flights.utils.dashboard_weather import get_dashboard_weather, get_weather_regions

    return {
        'active': [serialize_live_flight(f, active=True) for f in active_qs],
        'completed': [serialize_live_flight(f) for f in completed_qs],
        'map_points': get_dashboard_map_points(),
        'weather_regions': get_weather_regions(),
        'weather': get_dashboard_weather(weather_region_id),
        'daily_stats': get_dashboard_daily_stats(),
        'alerts': get_dashboard_alerts(),
        'updated_at': timezone.localtime(now).isoformat(),
    }
