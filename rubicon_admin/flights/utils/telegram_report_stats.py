"""Статистика вылетов из Telegram-отчётов (топик 2406 и др.)."""

from __future__ import annotations



import logging

import re

from datetime import datetime, time as dt_time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo



from django.conf import settings

from django.utils import timezone



from flights.models import TelegramFlightReport



logger = logging.getLogger(__name__)



_NOT_DEFEATED_RE = re.compile(r'не\s*пораж', re.IGNORECASE)





def normalize_result_text(result: str | None) -> str:

    if not result:

        return ''

    return str(result).casefold().strip()





def is_report_not_defeated(result: str | None) -> bool:

    """Не поражено / промах (как в боте result_filters)."""

    text = normalize_result_text(result)

    if not text:

        return False

    compact = re.sub(r'\s+', '', text)

    if 'непораж' in compact or 'неуспеш' in compact:

        return True

    if _NOT_DEFEATED_RE.search(text):

        return True

    return 'промах' in text





def is_report_defeated(result: str | None) -> bool:

    """Поражено / уничтожено / подавление — без «не поражено» и без «успешно»."""

    text = normalize_result_text(result)

    if not text or is_report_not_defeated(result):

        return False

    if 'успешн' in text:

        return False

    if 'уничтож' in text or 'поражен' in text or 'подавл' in text or 'добиван' in text:

        return True

    return False





def is_report_result_successful(result: str | None) -> bool:

    """Совместимость: «успех» для индекса = поражение цели (не «успешно» из Excel)."""

    return is_report_defeated(result)





def record_telegram_flight_report(

    *,

    chat_id,

    message_thread_id,

    telegram_message_id,

    flight_number,

    work_date='',

    result='',

    sent_at=None,

    parse_ok=True,

    pilot_callsign='',

    raw_text='',

):

    if not parse_ok:

        return {'ok': False, 'error': 'parse_failed'}



    when = sent_at or timezone.now()

    if isinstance(when, str):

        when = datetime.fromisoformat(when.replace('Z', '+00:00'))

    if timezone.is_naive(when):

        when = timezone.make_aware(when, dt_timezone.utc)



    defeated = is_report_defeated(result)

    report, created = TelegramFlightReport.objects.update_or_create(

        chat_id=int(chat_id),

        telegram_message_id=int(telegram_message_id),

        defaults={

            'message_thread_id': int(message_thread_id) if message_thread_id is not None else None,

            'flight_number': int(flight_number or 0),

            'work_date': (work_date or '')[:32],

            'result': (result or '')[:512],

            'pilot_callsign': (pilot_callsign or '')[:255],

            'is_successful': defeated,

            'parse_ok': True,

            'sent_at': when,

            'raw_text': raw_text or '',

        },

    )

    logger.info(

        'TG-отчёт %s: вылет №%s (%s)',

        'создан' if created else 'обновлён',

        flight_number,

        'поражено' if defeated else ('не поражено' if is_report_not_defeated(result) else '—'),

    )

    return {'ok': True, 'id': str(report.id), 'created': created, 'is_successful': defeated}





def _msk_calendar_day_bounds():
    """Текущие календарные сутки по Europe/Moscow: [00:00, 00:00 следующего дня)."""
    local_now = timezone.localtime(timezone.now())
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _dashboard_period_bounds():
    """Смена для KPI: с 18:00 вчера (МСК) до сейчас — как отчёт /командир."""
    shift_hour = int(getattr(settings, 'DASHBOARD_SHIFT_START_HOUR', 18))
    tz = ZoneInfo('Europe/Moscow')
    now = timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, dt_timezone.utc)
    now_msk = now.astimezone(tz)
    yesterday = now_msk.date() - timedelta(days=1)
    period_start = datetime.combine(yesterday, dt_time(shift_hour, 0), tzinfo=tz)
    return period_start, now_msk





def _count_results_from_reports(qs) -> dict[str, int]:

    """Подсчёт по полю result (актуально даже для старых записей в БД)."""

    defeated = 0

    not_defeated = 0

    other = 0

    for result in qs.values_list('result', flat=True):

        if is_report_defeated(result):

            defeated += 1

        elif is_report_not_defeated(result):

            not_defeated += 1

        else:

            other += 1

    return {

        'defeated_flights': defeated,

        'not_defeated_flights': not_defeated,

        'other_flights': other,

    }





def _msk_today_work_date_q():
    """Совпадение поля work_date с сегодняшней датой (МСК)."""
    from django.db.models import Q

    local_now = timezone.localtime(timezone.now())
    d = local_now.date()
    labels = {
        d.strftime('%d.%m.%Y'),
        d.strftime('%d.%m.%y'),
        f'{d.day:02d}.{d.month:02d}.{d.year}',
        f'{d.day}.{d.month}.{d.year}',
    }
    q = Q()
    for label in labels:
        if label:
            q |= Q(work_date__icontains=label)
    return q


def get_today_telegram_reports_qs():
    """Отчёты за текущую смену (с 18:00 вчера МСК по sent_at)."""
    period_start, period_end = _dashboard_period_bounds()

    chat_id = getattr(settings, 'TELEGRAM_REPORTS_CHAT_ID', None)
    topic_id = getattr(settings, 'TELEGRAM_REPORTS_TOPIC_ID', None)

    qs = TelegramFlightReport.objects.filter(
        parse_ok=True,
        flight_number__gt=0,
        sent_at__gte=period_start,
        sent_at__lte=period_end,
    )
    if chat_id:
        qs = qs.filter(chat_id=int(chat_id))
    if topic_id:
        qs = qs.filter(message_thread_id=int(topic_id))

    return qs.distinct()


def get_dashboard_daily_stats():
    """Вылеты за смену: max номер «N вылет» с 18:00 вчера (МСК) до сейчас."""
    from django.db.models import Max

    period_start, period_end = _dashboard_period_bounds()
    qs = get_today_telegram_reports_qs()

    max_flight = qs.aggregate(m=Max('flight_number'))['m'] or 0
    reports_count = qs.count()
    total = max_flight if max_flight > 0 else reports_count
    counts = _count_results_from_reports(qs)

    return {
        'total_flights': total,
        'latest_flight_number': max_flight,
        'reports_count': reports_count,
        'defeated_flights': counts['defeated_flights'],
        'not_defeated_flights': counts['not_defeated_flights'],
        'other_flights': counts['other_flights'],
        'successful_flights': counts['defeated_flights'],
        'success_rate_percent': round((counts['defeated_flights'] / total * 100), 1) if total else 0,
        'defeat_rate_percent': round((counts['defeated_flights'] / total * 100), 1) if total else 0,
        'source': 'telegram_reports',
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
    }


