"""Агрегация успешных результатов для статистики."""

from collections import defaultdict



from flights.models import FlightResultTypes



SUCCESS_CATEGORIES = ('porazheno',)

SUCCESS_CATEGORY_LABELS = {
    'porazheno': 'Поражено',
}





def empty_success_counts():

    return {key: 0 for key in SUCCESS_CATEGORIES}


def _increment_success_count(counts, category):
    if category in counts:
        counts[category] += 1





def success_total(counts):

    return sum(counts.get(key, 0) for key in SUCCESS_CATEGORIES)





def aggregate_success_counts(flights_qs):

    counts = empty_success_counts()

    for result_raw in flights_qs.values_list('result_raw', flat=True).iterator():

        category = FlightResultTypes.success_category_from_raw(result_raw)

        _increment_success_count(counts, category)

    return counts





def aggregate_pilot_success_stats(flights_qs):

    stats = {}

    rows = flights_qs.exclude(

        pilot__callname__istartswith='Неизвестный_'

    ).values('pilot__id', 'pilot__callname', 'result_raw')



    for row in rows.iterator():

        pilot_id = row['pilot__id']

        if pilot_id not in stats:

            stats[pilot_id] = {

                'pilot__id': pilot_id,

                'pilot__callname': row['pilot__callname'],

                'total_flights': 0,

                **empty_success_counts(),

            }

        entry = stats[pilot_id]

        entry['total_flights'] += 1

        category = FlightResultTypes.success_category_from_raw(row['result_raw'])

        _increment_success_count(entry, category)



    result = []

    for entry in stats.values():

        total = entry['total_flights']

        success = success_total(entry)

        entry['success_total'] = success

        entry['success_rate_percent'] = round((success / total * 100), 2) if total else 0

        result.append(entry)



    result.sort(key=lambda item: item['success_total'], reverse=True)

    return result





def aggregate_drone_success_stats(flights_qs, normalize_drone):

    stats = {}

    rows = flights_qs.values('drone', 'pilot', 'result_raw')



    for row in rows.iterator():

        normalized_drone = normalize_drone(row['drone'])

        if normalized_drone not in stats:

            stats[normalized_drone] = {

                'drone': normalized_drone,

                'total_flights': 0,

                'pilots_involved': set(),

                **empty_success_counts(),

            }

        entry = stats[normalized_drone]

        entry['total_flights'] += 1

        if row['pilot']:

            entry['pilots_involved'].add(row['pilot'])

        category = FlightResultTypes.success_category_from_raw(row['result_raw'])

        _increment_success_count(entry, category)



    result = []

    for entry in stats.values():

        total = entry['total_flights']

        success = success_total(entry)

        pilots_involved = entry.pop('pilots_involved')

        entry['pilots_involved'] = len(pilots_involved)

        entry['success_total'] = success

        entry['success_rate_percent'] = round((success / total * 100), 2) if total else 0

        result.append(entry)



    result.sort(key=lambda item: item['total_flights'], reverse=True)

    return result





def aggregate_daily_success_stats(flights_qs):

    daily = defaultdict(lambda: {'total_flights': 0, **empty_success_counts()})

    for row in flights_qs.values('flight_date', 'result_raw').iterator():

        day = row['flight_date']

        if not day:

            continue

        entry = daily[day]

        entry['total_flights'] += 1

        category = FlightResultTypes.success_category_from_raw(row['result_raw'])

        _increment_success_count(entry, category)



    result = []

    for day in sorted(daily.keys()):

        entry = daily[day]

        success = success_total(entry)

        total = entry['total_flights']

        result.append({

            'date': day.isoformat(),

            'total_flights': total,

            'porazheno_flights': entry['porazheno'],

            'success_total': success,

            'success_rate_percent': round((success / total * 100), 2) if total else 0,

        })

    return result





def aggregate_target_success_stats(flights_qs, limit=20):

    target_counts = defaultdict(int)

    rows = flights_qs.exclude(target__isnull=True).exclude(target='').values(

        'target', 'result_raw'

    )

    for row in rows.iterator():

        if FlightResultTypes.success_category_from_raw(row['result_raw']):

            target_counts[row['target']] += 1



    return [

        {'target': target, 'success_count': count}

        for target, count in sorted(target_counts.items(), key=lambda item: item[1], reverse=True)[:limit]

    ]





def aggregate_pilot_target_success_stats(flights_qs, pilot_callname):

    rows = flights_qs.exclude(

        pilot__callname__istartswith='Неизвестный_'

    ).exclude(target__isnull=True).exclude(target='').filter(

        pilot__callname__icontains=pilot_callname

    ).values('pilot__id', 'pilot__callname', 'target', 'result_raw')



    target_counts = defaultdict(lambda: defaultdict(int))

    pilot_ids = {}



    for row in rows.iterator():

        if not FlightResultTypes.success_category_from_raw(row['result_raw']):

            continue

        pilot_name = row['pilot__callname']

        pilot_ids[pilot_name] = row['pilot__id']

        target_counts[pilot_name][row['target']] += 1



    result = []

    for pilot_name, targets in target_counts.items():

        target_list = [

            {'target': target, 'success_count': count}

            for target, count in sorted(targets.items(), key=lambda item: item[1], reverse=True)

        ]

        total_success = sum(item['success_count'] for item in target_list)

        result.append({

            'pilot_name': pilot_name,

            'pilot_id': pilot_ids[pilot_name],

            'targets': target_list,

            'total_success': total_success,

        })



    result.sort(key=lambda item: item['total_success'], reverse=True)

    return result

